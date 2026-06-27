#!/usr/bin/env python3
"""
ai_corpus_retrieval.py — run model-guided OpenAlex retrieval over the FULL AI-claim corpus.

Reads:
  outputs/ai_corpus/claims_indexed.json     canonical id->claim list
  data/ai_claim_queries.json                Claude query/abstain decisions, keyed by claim id
Writes:
  outputs/ai_corpus/retrieved_pairs.json    per-claim OpenAlex hits (empirical claims only)

The query/abstain decisions are Claude's (committed as static data); OpenAlex returns the
references, so every reference is a real, dereferenceable DOI record. Resumable: existing
results are reused, so the script can be re-run to fill in claims added to the queries file.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Backend-agnostic retrieval: OpenAlex is preferred, but we fall back to Crossref (the free
# DOI registry) when OpenAlex rate-limits. The model-guided query approach is index-portable;
# both return real, DOI-bearing references. Backend chosen by AI_RETRIEVAL_BACKEND env var.
BACKEND = os.environ.get("AI_RETRIEVAL_BACKEND", "crossref")
if BACKEND == "openalex":
    import openalex_retrieval as _idx
else:
    import crossref_retrieval as _idx

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLAIMS = os.path.join(BASE, "outputs", "ai_corpus", "claims_indexed.json")
QUERIES = os.path.join(BASE, "data", "ai_claim_queries.json")
OUT = os.path.join(BASE, "outputs", "ai_corpus", "retrieved_pairs.json")
SLEEP = 0.5
K = 6


def retrieve_with_query(query, k=K, from_year=1990):
    refs = _idx.retrieve(query, k=k, from_year=from_year) or []
    for r in refs:
        r.setdefault("backend", BACKEND)
    return refs


def main():
    claims = {c["id"]: c for c in json.load(open(CLAIMS))}
    qspec = json.load(open(QUERIES))
    queries = qspec["queries"] if isinstance(qspec, dict) else qspec
    qmap = {q["id"]: q for q in queries}
    done = {}
    if os.path.exists(OUT):
        done = {r["id"]: r for r in json.load(open(OUT))}

    results = list(done.values())
    n_emp = n_new = 0
    # process FRESH (n*) claims first so the latest-12-month results land quickly,
    # then the historical backlog; both are cached so this is restart-safe.
    order = sorted(qmap.keys(), key=lambda k: (not k.startswith("n"), k))
    for cid in order:
        q = qmap[cid]
        if cid in done:
            continue
        c = claims.get(cid)
        if not c:
            continue
        rec = {"id": cid, "party": c["party"], "press_release": c["press_release"],
               "claim_number": c["claim_number"], "claim_text": c["claim_text"],
               "is_empirical": bool(q.get("is_empirical")), "query": q.get("query", "")}
        if rec["is_empirical"] and rec["query"]:
            n_emp += 1
            try:
                rec["refs"] = retrieve_with_query(rec["query"])
            except Exception as e:
                rec["refs"], rec["error"] = [], str(e)
            time.sleep(SLEEP)
        else:
            rec["refs"] = []
            rec["abstained"] = True
        results.append(rec)
        n_new += 1
        if n_new % 25 == 0:
            json.dump(results, open(OUT, "w"))   # checkpoint
            print(f"  ...{n_new} new ({n_emp} empirical retrieved)", flush=True)

    json.dump(results, open(OUT, "w"), indent=1)
    emp = sum(1 for r in results if r["is_empirical"])
    withref = sum(1 for r in results if r.get("refs"))
    print(f"done: {len(results)} claims | empirical {emp} | with >=1 ref {withref} -> {OUT}")


if __name__ == "__main__":
    main()
