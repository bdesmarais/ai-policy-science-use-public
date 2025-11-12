import csv
import json
import sys
import argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict

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
    parser = argparse.ArgumentParser(description="Summarize AI statements into analysis-ready tables and optional figures (no time series)")
    parser.add_argument("--outputs-v3-dir", default=str(WORKSPACE / "outputs" / "v3"), help="Directory containing v3 CSV outputs")
    parser.add_argument("--viz-data-dir", default=str(WORKSPACE / "outputs" / "viz_data" / "statements"), help="Directory to write analysis-ready CSVs")
    parser.add_argument("--figures-dir", default=str(WORKSPACE / "outputs" / "figures" / "statements"), help="Directory to write quick figures")
    parser.add_argument("--top-terms", type=int, default=25, help="Top-N AI terms per party")
    parser.add_argument("--no-figures", action="store_true", help="Do not generate figures")
    parser.add_argument("--export-markdown", action="store_true", help="Also export Markdown tables alongside CSVs")
    args = parser.parse_args()

    outputs_v3_dir = Path(args.outputs_v3_dir)
    viz_data_dir = Path(args.viz_data_dir)
    figures_dir = Path(args.figures_dir)
    viz_data_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    out_paths = build_statements_tables(outputs_v3_dir, viz_data_dir, top_terms_n=max(1, args.top_terms), export_markdown=bool(args.export_markdown))
    print({k: str(v) for k, v in out_paths.items()})

    if not args.no_figures:
        build_statements_figures(viz_data_dir, figures_dir)
        print(f"Figures written to: {figures_dir}")


def _read_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def _split_semicolon(s: str) -> List[str]:
    if not s:
        return []
    return [t.strip() for t in s.split(";") if t.strip()]


def _write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _write_markdown_table(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    lines: List[str] = []
    header = "| " + " | ".join(fieldnames) + " |"
    sep = "| " + " | ".join(["---"] * len(fieldnames)) + " |"
    lines.append(header)
    lines.append(sep)
    for r in rows:
        values = [str(r.get(k, "")) for k in fieldnames]
        lines.append("| " + " | ".join(values) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_statements_tables(outputs_v3_dir: Path, viz_data_dir: Path, top_terms_n: int, export_markdown: bool) -> Dict[str, Path]:
    statements_csv = outputs_v3_dir / "ai_statements_v3.csv"
    docs_csv = outputs_v3_dir / "ai_documents_v3.csv"
    if not statements_csv.exists() or not docs_csv.exists():
        print("Required v3 outputs not found. Run analyze_press_releases_v3.py first.", file=sys.stderr)
        sys.exit(2)

    statements = _read_csv(statements_csv)
    docs = _read_csv(docs_csv)

    # statements_by_party
    by_party_docs: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for d in docs:
        by_party_docs[d.get("source", "")] .append(d)

    by_party_statements: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for s in statements:
        by_party_statements[s.get("source", "")] .append(s)

    statements_by_party_rows: List[Dict[str, object]] = []
    for party in sorted(set(list(by_party_docs.keys()) + list(by_party_statements.keys()))):
        party_docs = by_party_docs.get(party, [])
        party_statements = by_party_statements.get(party, [])
        documents = len(party_docs)
        docs_with_ai = sum(1 for d in party_docs if str(d.get("ai_statement_count", "0")).strip() not in ("0", "False", "false"))
        ai_statements = sum(int(d.get("ai_statement_count", "0") or 0) for d in party_docs)
        documents_with_ai_ratio = round(docs_with_ai / max(1, documents), 4)
        avg_per_doc = round(ai_statements / max(1, documents), 3)
        avg_per_ai_doc = round(ai_statements / max(1, docs_with_ai), 3) if docs_with_ai else 0.0
        statements_by_party_rows.append({
            "source": party,
            "documents": documents,
            "documents_with_ai": docs_with_ai,
            "documents_with_ai_ratio": documents_with_ai_ratio,
            "ai_statements": ai_statements,
            "avg_ai_statements_per_doc": avg_per_doc,
            "avg_ai_statements_per_ai_doc": avg_per_ai_doc,
        })

    out_paths: Dict[str, Path] = {}
    out1 = viz_data_dir / "statements_by_party.csv"
    _write_csv(out1, statements_by_party_rows, [
        "source","documents","documents_with_ai","documents_with_ai_ratio","ai_statements","avg_ai_statements_per_doc","avg_ai_statements_per_ai_doc"
    ])
    out_paths["statements_by_party"] = out1
    if export_markdown:
        _write_markdown_table(viz_data_dir / "statements_by_party.md", statements_by_party_rows, [
            "source","documents","documents_with_ai","documents_with_ai_ratio","ai_statements","avg_ai_statements_per_doc","avg_ai_statements_per_ai_doc"
        ])

    # top_terms_by_party
    term_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for s in statements:
        party = s.get("source", "")
        terms = _split_semicolon(s.get("matched_ai_terms", ""))
        for t in terms:
            term_counts[(party, t)] += 1

    top_terms_rows: List[Dict[str, object]] = []
    parties = sorted(set(p for p, _ in term_counts.keys()))
    for party in parties:
        party_terms = [(term, cnt) for (p, term), cnt in term_counts.items() if p == party]
        party_terms.sort(key=lambda x: x[1], reverse=True)
        for rank, (term, cnt) in enumerate(party_terms[: max(1, top_terms_n)], start=1):
            top_terms_rows.append({"source": party, "term": term, "count": cnt, "rank": rank})

    out2 = viz_data_dir / "top_terms_by_party.csv"
    _write_csv(out2, top_terms_rows, ["source","term","count","rank"])
    out_paths["top_terms_by_party"] = out2
    if export_markdown:
        _write_markdown_table(viz_data_dir / "top_terms_by_party.md", top_terms_rows, ["source","term","count","rank"])

    # statements_per_doc
    per_doc_rows: List[Dict[str, object]] = []
    for d in docs:
        per_doc_rows.append({
            "source": d.get("source", ""),
            "filename": d.get("filename", ""),
            "ai_statement_count": int(d.get("ai_statement_count", "0") or 0),
        })
    out3 = viz_data_dir / "statements_per_doc.csv"
    _write_csv(out3, per_doc_rows, ["source","filename","ai_statement_count"])
    out_paths["statements_per_doc"] = out3

    # citations_in_text
    cite_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total_urls": 0, "total_dois": 0, "total_arxiv": 0, "num_statements": 0})
    for s in statements:
        party = s.get("source", "")
        urls = _split_semicolon(s.get("urls", ""))
        dois = _split_semicolon(s.get("dois", ""))
        arx = _split_semicolon(s.get("arxiv", ""))
        cite_totals[party]["total_urls"] += len(urls)
        cite_totals[party]["total_dois"] += len(dois)
        cite_totals[party]["total_arxiv"] += len(arx)
        cite_totals[party]["num_statements"] += 1

    citations_rows: List[Dict[str, object]] = []
    for party, agg in sorted(cite_totals.items()):
        n = max(1, agg["num_statements"])
        citations_rows.append({
            "source": party,
            "total_urls": agg["total_urls"],
            "total_dois": agg["total_dois"],
            "total_arxiv": agg["total_arxiv"],
            "avg_urls_per_statement": round(agg["total_urls"] / n, 3),
            "avg_dois_per_statement": round(agg["total_dois"] / n, 3),
            "avg_arxiv_per_statement": round(agg["total_arxiv"] / n, 3),
        })

    out4 = viz_data_dir / "citations_in_text.csv"
    _write_csv(out4, citations_rows, [
        "source","total_urls","total_dois","total_arxiv","avg_urls_per_statement","avg_dois_per_statement","avg_arxiv_per_statement"
    ])
    out_paths["citations_in_text"] = out4
    if export_markdown:
        _write_markdown_table(viz_data_dir / "citations_in_text.md", citations_rows, [
            "source","total_urls","total_dois","total_arxiv","avg_urls_per_statement","avg_dois_per_statement","avg_arxiv_per_statement"
        ])

    return out_paths


def build_statements_figures(viz_data_dir: Path, figures_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not available; skipping figure generation.")
        return

    sbp = _read_csv(viz_data_dir / "statements_by_party.csv")
    top_terms = _read_csv(viz_data_dir / "top_terms_by_party.csv")
    per_doc = _read_csv(viz_data_dir / "statements_per_doc.csv")

    figures_dir.mkdir(parents=True, exist_ok=True)

    parties = [r["source"] for r in sbp]
    docs_with_ai = [int(r["documents_with_ai"]) for r in sbp]
    import matplotlib.pyplot as plt  # safe after try above
    plt.figure(figsize=(6, 4))
    plt.bar(parties, docs_with_ai, color=["#2E86AB", "#C14953"][: len(parties)])
    plt.title("Documents with AI by party")
    plt.ylabel("Count")
    for i, v in enumerate(docs_with_ai):
        plt.text(i, v, str(v), ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(figures_dir / "docs_with_ai_by_party.png", dpi=150)
    plt.close()

    ai_counts = [int(r["ai_statements"]) for r in sbp]
    plt.figure(figsize=(6, 4))
    plt.bar(parties, ai_counts, color=["#2E86AB", "#C14953"][: len(parties)])
    plt.title("AI statements by party")
    plt.ylabel("Count")
    for i, v in enumerate(ai_counts):
        plt.text(i, v, str(v), ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(figures_dir / "ai_statements_by_party.png", dpi=150)
    plt.close()

    top10 = [r for r in top_terms if int(r.get("rank", "0") or 0) <= 10]
    parties_tt = sorted(set(r["source"] for r in top10))
    cols = len(parties_tt)
    fig, axes = plt.subplots(1, cols, figsize=(6 * cols, 5), squeeze=False)
    for idx, party in enumerate(parties_tt):
        ax = axes[0][idx]
        rows = [r for r in top10 if r["source"] == party]
        terms = [r["term"] for r in rows][::-1]
        counts = [int(r["count"]) for r in rows][::-1]
        ax.barh(terms, counts, color="#6C8EBF")
        ax.set_title(f"Top terms: {party}")
    plt.tight_layout()
    plt.savefig(figures_dir / "top_terms_by_party.png", dpi=150)
    plt.close()

    per_party_counts: Dict[str, List[int]] = defaultdict(list)
    for r in per_doc:
        per_party_counts[r["source"]].append(int(r["ai_statement_count"]))
    party_order = sorted(per_party_counts.keys())
    data = [per_party_counts[p] for p in party_order]
    plt.figure(figsize=(7, 5))
    plt.boxplot(data, labels=party_order, patch_artist=True)
    plt.title("AI statements per document")
    plt.ylabel("Statements per document")
    plt.tight_layout()
    plt.savefig(figures_dir / "statements_per_doc_distribution.png", dpi=150)
    plt.close()


if __name__ == "__main__":
    main()


