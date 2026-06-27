#!/usr/bin/env python3
"""
score_retrieval_arms.py — run the reproducible NLI surrogate on both retrieval arms
(naive keyword vs Claude-guided) and emit (a) a metrics JSON and (b) a human-readable
dump of the top-k retrieved titles per claim so the validated judge can label relevance
and stance on the same pairs.

Metric of interest: with the SAME stance scorer held fixed, does Claude-guided retrieval
surface more claim-relevant (non-silent) evidence than naive keyword retrieval?
"""
import json, os, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark_validation as bv

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAIRS = os.path.join(BASE, "outputs", "stance", "claude_retrieval_pairs.json")
TOPK = 3


def arm_pairs(claims, arm):
    """Flatten to (claim, ref) pairs, top-TOPK refs per claim for the given arm."""
    out = []
    for c in claims:
        for j, r in enumerate((c.get(f"{arm}_refs") or [])[:TOPK]):
            out.append({"party": c["party"], "claim": c["claim_text"],
                        "title": r.get("title") or "", "abstract": r.get("abstract") or "",
                        "is_empirical": c["is_empirical"],
                        "pr": c["press_release"], "cn": c["claim_number"], "rank": j,
                        "doi": r.get("doi")})
    return out


def summarize(name, pairs, preds):
    by_claim = defaultdict(list)
    for p, s in zip(pairs, preds):
        by_claim[(p["pr"], p["cn"])].append(s)
    dist = Counter(preds)
    n = len(preds) or 1
    nonsilent = sum(1 for s in preds if s in ("support", "refute"))
    support = sum(1 for s in preds if s == "support")
    # relevance yield: fraction of claims with >=1 non-silent retrieved ref
    yield_claims = sum(1 for v in by_claim.values() if any(s in ("support", "refute") for s in v))
    doi = sum(1 for p in pairs if p.get("doi"))
    return {"arm": name, "n_pairs": len(pairs), "n_claims_with_refs": len(by_claim),
            "dist": dict(dist),
            "nonsilent_rate": round(nonsilent / n, 3), "support_rate": round(support / n, 3),
            "relevance_yield_claims": yield_claims,
            "doi_rate": round(doi / (len(pairs) or 1), 3)}


def main():
    claims = json.load(open(PAIRS))
    emp = [c for c in claims if c["is_empirical"]]
    print(f"loaded {len(claims)} claims ({len(emp)} empirical)")

    model = bv.NLI_MODELS["nli_deberta"]
    reports = {}
    for arm in ["naive", "claude"]:
        # for the head-to-head, restrict to EMPIRICAL claims (where Claude emits a query);
        # naive on non-empirical is reported separately as the "cannot abstain" cost.
        pe = arm_pairs(emp, arm)
        preds = bv.run_nli(pe, model) if pe else []
        reports[f"{arm}_empirical"] = summarize(f"{arm} (empirical claims)", pe, preds)
        print(json.dumps(reports[f"{arm}_empirical"], indent=2))

    # naive arm on the 20 non-empirical claims: it retrieves anyway (cannot abstain)
    nonemp = [c for c in claims if not c["is_empirical"]]
    pn = arm_pairs(nonemp, "naive")
    preds = bv.run_nli(pn, model) if pn else []
    reports["naive_nonempirical"] = summarize("naive (non-empirical claims)", pn, preds)
    print(json.dumps(reports["naive_nonempirical"], indent=2))

    out = os.path.join(BASE, "outputs", "stance", "retrieval_arm_metrics_nli.json")
    json.dump(reports, open(out, "w"), indent=2)
    print("wrote", out)

    # human-readable dump of top-k titles per arm for the validated judge
    dump = []
    for c in emp:
        row = {"party": c["party"], "claim": c["claim_text"], "query": c["claude_query"],
               "naive_top": [{"t": (r.get("title") or "")[:140], "y": r.get("year")}
                             for r in (c.get("naive_refs") or [])[:TOPK]],
               "claude_top": [{"t": (r.get("title") or "")[:140], "y": r.get("year")}
                              for r in (c.get("claude_refs") or [])[:TOPK]]}
        dump.append(row)
    json.dump(dump, open(os.path.join(BASE, "outputs", "stance", "retrieval_top_titles.json"), "w"), indent=2)
    print("wrote retrieval_top_titles.json")


if __name__ == "__main__":
    main()
