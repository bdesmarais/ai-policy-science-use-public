#!/usr/bin/env python3
"""
integrate_fresh_claims.py — merge freshly-extracted AI claims (last 12 months) into the
corpus, with a distinct id namespace so they never collide with the historical claims.

Input:  data/fresh_ai_claims.json  — list of
  {party, date, source_slug, claim_text, is_empirical, query}
Effects:
  - appends to outputs/ai_corpus/claims_indexed.json  (ids: ndem:0.., nrep:0..)
  - appends to data/ai_claim_queries.json             (same ids, with query/abstain)
Idempotent: re-running replaces the n* entries rather than duplicating.
"""
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRESH = os.path.join(BASE, "data", "fresh_ai_claims.json")
CLAIMS = os.path.join(BASE, "outputs", "ai_corpus", "claims_indexed.json")
QUERIES = os.path.join(BASE, "data", "ai_claim_queries.json")


def main():
    fresh = json.load(open(FRESH))
    claims = [c for c in json.load(open(CLAIMS)) if not c["id"].startswith("n")]
    qspec = json.load(open(QUERIES))
    queries = [q for q in qspec["queries"] if not q["id"].startswith("n")]

    counts = {"dem": 0, "rep": 0}
    for f in fresh:
        p = f["party"]
        cid = f"n{p}:{counts[p]}"
        counts[p] += 1
        claims.append({"id": cid, "party": p, "press_release": f.get("source_slug", ""),
                       "claim_number": "", "claim_text": f["claim_text"],
                       "date": f.get("date"), "fresh": True})
        queries.append({"id": cid, "is_empirical": bool(f.get("is_empirical")),
                        "query": f.get("query", "")})

    json.dump(claims, open(CLAIMS, "w"), indent=1)
    qspec["queries"] = queries
    qspec.setdefault("_provenance", {})["n_fresh"] = len(fresh)
    json.dump(qspec, open(QUERIES, "w"), indent=1)
    print(f"integrated {len(fresh)} fresh claims (dem {counts['dem']}, rep {counts['rep']})")
    print(f"corpus now: {len(claims)} claims | queries: {len(queries)}")
    emp = sum(1 for f in fresh if f.get("is_empirical"))
    print(f"fresh empirical: {emp}/{len(fresh)}")


if __name__ == "__main__":
    main()
