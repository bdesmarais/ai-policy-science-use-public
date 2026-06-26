#!/usr/bin/env python3
"""
autonomous_validation.py — run the claim-evidence VALIDATION step with NO human RAs,
using OPEN-SOURCE models only (no OpenAI / no API keys).

This re-architects the project's "does the science support the claim?" step (the open
problem; checkpoint #4 in local_only/validation-ideas.md) to execute fully autonomously.
Human coders are replaced by an ensemble of *independent* open-source validators; their
mutual agreement is the autonomous analogue of inter-annotator reliability; a high-agreement
consensus is the internal anchor; and party-level estimates are debiased with a
prediction-powered correction so downstream inference stays valid despite imperfect labels.

Why this design (full write-up + citations: docs/04_autonomous_validation.md):
  - Gilardi/Alizadeh/Kubli 2023 (PNAS); Alizadeh et al. 2023 — LLMs match/beat crowd coders.
  - Calderon et al. 2025 ("alt-test") — when a model may statistically replace an annotator.
  - Egami et al. 2023 (DSL); Angelopoulos et al. 2023 (PPI) — valid downstream inference from
    imperfect (model) labels.
  - LLM/judge biases → never trust one model: combine methodologically *different* validators
    and report cross-validator agreement.

Open-source validators (auto-detected):
  nli_deberta : MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli  (zero-shot NLI)   [transformers]
  nli_bart    : facebook/bart-large-mnli                      (zero-shot NLI)   [transformers]
  osllm       : Qwen/Qwen2.5-1.5B-Instruct (generative LLM-as-judge, subset)    [transformers]
  tfidf       : sklearn TF-IDF cosine relevance + cue stance  (baseline)        [always]
  lexical     : negation-aware lexical relevance + stance     (baseline)        [always]

NLI stance mapping: premise = reference (title+abstract), hypothesis = claim;
  entailment -> support, contradiction -> refute, neutral -> silent.

Usage:
  python3 scripts/core/autonomous_validation.py --max-pairs 300            # auto = open-source NLI ensemble
  python3 scripts/core/autonomous_validation.py --validators nli_deberta nli_bart osllm --osllm-items 40
  python3 scripts/core/autonomous_validation.py --validators tfidf lexical # dependency-free baselines
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REFS_DIR = os.path.join(BASE, "outputs", "structured_refs")
OUT_DIR = os.path.join(BASE, "outputs", "stance")
STANCES = ["support", "refute", "mixed", "silent"]

NLI_MODELS = {
    "nli_deberta": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
    "nli_bart": "facebook/bart-large-mnli",
}
OSLLM_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
CLAUDE_LABELS = os.path.join(OUT_DIR, "claude_judge_labels.json")


# --------------------------------------------------------------------------- #
# Data: build (claim, reference) pairs from the GPT-5 reference outputs
# --------------------------------------------------------------------------- #
def load_pairs(party, per_claim, max_pairs):
    path = os.path.join(REFS_DIR, f"{party}_claim_references.json")
    if not os.path.exists(path):
        return []
    rows = json.load(open(path))
    rows = rows if isinstance(rows, list) else list(rows.values())
    pairs = []
    for entry in rows:
        claim = (entry.get("claim_text") or "").strip()
        if not claim:
            continue
        for i, r in enumerate((entry.get("references") or [])[:per_claim]):
            abstract, title = (r.get("abstract") or "").strip(), (r.get("title") or "").strip()
            if not (abstract or title):
                continue
            uid = r.get("doi") or r.get("id") or r.get("url") or f"{entry.get('press_release')}#{entry.get('claim_number')}#{i}"
            pairs.append({"party": party, "press_release": entry.get("press_release"),
                          "claim_number": entry.get("claim_number"), "claim_text": claim,
                          "ref_uid": str(uid), "ref_title": title, "ref_abstract": abstract,
                          "ref_year": r.get("year"), "ref_venue": r.get("venue")})
            if max_pairs and len(pairs) >= max_pairs:
                return pairs
    return pairs


# --------------------------------------------------------------------------- #
# Baseline validators (dependency-free)
# --------------------------------------------------------------------------- #
SUPPORT_CUES = re.compile(r"\b(support|confirm|consistent|demonstrate|show[s]?|evidence that|"
                          r"associated with|increase[sd]?|improve[sd]?|effective|benefit|caus)", re.I)
REFUTE_CUES = re.compile(r"\b(no (?:evidence|effect|association)|not (?:support|associated|effective)|"
                         r"contrary|refute|contradict|disprove|fail(?:s|ed)? to|ineffective|"
                         r"null result|no significant)", re.I)
NEG = re.compile(r"\b(no|not|never|without|fail|lack|absence|nor|cannot|n't)\b", re.I)
WORD = re.compile(r"[a-z][a-z0-9\-]{2,}")
STOP = set("the a an and or of to in for on with that this these those is are was were be as by at from "
           "it its their his her our your they we you i he she them us also into over under more most such "
           "than then but not no if can may will would should could about which who whom whose".split())


def _toks(t):
    return [w for w in WORD.findall((t or "").lower()) if w not in STOP]


def validator_tfidf(pairs):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    claims = [p["claim_text"] for p in pairs]
    docs = [f"{p['ref_title']}. {p['ref_abstract']}" for p in pairs]
    X = TfidfVectorizer(stop_words="english", min_df=1, ngram_range=(1, 2)).fit_transform(claims + docs)
    n = len(pairs)
    sims = cosine_similarity(X[:n], X[n:]).diagonal()
    out = []
    for p, s in zip(pairs, sims):
        rel = 2 if s >= 0.18 else (1 if s >= 0.07 else 0)
        txt = f"{p['ref_title']}. {p['ref_abstract']}"
        stance = "silent" if rel == 0 else ("refute" if REFUTE_CUES.search(txt)
                                            else ("support" if SUPPORT_CUES.search(txt) else "silent"))
        out.append({"relevance": rel, "stance": stance, "confidence": float(round(min(1, s * 2.5), 3))})
    return out


def validator_lexical(pairs):
    out = []
    for p in pairs:
        c, d_txt = set(_toks(p["claim_text"])), f"{p['ref_title']}. {p['ref_abstract']}"
        d = set(_toks(d_txt))
        overlap = len(c & d) / (len(c) + 1e-9)
        rel = 2 if overlap >= 0.30 else (1 if overlap >= 0.12 else 0)
        if rel == 0:
            stance = "silent"
        else:
            neg = len(NEG.findall(d_txt))
            stance = ("refute" if (REFUTE_CUES.search(d_txt) or neg >= 3)
                      else ("support" if SUPPORT_CUES.search(d_txt) and neg < 2
                            else ("mixed" if SUPPORT_CUES.search(d_txt) else "silent")))
        out.append({"relevance": rel, "stance": stance, "confidence": float(round(min(1, overlap * 2), 3))})
    return out


# --------------------------------------------------------------------------- #
# Open-source production validators (transformers)
# --------------------------------------------------------------------------- #
def _make_nli(pairs, model_id):
    from transformers import pipeline
    clf = pipeline("text-classification", model=model_id, top_k=None, truncation=True, max_length=512)
    inputs = [{"text": f"{p['ref_title']}. {p['ref_abstract']}"[:2000], "text_pair": p["claim_text"][:600]}
              for p in pairs]
    results = clf(inputs, batch_size=16)
    out = []
    for res in results:
        sc = {d["label"].lower(): d["score"] for d in res}
        ent, con, neu = sc.get("entailment", 0.0), sc.get("contradiction", 0.0), sc.get("neutral", 0.0)
        label, conf = max([("support", ent), ("refute", con), ("silent", neu)], key=lambda t: t[1])
        out.append({"relevance": 0 if label == "silent" else 2, "stance": label, "confidence": round(float(conf), 3)})
    return out


def validator_nli_deberta(pairs):
    return _make_nli(pairs, NLI_MODELS["nli_deberta"])


def validator_nli_bart(pairs):
    return _make_nli(pairs, NLI_MODELS["nli_bart"])


def validator_osllm(pairs, model_id=OSLLM_MODEL, max_items=40):
    """Open-source generative LLM-as-judge (Qwen2.5-Instruct). CPU-bound, so capped to a
    subset; pairs beyond max_items are returned as 'abstain' and excluded from agreement."""
    from transformers import pipeline
    gen = pipeline("text-generation", model=model_id, torch_dtype="auto")
    sysmsg = ("You assess scientific evidence. Decide whether the REFERENCE supports, refutes, "
              "is mixed on, or is silent (irrelevant / does not address) the CLAIM. "
              "Reply with exactly one word: support, refute, mixed, or silent.")
    out = []
    for i, p in enumerate(pairs):
        if i >= max_items:
            out.append({"relevance": None, "stance": "abstain", "confidence": 0.0})
            continue
        msg = [{"role": "system", "content": sysmsg},
               {"role": "user", "content": f"CLAIM: {p['claim_text']}\nREFERENCE: {p['ref_title']}. "
                                           f"{p['ref_abstract'][:1200]}\nAnswer:"}]
        try:
            r = gen(msg, max_new_tokens=4, do_sample=False, return_full_text=False)
            gt = r[0]["generated_text"]
            txt = (gt[-1]["content"] if isinstance(gt, list) else str(gt)).lower()
            stance = next((s for s in ["support", "refute", "mixed", "silent"] if s in txt), "silent")
        except Exception:
            stance = "silent"
        out.append({"relevance": 0 if stance == "silent" else 2, "stance": stance, "confidence": 1.0})
    return out


def validator_claude_judge(pairs):
    """Claude Opus 4.8's own stance judgments (NO API key — produced in-session under the Max
    plan), loaded from outputs/stance/claude_judge_labels.json. The high-quality GOLD validator;
    pairs outside the judged sample return 'abstain' (excluded from agreement, used as the
    PPI/DSL gold anchor where present)."""
    if not os.path.exists(CLAUDE_LABELS):
        return [{"relevance": None, "stance": "abstain", "confidence": 0.0} for _ in pairs]
    lab = json.load(open(CLAUDE_LABELS)).get("labels", {})
    out = []
    for p in pairs:
        k = f"{p['party']}|{p['press_release']}|{p['claim_number']}|{p['ref_uid']}"
        s = lab.get(k, {}).get("stance", "abstain")
        out.append({"relevance": None if s == "abstain" else (0 if s == "silent" else 2),
                    "stance": s, "confidence": 0.0 if s == "abstain" else 1.0})
    return out


VALIDATORS = {
    "claude_judge": validator_claude_judge,
    "nli_deberta": validator_nli_deberta,
    "nli_bart": validator_nli_bart,
    "osllm": validator_osllm,
    "tfidf": validator_tfidf,
    "lexical": validator_lexical,
}


def available_validators(requested):
    avail = []
    have_tf = False
    try:
        import transformers  # noqa
        have_tf = True
    except ImportError:
        pass
    for name in requested:
        if name == "claude_judge":
            if os.path.exists(CLAUDE_LABELS):
                avail.append(name)
        elif name in ("tfidf", "lexical"):
            avail.append(name)
        elif name in ("nli_deberta", "nli_bart", "osllm") and have_tf:
            avail.append(name)
    return avail, have_tf


# --------------------------------------------------------------------------- #
# Agreement + consensus + prediction-powered estimate
# --------------------------------------------------------------------------- #
def pairwise_agreement(labels):
    from sklearn.metrics import cohen_kappa_score
    names = list(labels)
    res = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = labels[names[i]], labels[names[j]]
            mask = [(x != "abstain" and y != "abstain") for x, y in zip(a, b)]
            aa = [x for x, m in zip(a, mask) if m]
            bb = [y for y, m in zip(b, mask) if m]
            if not aa:
                continue
            pct = float(np.mean([x == y for x, y in zip(aa, bb)]))
            try:
                kappa = float(cohen_kappa_score(aa, bb, labels=STANCES))
            except Exception:
                kappa = float("nan")
            res[f"{names[i]}~{names[j]}"] = {"n": len(aa), "percent_agreement": round(pct, 3),
                                             "cohens_kappa": round(kappa, 3)}
    return res


def consensus(labels):
    names = list(labels)
    n = len(labels[names[0]])
    cons, unanimous = [], []
    for k in range(n):
        votes = [labels[name][k] for name in names if labels[name][k] != "abstain"]
        if not votes:
            cons.append("silent"); unanimous.append(False); continue
        top, cnt = Counter(votes).most_common(1)[0]
        cons.append(top); unanimous.append(cnt == len(votes) and len(votes) >= 2)
    return cons, unanimous


def ppi_mean(pred_all, pred_lab, gold_lab):
    """Prediction-powered point estimate + 95% CI for a binary mean (Angelopoulos et al. 2023).
    Anchor = high-agreement consensus subset (autonomous stand-in for gold; a small true-gold
    set upgrades this to a formal PPI/DSL estimate — see docs/04)."""
    pred_all = np.asarray(pred_all, float)
    pred_lab, gold_lab = np.asarray(pred_lab, float), np.asarray(gold_lab, float)
    N, n = len(pred_all), max(len(gold_lab), 1)
    rect = float(np.mean(gold_lab - pred_lab)) if len(gold_lab) else 0.0
    est = float(np.mean(pred_all)) + rect
    var = np.var(pred_all) / N + (np.var(gold_lab - pred_lab) / n if len(gold_lab) else 0.0)
    half = 1.96 * float(np.sqrt(max(var, 0.0)))
    return {"estimate": round(min(1, max(0, est)), 4), "ci95": [round(est - half, 4), round(est + half, 4)],
            "naive_estimate": round(float(np.mean(pred_all)), 4), "n_all": N, "n_anchor": int(len(gold_lab))}


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parties", nargs="+", default=["dem", "rep"])
    ap.add_argument("--per-claim", type=int, default=5)
    ap.add_argument("--max-pairs", type=int, default=300, help="cap pairs per party (0 = all)")
    ap.add_argument("--validators", nargs="+", default=["auto"])
    ap.add_argument("--osllm-items", type=int, default=40, help="subset size for the generative LLM judge")
    args = ap.parse_args()

    if args.validators in (["auto"], ["all"]):
        base = ["nli_deberta", "nli_bart"] if args.validators == ["auto"] else ["nli_deberta", "nli_bart", "osllm", "tfidf", "lexical"]
        requested = (["claude_judge"] + base) if os.path.exists(CLAUDE_LABELS) else base
    else:
        requested = args.validators
    use, have_tf = available_validators(requested)
    if len(use) < 2:
        use = list(dict.fromkeys(use + ["tfidf", "lexical"]))
    print(f"[autonomous_validation] open-source validators in use: {use}  (transformers={have_tf})")

    pairs = []
    for party in args.parties:
        pairs += load_pairs(party, args.per_claim, args.max_pairs)
    if not pairs:
        print("No pairs under outputs/structured_refs/. Run gpt_references.py first.")
        sys.exit(1)
    print(f"[autonomous_validation] {len(pairs)} pairs ({dict(Counter(p['party'] for p in pairs))})")

    labels = {}
    for name in use:
        print(f"  running validator: {name} ...", flush=True)
        fn = (lambda pp, n=name: VALIDATORS[n](pp, max_items=args.osllm_items)) if name == "osllm" else VALIDATORS[name]
        labels[name] = [r["stance"] for r in fn(pairs)]

    agree = pairwise_agreement(labels)
    cons, unanimous = consensus(labels)
    n_unan = int(sum(unanimous))

    # Surrogate = scalable NLI on ALL pairs; GOLD = Claude Opus 4.8 judgments where available
    # (a true gold set -> formal PPI/DSL), else fall back to the unanimous-consensus anchor.
    primary = next((n for n in use if n.startswith("nli")), use[0])
    gold_name = "claude_judge" if "claude_judge" in labels else None
    anchor_desc = f"Claude Opus 4.8 gold labels (n where judged)" if gold_name else "unanimous-consensus subset"
    by_party = defaultdict(lambda: {"pred_all": [], "pred_lab": [], "gold_lab": []})
    for k, p in enumerate(pairs):
        pred = 1.0 if labels[primary][k] == "support" else 0.0
        by_party[p["party"]]["pred_all"].append(pred)
        if gold_name:
            g = labels[gold_name][k]
            if g != "abstain":
                by_party[p["party"]]["pred_lab"].append(pred)
                by_party[p["party"]]["gold_lab"].append(1.0 if g == "support" else 0.0)
        elif unanimous[k]:
            by_party[p["party"]]["pred_lab"].append(pred)
            by_party[p["party"]]["gold_lab"].append(1.0 if cons[k] == "support" else 0.0)
    support_rate = {pty: ppi_mean(d["pred_all"], d["pred_lab"], d["gold_lab"]) for pty, d in by_party.items()}

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "pairs_labeled.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["party", "press_release", "claim_number", "ref_uid"] + [f"stance_{n}" for n in use]
                   + ["consensus", "unanimous", "claim_text", "ref_title"])
        for k, p in enumerate(pairs):
            w.writerow([p["party"], p["press_release"], p["claim_number"], p["ref_uid"]]
                       + [labels[n][k] for n in use] + [cons[k], int(unanimous[k]),
                          p["claim_text"][:200], p["ref_title"][:160]])

    report = {"n_pairs": len(pairs), "validators": use, "transformers": have_tf,
              "models": {n: NLI_MODELS.get(n, OSLLM_MODEL if n == "osllm" else
                         ("Claude Opus 4.8 (claude-opus-4-8)" if n == "claude_judge" else "—")) for n in use},
              "pairwise_agreement": agree, "consensus_stance_distribution": dict(Counter(cons)),
              "unanimous_pairs": n_unan, "unanimous_fraction": round(n_unan / len(pairs), 3),
              "support_rate_by_party_ppi": support_rate, "ppi_anchor": anchor_desc,
              "notes": "Open-source models + Claude Opus 4.8 as in-session judge/gold (no API key). "
                       "Surrogate = NLI on all pairs; gold = Claude judgments -> formal PPI/DSL (docs/04)."}
    json.dump(report, open(os.path.join(OUT_DIR, "validation_report.json"), "w"), indent=2)

    lines = ["# Autonomous validation report (open-source models)", "",
             f"- Pairs judged: **{len(pairs)}**  |  Validators: **{', '.join(use)}**",
             f"- Models: " + ", ".join(f"`{n}`={report['models'][n]}" for n in use),
             f"- Unanimous (high-confidence) pairs: **{n_unan}** ({report['unanimous_fraction']:.1%})", "",
             "## Cross-validator agreement (autonomous inter-annotator reliability)"]
    for k, v in agree.items():
        lines.append(f"- `{k}`: {v['percent_agreement']:.1%} agree, κ={v['cohens_kappa']} (n={v['n']})")
    lines += ["", "## Consensus stance distribution", ""]
    for s, c in Counter(cons).most_common():
        lines.append(f"- {s}: {c} ({c/len(pairs):.1%})")
    lines += ["", f"## Support rate by party (PPI-debiased; gold anchor = {anchor_desc})", ""]
    for pty, d in support_rate.items():
        lines.append(f"- **{pty}**: {d['estimate']:.3f} (95% CI {d['ci95']}; naive {d['naive_estimate']:.3f}; "
                     f"anchor n={d['n_anchor']}/{d['n_all']})")
    open(os.path.join(OUT_DIR, "validation_report.md"), "w").write("\n".join(lines))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        cd = Counter(cons)
        ax[0].bar(list(cd), [cd[s] for s in cd], color="#4a86e8")
        ax[0].set_title("Consensus stance distribution"); ax[0].set_ylabel("pairs")
        ps = list(support_rate)
        ax[1].bar(ps, [support_rate[p]["estimate"] for p in ps],
                  yerr=[[support_rate[p]["estimate"] - support_rate[p]["ci95"][0] for p in ps],
                        [support_rate[p]["ci95"][1] - support_rate[p]["estimate"] for p in ps]],
                  color=["#2166AC", "#B2182B"][:len(ps)], capsize=5)
        ax[1].set_title("Support rate by party (PPI ± 95% CI)"); ax[1].set_ylim(0, 1)
        plt.tight_layout(); plt.savefig(os.path.join(OUT_DIR, "validation_overview.png"), dpi=150)
    except Exception as e:  # noqa
        print(f"(figure skipped: {e})")

    print("\n".join(lines))
    print(f"\n[autonomous_validation] outputs in {OUT_DIR}/")


if __name__ == "__main__":
    main()
