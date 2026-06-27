#!/usr/bin/env python3
"""
claude_retrieval.py — Claude-guided reproducible retrieval over the free OpenAlex index.

Motivation. The project's headline corroboration rates were produced by a *proprietary*
generative-retrieval step (GPT-5 with web search): not reproducible, paid, and only
27-35% of its references carried a DOI. The reproducible alternative we had — naive
keyword search over OpenAlex — returns real DOI-bearing papers but is not claim-targeted:
it returns broad, topically-adjacent works for *every* claim (it cannot abstain), so nearly
all (claim, reference) pairs are judged 'silent'.

This script closes that gap without a second paid service. A single frontier model
(Claude Opus 4.8, already used as the stance judge) reads each claim and either
  (a) emits a concise, claim-targeted query for the OpenAlex relevance search, or
  (b) abstains, when the claim is legal/procedural/political/value-laden with no
      scientific literature to retrieve.
Those decisions are committed as static data (data/claude_retrieval_queries.json),
exactly as the judge labels are. The references themselves still come from OpenAlex, so
every one is a real, dereferenceable DOI record — no fabrication, 100% verifiable.

We run two arms on the SAME claims and compare:
  - NAIVE  : openalex_retrieval._keywords(claim)   -> OpenAlex   (runs on all claims)
  - CLAUDE : Claude's targeted query               -> OpenAlex   (abstains where appropriate)

Output: outputs/stance/claude_retrieval_pairs.json  (candidate pairs for both arms)
"""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import openalex_retrieval as oa

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUERIES = os.path.join(BASE, "data", "claude_retrieval_queries.json")
OUT = os.path.join(BASE, "outputs", "stance")
SLEEP = 1.5   # polite pause between OpenAlex calls (the polite pool rate-limits under load)


def retrieve_with_query(query, k=8, from_year=1990):
    """OpenAlex relevance search with an explicit (Claude-authored) query string."""
    q = urllib.parse.quote(query)
    url = (f"{oa.OPENALEX}?search={q}"
           f"&filter=type:article,has_abstract:true,from_publication_date:{from_year}-01-01"
           f"&per-page={k}&sort=relevance_score:desc&mailto={oa.MAILTO}")
    data = oa._get(url)
    out = []
    for w in (data or {}).get("results", []):
        ab = oa._abstract_from_inverted(w.get("abstract_inverted_index"))
        if not ab:
            continue
        loc = (w.get("primary_location") or {}).get("source") or {}
        out.append({
            "title": w.get("title") or "", "abstract": ab,
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "year": w.get("publication_year"), "venue": loc.get("display_name"),
            "oa": bool((w.get("open_access") or {}).get("is_oa")),
            "openalex_id": w.get("id"), "cited_by_count": w.get("cited_by_count"),
        })
    return out


def main():
    spec = json.load(open(QUERIES))
    items = spec["queries"]
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    results = []
    for i, it in enumerate(items):
        claim = it["claim_text"]
        rec = {"party": it["party"], "press_release": it["press_release"],
               "claim_number": it["claim_number"], "claim_text": claim,
               "is_empirical": it["is_empirical"], "claude_query": it.get("query", ""),
               "naive_keywords": oa._keywords(claim)}
        # NAIVE arm: always retrieves (keyword search cannot abstain)
        try:
            rec["naive_refs"] = oa.retrieve(claim, k=k)
        except Exception as e:
            rec["naive_refs"], rec["naive_error"] = [], str(e)
        time.sleep(SLEEP)
        # CLAUDE arm: retrieves only when Claude emitted a query; otherwise abstains
        if it["is_empirical"] and it.get("query"):
            try:
                rec["claude_refs"] = retrieve_with_query(it["query"], k=k)
            except Exception as e:
                rec["claude_refs"], rec["claude_error"] = [], str(e)
            time.sleep(SLEEP)
        else:
            rec["claude_refs"] = []   # principled abstention
            rec["claude_abstained"] = True
        nn, nc = len(rec["naive_refs"]), len(rec["claude_refs"])
        print(f"[{i:02d}] {it['party']} emp={int(it['is_empirical'])} "
              f"naive={nn} claude={nc}  | {claim[:60]}", flush=True)
        results.append(rec)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "claude_retrieval_pairs.json")
    json.dump(results, open(path, "w"), indent=2)
    print(f"\nwrote {path}  ({len(results)} claims)")


if __name__ == "__main__":
    main()
