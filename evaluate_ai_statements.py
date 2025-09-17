import csv
import json
import sys
import argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import urllib.request
import urllib.parse

"""
Evaluation helper (standalone):

Purpose:
- Reads ai_statements_v3.csv produced by analyze_press_releases_v3.py
- For a selected subset of AI statements (by simple filters), fetches candidate evidence
  metadata from Crossref (for DOI-free sentences) and arXiv (for arXiv-free sentences) based
  on the sentence text and matched AI terms.
- Outputs a JSON with candidate references per statement and a compact CSV.

Notes:
- This does NOT perform verification. It only surfaces likely references to assist manual review.
- Standard library only: uses urllib to call public APIs without extra deps.
- APIs used:
  - Crossref Works: https://api.crossref.org/works?query=...
  - arXiv API: http://export.arxiv.org/api/query?search_query=all:...
"""


WORKSPACE = Path(__file__).parent


@dataclass
class CandidateRef:
    source_api: str  # crossref or arxiv
    title: str
    authors: List[str]
    year: Optional[int]
    doi: Optional[str]
    url: Optional[str]


@dataclass
class StatementEvaluation:
    source: str
    filename: str
    sentence_index: int
    sentence_text: str
    matched_ai_terms: List[str]
    existing_urls: List[str]
    existing_dois: List[str]
    existing_arxiv: List[str]
    candidates: List[CandidateRef]


def read_ai_statements(csv_path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def http_get_json(url: str) -> Dict:
    req = urllib.request.Request(url, headers={"User-Agent": "press-releases-eval/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return {}


def http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "press-releases-eval/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="ignore")


def search_crossref(query: str, rows: int = 5) -> List[CandidateRef]:
    params = urllib.parse.urlencode({"query": query, "rows": rows})
    url = f"https://api.crossref.org/works?{params}"
    j = http_get_json(url)
    items = j.get("message", {}).get("items", [])
    results: List[CandidateRef] = []
    for it in items:
        title_list = it.get("title", [])
        title = title_list[0] if title_list else ""
        authors = [
            " ".join([a.get("given", ""), a.get("family", "")]).strip()
            for a in it.get("author", [])
        ]
        year = None
        if it.get("issued", {}).get("date-parts"):
            try:
                year = int(it["issued"]["date-parts"][0][0])
            except Exception:
                year = None
        doi = it.get("DOI")
        url_item = it.get("URL")
        results.append(CandidateRef(
            source_api="crossref",
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            url=url_item,
        ))
    return results


def parse_arxiv_feed(feed_xml: str) -> List[CandidateRef]:
    # crude parse without external libs
    # Extract titles, authors, links, and published year
    results: List[CandidateRef] = []
    entries = feed_xml.split("<entry>")
    for e in entries[1:]:
        # title
        t0 = e.find("<title>")
        t1 = e.find("</title>")
        title = e[t0 + 7:t1].strip() if t0 != -1 and t1 != -1 else ""
        # authors
        authors: List[str] = []
        idx = 0
        while True:
            a0 = e.find("<name>", idx)
            if a0 == -1:
                break
            a1 = e.find("</name>", a0)
            if a1 == -1:
                break
            authors.append(e[a0 + 6:a1].strip())
            idx = a1 + 7
        # link
        link = None
        l0 = e.find("<link rel=\"alternate\" type=\"text/html\" href=\"")
        if l0 != -1:
            l0 += len("<link rel=\"alternate\" type=\"text/html\" href=\"")
            l1 = e.find("\"", l0)
            if l1 != -1:
                link = e[l0:l1]
        # published year
        y0 = e.find("<published>")
        year = None
        if y0 != -1:
            y1 = e.find("</published>", y0)
            if y1 != -1:
                ts = e[y0 + 11:y1]
                if len(ts) >= 4 and ts[:4].isdigit():
                    year = int(ts[:4])

        results.append(CandidateRef(
            source_api="arxiv",
            title=title,
            authors=authors,
            year=year,
            doi=None,
            url=link,
        ))
    return results


def search_arxiv(query: str, max_results: int = 5) -> List[CandidateRef]:
    q = urllib.parse.quote(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{q}&start=0&max_results={max_results}"
    xml = http_get_text(url)
    return parse_arxiv_feed(xml)


def build_query(sentence: str, terms: List[str]) -> str:
    # Compact query: top few distinctive keywords plus sentence fragment
    core = " ".join(terms[:3]) if terms else "ai"
    snippet = sentence
    if len(snippet) > 200:
        snippet = snippet[:200]
    return f"{core} {snippet}"


def build_key(source: str, filename: str, sentence_index: int) -> Tuple[str, str, int]:
    return (source or "", filename or "", int(sentence_index or 0))


def evaluate(statements_csv: Path, outputs_dir: Path, limit: int = -1, rows_per_source: int = 3, skip_fetch: bool = False, fill_missing: bool = True) -> None:
    rows = read_ai_statements(statements_csv)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Load existing JSON (if present) to merge and ensure full coverage without re-fetching
    existing_map: Dict[Tuple[str, str, int], Dict] = {}
    existing_json_path = outputs_dir / "ai_statement_candidate_evidence.json"
    if existing_json_path.exists():
        try:
            with open(existing_json_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            for e in existing:
                k = build_key(e.get("source", ""), e.get("filename", ""), e.get("sentence_index", 0))
                existing_map[k] = e
        except Exception:
            existing_map = {}

    evals: List[StatementEvaluation] = []
    processed = 0
    for r in rows:
        if limit >= 0 and processed >= limit:
            break
        source = r.get("source", "")
        filename = r.get("filename", "")
        sentence_index = int(r.get("sentence_index", "0") or 0)
        k = build_key(source, filename, sentence_index)

        sentence = r.get("sentence_text", "")
        terms = [t.strip() for t in (r.get("matched_ai_terms", "").split(";") if r.get("matched_ai_terms") else []) if t.strip()]
        existing_urls = [t.strip() for t in (r.get("urls", "").split(";") if r.get("urls") else []) if t.strip()]
        existing_dois = [t.strip() for t in (r.get("dois", "").split(";") if r.get("dois") else []) if t.strip()]
        existing_arxiv = [t.strip() for t in (r.get("arxiv", "").split(";") if r.get("arxiv") else []) if t.strip()]

        # If already present and we are filling missing only, preserve
        if k in existing_map and fill_missing:
            e = existing_map[k]
            # Ensure fields exist (backfill metadata from CSV in case prior run missed them)
            out = StatementEvaluation(
                source=source,
                filename=filename,
                sentence_index=sentence_index,
                sentence_text=sentence or e.get("sentence_text", ""),
                matched_ai_terms=terms or (e.get("matched_ai_terms", []) or []),
                existing_urls=existing_urls or (e.get("existing_urls", []) or []),
                existing_dois=existing_dois or (e.get("existing_dois", []) or []),
                existing_arxiv=existing_arxiv or (e.get("existing_arxiv", []) or []),
                candidates=[CandidateRef(**c) for c in (e.get("candidates", []) or [])],
            )
            evals.append(out)
            processed += 1
            continue

        # Decide whether to fetch
        candidates: List[CandidateRef] = []
        if not skip_fetch:
            query = build_query(sentence, terms)
            # Try Crossref if no DOIs present
            if not existing_dois:
                try:
                    candidates.extend(search_crossref(query, rows=rows_per_source))
                except Exception:
                    pass
            # Try arXiv if no arXiv IDs present
            if not existing_arxiv:
                try:
                    candidates.extend(search_arxiv(query, max_results=rows_per_source))
                except Exception:
                    pass

        ev = StatementEvaluation(
            source=source,
            filename=filename,
            sentence_index=sentence_index,
            sentence_text=sentence,
            matched_ai_terms=terms,
            existing_urls=existing_urls,
            existing_dois=existing_dois,
            existing_arxiv=existing_arxiv,
            candidates=candidates,
        )
        evals.append(ev)
        processed += 1

    # JSON output (full)
    with open(outputs_dir / "ai_statement_candidate_evidence.json", "w", encoding="utf-8") as jf:
        json.dump([
            {
                **{k: v for k, v in asdict(e).items() if k != "candidates"},
                "candidates": [asdict(c) for c in e.candidates],
            }
            for e in evals
        ], jf, ensure_ascii=False, indent=2)

    # Compact CSV
    with open(outputs_dir / "ai_statement_candidate_evidence.csv", "w", encoding="utf-8", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow(["source", "filename", "sentence_index", "num_candidates", "top_candidate_title", "top_candidate_url"])
        for e in evals:
            if e.candidates:
                c0 = e.candidates[0]
                top_title = c0.title or ""
                top_url = c0.url or (f"https://doi.org/{c0.doi}" if c0.doi else "")
            else:
                top_title = ""
                top_url = ""
            writer.writerow([e.source, e.filename, e.sentence_index, len(e.candidates), top_title, top_url])

    print(f"Wrote evaluation candidates to: {outputs_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate AI statements by fetching candidate references or filling from existing outputs.")
    parser.add_argument("--limit", type=int, default=-1, help="Max number of statements to process (-1 for all)")
    parser.add_argument("--rows-per-source", type=int, default=3, help="Max candidates to fetch per source (Crossref/arXiv)")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not call external APIs; keep candidates empty")
    parser.add_argument("--fill-missing", action="store_true", help="Merge existing JSON and ensure coverage for all statements")
    args = parser.parse_args()

    inputs_csv = WORKSPACE / "outputs" / "v3" / "ai_statements_v3.csv"
    outputs_dir = WORKSPACE / "outputs" / "v3_eval"
    if not inputs_csv.exists():
        print("ai_statements_v3.csv not found. Run analyze_press_releases_v3.py first.", file=sys.stderr)
        sys.exit(2)

    evaluate(
        inputs_csv,
        outputs_dir,
        limit=args.limit,
        rows_per_source=args.rows_per_source,
        skip_fetch=args.skip_fetch,
        fill_missing=args.fill_missing or True,
    )


if __name__ == "__main__":
    main()


