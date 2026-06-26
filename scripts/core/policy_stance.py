#!/usr/bin/env python3
"""
policy_stance.py — run the validated stance judges on the policy (claim, reference) pairs
and estimate party-level support rates. Reuses the exact validators benchmarked in
benchmark_validation.py, so the numbers here inherit those validators' human-anchored
accuracies. Works on either reference set:

  --refs gpt5      outputs/structured_refs/          (original web-LLM retrieval)
  --refs openalex  outputs/structured_refs_openalex/ (reproducible OpenAlex retrieval)

For each validator we report the support rate by party (share of pairs judged 'support')
and, for the NLI surrogate, a PPI estimate anchored on the Claude gold labels if available.
"""
import argparse, csv, json, os, sys
from collections import Counter, defaultdict
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark_validation as bv

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REFS = {"gpt5": "structured_refs", "openalex": "structured_refs_openalex"}
OUT = os.path.join(BASE, "outputs", "stance")


def load_policy_pairs(refs_dir, per_claim=5):
    pairs = []
    for party in ["dem", "rep"]:
        path = os.path.join(BASE, "outputs", refs_dir, f"{party}_claim_references.json")
        if not os.path.exists(path):
            continue
        rows = json.load(open(path)); rows = rows if isinstance(rows, list) else list(rows.values())
        seen = set()
        for e in rows:
            claim = (e.get("claim_text") or "").strip()
            if not claim:
                continue
            for i, r in enumerate((e.get("references") or [])[:per_claim]):
                ab, ti = (r.get("abstract") or "").strip(), (r.get("title") or "").strip()
                if not (ab or ti):
                    continue
                uid = str(r.get("doi") or r.get("openalex_id") or r.get("url") or f"{e.get('press_release')}#{e.get('claim_number')}#{i}")
                key = f"{party}|{e.get('press_release')}|{e.get('claim_number')}|{uid}"
                if key in seen:
                    continue
                seen.add(key)
                pairs.append({"party": party, "uid": key, "claim": claim, "title": ti,
                              "abstract": ab, "gold": ""})
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", default="openalex", choices=list(REFS))
    ap.add_argument("--validators", nargs="+", default=["nli_deberta", "nli_bart"])
    args = ap.parse_args()

    pairs = load_policy_pairs(REFS[args.refs])
    print(f"[policy_stance:{args.refs}] {len(pairs)} pairs "
          f"({dict(Counter(p['party'] for p in pairs))})", flush=True)

    preds = {}
    for v in args.validators:
        print(f"  validator {v} ...", flush=True)
        if v == "nli_deberta":
            preds[v] = bv.run_nli(pairs, bv.NLI_MODELS["nli_deberta"])
        elif v == "nli_bart":
            preds[v] = bv.run_nli(pairs, bv.NLI_MODELS["nli_bart"])
        elif v == "tfidf":
            preds[v] = bv.run_tfidf(pairs)
        elif v.startswith("llm:"):
            preds[v] = bv.run_llm_judge(pairs, v[4:])

    # support rate by party for each validator
    rates = {}
    for v, pr in preds.items():
        by = defaultdict(list)
        for p, s in zip(pairs, pr):
            by[p["party"]].append(1.0 if s == "support" else 0.0)
        rates[v] = {party: round(float(np.mean(vals)), 3) for party, vals in by.items()}
        dist = Counter(pr)
        print(f"  {v}: support-rate dem={rates[v].get('dem')} rep={rates[v].get('rep')}  dist={dict(dist)}")

    os.makedirs(OUT, exist_ok=True)
    json.dump({"refs": args.refs, "n_pairs": len(pairs), "validators": list(preds),
               "support_rate_by_party": rates,
               "by_party_n": dict(Counter(p["party"] for p in pairs))},
              open(os.path.join(OUT, f"policy_stance_{args.refs}.json"), "w"), indent=2)
    with open(os.path.join(OUT, f"policy_pairs_{args.refs}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        names = list(preds)
        w.writerow(["party", "uid"] + names + ["claim", "title"])
        for k, p in enumerate(pairs):
            w.writerow([p["party"], p["uid"]] + [preds[n][k] for n in names]
                       + [p["claim"][:160], p["title"][:120]])
    print(f"[policy_stance:{args.refs}] wrote stance/policy_stance_{args.refs}.json")


if __name__ == "__main__":
    main()
