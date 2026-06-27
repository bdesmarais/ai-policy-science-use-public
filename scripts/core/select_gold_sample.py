#!/usr/bin/env python3
"""
select_gold_sample.py — draw the validated-judge gold sample from the retrieved AI corpus
and dump the top-3 references per sampled claim for stance judging.

Democrats: a reproducible stratified random sample (fixed seed) of empirical claims that
retrieved >=1 reference. Republicans: ALL empirical claims with refs (the set is small).
The judge then labels the best on-topic reference per claim (support/refute/silent),
mirroring the retrieval experiment, and we propagate via PPI over all empirical claims.
"""
import json, os, random, sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAIRS = os.path.join(BASE, "outputs", "ai_corpus", "retrieved_pairs.json")
OUT_DUMP = os.path.join(BASE, "outputs", "ai_corpus", "gold_sample_to_judge.json")
N_DEM = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SEED = 20260627


def main():
    claims = json.load(open(PAIRS))
    emp = [c for c in claims if c["is_empirical"] and c.get("refs")]
    dem = [c for c in emp if c["party"] == "dem"]
    rep = [c for c in emp if c["party"] == "rep"]
    rng = random.Random(SEED)
    dem_sample = rng.sample(dem, min(N_DEM, len(dem)))
    sample = sorted(dem_sample + rep, key=lambda c: c["id"])
    dump = []
    for c in sample:
        dump.append({"id": c["id"], "party": c["party"], "claim": c["claim_text"],
                     "query": c.get("query", ""),
                     "top": [{"t": (r.get("title") or "")[:150], "y": r.get("year"),
                              "abs": (r.get("abstract") or "")[:420]}
                             for r in c["refs"][:3]]})
    json.dump(dump, open(OUT_DUMP, "w"), indent=1)
    print(f"empirical-with-refs: {len(emp)} (dem {len(dem)}, rep {len(rep)})")
    print(f"gold sample: {len(sample)} (dem {len(dem_sample)}, rep {len(rep)}) -> {OUT_DUMP}")


if __name__ == "__main__":
    main()
