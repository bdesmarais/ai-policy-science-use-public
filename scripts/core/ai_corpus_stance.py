#!/usr/bin/env python3
"""
ai_corpus_stance.py — corroboration estimation over the full AI corpus with model-guided
(OpenAlex) retrieval and NO proprietary retrieval anywhere.

Unit of analysis: the empirical claim that retrieved >=1 reference. A claim is "corroborated"
if its best retrieved reference supports it.
  - surrogate f (all such claims): NLI-support on ANY retrieved reference (scales for free)
  - gold y (sampled claims): the benchmark-validated judge's stance on the claim's best ref
    (data/ai_gold_stance.json: {id: {"stance": "support|refute|silent"}})
We report, by party: the surrogate mean over all claims, the direct judge mean + Wilson 95% CI
on the gold sample, and the PPI estimate combining them (valid for the rate the judge would
assign over all claims). Because the surrogate is near-constant on policy text, PPI reduces in
practice to the judge mean on the gold sample, and we say so.
"""
import json, math, os, sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark_validation as bv

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAIRS = os.path.join(BASE, "outputs", "ai_corpus", "retrieved_pairs.json")
GOLD = os.path.join(BASE, "data", "ai_gold_stance.json")
OUT = os.path.join(BASE, "benchmarks", "results", "ai_corpus_corroboration.json")
TOPK = 6


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z*z/n
    c = p + z*z/(2*n)
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (round(p, 3), round((c-h)/d, 3), round((c+h)/d, 3))


def main():
    claims = json.load(open(PAIRS))
    emp = [c for c in claims if c["is_empirical"] and c.get("refs")]
    print(f"empirical claims with >=1 retrieved ref: {len(emp)} "
          f"(dem {sum(1 for c in emp if c['party']=='dem')}, rep {sum(1 for c in emp if c['party']=='rep')})")

    # NLI surrogate over every retrieved pair
    pairs, owner = [], []
    for c in emp:
        for r in c["refs"][:TOPK]:
            pairs.append({"claim": c["claim_text"], "title": r.get("title", ""),
                          "abstract": r.get("abstract", "")})
            owner.append(c["id"])
    preds = bv.run_nli(pairs, bv.NLI_MODELS["nli_deberta"]) if pairs else []
    sup_by_claim = defaultdict(int)
    for cid, s in zip(owner, preds):
        if s == "support":
            sup_by_claim[cid] += 1
    surrogate = {c["id"]: (1 if sup_by_claim.get(c["id"], 0) > 0 else 0) for c in emp}

    gold = json.load(open(GOLD)) if os.path.exists(GOLD) else {}
    gold = {k: (1 if (v.get("stance") if isinstance(v, dict) else v) == "support" else 0)
            for k, v in gold.items()}

    report = {"n_empirical_with_refs": len(emp), "topk": TOPK, "by_party": {}}
    for party in ["dem", "rep"]:
        ids = [c["id"] for c in emp if c["party"] == party]
        f_all = np.array([surrogate[i] for i in ids], float)
        g_ids = [i for i in ids if i in gold]
        y = np.array([gold[i] for i in g_ids], float)
        f_g = np.array([surrogate[i] for i in g_ids], float)
        n, m = len(ids), len(g_ids)
        rep_p = {"n_claims": n, "n_gold": m,
                 "surrogate_support_rate": round(float(f_all.mean()), 3) if n else None}
        if m:
            direct = wilson(int(y.sum()), m)
            rep_p["judge_direct_support_rate"] = direct[0]
            rep_p["judge_direct_wilson95"] = [direct[1], direct[2]]
            theta = float(f_all.mean() + (y - f_g).mean())   # PPI point estimate
            var = f_all.var(ddof=1)/n + (y - f_g).var(ddof=1)/m if n > 1 and m > 1 else (y.var()/max(m,1))
            se = math.sqrt(max(var, 0))
            rep_p["ppi_support_rate"] = round(theta, 3)
            rep_p["ppi_wald95"] = [round(theta - 1.96*se, 3), round(theta + 1.96*se, 3)]
        report["by_party"][party] = rep_p
        print(f"  {party}: n={n} gold={m} "
              f"surrogate={rep_p['surrogate_support_rate']} "
              f"judge_direct={rep_p.get('judge_direct_support_rate')} "
              f"{rep_p.get('judge_direct_wilson95')} ppi={rep_p.get('ppi_support_rate')}")

    json.dump(report, open(OUT, "w"), indent=2)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
