#!/usr/bin/env python3
"""
openalex_retrieval.py — reproducible scientific-evidence retrieval from the OpenAlex API.

This replaces the original pipeline's "ask a web-connected proprietary LLM for references"
step, which is (a) not reproducible, (b) closed/paid, and (c) prone to *fabricating*
citations. Instead, for each empirical claim we query OpenAlex (https://openalex.org), a
free, open bibliographic database of ~250M works, and return real, dereferenceable papers
with abstracts, DOIs, venues and open-access status. Every reference is therefore a real
record an auditor can pull up by DOI — eliminating the citation-fabrication failure mode.

No API key is required (OpenAlex is open); we pass a mailto for the polite pool.

Usage (library):
  from openalex_retrieval import retrieve
  refs = retrieve("Aerobic exercise reduces cardiovascular disease risk.", k=5)
"""
import json, re, sys, time, urllib.parse, urllib.request

OPENALEX = "https://api.openalex.org/works"
MAILTO = "acadtasks@agentmail.to"
STOP = set("the a an and or of to in for on with that this these those is are was were be as by at "
           "from it its their our your they we you i he she them than then but not no if can may will "
           "would should could about which who whose into over under more most such also our".split())


def _abstract_from_inverted(inv):
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))[:3000]


def _keywords(claim, n=8):
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", claim.lower()) if w not in STOP]
    seen, out = set(), []
    for w in words:
        if w not in seen:
            seen.add(w); out.append(w)
    return " ".join(out[:n]) or claim[:80]


def _get(url, tries=6):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"ai-policy-science-use ({MAILTO})"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and t < tries - 1:        # rate limited: exponential backoff
                time.sleep(min(60, 5 * (2 ** t)))
                continue
            if t == tries - 1:
                raise
            time.sleep(3 * (t + 1))
        except Exception:
            if t == tries - 1:
                raise
            time.sleep(3 * (t + 1))


def retrieve(claim, k=5, from_year=1990):
    """Return up to k real candidate references (dicts) for a claim, ranked by OpenAlex
    relevance. Uses full-text relevance search restricted to research articles with abstracts."""
    q = urllib.parse.quote(_keywords(claim))
    url = (f"{OPENALEX}?search={q}"
           f"&filter=type:article,has_abstract:true,from_publication_date:{from_year}-01-01"
           f"&per-page={k}&sort=relevance_score:desc&mailto={MAILTO}")
    data = _get(url)
    out = []
    for w in (data or {}).get("results", []):
        abs = _abstract_from_inverted(w.get("abstract_inverted_index"))
        if not abs:
            continue
        loc = (w.get("primary_location") or {}).get("source") or {}
        out.append({
            "title": w.get("title") or "",
            "abstract": abs,
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "year": w.get("publication_year"),
            "venue": loc.get("display_name"),
            "oa": bool((w.get("open_access") or {}).get("is_oa")),
            "openalex_id": w.get("id"),
            "cited_by_count": w.get("cited_by_count"),
        })
    return out


if __name__ == "__main__":
    claims = sys.argv[1:] or [
        "Regular aerobic exercise reduces the risk of cardiovascular disease.",
        "Facial recognition technology has higher error rates for people with darker skin.",
        "Algorithmic decision tools used in hiring can reproduce historical bias.",
    ]
    for c in claims:
        print(f"\nCLAIM: {c}\n  keywords: {_keywords(c)}")
        for r in retrieve(c, k=4):
            print(f"  - [{r['year']}] {r['title'][:90]}  (DOI {r['doi']}, cites={r['cited_by_count']}, OA={r['oa']})")
