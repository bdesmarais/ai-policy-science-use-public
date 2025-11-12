import csv
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


"""
Press release analyzer (v3)

What is new in v3:
- Focuses on current data already in data/press_releases/Democratic and .../Republican (no zip extraction).
- Redefines "claims": In v3, "claims" are simply any statements that mention AI or AI-related keywords.
  We call these AI "statements" to avoid confusion and do not perform claim verification here.
- Produces exploratory data analysis (EDA) for AI mentions across both sources.
- Copies any press release containing AI statements into data/Dem_AI or data/Rep_AI for downstream work.
- Exports ai_statements_v3.csv (one row per AI statement) and multiple EDA CSVs/Markdown.

Standard library only. Optional charts if matplotlib is available.
"""


WORKSPACE = Path(__file__).parent


# Core keyword definitions (aligned with v2 with a few modern terms)
AI_KEYWORDS = [
    "artificial intelligence",
    "ai",
    "machine learning",
    "ml",
    "deep learning",
    "neural network",
    "neural networks",
    "algorithm",
    "algorithms",
    "automated decision",
    "automation",
    "predictive model",
    "predictive modeling",
    # Modern terms
    "large language model",
    "large-language model",
    "llm",
    "foundation model",
    "generative ai",
    "genai",
    "chatbot",
    "chatgpt",
    "gpt-",  # handle GPT-4/3.5 etc
    "openai",
    "anthropic",
    "google deepmind",
    # Subfields & applications
    "computer vision",
    "natural language processing",
    "nlp",
    "speech recognition",
    "facial recognition",
    "recommendation system",
    "recommender system",
    "predictive policing",
    # Governance and risk terms often tied to AI
    "algorithmic transparency",
    "algorithmic accountability",
    "bias",
    "fairness",
    "explainability",
    "xai",
    "risk assessment",
]


# Reference regexes (kept to help extract contextual info, although we don't score verifiability in v3)
URL_REGEX = re.compile(r"https?://[^\s)\]}]+", re.IGNORECASE)
DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ARXIV_REGEX = re.compile(r"arXiv:\d{4}\.\d{4,5}", re.IGNORECASE)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"[\t\x0b\x0c\r]+", " ", text)


def normalize_ai_variants(text: str) -> str:
    # Normalize A.I. -> AI, M.L. -> ML, L.L.M. -> LLM
    text = re.sub(r"\bA\.\s?I\.\b", "AI", text)
    text = re.sub(r"\bM\.\s?L\.\b", "ML", text)
    text = re.sub(r"\bL\.\s?L\.\s?M\.\b", "LLM", text)
    return text


def split_sentences(text: str) -> List[str]:
    # Simple sentence splitter that respects punctuation and bullets
    text = text.replace("\u2022", "\n").replace("\u2023", "\n").replace("\u25E6", "\n")
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    sentences = [s.strip() for s in chunks if s and s.strip()]
    return sentences


def compile_term_patterns(terms: Iterable[str]) -> Dict[str, re.Pattern]:
    patterns: Dict[str, re.Pattern] = {}
    for term in terms:
        t = term.strip()
        if not t:
            continue
        if t == "ai":
            pat = r"\bai\b|\bA\.I\.\b"
        elif t == "ml":
            pat = r"\bml\b|\bM\.L\.\b"
        elif t == "llm":
            pat = r"\bllms?\b|\bL\.L\.M\.\b"
        elif t == "gpt-":
            pat = r"\bgpt(?:-\d+(?:\.\d+)?)?\b"
        else:
            escaped = re.escape(t)
            if " " in t:
                pat = r"\b" + escaped.replace("\\ ", "\\s+") + r"\b"
            else:
                pat = r"\b" + escaped + r"\b"
        patterns[t] = re.compile(pat, re.IGNORECASE)
    return patterns


AI_PATTERNS = compile_term_patterns(AI_KEYWORDS)


def find_term_matches(text: str, patterns: Dict[str, re.Pattern]) -> List[str]:
    matches: List[str] = []
    for term, pat in patterns.items():
        if pat.search(text):
            matches.append(term)
    return matches


def guess_date(text: str, fallback: Optional[str] = None) -> Optional[str]:
    patterns = [
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0)
    return fallback


@dataclass
class AIStatement:
    source: str  # Democratic Assembly or Republican Assembly
    filename: str
    document_date: Optional[str]
    sentence_index: int
    sentence_text: str
    matched_ai_terms: List[str]
    urls: List[str]
    dois: List[str]
    arxiv: List[str]


@dataclass
class DocumentAIResult:
    source: str
    filename: str
    document_date: Optional[str]
    num_sentences: int
    ai_statement_count: int
    matched_ai_terms: List[str]
    unique_urls: List[str]
    unique_dois: List[str]
    unique_arxiv: List[str]


def read_text_with_fallback(binary: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            return binary.decode(enc)
        except UnicodeDecodeError:
            continue
    return binary.decode("utf-8", errors="ignore")


def analyze_directory(root_dir: Path, source: str) -> Tuple[List[AIStatement], List[DocumentAIResult]]:
    statements: List[AIStatement] = []
    doc_results: List[DocumentAIResult] = []
    for path in sorted(root_dir.rglob("*.txt")):
        try:
            with open(path, "rb") as f:
                text = read_text_with_fallback(f.read())
        except Exception as e:
            print(f"Failed to read {path}: {e}", file=sys.stderr)
            continue

        text = normalize_ai_variants(text)
        cleaned = normalize_whitespace(text)
        sentences = split_sentences(cleaned)
        doc_date = guess_date(text)

        doc_ai_terms: Counter = Counter()
        doc_urls: List[str] = []
        doc_dois: List[str] = []
        doc_arxiv: List[str] = []
        ai_statement_count = 0

        for idx, sentence in enumerate(sentences):
            matched_ai = find_term_matches(sentence, AI_PATTERNS)
            if not matched_ai:
                continue
            urls = URL_REGEX.findall(sentence)
            dois = DOI_REGEX.findall(sentence)
            arxiv = ARXIV_REGEX.findall(sentence)

            ai_statement = AIStatement(
                source=source,
                filename=path.name,
                document_date=doc_date,
                sentence_index=idx,
                sentence_text=sentence,
                matched_ai_terms=sorted(set(matched_ai)),
                urls=urls,
                dois=dois,
                arxiv=arxiv,
            )
            statements.append(ai_statement)

            ai_statement_count += 1
            doc_ai_terms.update(matched_ai)
            doc_urls.extend(urls)
            doc_dois.extend(dois)
            doc_arxiv.extend(arxiv)

        doc_results.append(
            DocumentAIResult(
                source=source,
                filename=path.name,
                document_date=doc_date,
                num_sentences=len(sentences),
                ai_statement_count=ai_statement_count,
                matched_ai_terms=sorted(set(doc_ai_terms.elements())),
                unique_urls=sorted(set(doc_urls)),
                unique_dois=sorted(set(doc_dois)),
                unique_arxiv=sorted(set(doc_arxiv)),
            )
        )

    return statements, doc_results


def write_v3_outputs(statements: List[AIStatement], doc_results: List[DocumentAIResult], outputs_dir: Path) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = outputs_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # Statements CSV
    statements_csv = outputs_dir / "ai_statements_v3.csv"
    with open(statements_csv, "w", encoding="utf-8", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow([
            "source",
            "filename",
            "document_date",
            "sentence_index",
            "matched_ai_terms",
            "urls",
            "dois",
            "arxiv",
            "sentence_text",
        ])
        for s in statements:
            writer.writerow([
                s.source,
                s.filename,
                s.document_date or "",
                s.sentence_index,
                "; ".join(s.matched_ai_terms),
                "; ".join(s.urls),
                "; ".join(s.dois),
                "; ".join(s.arxiv),
                s.sentence_text,
            ])

    # Per-document table
    docs_csv = outputs_dir / "ai_documents_v3.csv"
    with open(docs_csv, "w", encoding="utf-8", newline="") as df:
        writer = csv.writer(df)
        writer.writerow([
            "source",
            "filename",
            "document_date",
            "num_sentences",
            "ai_statement_count",
            "matched_ai_terms",
            "unique_urls_count",
            "unique_dois_count",
            "unique_arxiv_count",
            "has_ai",
        ])
        for d in doc_results:
            writer.writerow([
                d.source,
                d.filename,
                d.document_date or "",
                d.num_sentences,
                d.ai_statement_count,
                "; ".join(sorted(set(d.matched_ai_terms))),
                len(d.unique_urls),
                len(d.unique_dois),
                len(d.unique_arxiv),
                bool(d.ai_statement_count > 0),
            ])

    # Party-level EDA summary
    by_source: Dict[str, List[DocumentAIResult]] = defaultdict(list)
    for d in doc_results:
        by_source[d.source].append(d)

    eda_rows: List[Dict[str, object]] = []
    for source, docs in by_source.items():
        total_docs = len(docs)
        docs_with_ai = sum(1 for x in docs if x.ai_statement_count > 0)
        ai_statements_total = sum(x.ai_statement_count for x in docs)
        eda_rows.append({
            "source": source,
            "documents": total_docs,
            "documents_with_ai": docs_with_ai,
            "documents_with_ai_ratio": round(docs_with_ai / max(1, total_docs), 4),
            "ai_statements": ai_statements_total,
            "avg_ai_statements_per_doc": round(ai_statements_total / max(1, total_docs), 3),
            "avg_ai_statements_per_ai_doc": round(ai_statements_total / max(1, docs_with_ai), 3) if docs_with_ai else 0.0,
        })

    eda_csv = outputs_dir / "ai_eda_summary_v3.csv"
    with open(eda_csv, "w", encoding="utf-8", newline="") as ef:
        writer = csv.DictWriter(ef, fieldnames=list(eda_rows[0].keys()) if eda_rows else ["source","documents","documents_with_ai","documents_with_ai_ratio","ai_statements","avg_ai_statements_per_doc","avg_ai_statements_per_ai_doc"])
        writer.writeheader()
        for row in eda_rows:
            writer.writerow(row)

    # Top AI terms per source
    top_terms_csv = outputs_dir / "ai_top_terms_v3.csv"
    with open(top_terms_csv, "w", encoding="utf-8", newline="") as tf:
        writer = csv.writer(tf)
        writer.writerow(["source", "term", "count"])
        for source, docs in by_source.items():
            counter: Counter = Counter()
            for d in docs:
                counter.update(d.matched_ai_terms)
            for term, count in counter.most_common(25):
                writer.writerow([source, term, count])

    # Time series by month if dates available
    ts_counter: Dict[Tuple[str, str], int] = defaultdict(int)  # (source, YYYY-MM) -> count of AI statements
    for s in statements:
        if not s.document_date:
            continue
        # Normalize to YYYY-MM if possible
        dt_key = s.document_date
        try:
            if re.match(r"\d{4}-\d{2}-\d{2}", dt_key):
                dt = datetime.strptime(dt_key, "%Y-%m-%d")
            elif re.match(r"\d{1,2}/\d{1,2}/\d{2,4}", dt_key):
                parts = dt_key.split("/")
                m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100:
                    y += 2000 if y < 50 else 1900
                dt = datetime(y, m, d)
            else:
                dt = datetime.strptime(dt_key, "%B %d, %Y")
            ym = f"{dt.year:04d}-{dt.month:02d}"
        except Exception:
            # fallback: try to find a YYYY in the string
            m = re.search(r"(20\d{2}|19\d{2})", dt_key)
            ym = m.group(1) + "-01" if m else "unknown"
        ts_counter[(s.source, ym)] += 1

    ts_csv = outputs_dir / "ai_time_series_v3.csv"
    with open(ts_csv, "w", encoding="utf-8", newline="") as tf:
        writer = csv.writer(tf)
        writer.writerow(["source", "year_month", "ai_statements"])
        for (source, ym), count in sorted(ts_counter.items()):
            writer.writerow([source, ym, count])

    # Markdown summary
    md_path = outputs_dir / "ai_eda_summary_v3.md"
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write("## AI Mentions EDA (v3)\n\n")
        mf.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
        total_statements = len(statements)
        total_docs = len(doc_results)
        docs_with_ai = sum(1 for d in doc_results if d.ai_statement_count > 0)
        mf.write(f"- Total documents: {total_docs}\n")
        mf.write(f"- Documents with AI statements: {docs_with_ai}\n")
        mf.write(f"- Total AI statements (sentences): {total_statements}\n\n")
        for row in eda_rows:
            mf.write(f"### {row['source']}\n\n")
            mf.write(f"- Documents: {row['documents']}\n")
            mf.write(f"- Documents with AI: {row['documents_with_ai']} ({row['documents_with_ai_ratio']})\n")
            mf.write(f"- AI statements: {row['ai_statements']}\n")
            mf.write(f"- Avg AI statements/doc: {row['avg_ai_statements_per_doc']}\n")
            mf.write(f"- Avg AI statements/AI doc: {row['avg_ai_statements_per_ai_doc']}\n\n")

    # Optional visualizations using matplotlib (if available)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sources = [row["source"] for row in eda_rows]
        doc_counts = [row["documents_with_ai"] for row in eda_rows]
        stmt_counts = [row["ai_statements"] for row in eda_rows]

        def save_bar(values: List[int], title: str, filename: str) -> None:
            plt.figure(figsize=(6, 4))
            plt.bar(sources, values, color=["#2E86AB", "#C14953"][: len(sources)])
            plt.title(title)
            plt.ylabel("Count")
            for i, v in enumerate(values):
                plt.text(i, v, str(v), ha="center", va="bottom")
            plt.tight_layout()
            plt.savefig(figures_dir / filename, dpi=150)
            plt.close()

        save_bar(doc_counts, "Documents with AI by source", "docs_with_ai_by_source.png")
        save_bar(stmt_counts, "AI statements by source", "ai_statements_by_source.png")

    except Exception:
        pass


def copy_ai_documents(doc_results: List[DocumentAIResult], source_dirs: Dict[str, Path], data_dir: Path) -> Tuple[int, int]:
    """Copy full press release files that contain AI statements into data/Dem_AI and data/Rep_AI.

    Returns (num_dem_copied, num_rep_copied).
    """
    dem_ai_dir = data_dir / "Dem_AI"
    rep_ai_dir = data_dir / "Rep_AI"
    dem_ai_dir.mkdir(parents=True, exist_ok=True)
    rep_ai_dir.mkdir(parents=True, exist_ok=True)

    dem_copied = 0
    rep_copied = 0

    # Build index of filename -> original path for both sources
    source_file_maps: Dict[str, Dict[str, Path]] = {"Democratic Assembly": {}, "Republican Assembly": {}}
    for label, root in source_dirs.items():
        for p in root.rglob("*.txt"):
            source_file_maps[label][p.name] = p

    for d in doc_results:
        if d.ai_statement_count <= 0:
            continue
        if d.source == "Democratic Assembly":
            src_map = source_file_maps.get("Democratic Assembly", {})
            if d.filename in src_map:
                shutil.copy2(src_map[d.filename], dem_ai_dir / d.filename)
                dem_copied += 1
        elif d.source == "Republican Assembly":
            src_map = source_file_maps.get("Republican Assembly", {})
            if d.filename in src_map:
                shutil.copy2(src_map[d.filename], rep_ai_dir / d.filename)
                rep_copied += 1

    return dem_copied, rep_copied


def main() -> None:
    data_dir = WORKSPACE / "data" / "press_releases"
    outputs_dir = WORKSPACE / "outputs" / "v3"

    dem_dir = data_dir / "Democratic"
    rep_dir = data_dir / "Republican"
    if not dem_dir.exists() and not rep_dir.exists():
        print("No input directories found under data/press_releases/. Expected 'Democratic' and/or 'Republican'.", file=sys.stderr)
        sys.exit(2)

    all_statements: List[AIStatement] = []
    all_doc_results: List[DocumentAIResult] = []

    if dem_dir.exists():
        s_dem, d_dem = analyze_directory(dem_dir, source="Democratic Assembly")
        all_statements.extend(s_dem)
        all_doc_results.extend(d_dem)

    if rep_dir.exists():
        s_rep, d_rep = analyze_directory(rep_dir, source="Republican Assembly")
        all_statements.extend(s_rep)
        all_doc_results.extend(d_rep)

    if not all_doc_results:
        print("No documents analyzed.", file=sys.stderr)
        sys.exit(2)

    # Write outputs (EDA + statements)
    write_v3_outputs(all_statements, all_doc_results, outputs_dir)

    # Copy AI-containing documents to data/Dem_AI and data/Rep_AI
    ai_dem_copied, ai_rep_copied = copy_ai_documents(
        all_doc_results,
        source_dirs={
            "Democratic Assembly": dem_dir,
            "Republican Assembly": rep_dir,
        },
        data_dir=WORKSPACE / "data",
    )

    # Write a small log
    with open(outputs_dir / "ai_documents_copied_v3.json", "w", encoding="utf-8") as jf:
        json.dump({
            "democratic_ai_docs_copied": ai_dem_copied,
            "republican_ai_docs_copied": ai_rep_copied,
        }, jf, indent=2)

    print(f"Wrote v3 outputs to: {outputs_dir}")
    print(f"Copied AI-containing docs -> data/Dem_AI: {ai_dem_copied}, data/Rep_AI: {ai_rep_copied}")


if __name__ == "__main__":
    main()


