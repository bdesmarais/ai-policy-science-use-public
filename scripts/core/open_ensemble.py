"""Improve the open stance methods to close the gap to the proprietary judge.

The single-model open validators lag the proprietary judge, and they fail in
*different* ways on the two benchmarks: zero-shot NLI is strong on clean SciFact
pairs but collapses on lay Climate-FEVER claims (it almost never fires SUPPORT),
while the small instruction-tuned panel is the reverse. That complementarity is
exactly what an ensemble can exploit. This module builds three open combiners on
top of the committed per-pair predictions of the five open models (NLI-DeBERTa,
NLI-BART, Qwen2.5-3B, Phi-3.5-mini, OLMo-2-7B) and the SciFact abstracts, with no
proprietary model and no new model downloads:

  (1) majority   -- zero-shot plurality vote of the five models (no labels used);
  (2) xfer-vote  -- per-class-F1-weighted vote whose weights are estimated on the
                    *other* benchmark, so no test-domain labels are used;
  (3) stacker    -- a logistic-regression / gradient-boosted combiner trained on
                    the *public* benchmark gold with 5-fold out-of-fold CV (uses
                    existing public labels, never new in-domain labels), with
                    model-vote features plus light text features.

Every method is scored against the expert gold with accuracy (Wilson 95% CI),
macro-F1, and per-class F1, both on the full benchmark and on the exact pairs the
proprietary judge labelled (n=66 SciFact, n=45 Climate-FEVER), so the head-to-head
with the judge is like-for-like.
"""
import json, csv, math, os, re
from collections import Counter, defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score, accuracy_score

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "benchmarks", "results")
LABELS = ["support", "refute", "silent"]
MODELS = ["nli_deberta", "nli_bart",
          "llm:Qwen/Qwen2.5-3B-Instruct",
          "llm:microsoft/Phi-3.5-mini-instruct",
          "llm:allenai/OLMo-2-1124-7B-Instruct"]
SHORT = {"nli_deberta": "NLI-DeBERTa", "nli_bart": "NLI-BART",
         "llm:Qwen/Qwen2.5-3B-Instruct": "Qwen2.5-3B",
         "llm:microsoft/Phi-3.5-mini-instruct": "Phi-3.5-mini",
         "llm:allenai/OLMo-2-1124-7B-Instruct": "OLMo-2-7B"}
JUDGE = {"scifact": (0.803, 66), "climate_fever": (0.778, 45)}
NEG = re.compile(r"\b(no|not|never|none|cannot|can't|won't|doesn't|don't|isn't|"
                 r"aren't|reduce|reduces|reduced|decline|declines|contrary|"
                 r"however|but|false|myth|debunk|disprove|refute|contradict)\b", re.I)


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def clean(lbl):
    lbl = (lbl or "").strip().lower()
    return lbl if lbl in LABELS else "silent"


def load_scifact():
    nli = {r["uid"]: r for r in csv.DictReader(open(os.path.join(RES, "preds_scifact_nli.csv")))}
    pan = {r["uid"]: r for r in csv.DictReader(open(os.path.join(RES, "preds_scifact_panel.csv")))}
    corpus = {}
    for line in open(os.path.join(ROOT, "benchmarks", "data", "corpus.jsonl")):
        d = json.loads(line)
        corpus[str(d["doc_id"])] = " ".join(d["abstract"]) if isinstance(d["abstract"], list) else str(d["abstract"])
    rows = []
    for uid in nli:
        if uid not in pan:
            continue
        a = nli[uid]; b = pan[uid]
        docid = uid.split("_", 1)[1] if "_" in uid else uid
        rows.append({
            "uid": uid, "gold": clean(a["gold"]),
            "claim": a.get("claim", ""), "title": a.get("title", ""),
            "abstract": corpus.get(docid, a.get("title", "")),
            "tfidf": clean(a.get("tfidf")),
            "nli_deberta": clean(a["nli_deberta"]), "nli_bart": clean(a["nli_bart"]),
            "llm:Qwen/Qwen2.5-3B-Instruct": clean(b["llm:Qwen/Qwen2.5-3B-Instruct"]),
            "llm:microsoft/Phi-3.5-mini-instruct": clean(b["llm:microsoft/Phi-3.5-mini-instruct"]),
            "llm:allenai/OLMo-2-1124-7B-Instruct": clean(b["llm:allenai/OLMo-2-1124-7B-Instruct"]),
        })
    return rows


def load_cf():
    rows = []
    for r in csv.DictReader(open(os.path.join(RES, "preds_cf.csv"))):
        rows.append({
            "uid": r["uid"], "gold": clean(r["gold"]),
            "claim": r.get("claim", ""), "title": r.get("title", ""),
            "abstract": r.get("title", ""), "tfidf": "silent",
            **{m: clean(r[m]) for m in MODELS},
        })
    return rows


def judge_subset(bench):
    f = {"scifact": "claude_labels_scifact.json",
         "climate_fever": "claude_labels_climate_fever.json"}[bench]
    return set(json.load(open(os.path.join(ROOT, "benchmarks", f)))["labels"].keys())


# ---- combiners -------------------------------------------------------------
def majority(rows):
    out = {}
    for r in rows:
        votes = [r[m] for m in MODELS]
        cnt = Counter(votes)
        top = max(cnt.values())
        tied = [l for l in LABELS if cnt.get(l, 0) == top]
        # deterministic tie-break: trust NLI-DeBERTa, then the model order
        if len(tied) == 1:
            out[r["uid"]] = tied[0]
        else:
            out[r["uid"]] = next((r[m] for m in MODELS if r[m] in tied), tied[0])
    return out


def per_class_f1(rows, model):
    y = [r["gold"] for r in rows]; p = [r[model] for r in rows]
    return {c: f1_score(y, p, labels=[c], average="macro", zero_division=0) for c in LABELS}


def xfer_vote(rows, weight_rows):
    """Per-class-F1-weighted vote; weights estimated on weight_rows (other benchmark)."""
    w = {m: per_class_f1(weight_rows, m) for m in MODELS}
    out = {}
    for r in rows:
        score = defaultdict(float)
        for m in MODELS:
            score[r[m]] += w[m][r[m]]
        out[r["uid"]] = max(LABELS, key=lambda c: (score[c], -LABELS.index(c)))
    return out


def featurize(rows, vec=None, fit=False):
    texts_claim = [r["claim"] for r in rows]
    texts_evid = [r["abstract"] for r in rows]
    if fit:
        vec = TfidfVectorizer(max_features=4000, ngram_range=(1, 2), stop_words="english")
        vec.fit(texts_claim + texts_evid)
    Xc = vec.transform(texts_claim); Xe = vec.transform(texts_evid)
    cos = np.asarray(Xc.multiply(Xe).sum(axis=1)).ravel()  # both L2-normalised -> cosine
    feats = []
    for i, r in enumerate(rows):
        votes = [r[m] for m in MODELS]
        cnt = Counter(votes)
        row = []
        for m in MODELS:                      # one-hot of each model's label (15)
            row += [1.0 if r[m] == c else 0.0 for c in LABELS]
        row += [cnt.get(c, 0) / len(MODELS) for c in LABELS]   # vote share (3)
        row += [1.0 if len(set(votes)) == 1 else 0.0]          # unanimity
        row += [1.0 if r["tfidf"] == c else 0.0 for c in LABELS]  # tfidf voter (3)
        ctoks = set(re.findall(r"[a-z]+", r["claim"].lower()))
        etoks = set(re.findall(r"[a-z]+", r["abstract"].lower()))
        jac = len(ctoks & etoks) / max(1, len(ctoks | etoks))
        row += [cos[i], jac,
                len(NEG.findall(r["claim"])), len(NEG.findall(r["abstract"])),
                math.log1p(len(r["claim"])), math.log1p(len(r["abstract"]))]
        feats.append(row)
    return np.array(feats, dtype=float), vec


def stacker_oof(rows, seeds=(0, 1, 2, 3, 4)):
    """Out-of-fold predictions, TF-IDF fit *inside* each fold (no transductive leak),
    majority-voted over `seeds` 5-fold splits for stability. Returns logreg and HGB."""
    y = np.array([r["gold"] for r in rows])
    idx = np.arange(len(rows))
    results = {}
    for name, mk in [("stacker_lr", lambda s: LogisticRegression(max_iter=2000, C=1.0,
                                                                 class_weight="balanced")),
                     ("stacker_gb", lambda s: HistGradientBoostingClassifier(
                         max_depth=3, learning_rate=0.1, max_iter=300, random_state=s))]:
        votes = [defaultdict(int) for _ in rows]
        for seed in seeds:
            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
            for tr, te in skf.split(idx, y):
                tr_rows = [rows[i] for i in tr]; te_rows = [rows[i] for i in te]
                Xtr, vec = featurize(tr_rows, fit=True)
                Xte, _ = featurize(te_rows, vec=vec, fit=False)
                clf = mk(seed); clf.fit(Xtr, y[tr])
                for j, lab in zip(te, clf.predict(Xte)):
                    votes[j][lab] += 1
        results[name] = {rows[i]["uid"]: max(votes[i], key=votes[i].get) for i in range(len(rows))}
    return results


# ---- scoring ---------------------------------------------------------------
def score(rows, pred, subset=None):
    rs = [r for r in rows if subset is None or r["uid"] in subset]
    y = [r["gold"] for r in rs]; p = [pred[r["uid"]] for r in rs]
    k = sum(a == b for a, b in zip(y, p)); n = len(rs)
    return {
        "n": n, "accuracy": round(k / n, 3), "acc_ci95": list(wilson(k, n)),
        "macro_f1": round(f1_score(y, p, labels=LABELS, average="macro", zero_division=0), 3),
        "per_class_f1": {c: round(f1_score(y, p, labels=[c], average="macro", zero_division=0), 3)
                         for c in LABELS},
    }


def run_benchmark(bench, rows, other_rows):
    sub = judge_subset(bench)
    preds = {m: {r["uid"]: r[m] for r in rows} for m in MODELS}
    preds["tfidf"] = {r["uid"]: r["tfidf"] for r in rows}
    preds["majority"] = majority(rows)
    preds["xfer_vote"] = xfer_vote(rows, other_rows)
    preds.update(stacker_oof(rows))
    report = {"benchmark": bench, "n_pairs": len(rows),
              "judge": {"accuracy": JUDGE[bench][0], "n": JUDGE[bench][1],
                        "acc_ci95": list(wilson(round(JUDGE[bench][0] * JUDGE[bench][1]), JUDGE[bench][1]))},
              "full": {}, "judge_subset": {}}
    for name, pr in preds.items():
        report["full"][name] = score(rows, pr)
        report["judge_subset"][name] = score(rows, pr, subset=sub)
    return report


def main():
    sf = load_scifact(); cf = load_cf()
    rep = {"scifact": run_benchmark("scifact", sf, cf),
           "climate_fever": run_benchmark("climate_fever", cf, sf)}
    out = os.path.join(RES, "open_ensemble_report.json")
    json.dump(rep, open(out, "w"), indent=2)

    # console summary
    order = MODELS + ["tfidf", "majority", "xfer_vote", "stacker_lr", "stacker_gb"]
    for bench in ("scifact", "climate_fever"):
        R = rep[bench]
        print(f"\n================  {bench.upper()}  (n={R['n_pairs']})  ================")
        jb = R["judge"]
        print(f"{'method':<14}{'FULL acc [CI]':<24}{'mF1':<7}"
              f"{'JUDGE-SUBSET acc [CI]':<26}{'mF1':<7}")
        print(f"{'PROPRIETARY':<14}{'-- (n='+str(jb['n'])+')':<24}{'':<7}"
              f"{str(jb['accuracy'])+' '+str(jb['acc_ci95']):<26}{'':<7}  <-- judge")
        best_full = max(order, key=lambda m: R["full"][m]["macro_f1"])
        for m in order:
            f = R["full"][m]; s = R["judge_subset"][m]
            star = "  *best mF1" if m == best_full else ""
            print(f"{SHORT.get(m, m):<14}"
                  f"{str(f['accuracy'])+' '+str(f['acc_ci95']):<24}{f['macro_f1']:<7}"
                  f"{str(s['accuracy'])+' '+str(s['acc_ci95']):<26}{s['macro_f1']:<7}{star}")
    print(f"\nwrote {out}")
    return rep


if __name__ == "__main__":
    main()
