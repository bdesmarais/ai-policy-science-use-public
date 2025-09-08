import csv
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


"""
Enhanced press release analyzer (v2)

Goals:
- Reduce false positives for short abbreviations like "ai" by using word-boundary regexes and variants (e.g., A.I.).
- Identify claims specifically in the context of AI/science by requiring co-occurrence within a sentence window.
- Compute verifiability scores for claims based on references (DOI/arXiv/URLs), journal-like strings, and quantitative metrics.
- Produce comparative statistics between sources (Democratic vs Republican assemblies).
- Optionally render simple visualizations if matplotlib is installed; otherwise, skip gracefully.

This file is standalone and uses only the Python standard library. Visualizations are optional and enabled only if matplotlib is available.
"""


WORKSPACE = Path(__file__).parent


# Core keyword definitions (kept close to v1 but with some additions and normalization patterns)
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
    r"\bdata (?:show|shows|indicate|indicates|suggest|suggests)\b",
    r"\bresults (?:show|shows|indicate|indicates|demonstrate|demonstrates)\b",
    r"\bscientists? (?:say|report|found|find)\b",
    r"\bthis (?:study|research) (?:shows|finds|demonstrates|confirms|validates)\b",
    r"\bevidence[-\s]?based\b",
    r"\bexperts? (?:say|stated|concluded|conclude)\b",
    r"\bwe (?:find|found|show|demonstrate|measured)\b",
    r"\bshows? (?:an? )?(?:increase|decrease|improvement|reduction)\b",
]


# Reference and metric regexes
URL_REGEX = re.compile(r"https?://[^\s)\]}]+", re.IGNORECASE)
DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ARXIV_REGEX = re.compile(r"arXiv:\d{4}\.\d{4,5}", re.IGNORECASE)
BRACKET_CITATION_REGEX = re.compile(r"\[(?:\d+|[A-Za-z\-]+,\s*\d{4})\]")
JOURNAL_LIKE_REGEX = re.compile(r"\b(Journal|Proceedings|Transactions|Nature|Science|Lancet)\b[^\n]*", re.IGNORECASE)
PERCENT_REGEX = re.compile(r"\b\d{1,3}(?:\.\d+)?%\b")
NUMBER_METRIC_REGEX = re.compile(r"\b\d+(?:\.\d+)?\s*(?:points?|pp|percent|percentage|cases|errors|samples)\b", re.IGNORECASE)


SCHOLARLY_DOMAINS = (
    "doi.org",
    "arxiv.org",
    "nature.com",
    "science.org",
    "acm.org",
    "ieee.org",
    "springer",
    "elsevier",
    "ncbi.nlm.nih.gov",
    "nih.gov",
    "bmj.com",
    "thelancet.com",
)


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
            # Phrase or single token with boundaries, allow optional hyphen in known hyphenated variant
            escaped = re.escape(t)
            if " " in t:
                # require boundaries around first and last token
                pat = r"\b" + escaped.replace("\\ ", "\\s+") + r"\b"
            else:
                pat = r"\b" + escaped + r"\b"
        patterns[t] = re.compile(pat, re.IGNORECASE)
    return patterns


AI_PATTERNS = compile_term_patterns(AI_KEYWORDS)
SCI_PATTERNS = compile_term_patterns(SCIENCE_TERMS)


def find_term_matches(text: str, patterns: Dict[str, re.Pattern]) -> List[str]:
    matches: List[str] = []
    for term, pat in patterns.items():
        if pat.search(text):
            matches.append(term)
    return matches


def detect_claim_like(text: str) -> bool:
    return any(re.search(pat, text, flags=re.IGNORECASE) for pat in CLAIM_PATTERNS)


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
class MentionV2:
    sentence_index: int
    sentence_text: str
    contains_ai: bool
    contains_science: bool
    claim_like: bool
    is_ai_claim: bool
    matched_ai_terms: List[str]
    matched_science_terms: List[str]
    urls: List[str]
    dois: List[str]
    arxiv: List[str]
    other_refs: List[str]
    percents: List[str]
    number_metrics: List[str]
    verifiability_score: int
    verifiability_level: str
    context_before: Optional[str]
    context_after: Optional[str]


@dataclass
class DocumentResultV2:
    source: str
    filename: str
    document_date: Optional[str]
    num_sentences: int
    mentions: List[MentionV2]
    unique_urls: List[str]
    unique_dois: List[str]
    unique_arxiv: List[str]
    unique_other_refs: List[str]


def score_verifiability(urls: List[str], dois: List[str], arxiv: List[str], other_refs: List[str], percents: List[str], number_metrics: List[str]) -> Tuple[int, str]:
    score = 0
    if dois:
        score += 4
    if arxiv:
        score += 3
    if urls:
        # Heavier weight if any scholarly domain appears
        if any(any(domain in u for domain in SCHOLARLY_DOMAINS) for u in urls):
            score += 3
        else:
            score += 1
    if other_refs:
        score += 1
    if percents:
        score += 1
    if number_metrics:
        score += 1
    # Map to level
    if score >= 6:
        level = "high"
    elif score >= 3:
        level = "medium"
    else:
        level = "low"
    return score, level


def extract_from_text_v2(text: str, source: str, filename: str) -> DocumentResultV2:
    text = normalize_ai_variants(text)
    cleaned = normalize_whitespace(text)
    sentences = split_sentences(cleaned)
    mentions: List[MentionV2] = []
    all_urls: List[str] = []
    all_dois: List[str] = []
    all_arxiv: List[str] = []
    all_other_refs: List[str] = []

    # Precompute lower-cased sentences for matching
    lower_sentences = [s.lower() for s in sentences]

    for idx, sentence in enumerate(sentences):
        lower_sentence = lower_sentences[idx]
        matched_ai = find_term_matches(sentence, AI_PATTERNS)
        matched_science = find_term_matches(sentence, SCI_PATTERNS)
        contains_ai = len(matched_ai) > 0
        contains_science = len(matched_science) > 0
        claim_like = detect_claim_like(sentence)

        # Neighbor context for co-occurrence logic
        prev_text = sentences[idx - 1] if idx - 1 >= 0 else None
        next_text = sentences[idx + 1] if idx + 1 < len(sentences) else None

        prev_has_ai_sci = False
        next_has_ai_sci = False
        if prev_text:
            prev_has_ai_sci = bool(find_term_matches(prev_text, AI_PATTERNS) or find_term_matches(prev_text, SCI_PATTERNS))
        if next_text:
            next_has_ai_sci = bool(find_term_matches(next_text, AI_PATTERNS) or find_term_matches(next_text, SCI_PATTERNS))

        is_ai_claim = claim_like and (contains_ai or contains_science or prev_has_ai_sci or next_has_ai_sci)

        urls = URL_REGEX.findall(sentence)
        dois = DOI_REGEX.findall(sentence)
        arxiv = ARXIV_REGEX.findall(sentence)
        bracket_cites = BRACKET_CITATION_REGEX.findall(sentence)
        journal_like = JOURNAL_LIKE_REGEX.findall(sentence)
        percents = PERCENT_REGEX.findall(sentence)
        number_metrics = NUMBER_METRIC_REGEX.findall(sentence)

        other_refs: List[str] = []
        if bracket_cites:
            other_refs.extend(bracket_cites)
        if journal_like:
            other_refs.extend(journal_like)

        # Verifiability considers only the current sentence. Context-aware verifiability is handled for is_ai_claim below.
        v_score, v_level = score_verifiability(urls, dois, arxiv, other_refs, percents, number_metrics)

        mention = None
        if contains_ai or contains_science or claim_like or urls or dois or arxiv or other_refs:
            mention = MentionV2(
                sentence_index=idx,
                sentence_text=sentence,
                contains_ai=contains_ai,
                contains_science=contains_science,
                claim_like=claim_like,
                is_ai_claim=is_ai_claim,
                matched_ai_terms=sorted(set(matched_ai)),
                matched_science_terms=sorted(set(matched_science)),
                urls=urls,
                dois=dois,
                arxiv=arxiv,
                other_refs=other_refs,
                percents=percents,
                number_metrics=number_metrics,
                verifiability_score=v_score,
                verifiability_level=v_level,
                context_before=prev_text,
                context_after=next_text,
            )
            mentions.append(mention)
            all_urls.extend(urls)
            all_dois.extend(dois)
            all_arxiv.extend(arxiv)
            all_other_refs.extend(other_refs)

        # If a claim is AI-related but references appear in neighboring sentences, upgrade verifiability in-place
        if mention and is_ai_claim and v_score < 3:
            neighbor_texts = []
            if prev_text:
                neighbor_texts.append(prev_text)
            if next_text:
                neighbor_texts.append(next_text)
            n_urls = []
            n_dois = []
            n_arxiv = []
            n_other = []
            for t in neighbor_texts:
                n_urls.extend(URL_REGEX.findall(t))
                n_dois.extend(DOI_REGEX.findall(t))
                n_arxiv.extend(ARXIV_REGEX.findall(t))
                bc = BRACKET_CITATION_REGEX.findall(t)
                jl = JOURNAL_LIKE_REGEX.findall(t)
                if bc:
                    n_other.extend(bc)
                if jl:
                    n_other.extend(jl)
            if n_dois or n_arxiv or n_urls or n_other:
                up_score, up_level = score_verifiability(n_urls, n_dois, n_arxiv, n_other, [], [])
                mention.verifiability_score = max(mention.verifiability_score, up_score)
                mention.verifiability_level = up_level

    doc_date = guess_date(text)

    return DocumentResultV2(
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
                continue
            if not name.lower().endswith(".txt"):
                continue
            data = zf.read(name)
            out_path = target_dir / Path(name).name
            with open(out_path, "wb") as f:
                f.write(data)
            extracted_paths.append(out_path)
    return extracted_paths


def analyze_files(root_dir: Path, source: str) -> List[DocumentResultV2]:
    results: List[DocumentResultV2] = []
    for path in sorted(root_dir.rglob("*.txt")):
        try:
            with open(path, "rb") as f:
                text = read_text_with_fallback(f.read())
        except Exception as e:
            print(f"Failed to read {path}: {e}", file=sys.stderr)
            continue
        result = extract_from_text_v2(text, source=source, filename=path.name)
        results.append(result)
    return results


def write_outputs_v2(results: List[DocumentResultV2], outputs_dir: Path) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = outputs_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = outputs_dir / "press_release_science_mentions_v2.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump([
            {
                **{k: v for k, v in asdict(doc).items() if k != "mentions"},
                "mentions": [asdict(m) for m in doc.mentions],
            }
            for doc in results
        ], jf, ensure_ascii=False, indent=2)

    # CSV (one row per mention)
    csv_path = outputs_dir / "press_release_science_mentions_v2.csv"
    fieldnames = [
        "source",
        "filename",
        "document_date",
        "sentence_index",
        "contains_ai",
        "contains_science",
        "claim_like",
        "is_ai_claim",
        "matched_ai_terms",
        "matched_science_terms",
        "verifiability_score",
        "verifiability_level",
        "urls",
        "dois",
        "arxiv",
        "other_refs",
        "percents",
        "number_metrics",
        "context_before",
        "context_after",
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
                    "is_ai_claim": m.is_ai_claim,
                    "matched_ai_terms": "; ".join(m.matched_ai_terms),
                    "matched_science_terms": "; ".join(m.matched_science_terms),
                    "verifiability_score": m.verifiability_score,
                    "verifiability_level": m.verifiability_level,
                    "urls": "; ".join(m.urls),
                    "dois": "; ".join(m.dois),
                    "arxiv": "; ".join(m.arxiv),
                    "other_refs": "; ".join(m.other_refs),
                    "percents": "; ".join(m.percents),
                    "number_metrics": "; ".join(m.number_metrics),
                    "context_before": m.context_before or "",
                    "context_after": m.context_after or "",
                    "sentence_text": m.sentence_text,
                })

    # Per-document summary CSV
    doc_csv_path = outputs_dir / "press_release_document_summary_v2.csv"
    doc_fields = [
        "source",
        "filename",
        "document_date",
        "num_sentences",
        "num_mentions",
        "num_ai_mentions",
        "num_science_mentions",
        "num_claim_like",
        "num_ai_claims",
        "avg_verifiability_score",
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
            num_ai_claim = sum(1 for m in doc.mentions if m.is_ai_claim)
            avg_v = round((sum(m.verifiability_score for m in doc.mentions) / len(doc.mentions)) if doc.mentions else 0, 2)
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
                "num_ai_claims": num_ai_claim,
                "avg_verifiability_score": avg_v,
                "unique_urls_count": len(doc.unique_urls),
                "unique_dois_count": len(doc.unique_dois),
                "unique_arxiv_count": len(doc.unique_arxiv),
                "unique_other_refs_count": len(doc.unique_other_refs),
                "has_any_reference": bool(has_ref),
            })

    # Party-level comparative CSV and Markdown summary
    by_source: Dict[str, List[DocumentResultV2]] = defaultdict(list)
    for doc in results:
        by_source[doc.source].append(doc)

    comp_rows: List[Dict[str, object]] = []
    for source, docs in by_source.items():
        num_docs = len(docs)
        ai_mentions = sum(1 for d in docs for m in d.mentions if m.contains_ai)
        sci_mentions = sum(1 for d in docs for m in d.mentions if m.contains_science)
        claims = sum(1 for d in docs for m in d.mentions if m.claim_like)
        ai_claims = sum(1 for d in docs for m in d.mentions if m.is_ai_claim)
        mean_v = round((sum(m.verifiability_score for d in docs for m in d.mentions) / max(1, sum(len(d.mentions) for d in docs))), 2)
        comp_rows.append({
            "source": source,
            "documents": num_docs,
            "ai_mentions": ai_mentions,
            "science_mentions": sci_mentions,
            "claim_like": claims,
            "ai_claims": ai_claims,
            "avg_verifiability_score": mean_v,
        })

    comp_csv = outputs_dir / "press_release_party_comparison_v2.csv"
    comp_fields = list(comp_rows[0].keys()) if comp_rows else ["source", "documents", "ai_mentions", "science_mentions", "claim_like", "ai_claims", "avg_verifiability_score"]
    with open(comp_csv, "w", encoding="utf-8", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=comp_fields)
        writer.writeheader()
        for row in comp_rows:
            writer.writerow(row)

    # Top AI/science term frequencies per source
    top_terms_csv = outputs_dir / "press_release_top_terms_v2.csv"
    with open(top_terms_csv, "w", encoding="utf-8", newline="") as tf:
        writer = csv.writer(tf)
        writer.writerow(["source", "term_type", "term", "count"])
        for source, docs in by_source.items():
            ai_counter: Counter = Counter()
            sci_counter: Counter = Counter()
            for d in docs:
                for m in d.mentions:
                    ai_counter.update(m.matched_ai_terms)
                    sci_counter.update(m.matched_science_terms)
            for term, count in ai_counter.most_common(25):
                writer.writerow([source, "ai", term, count])
            for term, count in sci_counter.most_common(25):
                writer.writerow([source, "science", term, count])

    # Markdown summary with comparison
    md_path = outputs_dir / "press_release_science_mentions_v2.md"
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write("## Press Release Science & AI Mentions Summary (v2)\n\n")
        mf.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
        total_docs = len(results)
        total_ai = sum(1 for d in results for m in d.mentions if m.contains_ai)
        total_sci = sum(1 for d in results for m in d.mentions if m.contains_science)
        total_claims = sum(1 for d in results for m in d.mentions if m.claim_like)
        total_ai_claims = sum(1 for d in results for m in d.mentions if m.is_ai_claim)
        mean_v_all = round((sum(m.verifiability_score for d in results for m in d.mentions) / max(1, sum(len(d.mentions) for d in results))), 2)
        mf.write(f"- Total documents analyzed: {total_docs}\n")
        mf.write(f"- Total AI-related mentions: {total_ai}\n")
        mf.write(f"- Total science-related mentions: {total_sci}\n")
        mf.write(f"- Total claim-like sentences: {total_claims}\n")
        mf.write(f"- Total AI-related claims (context-aware): {total_ai_claims}\n")
        mf.write(f"- Average verifiability score (all mentions): {mean_v_all}\n\n")

        for row in comp_rows:
            mf.write(f"### {row['source']}\n\n")
            mf.write(f"- Documents: {row['documents']}\n")
            mf.write(f"- AI mentions: {row['ai_mentions']}\n")
            mf.write(f"- Science mentions: {row['science_mentions']}\n")
            mf.write(f"- Claim-like sentences: {row['claim_like']}\n")
            mf.write(f"- AI-related claims: {row['ai_claims']}\n")
            mf.write(f"- Average verifiability score: {row['avg_verifiability_score']}\n\n")

        # Exemplars
        mf.write("### Sample AI-related claims (up to 6)\n\n")
        exemplars: List[Tuple[DocumentResultV2, MentionV2]] = []
        for d in results:
            for m in d.mentions:
                if m.is_ai_claim:
                    exemplars.append((d, m))
        for d, m in exemplars[:6]:
            mf.write(f"- {d.source} — {d.filename} [#{m.sentence_index}]: {m.sentence_text}\n")
            if m.context_before:
                mf.write(f"  - context before: {m.context_before}\n")
            if m.context_after:
                mf.write(f"  - context after: {m.context_after}\n")
        mf.write("\n")

    # Optional visualizations using matplotlib (if available)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Bar chart: AI mentions by source
        sources = [row["source"] for row in comp_rows]
        ai_counts = [row["ai_mentions"] for row in comp_rows]
        sci_counts = [row["science_mentions"] for row in comp_rows]
        ai_claim_counts = [row["ai_claims"] for row in comp_rows]

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

        save_bar(ai_counts, "AI mentions by source", "ai_mentions_by_source.png")
        save_bar(sci_counts, "Science mentions by source", "science_mentions_by_source.png")
        save_bar(ai_claim_counts, "AI-related claims by source", "ai_claims_by_source.png")

    except Exception:
        # Visualization not available or failed; continue silently
        pass


def main() -> None:
    zip_map = {
        "OneDrive_2025-08-19.zip": "Democratic Assembly",
        "OneDrive_2025-08-19 (1).zip": "Republican Assembly",
    }

    data_dir = WORKSPACE / "data" / "press_releases"
    outputs_dir = WORKSPACE / "outputs"
    all_results: List[DocumentResultV2] = []

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
                f"Warning: {zip_name} not found in any of: " + ", ".join(str(p) for p in candidate_dirs),
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

    write_outputs_v2(all_results, outputs_dir)
    print(f"Wrote v2 outputs to: {outputs_dir}")


if __name__ == "__main__":
    main()


