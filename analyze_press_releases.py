import csv
import json
import os
import re
import sys
import zipfile
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


WORKSPACE = Path(__file__).parent


AI_KEYWORDS = [
    # Core terms
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
    "gpt-",
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


SCIENCE_TERMS = [
    "scientific",
    "peer-reviewed",
    "peer reviewed",
    "evidence",
    "study",
    "studies",
    "research",
    "statistically",
    "dataset",
    "datasets",
    "data set",
    "sample size",
    "randomized",
    "randomised",
    "rct",
    "experiment",
    "experimental",
    "meta-analysis",
    "systematic review",
    "preprint",
    "arxiv",
    "doi",
    "journal",
    "conference",
    "proceedings",
    "citation",
    "citations",
    "bibliography",
    "reference",
    "references",
    "white paper",
    "technical report",
    "benchmark",
    "accuracy",
    "precision",
    "recall",
    "auc",
    "f1",
    "p-value",
    "significant",
    "confidence interval",
    "95%",
]


CLAIM_PATTERNS = [
    r"\baccording to\b",
    r"\bresearch (?:shows|finds|indicates|suggests)\b",
    r"\bstudies (?:show|find|indicate|suggest)\b",
    r"\bthe evidence (?:shows|indicates|suggests)\b",
    r"\bdata (?:show|shows|indicate|indicates)\b",
    r"\bresults (?:show|shows|indicate|indicates)\b",
    r"\bscientists? (?:say|report|found|find)\b",
    r"\bhas been (?:proven|demonstrated|validated)\b",
    r"\bthis (?:study|research) (?:shows|finds|demonstrates)\b",
]


URL_REGEX = re.compile(r"https?://[^\s)\]}]+", re.IGNORECASE)
DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ARXIV_REGEX = re.compile(r"arXiv:\d{4}\.\d{4,5}", re.IGNORECASE)
BRACKET_CITATION_REGEX = re.compile(r"\[(?:\d+|[A-Za-z\-]+,\s*\d{4})\]")
JOURNAL_LIKE_REGEX = re.compile(r"\b(Journal|Proceedings|Transactions|Nature|Science|Lancet)\b[^\n]*", re.IGNORECASE)
PERCENT_REGEX = re.compile(r"\b\d{1,3}(?:\.\d+)?%\b")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"[\t\x0b\x0c\r]+", " ", text)


def split_sentences(text: str) -> List[str]:
    # Simple sentence splitter that respects common punctuation
    # Also splits on newlines and bullet points
    text = text.replace("\u2022", "\n").replace("\u2023", "\n").replace("\u25E6", "\n")
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    sentences = [s.strip() for s in chunks if s and s.strip()]
    return sentences


def find_matches(lower_text: str, terms: List[str]) -> List[str]:
    matches = []
    for term in terms:
        if term in lower_text:
            matches.append(term)
    return matches


def detect_claim_like(lower_sentence: str) -> bool:
    return any(re.search(pat, lower_sentence) for pat in CLAIM_PATTERNS)


@dataclass
class Mention:
    sentence_index: int
    sentence_text: str
    contains_ai: bool
    contains_science: bool
    claim_like: bool
    matched_ai_terms: List[str]
    matched_science_terms: List[str]
    urls: List[str]
    dois: List[str]
    arxiv: List[str]
    other_refs: List[str]
    percents: List[str]


@dataclass
class DocumentResult:
    source: str
    filename: str
    document_date: Optional[str]
    num_sentences: int
    mentions: List[Mention]
    unique_urls: List[str]
    unique_dois: List[str]
    unique_arxiv: List[str]
    unique_other_refs: List[str]


def guess_date(text: str, fallback: Optional[str] = None) -> Optional[str]:
    # Try to find a date like Month DD, YYYY or YYYY-MM-DD
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


def extract_from_text(text: str, source: str, filename: str) -> DocumentResult:
    cleaned = normalize_whitespace(text)
    sentences = split_sentences(cleaned)
    mentions: List[Mention] = []
    all_urls: List[str] = []
    all_dois: List[str] = []
    all_arxiv: List[str] = []
    all_other_refs: List[str] = []

    for idx, sentence in enumerate(sentences):
        lower_sentence = sentence.lower()
        matched_ai = find_matches(lower_sentence, AI_KEYWORDS)
        matched_science = find_matches(lower_sentence, SCIENCE_TERMS)
        contains_ai = len(matched_ai) > 0
        contains_science = len(matched_science) > 0
        claim_like = detect_claim_like(lower_sentence)

        urls = URL_REGEX.findall(sentence)
        dois = DOI_REGEX.findall(sentence)
        arxiv = ARXIV_REGEX.findall(sentence)
        bracket_cites = BRACKET_CITATION_REGEX.findall(sentence)
        journal_like = JOURNAL_LIKE_REGEX.findall(sentence)
        percents = PERCENT_REGEX.findall(sentence)

        other_refs = []
        if bracket_cites:
            other_refs.extend(bracket_cites)
        if journal_like:
            other_refs.extend(journal_like)

        if contains_ai or contains_science or claim_like or urls or dois or arxiv or other_refs:
            mention = Mention(
                sentence_index=idx,
                sentence_text=sentence,
                contains_ai=contains_ai,
                contains_science=contains_science,
                claim_like=claim_like,
                matched_ai_terms=sorted(set(matched_ai)),
                matched_science_terms=sorted(set(matched_science)),
                urls=urls,
                dois=dois,
                arxiv=arxiv,
                other_refs=other_refs,
                percents=percents,
            )
            mentions.append(mention)
            all_urls.extend(urls)
            all_dois.extend(dois)
            all_arxiv.extend(arxiv)
            all_other_refs.extend(other_refs)

    doc_date = guess_date(text)

    return DocumentResult(
        source=source,
        filename=filename,
        document_date=doc_date,
        num_sentences=len(sentences),
        mentions=mentions,
        unique_urls=sorted(set(all_urls)),
        unique_dois=sorted(set(all_dois)),
        unique_arxiv=sorted(set(all_arxiv)),
        unique_other_refs=sorted(set(all_other_refs)),
    )


def read_text_with_fallback(binary: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            return binary.decode(enc)
        except UnicodeDecodeError:
            continue
    return binary.decode("utf-8", errors="ignore")


def extract_zip_members(zip_path: Path, target_dir: Path) -> List[Path]:
    extracted_paths: List[Path] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(zip_path), "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                # directory
                continue
            # Only .txt files per task description
            if not name.lower().endswith(".txt"):
                continue
            data = zf.read(name)
            # Preserve only the basename to avoid deep nested paths
            out_path = target_dir / Path(name).name
            with open(out_path, "wb") as f:
                f.write(data)
            extracted_paths.append(out_path)
    return extracted_paths


def analyze_files(root_dir: Path, source: str) -> List[DocumentResult]:
    results: List[DocumentResult] = []
    for path in sorted(root_dir.rglob("*.txt")):
        try:
            with open(path, "rb") as f:
                text = read_text_with_fallback(f.read())
        except Exception as e:
            print(f"Failed to read {path}: {e}", file=sys.stderr)
            continue
        result = extract_from_text(text, source=source, filename=path.name)
        results.append(result)
    return results


def write_outputs(results: List[DocumentResult], outputs_dir: Path) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = outputs_dir / "press_release_science_mentions.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump([
            {
                **{k: v for k, v in asdict(doc).items() if k != "mentions"},
                "mentions": [asdict(m) for m in doc.mentions],
            }
            for doc in results
        ], jf, ensure_ascii=False, indent=2)

    # CSV (one row per mention)
    csv_path = outputs_dir / "press_release_science_mentions.csv"
    fieldnames = [
        "source",
        "filename",
        "document_date",
        "sentence_index",
        "contains_ai",
        "contains_science",
        "claim_like",
        "matched_ai_terms",
        "matched_science_terms",
        "urls",
        "dois",
        "arxiv",
        "other_refs",
        "percents",
        "sentence_text",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        for doc in results:
            for m in doc.mentions:
                writer.writerow({
                    "source": doc.source,
                    "filename": doc.filename,
                    "document_date": doc.document_date or "",
                    "sentence_index": m.sentence_index,
                    "contains_ai": m.contains_ai,
                    "contains_science": m.contains_science,
                    "claim_like": m.claim_like,
                    "matched_ai_terms": "; ".join(m.matched_ai_terms),
                    "matched_science_terms": "; ".join(m.matched_science_terms),
                    "urls": "; ".join(m.urls),
                    "dois": "; ".join(m.dois),
                    "arxiv": "; ".join(m.arxiv),
                    "other_refs": "; ".join(m.other_refs),
                    "percents": "; ".join(m.percents),
                    "sentence_text": m.sentence_text,
                })

    # Markdown summary
    md_path = outputs_dir / "press_release_science_mentions.md"
    by_source: Dict[str, List[DocumentResult]] = defaultdict(list)
    for doc in results:
        by_source[doc.source].append(doc)

    def count_mentions(docs: List[DocumentResult]) -> Tuple[int, int, int]:
        ai = sum(1 for d in docs for m in d.mentions if m.contains_ai)
        sci = sum(1 for d in docs for m in d.mentions if m.contains_science)
        claims = sum(1 for d in docs for m in d.mentions if m.claim_like)
        return ai, sci, claims

    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write("## Press Release Science Mentions Summary\n\n")
        mf.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
        total_docs = len(results)
        total_ai, total_sci, total_claims = count_mentions(results)
        mf.write(f"- Total documents analyzed: {total_docs}\n")
        mf.write(f"- Total AI-related mentions: {total_ai}\n")
        mf.write(f"- Total science-related mentions: {total_sci}\n")
        mf.write(f"- Total claim-like sentences: {total_claims}\n\n")

        for source, docs in by_source.items():
            ai_c, sci_c, claim_c = count_mentions(docs)
            mf.write(f"### {source}\n\n")
            mf.write(f"- Documents: {len(docs)}\n")
            mf.write(f"- AI mentions: {ai_c}\n")
            mf.write(f"- Science mentions: {sci_c}\n")
            mf.write(f"- Claim-like sentences: {claim_c}\n\n")

            # Show up to 5 exemplar sentences per source
            exemplars = []
            for d in docs:
                for m in d.mentions:
                    if m.contains_ai or m.contains_science or m.claim_like:
                        exemplars.append((d, m))
            exemplars = exemplars[:5]
            if exemplars:
                mf.write("Sample sentences:\n\n")
                for d, m in exemplars:
                    mf.write(f"- {d.filename} [#{m.sentence_index}]: {m.sentence_text}\n")
                mf.write("\n")

            # Unique references per source
            urls = sorted(set(u for d in docs for u in d.unique_urls))
            dois = sorted(set(u for d in docs for u in d.unique_dois))
            arxiv = sorted(set(u for d in docs for u in d.unique_arxiv))
            other = sorted(set(u for d in docs for u in d.unique_other_refs))

            if urls:
                mf.write("Links:\n")
                for u in urls[:20]:
                    mf.write(f"- {u}\n")
                if len(urls) > 20:
                    mf.write(f"- ... (+{len(urls)-20} more)\n")
                mf.write("\n")
            if dois:
                mf.write("DOIs:\n")
                for u in dois:
                    mf.write(f"- {u}\n")
                mf.write("\n")
            if arxiv:
                mf.write("arXiv IDs:\n")
                for u in arxiv:
                    mf.write(f"- {u}\n")
                mf.write("\n")
            if other:
                mf.write("Other references/citations:\n")
                for u in other[:20]:
                    mf.write(f"- {u}\n")
                if len(other) > 20:
                    mf.write(f"- ... (+{len(other)-20} more)\n")
                mf.write("\n")

    # Per-document summary CSV
    doc_csv_path = outputs_dir / "press_release_document_summary.csv"
    doc_fields = [
        "source",
        "filename",
        "document_date",
        "num_sentences",
        "num_mentions",
        "num_ai_mentions",
        "num_science_mentions",
        "num_claim_like",
        "unique_urls_count",
        "unique_dois_count",
        "unique_arxiv_count",
        "unique_other_refs_count",
        "has_any_reference",
    ]
    with open(doc_csv_path, "w", encoding="utf-8", newline="") as df:
        writer = csv.DictWriter(df, fieldnames=doc_fields)
        writer.writeheader()
        for doc in results:
            num_ai = sum(1 for m in doc.mentions if m.contains_ai)
            num_sci = sum(1 for m in doc.mentions if m.contains_science)
            num_claim = sum(1 for m in doc.mentions if m.claim_like)
            has_ref = any((doc.unique_urls, doc.unique_dois, doc.unique_arxiv, doc.unique_other_refs))
            writer.writerow({
                "source": doc.source,
                "filename": doc.filename,
                "document_date": doc.document_date or "",
                "num_sentences": doc.num_sentences,
                "num_mentions": len(doc.mentions),
                "num_ai_mentions": num_ai,
                "num_science_mentions": num_sci,
                "num_claim_like": num_claim,
                "unique_urls_count": len(doc.unique_urls),
                "unique_dois_count": len(doc.unique_dois),
                "unique_arxiv_count": len(doc.unique_arxiv),
                "unique_other_refs_count": len(doc.unique_other_refs),
                "has_any_reference": bool(has_ref),
            })


def main() -> None:
    # Map zip files to sources based on the user's description
    zip_map = {
        "OneDrive_2025-08-19.zip": "Democratic Assembly",
        "OneDrive_2025-08-19 (1).zip": "Republican Assembly",
    }

    data_dir = WORKSPACE / "data" / "press_releases"
    outputs_dir = WORKSPACE / "outputs"
    all_results: List[DocumentResult] = []

    # Allow zip files to be located either next to the script or in the parent directory
    candidate_dirs: List[Path] = [WORKSPACE, WORKSPACE.parent]

    for zip_name, source in zip_map.items():
        zip_path: Optional[Path] = None
        for base in candidate_dirs:
            candidate = base / zip_name
            if candidate.exists():
                zip_path = candidate
                break
        if zip_path is None:
            print(
                f"Warning: {zip_name} not found in any of: "
                + ", ".join(str(p) for p in candidate_dirs),
                file=sys.stderr,
            )
            continue
        target_dir = data_dir / ("Democratic" if "(1)" not in zip_name else "Republican")
        extracted = extract_zip_members(zip_path, target_dir)
        if not extracted:
            print(f"No .txt files found in {zip_name}", file=sys.stderr)
        results = analyze_files(target_dir, source=source)
        all_results.extend(results)

    if not all_results:
        print("No documents analyzed. Ensure the zip files contain .txt documents.", file=sys.stderr)
        sys.exit(2)

    write_outputs(all_results, outputs_dir)
    print(f"Wrote outputs to: {outputs_dir}")


if __name__ == "__main__":
    main()


