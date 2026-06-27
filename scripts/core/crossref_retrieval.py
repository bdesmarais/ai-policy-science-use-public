#!/usr/bin/env python3
"""
crossref_retrieval.py — model-guided retrieval over the free Crossref index (the DOI
registry), used as a backend-agnostic fallback when OpenAlex is rate-limited. Same contract
as openalex_retrieval.retrieve(): given a claim-targeted query, return real, DOI-bearing
references with title + abstract. Crossref is free (polite pool via mailto), and every
record is a registered DOI by construction.
"""
import json, re, time, urllib.parse, urllib.request, html

CROSSREF = "https://api.crossref.org/works"
MAILTO = "acadtasks@agentmail.to"


def _strip_jats(a):
    if not a:
        return ""
    a = re.sub(r"(?is)<[^>]+>", " ", a)      # drop JATS/XML tags
    a = html.unescape(a)
    return re.sub(r"\s+", " ", a).strip()[:3000]


def _get(url, tries=4):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"ai-policy-science-use ({MAILTO})"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and t < tries - 1:
                time.sleep(min(8, 2 * (t + 1)))
                continue
            if t == tries - 1:
                return None
            time.sleep(2 * (t + 1))
        except Exception:
            if t == tries - 1:
                return None
            time.sleep(2 * (t + 1))


def retrieve(query, k=6, from_year=1990):
    """Return up to k real Crossref references (dicts) for a claim-targeted query,
    restricted to journal articles that carry an abstract."""
    q = urllib.parse.quote(query)
    url = (f"{CROSSREF}?query={q}&rows={k}&select=title,abstract,DOI,issued,container-title,type"
           f"&filter=has-abstract:true,type:journal-article,from-pub-date:{from_year}-01-01"
           f"&mailto={MAILTO}")
    data = _get(url)
    out = []
    for w in ((data or {}).get("message", {}) or {}).get("items", []):
        ab = _strip_jats(w.get("abstract"))
        if not ab:
            continue
        title = (w.get("title") or [""])[0]
        year = None
        try:
            year = (w.get("issued", {}).get("date-parts", [[None]])[0][0])
        except Exception:
            pass
        out.append({"title": title, "abstract": ab,
                    "doi": w.get("DOI"), "year": year,
                    "venue": (w.get("container-title") or [None])[0],
                    "oa": None, "openalex_id": None, "cited_by_count": None})
    return out


if __name__ == "__main__":
    import sys
    for c in sys.argv[1:] or ["data center water consumption gallons daily",
                              "AI chatbots impersonate health professionals medical",
                              "algorithmic price fixing consumer prices"]:
        rs = retrieve(c, k=4)
        print(f"\nQUERY: {c}  -> {len(rs)} refs")
        for r in rs:
            print(f"  [{r['year']}] {(r['title'] or '')[:80]} (DOI {r['doi']}) abs={len(r['abstract'])}c")
