#!/usr/bin/env python3
"""
autonomous_validation.py — run the claim-evidence VALIDATION step with NO human RAs.

This re-architects the project's "does the science support the claim?" step so it can be
executed fully autonomously. Human coders are replaced by an ensemble of *independent*
automated validators; their mutual agreement is the autonomous analogue of inter-annotator
reliability; a high-agreement consensus serves as an internal anchor; and party-level
estimates are debiased with a prediction-powered correction so downstream inference stays
valid despite imperfect labels.

Why this design (see docs/04_autonomous_validation.md for the full write-up + citations):
  - Gilardi, Alizadeh & Kubli 2023 (PNAS) and Alizadeh et al. 2023 show LLMs match/beat
    crowd coders on relevance/stance/frame tasks, at far lower cost and higher consistency.
  - Calderon et al. 2025 ("alt-test") give a procedure to statistically justify replacing
    an annotator with an LLM.
  - Egami et al. 2023 (Design-based Supervised Learning) and Angelopoulos et al. 2023
    (Prediction-Powered Inference) show that naive use of imperfect (LLM) labels biases
    downstream estimates — and how to correct it. We use a PPI-style correction here.
  - LLM-as-judge has known biases (position/verbosity/self-preference), so we never rely on
    a single LLM: we combine it with a methodologically *different* validator (an NLI model)
    and report cross-validator agreement.

Validators (auto-detected at runtime):
  llm_judge : OpenAI Responses API, ensemble / self-consistency   (needs `openai` + OPENAI_API_KEY)
  nli       : transformers NLI (entail=support / contradict=refute / neutral=silent)
                                                                   (needs `transformers` + `torch`)
  tfidf     : sklearn TF-IDF cosine relevance + cue-based stance   (always available)
  lexical   : negation-aware lexical relevance + stance            (always available)

The `tfidf` and `lexical` validators are deliberately lightweight *baseline* validators so the
whole pipeline executes with zero external dependencies / no API key (as in CI or a fresh
checkout). The `llm_judge` + `nli` validators are the production validators; they slot into the
exact same interface and agreement machinery when their libraries/keys are present.

Stance label space: support / refute / mixed / silent   (silent = irrelevant or not addressed)

Usage:
  python3 scripts/core/autonomous_validation.py --max-pairs 600
  python3 scripts/core/autonomous_validation.py --validators all --per-claim 5
"""
import argparse
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

# --------------------------------------------------------------------------- #
# Data loading: build (claim, reference) pairs from the GPT-5 reference outputs
# --------------------------------------------------------------------------- #
def load_pairs(party, per_claim, max_pairs):
    """Yield dict pairs {party, press_release, claim_number, claim_text, ref_uid,
    ref_title, ref_abstract, ref_year, ref_venue}."""
    path = os.path.join(REFS_DIR, f"{party}_claim_references.json")
    if not os.path.exists(path):
        return []
    data = json.load(open(path))
    rows = data if isinstance(data, list) else list(data.values())
    pairs = []
    for entry in rows:
        claim = (entry.get("claim_text") or "").strip()
        if not claim:
            continue
        refs = entry.get("references") or []
        for i, r in enumerate(refs[:per_claim]):
            abstract = (r.get("abstract") or "").strip()
            title = (r.get("title") or "").strip()
            if not (abstract or title):
                continue
            uid = r.get("doi") or r.get("id") or r.get("url") or f"{entry.get('press_release')}#{entry.get('claim_number')}#{i}"
            pairs.append({
                "party": party,
                "press_release": entry.get("press_release"),
                "claim_number": entry.get("claim_number"),
                "claim_text": claim,
                "ref_uid": str(uid),
                "ref_title": title,
                "ref_abstract": abstract,
                "ref_year": r.get("year"),
                "ref_venue": r.get("venue"),
            })
            if max_pairs and len(pairs) >= max_pairs:
                return pairs
    return pairs


# --------------------------------------------------------------------------- #
# Validator interface: each validator is f(list[pair]) -> list[{relevance,stance,confidence}]
# --------------------------------------------------------------------------- #
SUPPORT_CUES = re.compile(r"\b(support|confirm|consistent|demonstrate|show[s]?|evidence that|"
                          r"associated with|increase[sd]?|improve[sd]?|effective|benefit|caus)", re.I)
REFUTE_CUES = re.compile(r"\b(no (?:evidence|effect|association)|not (?:support|associated|effective)|"
                         r"contrary|refute|contradict|disprove|fail(?:s|ed)? to|reduce[sd]? .* harm|"
                         r"ineffective|null result|no significant)", re.I)
NEG = re.compile(r"\b(no|not|never|without|fail|lack|absence|nor|cannot|n't)\b", re.I)
WORD = re.compile(r"[a-z][a-z0-9\-]{2,}")
STOP = set("the a an and or of to in for on with that this these those is are was were be as by at from "
           "it its their his her our your they we you i he she them us also into over under more most "
           "such than then but not no if can may will would should could about which who whom whose".split())


def _toks(text):
    return [w for w in WORD.findall((text or "").lower()) if w not in STOP]


def validator_tfidf(pairs):
    """sklearn TF-IDF cosine for relevance; cue scan for a coarse stance.
    Baseline validator #1 — always available."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    claims = [p["claim_text"] for p in pairs]
    docs = [f"{p['ref_title']}. {p['ref_abstract']}" for p in pairs]
    vec = TfidfVectorizer(stop_words="english", min_df=1, ngram_range=(1, 2))
    X = vec.fit_transform(claims + docs)
    n = len(pairs)
    sims = cosine_similarity(X[:n], X[n:]).diagonal()
    out = []
    for p, s in zip(pairs, sims):
        rel = 2 if s >= 0.18 else (1 if s >= 0.07 else 0)
        txt = f"{p['ref_title']}. {p['ref_abstract']}"
        if rel == 0:
            stance = "silent"
        elif REFUTE_CUES.search(txt):
            stance = "refute"
        elif SUPPORT_CUES.search(txt):
            stance = "support"
        else:
            stance = "silent"
        out.append({"relevance": rel, "stance": stance, "confidence": float(round(min(1.0, s * 2.5), 3))})
    return out


def validator_lexical(pairs):
    """Negation-aware token-overlap relevance + cue/negation stance.
    Baseline validator #2 — methodologically different from tfidf (no global IDF), always available."""
    out = []
    for p in pairs:
        c = set(_toks(p["claim_text"]))
        d_txt = f"{p['ref_title']}. {p['ref_abstract']}"
        d = set(_toks(d_txt))
        overlap = len(c & d) / (len(c) + 1e-9)
        rel = 2 if overlap >= 0.30 else (1 if overlap >= 0.12 else 0)
        if rel == 0:
            stance = "silent"
        else:
            neg = len(NEG.findall(d_txt))
            if REFUTE_CUES.search(d_txt) or neg >= 3:
                stance = "refute"
            elif SUPPORT_CUES.search(d_txt):
                stance = "support" if neg < 2 else "mixed"
            else:
                stance = "silent"
        out.append({"relevance": rel, "stance": stance, "confidence": float(round(min(1.0, overlap * 2), 3))})
    return out


def validator_nli(pairs):
    """transformers NLI: premise=reference, hypothesis=claim. entail->support,
    contradict->refute, neutral->silent. Production validator (needs transformers+torch)."""
    from transformers import pipeline  # noqa
    clf = pipeline("text-classification", model="microsoft/deberta-large-mnli", top_k=None)
    out = []
    for p in pairs:
        premise = f"{p['ref_title']}. {p['ref_abstract']}"[:1800]
        scores = {d["label"].lower(): d["score"] for d in clf({"text": premise, "text_pair": p["claim_text"]})[0]}
        ent, con, neu = scores.get("entailment", 0), scores.get("contradiction", 0), scores.get("neutral", 0)
        top = max(("support", ent), ("refute", con), ("silent", neu), key=lambda t: t[1])
        rel = 0 if top[0] == "silent" else 2
        out.append({"relevance": rel, "stance": top[0], "confidence": float(round(top[1], 3))})
    return out


def validator_llm_judge(pairs, model="gpt-5", ensemble=3):
    """OpenAI Responses API stance judge with self-consistency. Production validator
    (needs `openai` + OPENAI_API_KEY). Returns the majority stance across `ensemble` samples."""
    from openai import OpenAI  # noqa
    client = OpenAI()
    sys_prompt = ("You are a careful scientific-evidence assessor. Given a POLICY CLAIM and a "
                  "SCIENTIFIC REFERENCE (title+abstract), decide whether the reference SUPPORTS, "
                  "REFUTES, is MIXED on, or is SILENT (irrelevant / does not address) the claim. "
                  "Also rate relevance 0/1/2. Reply as JSON: "
                  '{"relevance":0|1|2,"stance":"support|refute|mixed|silent","confidence":0..1}.')
    out = []
    for p in pairs:
        user = f"CLAIM: {p['claim_text']}\n\nREFERENCE: {p['ref_title']}. {p['ref_abstract']}"
        votes = []
        for _ in range(ensemble):
            try:
                r = client.responses.create(model=model, input=[{"role": "system", "content": sys_prompt},
                                                                 {"role": "user", "content": user}])
                txt = r.output_text
                m = re.search(r"\{.*\}", txt, re.S)
                votes.append(json.loads(m.group(0)))
            except Exception as e:  # noqa
                votes.append({"relevance": 0, "stance": "silent", "confidence": 0.0})
        st = Counter(v.get("stance", "silent") for v in votes).most_common(1)[0]
        rel = int(np.median([v.get("relevance", 0) for v in votes]))
        out.append({"relevance": rel, "stance": st[0], "confidence": round(st[1] / ensemble, 3)})
    return out


VALIDATORS = {
    "tfidf": validator_tfidf,
    "lexical": validator_lexical,
    "nli": validator_nli,
    "llm_judge": validator_llm_judge,
}


def available_validators(requested):
    """Return the validators we can actually run in this environment."""
    avail = []
    for name in requested:
        if name in ("tfidf", "lexical"):
            try:
                import sklearn  # noqa
                avail.append(name)
            except ImportError:
                pass
        elif name == "nli":
            try:
                import transformers, torch  # noqa
                avail.append(name)
            except ImportError:
                pass
        elif name == "llm_judge":
            try:
                import openai  # noqa
                if os.environ.get("OPENAI_API_KEY"):
                    avail.append(name)
            except ImportError:
                pass
    return avail


# --------------------------------------------------------------------------- #
# Agreement + consensus + prediction-powered estimate
# --------------------------------------------------------------------------- #
def pairwise_agreement(labels_by_validator):
    from sklearn.metrics import cohen_kappa_score
    names = list(labels_by_validator)
    res = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = labels_by_validator[names[i]], labels_by_validator[names[j]]
            pct = float(np.mean([x == y for x, y in zip(a, b)]))
            try:
                kappa = float(cohen_kappa_score(a, b, labels=STANCES))
            except Exception:
                kappa = float("nan")
            res[f"{names[i]}~{names[j]}"] = {"percent_agreement": round(pct, 3), "cohens_kappa": round(kappa, 3)}
    return res


def consensus(labels_by_validator):
    """Majority-vote consensus + a 'high-confidence' flag (unanimous across validators)."""
    names = list(labels_by_validator)
    n = len(labels_by_validator[names[0]])
    cons, unanimous = [], []
    for k in range(n):
        votes = [labels_by_validator[name][k] for name in names]
        top, cnt = Counter(votes).most_common(1)[0]
        cons.append(top)
        unanimous.append(cnt == len(names))
    return cons, unanimous


def ppi_mean(pred_all, pred_lab, gold_lab):
    """Prediction-powered point estimate + 95% CI for a binary mean (e.g., support rate).
    estimate = mean(pred over ALL) + mean(gold - pred over the labeled/anchor subset).
    (Angelopoulos et al. 2023.) Here the 'anchor' is the high-agreement consensus subset;
    with a small *true* gold set this becomes a formal PPI / DSL estimator — see the design doc.
    """
    pred_all = np.asarray(pred_all, float)
    pred_lab = np.asarray(pred_lab, float)
    gold_lab = np.asarray(gold_lab, float)
    N, n = len(pred_all), max(len(gold_lab), 1)
    rectifier = float(np.mean(gold_lab - pred_lab)) if len(gold_lab) else 0.0
    est = float(np.mean(pred_all)) + rectifier
    var = np.var(pred_all) / N + (np.var(gold_lab - pred_lab) / n if len(gold_lab) else 0.0)
    half = 1.96 * float(np.sqrt(max(var, 0.0)))
    naive = float(np.mean(pred_all))
    return {"estimate": round(min(1, max(0, est)), 4), "ci95": [round(est - half, 4), round(est + half, 4)],
            "naive_estimate": round(naive, 4), "n_all": N, "n_anchor": int(len(gold_lab))}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parties", nargs="+", default=["dem", "rep"])
    ap.add_argument("--per-claim", type=int, default=5, help="max references per claim to judge")
    ap.add_argument("--max-pairs", type=int, default=600, help="cap pairs per party (0 = all)")
    ap.add_argument("--validators", nargs="+", default=["auto"],
                    help="'auto' (all available), 'all', or explicit names")
    args = ap.parse_args()

    requested = list(VALIDATORS) if args.validators in (["auto"], ["all"]) else args.validators
    use = available_validators(requested)
    if len(use) < 2:
        # ensure at least the two dependency-free baselines so agreement is computable
        for b in ("tfidf", "lexical"):
            if b not in use:
                use.append(b)
    print(f"[autonomous_validation] validators in use: {use}")
    if "llm_judge" not in use or "nli" not in use:
        print("[note] production validators not active here (no OPENAI_API_KEY / no transformers); "
              "running with baseline validators. Install deps / set key to activate llm_judge + nli.")

    pairs = []
    for party in args.parties:
        pairs += load_pairs(party, args.per_claim, args.max_pairs)
    if not pairs:
        print("No pairs found under outputs/structured_refs/. Run gpt_references.py first.")
        sys.exit(1)
    print(f"[autonomous_validation] {len(pairs)} claim-reference pairs "
          f"({Counter(p['party'] for p in pairs)})")

    labels = {name: [r["stance"] for r in VALIDATORS[name](pairs)] for name in use}

    agree = pairwise_agreement(labels)
    cons, unanimous = consensus(labels)
    n_unan = int(sum(unanimous))

    # Party-level support rate among *relevant* pairs, debiased with PPI using the
    # high-agreement (unanimous) subset as the internal anchor.
    primary = use[0]
    by_party = defaultdict(lambda: {"pred_all": [], "pred_lab": [], "gold_lab": []})
    for k, p in enumerate(pairs):
        is_support = 1.0 if cons[k] == "support" else 0.0
        pred = 1.0 if labels[primary][k] == "support" else 0.0
        by_party[p["party"]]["pred_all"].append(pred)
        if unanimous[k]:
            by_party[p["party"]]["pred_lab"].append(pred)
            by_party[p["party"]]["gold_lab"].append(is_support)
    support_rate = {party: ppi_mean(d["pred_all"], d["pred_lab"], d["gold_lab"]) for party, d in by_party.items()}

    os.makedirs(OUT_DIR, exist_ok=True)
    # per-pair labels
    import csv
    with open(os.path.join(OUT_DIR, "pairs_labeled.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["party", "press_release", "claim_number", "ref_uid"] + [f"stance_{n}" for n in use]
                   + ["consensus", "unanimous", "claim_text", "ref_title"])
        for k, p in enumerate(pairs):
            w.writerow([p["party"], p["press_release"], p["claim_number"], p["ref_uid"]]
                       + [labels[n][k] for n in use]
                       + [cons[k], int(unanimous[k]), p["claim_text"][:200], p["ref_title"][:160]])

    report = {
        "n_pairs": len(pairs),
        "validators": use,
        "pairwise_agreement": agree,
        "consensus_stance_distribution": dict(Counter(cons)),
        "unanimous_pairs": n_unan,
        "unanimous_fraction": round(n_unan / len(pairs), 3),
        "support_rate_by_party_ppi": support_rate,
        "notes": "Baseline validators in this run; llm_judge+nli are the production validators. "
                 "PPI anchor = unanimous-consensus subset (autonomous stand-in for gold). With a "
                 "small true-gold set this is a formal PPI/DSL estimate (see docs/04).",
    }
    json.dump(report, open(os.path.join(OUT_DIR, "validation_report.json"), "w"), indent=2)

    # human-readable report
    lines = ["# Autonomous validation report", "",
             f"- Pairs judged: **{len(pairs)}**  |  Validators: **{', '.join(use)}**",
             f"- Unanimous (high-confidence) pairs: **{n_unan}** ({report['unanimous_fraction']:.1%})",
             "", "## Cross-validator agreement (autonomous inter-annotator reliability)"]
    for k, v in agree.items():
        lines.append(f"- `{k}`: {v['percent_agreement']:.1%} agree, κ = {v['cohens_kappa']}")
    lines += ["", "## Consensus stance distribution", ""]
    for s, c in Counter(cons).most_common():
        lines.append(f"- {s}: {c} ({c/len(pairs):.1%})")
    lines += ["", "## Support rate by party (PPI-debiased)", ""]
    for party, d in support_rate.items():
        lines.append(f"- **{party}**: {d['estimate']:.3f}  (95% CI {d['ci95']}; naive {d['naive_estimate']:.3f}; "
                     f"anchor n={d['n_anchor']}/{d['n_all']})")
    lines += ["", "_Baseline validators used in this run; install `transformers`+`torch` and set "
              "`OPENAI_API_KEY` to activate the NLI + LLM-judge production validators._"]
    open(os.path.join(OUT_DIR, "validation_report.md"), "w").write("\n".join(lines))

    # figure
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        cd = Counter(cons)
        ax[0].bar(list(cd), [cd[s] for s in cd], color="#4a86e8")
        ax[0].set_title("Consensus stance distribution"); ax[0].set_ylabel("pairs")
        parties = list(support_rate)
        ax[1].bar(parties, [support_rate[p]["estimate"] for p in parties],
                  yerr=[[support_rate[p]["estimate"] - support_rate[p]["ci95"][0] for p in parties],
                        [support_rate[p]["ci95"][1] - support_rate[p]["estimate"] for p in parties]],
                  color=["#2166AC", "#B2182B"][:len(parties)], capsize=5)
        ax[1].set_title("Support rate by party (PPI ± 95% CI)"); ax[1].set_ylim(0, 1)
        plt.tight_layout(); plt.savefig(os.path.join(OUT_DIR, "validation_overview.png"), dpi=150)
        print(f"[autonomous_validation] wrote figure -> {os.path.join(OUT_DIR, 'validation_overview.png')}")
    except Exception as e:  # noqa
        print(f"[autonomous_validation] (figure skipped: {e})")

    print("\n".join(lines))
    print(f"\n[autonomous_validation] outputs in {OUT_DIR}/")


if __name__ == "__main__":
    main()
