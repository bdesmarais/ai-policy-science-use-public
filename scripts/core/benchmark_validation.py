#!/usr/bin/env python3
"""
benchmark_validation.py — HUMAN-ANCHORED validation of the stance judge.

The central validity problem in the policy pipeline is that we replace human coders
with model "judges," and the policy corpus has no human gold labels to check them
against. This script breaks that circularity by validating every judge on EXTERNAL
benchmarks that DO have expert-human labels for the *identical* task — deciding
whether a scientific abstract SUPPORTS / REFUTES / is SILENT on a claim:

  scifact        Wadden et al. 2020 (EMNLP). Expert-written claims + cited abstracts,
                 human SUPPORT / CONTRADICT / NOINFO labels.  (benchmarks/data/)
  climate_fever  Diggelmann et al. 2020. Real-world *contested* claims + retrieved
                 evidence, human SUPPORTS / REFUTES / NOT_ENOUGH_INFO labels.

Stance mapping (both benchmarks -> our three classes):
  SUPPORT/SUPPORTS -> support ; CONTRADICT/REFUTES -> refute ; NOINFO/NEI -> silent.

Each validator predicts a label for every (claim, abstract) pair; we then report
accuracy, macro-F1, per-class F1 and the confusion matrix AGAINST THE HUMAN GOLD.
A judge that matches the human labels here is licensed to stand in for human coders
on the (unlabeled) policy corpus. Self-preference (Panickssery et al. 2024) cannot
explain accuracy on these benchmarks because the text is human-written, not model-
generated — so strong benchmark accuracy is direct evidence against that threat.

Validators:
  nli_deberta : MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli          (transformers)
  nli_bart    : facebook/bart-large-mnli                              (transformers)
  llm:<id>    : any HF instruction-tuned causal LM as generative judge (transformers)
  claude      : Claude Opus 4.8 in-session labels from a JSON file     (no API key)
  tfidf       : TF-IDF cosine + lexical-cue stance (dependency-free baseline)

Usage:
  python3 scripts/core/benchmark_validation.py --benchmark scifact \
      --validators nli_deberta nli_bart llm:Qwen/Qwen2.5-7B-Instruct --max-pairs 0
  python3 scripts/core/benchmark_validation.py --benchmark scifact --validators claude
"""
import argparse, json, os, re, sys, time
from collections import Counter, defaultdict
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BENCH = os.path.join(BASE, "benchmarks")
OUT = os.path.join(BENCH, "results")
STANCES = ["support", "refute", "silent"]

NLI_MODELS = {
    "nli_deberta": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
    "nli_bart": "facebook/bart-large-mnli",
}

# --------------------------------------------------------------------------- #
# Benchmark loaders -> list of {claim, title, abstract, gold, uid}
# --------------------------------------------------------------------------- #
def load_scifact(split="dev", max_pairs=0):
    d = os.path.join(BENCH, "data")
    corpus = {}
    for line in open(os.path.join(d, "corpus.jsonl")):
        r = json.loads(line)
        corpus[r["doc_id"]] = {"title": r.get("title", ""),
                               "abstract": " ".join(r.get("abstract", []))}
    pairs = []
    for line in open(os.path.join(d, f"claims_{split}.jsonl")):
        r = json.loads(line)
        claim = r["claim"]
        ev = r.get("evidence") or {}
        for doc_id in r.get("cited_doc_ids", []):
            doc = corpus.get(doc_id)
            if not doc:
                continue
            if str(doc_id) in ev:
                lab = ev[str(doc_id)][0]["label"]
            elif doc_id in ev:
                lab = ev[doc_id][0]["label"]
            else:
                lab = "NOINFO"
            gold = {"SUPPORT": "support", "CONTRADICT": "refute",
                    "NOINFO": "silent"}[lab]
            pairs.append({"uid": f"sf{r['id']}_{doc_id}", "claim": claim,
                          "title": doc["title"], "abstract": doc["abstract"],
                          "gold": gold})
            if max_pairs and len(pairs) >= max_pairs:
                return pairs
    return pairs


def load_climate_fever(max_pairs=0):
    """Climate-FEVER (Diggelmann et al. 2020): real-world *contested* climate claims with
    retrieved Wikipedia evidence sentences, each human-labeled. HF `climate_fever` encodes
    evidence_label as int 0=SUPPORTS, 1=REFUTES, 2=NOT_ENOUGH_INFO -> support/refute/silent.
    One (claim, evidence-sentence) pair per evidence. This benchmark is deliberately closer to
    the policy setting than SciFact: lay claims, contested topics, short evidence."""
    from datasets import load_dataset
    ds = load_dataset("climate_fever", split="test")
    m = {0: "support", 1: "refute", 2: "silent"}
    pairs = []
    for r in ds:
        claim = r["claim"]
        for i, ev in enumerate(r["evidences"]):
            lab = ev["evidence_label"]
            if lab not in m:
                continue
            pairs.append({"uid": f"cf{r['claim_id']}_{i}", "claim": claim,
                          "title": ev.get("article", ""), "abstract": ev["evidence"],
                          "gold": m[lab]})
            if max_pairs and len(pairs) >= max_pairs:
                return pairs
    return pairs


LOADERS = {"scifact": load_scifact, "climate_fever": load_climate_fever}

# --------------------------------------------------------------------------- #
# Validators -> list of predicted stance strings (aligned to pairs)
# --------------------------------------------------------------------------- #
def run_nli(pairs, model_id, batch_size=16):
    from transformers import pipeline
    clf = pipeline("text-classification", model=model_id, top_k=None,
                   truncation=True, max_length=512,
                   device=("mps" if _has_mps() else -1))
    inputs = [{"text": f"{p['title']}. {p['abstract']}"[:2000],
               "text_pair": p["claim"][:500]} for p in pairs]
    out = []
    for res in clf(inputs, batch_size=batch_size):
        sc = {d["label"].lower(): d["score"] for d in res}
        ent, con, neu = sc.get("entailment", 0), sc.get("contradiction", 0), sc.get("neutral", 0)
        out.append(max([("support", ent), ("refute", con), ("silent", neu)],
                       key=lambda t: t[1])[0])
    return out


JUDGE_PROMPT = """You are an expert scientific fact-checker. You are given a CLAIM and the TITLE and ABSTRACT of a scientific reference.

Decide the reference's stance toward the claim:
- SUPPORT: the reference provides evidence that the claim is true.
- REFUTE: the reference provides evidence that the claim is false.
- SILENT: the reference is irrelevant to the claim or does not provide enough information to support or refute it.

CLAIM: {claim}

REFERENCE TITLE: {title}
REFERENCE ABSTRACT: {abstract}

Respond with exactly one word — SUPPORT, REFUTE, or SILENT."""


def _parse_stance(txt):
    t = txt.lower()
    # explicit class words first, in priority order
    if re.search(r"\brefut|contradict|\bfalse\b|disprov", t):
        return "refute"
    if re.search(r"\bsupport|\btrue\b|entail|confirm", t):
        return "support"
    if re.search(r"\bsilent|neutral|not enough|no information|irrelevant|insufficient|unrelated", t):
        return "silent"
    return "silent"


def run_llm_judge(pairs, model_id, max_new_tokens=6, log_every=50):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dev = "mps" if _has_mps() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=(torch.float16 if dev == "mps" else torch.float32)).to(dev)
    model.eval()
    out, t0 = [], time.time()
    for i, p in enumerate(pairs):
        msg = [{"role": "user", "content": JUDGE_PROMPT.format(
            claim=p["claim"], title=p["title"], abstract=p["abstract"][:1600])}]
        text = tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
        inp = tok(text, return_tensors="pt", truncation=True, max_length=2048).to(dev)
        with torch.no_grad():
            gen = model.generate(**inp, max_new_tokens=max_new_tokens, do_sample=False,
                                 pad_token_id=(tok.pad_token_id or tok.eos_token_id))
        ans = tok.decode(gen[0][inp.input_ids.shape[1]:], skip_special_tokens=True)
        out.append(_parse_stance(ans))
        if (i + 1) % log_every == 0:
            print(f"    {model_id}: {i+1}/{len(pairs)} ({(time.time()-t0)/(i+1):.2f}s/pair)", flush=True)
    del model
    _empty_cache()
    return out


def run_claude(pairs, labels_path):
    """Read Claude Opus 4.8 in-session stance labels (no API key) keyed by pair uid."""
    lab = json.load(open(labels_path)).get("labels", {}) if os.path.exists(labels_path) else {}
    return [lab.get(p["uid"], "abstain") for p in pairs]


def run_tfidf(pairs):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    sup = re.compile(r"\b(support|confirm|consistent|demonstrate|show|increase|improve|"
                     r"effective|benefit|caus|associat)", re.I)
    ref = re.compile(r"\b(no (?:evidence|effect|association)|not (?:support|associat|effective)|"
                     r"contrary|refute|contradict|disprove|fail|ineffective|no significant|decreas|reduc)", re.I)
    claims = [p["claim"] for p in pairs]
    docs = [f"{p['title']}. {p['abstract']}" for p in pairs]
    X = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(claims + docs)
    n = len(pairs)
    sims = cosine_similarity(X[:n], X[n:]).diagonal()
    out = []
    for p, s in zip(pairs, sims):
        if s < 0.07:
            out.append("silent")
        else:
            txt = f"{p['title']}. {p['abstract']}"
            out.append("refute" if ref.search(txt) else ("support" if sup.search(txt) else "silent"))
    return out


# --------------------------------------------------------------------------- #
def _has_mps():
    try:
        import torch
        return torch.backends.mps.is_available()
    except Exception:
        return False


def _empty_cache():
    try:
        import torch
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


def metrics(gold, pred):
    """Accuracy, macro-F1, per-class P/R/F1, confusion — over non-abstain items."""
    idx = [i for i, p in enumerate(pred) if p != "abstain"]
    g = [gold[i] for i in idx]
    pr = [pred[i] for i in idx]
    n = len(g)
    acc = float(np.mean([a == b for a, b in zip(g, pr)])) if n else 0.0
    per = {}
    f1s = []
    for c in STANCES:
        tp = sum(1 for a, b in zip(g, pr) if a == c and b == c)
        fp = sum(1 for a, b in zip(g, pr) if a != c and b == c)
        fn = sum(1 for a, b in zip(g, pr) if a == c and b != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per[c] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
                  "support": sum(1 for a in g if a == c)}
        f1s.append(f1)
    conf = {a: {b: 0 for b in STANCES} for a in STANCES}
    for a, b in zip(g, pr):
        conf[a][b] += 1
    return {"n": n, "accuracy": round(acc, 3), "macro_f1": round(float(np.mean(f1s)), 3),
            "per_class": per, "confusion": conf}


def cohens_kappa(a, b):
    from sklearn.metrics import cohen_kappa_score
    idx = [i for i in range(len(a)) if a[i] != "abstain" and b[i] != "abstain"]
    if not idx:
        return float("nan"), 0
    aa, bb = [a[i] for i in idx], [b[i] for i in idx]
    try:
        return round(float(cohen_kappa_score(aa, bb, labels=STANCES)), 3), len(idx)
    except Exception:
        return float("nan"), len(idx)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benchmark", default="scifact", choices=list(LOADERS))
    ap.add_argument("--validators", nargs="+", required=True,
                    help="nli_deberta nli_bart tfidf claude llm:<hf_model_id>")
    ap.add_argument("--max-pairs", type=int, default=0, help="0 = all")
    ap.add_argument("--balanced", type=int, default=0, help="if >0, sample this many pairs PER class (seed 7)")
    ap.add_argument("--claude-labels", default=os.path.join(BENCH, "claude_labels_scifact.json"))
    ap.add_argument("--tag", default="", help="suffix for output filenames")
    args = ap.parse_args()

    pairs = LOADERS[args.benchmark](max_pairs=(0 if args.balanced else args.max_pairs))
    if args.balanced:
        rng = np.random.default_rng(7)
        by = {}
        for p in pairs:
            by.setdefault(p["gold"], []).append(p)
        sel = []
        for c, arr in by.items():
            idx = rng.choice(len(arr), size=min(args.balanced, len(arr)), replace=False)
            sel += [arr[i] for i in idx]
        rng.shuffle(sel)
        pairs = sel
    print(f"[benchmark_validation] {args.benchmark}: {len(pairs)} pairs "
          f"gold={dict(Counter(p['gold'] for p in pairs))}", flush=True)

    preds = {}
    for v in args.validators:
        print(f"  validator: {v} ...", flush=True)
        t = time.time()
        try:
            if v == "nli_deberta":
                preds[v] = run_nli(pairs, NLI_MODELS["nli_deberta"])
            elif v == "nli_bart":
                preds[v] = run_nli(pairs, NLI_MODELS["nli_bart"])
            elif v == "tfidf":
                preds[v] = run_tfidf(pairs)
            elif v == "claude":
                preds[v] = run_claude(pairs, args.claude_labels)
            elif v.startswith("llm:"):
                preds[v] = run_llm_judge(pairs, v[4:])
            else:
                print(f"   unknown validator {v}, skipping"); continue
        except Exception as e:
            print(f"   !! validator {v} FAILED: {repr(e)[:200]} — skipping", flush=True)
            continue
        print(f"    done in {time.time()-t:.1f}s", flush=True)

    gold = [p["gold"] for p in pairs]
    report = {"benchmark": args.benchmark, "n_pairs": len(pairs),
              "gold_distribution": dict(Counter(gold)), "validators": {}}
    for v, pr in preds.items():
        m = metrics(gold, pr)
        report["validators"][v] = m
        print(f"\n=== {v} ===  n={m['n']}  acc={m['accuracy']}  macroF1={m['macro_f1']}")
        for c in STANCES:
            pc = m["per_class"][c]
            print(f"    {c:8s} P={pc['precision']:.3f} R={pc['recall']:.3f} F1={pc['f1']:.3f} (n={pc['support']})")

    # pairwise agreement among validators (cross-method reliability)
    names = list(preds)
    report["pairwise_kappa"] = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            k, n = cohens_kappa(preds[names[i]], preds[names[j]])
            report["pairwise_kappa"][f"{names[i]}~{names[j]}"] = {"kappa": k, "n": n}

    os.makedirs(OUT, exist_ok=True)
    tag = args.tag or args.benchmark
    json.dump(report, open(os.path.join(OUT, f"report_{tag}.json"), "w"), indent=2)
    # per-pair predictions
    import csv
    with open(os.path.join(OUT, f"preds_{tag}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["uid", "gold"] + names + ["claim", "title"])
        for k, p in enumerate(pairs):
            w.writerow([p["uid"], p["gold"]] + [preds[n][k] for n in names]
                       + [p["claim"][:200], p["title"][:120]])
    print(f"\n[benchmark_validation] wrote results/report_{tag}.json + preds_{tag}.csv")


if __name__ == "__main__":
    main()
