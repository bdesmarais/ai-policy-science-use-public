#!/usr/bin/env python3
"""
Structured References Fetcher

Reads structured claims from CSV files in data/structured_claims and fetches
scientific literature references for each claim using OpenAlex or Semantic Scholar.

Outputs two JSON files (Democratic and Republican) under outputs/structured_refs/.

Usage examples:
  python structured_references.py
  python structured_references.py --provider openalex --per-claim 5 --limit 50
  python structured_references.py --provider semanticscholar --skip-fetch

Notes:
- No API keys are required for OpenAlex. To get "polite pool" performance, set
  a contact email via --mailto or OPENALEX_MAILTO env; we'll add User-Agent and
  mailto= param as recommended.
- Semantic Scholar works best with an API key (1 rps). Provide via --s2-api-key
  or env S2_API_KEY. We'll throttle automatically to respect 1 request/second.
- Use --skip-fetch for quick structure validation without network calls.
"""

import argparse
import csv
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
import logging

try:
    # Standard library HTTP stack to avoid external deps
    import urllib.parse
    import urllib.request
    from urllib.error import HTTPError, URLError
except Exception as e:  # pragma: no cover
    print(f"Failed to import urllib: {e}", file=sys.stderr)
    raise


# ---------- Configuration Defaults ----------

DEFAULT_DEM_CSV = os.path.join("data", "structured_claims", "Demsfull_AI_LMclaims.csv")
DEFAULT_REP_CSV = os.path.join("data", "structured_claims", "Rep_AI_LMclaims.csv")
DEFAULT_OUTPUT_DIR = os.path.join("outputs", "structured_refs")

SUPPORTED_PROVIDERS = ("openalex", "semanticscholar")

# Hardcoded Semantic Scholar API key (per user request)
S2_API_KEY_HARDCODED = "HAAw0qJwSEHpEG07BKZL46n2fPJt13Q1CE8ib9b0"


# ---------- Data Models ----------

def safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(str(value).strip())
    except Exception:
        return None


def ensure_dir(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------- CSV Reading ----------

def read_claims_csv(csv_path: str, is_republican: bool) -> List[Dict[str, Any]]:
    claims: List[Dict[str, Any]] = []
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            press_release = (row.get("press_release") or "").strip()
            claim_number_raw = row.get("claim_number")
            claim_number = safe_int(claim_number_raw)
            claim_text = (row.get("claim_text") or "").strip()

            if is_republican:
                note_val = (row.get("note") or "").strip()
                # Skip rows explicitly marked as having no AI/emergent tech claims
                if note_val == "This source does not contain any AI/Emergent Technology claims.":
                    continue

            # Skip rows without a non-empty claim
            if not press_release or not claim_text:
                continue

            claims.append(
                {
                    "press_release": press_release,
                    "claim_number": claim_number,
                    "claim_text": claim_text,
                }
            )

    return claims


# ---------- Query Building ----------

_STOPWORDS = {
    "the","a","an","and","or","but","if","then","than","that","this","these","those",
    "to","of","in","on","for","by","with","without","as","at","from","about","into","over",
    "is","are","was","were","be","being","been","has","have","had","can","could","should","would",
    "may","might","will","shall","do","does","did","it's","its","it's","their","there","our","your",
    "we","they","you","i","he","she","it","his","her","them","us","one","two","three","more",
}

_PHRASE_HEURISTICS: List[Tuple[List[str], str]] = [
    (["deepfake"], '"deepfake" OR "synthetic media"'),
    (["automated decision", "adt", "ads"], '"automated decision" OR "algorithmic decision"'),
    (["facial recognition", "face recognition"], '"facial recognition" OR "face recognition"'),
    (["generative ai", "genai", "large language model", "foundation model"], '"generative AI" OR "large language model" OR "foundation model"'),
    (["algorithmic bias", "fairness", "discrimination"], '"algorithmic bias" OR fairness OR discrimination'),
    (["child sexual abuse", "csam"], '"child sexual abuse material" OR CSAM'),
    (["election", "disinformation"], 'election disinformation OR deepfake'),
    (["data center", "energy"], 'data center energy consumption AI'),
]

# Extra aggressive boilerplate/political stopwords for S2
_BOILERPLATE_STOP = {
    "california","state","assembly","senate","senator","assemblymember","governor","newsom","committee",
    "bill","bills","ab","sb","measure","package","legislation","law","laws","policy","policies",
    "working","group","workinggroup","report","reports","study","studies","initiative","program",
    "announces","announce","announced","introduces","introduced","introduce","passes","passed","pass",
    "signs","signed","sign","advance","advances","advancing","focus","focusing","ensure","ensuring",
    "promote","promotes","promoting","protect","protects","protecting","require","requires","required",
    "provide","provides","provided","establish","establishes","established","update","updated","updating",
    "framework","frameworks","package","press","pressrelease","release","news","newsroom","office",
    "county","city","district","public","statewide","unanimously","bipartisan","leaders","leader",
}

# Curated technical lexicon (expanded for recall across target themes)
TECH_PHRASES: List[str] = [
    # Deepfakes / authenticity / provenance
    "deepfake detection","synthetic media detection","content authenticity","media provenance",
    # Elections / disinformation
    "election disinformation","misinformation detection",
    # Vision / biometrics
    "facial recognition bias","facial recognition accuracy","emotion recognition bias","emotion recognition accuracy",
    # Algorithmic decision-making / fairness / audits
    "algorithmic decision making","automated decision system","algorithmic impact assessment",
    "algorithmic bias mitigation","fairness in machine learning","explainable ai",
    # Generative AI / LLMs
    "generative ai safety","large language model safety","hallucination detection","model hallucinations",
    "model watermarking","ai watermarking","content watermarking",
    # Voice cloning / speech synthesis
    "voice cloning detection","synthetic speech detection",
    # Child safety
    "child sexual abuse material detection","csam detection",
    # Energy / infrastructure
    "data center energy consumption","data center efficiency ai","ai energy consumption",
    # Robotics / industry
    "robotic welding","industrial robotics automation","industrial automation",
    # Pricing / antitrust
    "algorithmic pricing","algorithmic pricing collusion","personalized pricing discrimination",
    # Healthcare / insurance
    "prior authorization algorithm","insurance claims algorithm","insurance algorithm bias",
    # Safety for children / chatbots
    "chatbot safety children",
]

TECH_ANCHORS: List[str] = [
    # General AI/ML
    "ai","ml","model","models","neural","network","networks","learning","dataset","datasets",
    # Authenticity / provenance
    "deepfake","watermark","watermarking","provenance","authenticity",
    # Disinformation / safety
    "disinformation","misinformation","detection","classifier","robustness","safety","alignment","hallucination","hallucinations",
    # Biometrics
    "facial","recognition","biometric","accuracy","bias","fairness","mitigation","audit","assessment","xai","explainability",
    # Automated decision-making
    "automated","decision","impact","risk","assessment",
    # Generative AI / LLM
    "generative","foundation","llm","gpt","watermarking",
    # Child safety / CSAM
    "csam","child","sexual","abuse",
    # Energy / infrastructure
    "data","center","energy","efficiency","cooling",
    # Robotics / industry
    "robotic","welding","automation","industrial",
    # Pricing / antitrust
    "pricing","price","antitrust","collusion","personalized",
    # Healthcare / insurance
    "insurance","claims","authorization","prior",
    # Speech / voice
    "voice","cloning","synthetic","speech",
]


def _remove_parentheticals(text: str) -> str:
    out = []
    depth = 0
    for ch in text:
        if ch == '(':
            depth += 1
            continue
        if ch == ')':
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return ''.join(out)


def _normalize_spaces(text: str) -> str:
    return " ".join(text.split())


def build_query_from_claim(claim_text: str) -> str:
    base = _remove_parentheticals(claim_text)
    base = base.replace('“', '"').replace('”', '"').replace("'", " ")
    base = base.replace("/", " ").replace("\\", " ")
    base = ''.join(ch if (ch.isalnum() or ch in [' ', '-', '"']) else ' ' for ch in base)
    base = _normalize_spaces(base.lower())

    # Phrase heuristics
    boosted: List[str] = []
    for patterns, phrase_query in _PHRASE_HEURISTICS:
        if any(p in base for p in patterns):
            boosted.append(phrase_query)

    tokens = [t for t in base.split() if t not in _STOPWORDS and len(t) > 2]
    # Truncate to avoid overly long queries
    tokens = tokens[:20]
    token_query = " ".join(tokens)

    if boosted:
        return f"{token_query} {" OR ".join(boosted)}".strip()
    return token_query


def build_query_variant_minimal(claim_text: str) -> str:
    base = _remove_parentheticals(claim_text)
    base = base.lower()
    # Keep only likely technical terms
    keep_terms = [
        "artificial intelligence", "ai", "machine learning", "ml", "deep learning", "neural",
        "algorithm", "algorithms", "algorithmic", "bias", "fairness", "discrimination",
        "deepfake", "synthetic media", "facial recognition", "computer vision", "autonomous",
        "robot", "robotics", "generative", "large language model", "foundation model",
        "csam", "child sexual abuse", "disinformation", "misinformation", "data center",
    ]
    present: List[str] = []
    for term in keep_terms:
        if term in base:
            present.append(term)
    if not present and (" ai " in f" {base} " or "artificial intelligence" in base):
        present.append("artificial intelligence")
    if not present:
        # Fallback to core AI terms
        present = ["artificial intelligence", "algorithm"]
    return " ".join(sorted(set([f'"{t}"' if " " in t else t for t in present])))


def build_s2_query_from_claim(claim_text: str) -> str:
    # Build a Semantic Scholar-friendly query: compact, no boolean operators
    base = _remove_parentheticals(claim_text)
    base = base.replace('“', '"').replace('”', '"').replace("'", " ")
    base = base.replace("/", " ").replace("\\", " ")
    base = ''.join(ch if (ch.isalnum() or ch in [' ', '-', '"']) else ' ' for ch in base)
    base = _normalize_spaces(base.lower())

    # Start from curated phrases present in text
    present_phrases: List[str] = [p for p in TECH_PHRASES if p in base]
    # Token filtering: remove boilerplate and generic stopwords
    tokens = [t for t in base.split() if t not in _STOPWORDS and t not in _BOILERPLATE_STOP and len(t) > 2]
    # Remove filler verbs/adverbs/adjectives aggressively
    filler = {
        "said","say","says","making","made","make","extremely","very","really","hard","harder","easier","easily",
        "potentially","already","widely","quickly","cheaply","significantly","severely","challenging","difficult",
        "appear","appearing","seamlessly","further","furthermore","often","sometimes","increasingly","likely",
        "new","powerful","dangerous","strong","major","minor","severe","massive","profound","growing","rapidly",
        "true","false","real","fake","genuine","not",
    }
    tokens = [t for t in tokens if t not in filler]
    # Keep only tokens that intersect anchors or look technical
    token_keep = [t for t in tokens if t in TECH_ANCHORS or t in {
        "ai","ml","model","models","neural","network","networks","dataset","datasets","learning"
    }]
    # Prioritize anchors first, then remaining technical tokens
    ordered = [t for t in token_keep if t in TECH_ANCHORS] + [t for t in token_keep if t not in TECH_ANCHORS]
    # Build compact list: phrases (quoted) + top tokens
    parts: List[str] = []
    for ph in present_phrases[:1]:
        parts.append(f'"{ph}"')
    for tok in ordered:
        if tok not in parts:
            parts.append(tok)
        if len(parts) >= 3:
            break
    if not parts:
        parts = ["artificial", "intelligence"]
    return " ".join(parts)


def build_s2_topic_query(claim_text: str) -> Optional[str]:
    """Rule-based topic mapper to robust S2 queries for common themes."""
    t = claim_text.lower()
    token_set = set(_normalize_spaces(_remove_parentheticals(t)).replace('/', ' ').replace('\\', ' ').replace('"', ' ').split())
    mappings: List[Tuple[List[str], str]] = [
        (["deepfake","synthetic media","face swap"], "deepfake detection"),
        (["watermark","provenance","authenticity"], "content authenticity"),
        (["facial recognition","face recognition"], "facial recognition bias"),
        (["emotion recognition","emotion detection"], "emotion recognition bias"),
        (["automated decision","algorithmic decision","adt","ads"], "algorithmic decision bias"),
        (["algorithmic bias","bias","fairness","discrimination"], "algorithmic bias fairness"),
        (["generative ai","foundation model","llm","gpt"], "generative ai safety"),
        (["hallucination","hallucinations"], "hallucination detection"),
        (["voice","likeness","cloning"], "voice cloning"),
        (["csam","child sexual abuse"], "csam detection"),
        (["election","disinformation","misinformation"], "election disinformation"),
        (["data center","energy","cooling"], "data center energy"),
        (["autonomous vehicle","driverless","av"], "autonomous vehicles safety"),
        (["price","pricing","collusion","antitrust"], "algorithmic pricing"),
        (["surveillance pricing","personalized pricing"], "personalized pricing"),
        (["chatbot","companion","child"], "chatbot safety children"),
        (["robot","robotic","industrial"], "industrial robotics"),
        (["weld","welding"], "robotic welding"),
        (["insurance","prior authorization"], "insurance claims algorithm"),
    ]
    for keys, query in mappings:
        for k in keys:
            if len(k) <= 3:
                if k in token_set:
                    return query
            else:
                if k in t:
                    return query
    return None


# Single compact S2 query builder used for one-shot fetching
def build_compact_s2_query(claim_text: str) -> str:
    # Prefer a concise topic phrase if we can map it
    topic_q = build_s2_topic_query(claim_text)
    if topic_q:
        return topic_q
    # Extract only AI/emergent-tech terms from the claim and build <=3-term query
    t = _normalize_spaces(_remove_parentheticals(claim_text).lower())
    # Phrases found in-text, preserve TECH_PHRASES order
    phrases = [p for p in TECH_PHRASES if p in t]
    # Tokenize for whole-word anchor matching
    tokens = set(t.replace('/', ' ').replace('\\', ' ').replace('"', ' ').split())
    anchors = [a for a in TECH_ANCHORS if a in tokens]
    parts: List[str] = []
    if phrases:
        # Add up to first two words from the first phrase (no quotes)
        for word in phrases[0].split():
            if len(parts) >= 3:
                break
            if word not in parts:
                parts.append(word)
    for a in anchors:
        if len(parts) >= 3:
            break
        if a not in parts:
            parts.append(a)
    if not parts:
        # Very short fallback
        return "ai"
    return " ".join(parts)

# ---------- Provider: OpenAlex ----------

def _reconstruct_openalex_abstract(abstract_inverted_index: Optional[Dict[str, List[int]]]) -> Optional[str]:
    if not abstract_inverted_index:
        return None
    # Reconstruct by placing words at their position indices
    positions_to_word: Dict[int, str] = {}
    try:
        for word, positions in abstract_inverted_index.items():
            for position in positions:
                positions_to_word[position] = word
        if not positions_to_word:
            return None
        abstract_tokens: List[str] = [positions_to_word[i] for i in range(max(positions_to_word.keys()) + 1)]
        return " ".join(abstract_tokens)
    except Exception:
        # Fallback to concatenating words roughly
        try:
            words = sorted(abstract_inverted_index.items(), key=lambda kv: min(kv[1]) if kv[1] else 0)
            return " ".join(w for w, _ in words)
        except Exception:
            return None


def fetch_from_openalex(
    query: str,
    per_claim: int,
    timeout: float,
    mailto: Optional[str],
    retries: int = 2,
    sleep_between: float = 0.2,
) -> List[Dict[str, Any]]:
    base_url = "https://api.openalex.org/works"
    per_page = 200  # OpenAlex max
    params_base = {
        "search": query,
        "per_page": per_page,
        "sort": "relevance_score:desc",
    }
    if mailto:
        params_base["mailto"] = mailto

    headers = {
        "User-Agent": f"structured-references/1.0 (mailto:{mailto})" if mailto else "structured-references/1.0",
    }

    results: List[Dict[str, Any]] = []
    fetched = 0
    cursor = "*"
    max_total = None if per_claim == -1 else per_claim

    while True:
        params = dict(params_base)
        params["cursor"] = cursor
        url = f"{base_url}?{urllib.parse.urlencode(params)}"

        last_err: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                break
            except HTTPError as he:
                last_err = he
                code = getattr(he, 'code', None)
                if code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise RuntimeError(f"OpenAlex HTTPError {he.code}: {he.reason}")
            except URLError as ue:
                last_err = ue
                if attempt < retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise RuntimeError(f"OpenAlex URLError: {ue}")

        page_items = data.get("results", [])
        if not page_items:
            break

        for item in page_items:
            work_id = item.get("id")
            doi = (item.get("doi") or "").replace("https://doi.org/", "") if item.get("doi") else None
            title = item.get("title")
            year = item.get("publication_year")
            venue = (item.get("host_venue", {}) or {}).get("display_name")
            oa = (item.get("open_access", {}) or {}).get("is_oa")
            oai = item.get("open_access", {}) or {}
            best_oa_url = oai.get("oa_url") or (item.get("primary_location", {}) or {}).get("pdf_url")
            authors = [a.get("author", {}).get("display_name") for a in (item.get("authorships") or [])]
            abstract = _reconstruct_openalex_abstract(item.get("abstract_inverted_index"))

            results.append(
                {
                    "provider": "openalex",
                    "id": work_id,
                    "doi": doi,
                    "title": title,
                    "abstract": abstract,
                    "year": year,
                    "venue": venue,
                    "authors": [n for n in authors if n],
                    "url": best_oa_url or work_id,
                    "is_open_access": bool(oa),
                }
            )
            fetched += 1
            if max_total is not None and fetched >= max_total:
                return results

        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(max(0.0, sleep_between))

    return results


# ---------- Provider: Semantic Scholar ----------

def fetch_from_semanticscholar(
    query: str,
    per_claim: int,
    timeout: float,
    api_key: Optional[str],
    retries: int = 2,
    sleep_between: float = 1.05,
) -> List[Dict[str, Any]]:
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    # Reduce page size if caller requests fewer than 100 total
    page_size = 100
    if per_claim != -1 and per_claim > 0:
        page_size = min(page_size, per_claim)
    headers = {"User-Agent": "structured-references/1.0", "Accept": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    results: List[Dict[str, Any]] = []
    fetched = 0
    offset = 0
    max_total = None if per_claim == -1 else per_claim

    global LAST_S2_QUERY_USED
    LAST_S2_QUERY_USED = None
    while True:
        params = {
            "query": query,
            "limit": page_size,
            "offset": offset,
            "fields": ",".join(
                [
                    "title",
                    "abstract",
                    "year",
                    "authors",
                    "venue",
                    "externalIds",
                    "doi",
                    "url",
                    "openAccessPdf",
                ]
            ),
        }
        # Ensure minimal length for S2 query; if empty, skip
        if not params["query"]:
            break
        url = f"{base_url}?{urllib.parse.urlencode(params)}"

        last_err: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                break
            except HTTPError as he:
                last_err = he
                code = getattr(he, 'code', None)
                if code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                raise RuntimeError(f"SemanticScholar HTTPError {he.code}: {he.reason}")
            except URLError as ue:
                last_err = ue
                if attempt < retries:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                raise RuntimeError(f"SemanticScholar URLError: {ue}")

        # Record the exact query used regardless of results
        if LAST_S2_QUERY_USED is None:
            LAST_S2_QUERY_USED = params.get("query")

        items = data.get("data", [])
        if not items:
            # If API returned metadata, log rough diagnostics at INFO level
            try:
                total = data.get("total")
                err = data.get("error") or data.get("message")
                logging.getLogger("structured_refs").info(f"Semantic Scholar returned no items (total={total}, error={err}) for query='{params.get('query')}'")
            except Exception:
                pass
            break

        for item in items:
            doi = item.get("doi") or (item.get("externalIds", {}) or {}).get("DOI")
            title = item.get("title")
            abstract = item.get("abstract")
            year = item.get("year")
            venue = item.get("venue")
            authors = [a.get("name") for a in (item.get("authors") or []) if a.get("name")]
            url_out = (item.get("openAccessPdf", {}) or {}).get("url") or item.get("url")
            results.append(
                {
                    "provider": "semanticscholar",
                    "id": item.get("paperId") or item.get("url"),
                    "doi": doi,
                    "title": title,
                    "abstract": abstract,
                    "year": year,
                    "venue": venue,
                    "authors": authors,
                    "url": url_out,
                    "is_open_access": bool(item.get("openAccessPdf")),
                }
            )
            fetched += 1
            if max_total is not None and fetched >= max_total:
                return results

        offset += page_size
        time.sleep(max(0.0, sleep_between))

    return results


# ---------- Search Orchestration ----------

def search_references_for_claim(
    claim_text: str,
    provider: str,
    per_claim: int,
    timeout: float,
    fallback_provider: Optional[str] = None,
    sleep_seconds: float = 0.0,
) -> Tuple[str, List[Dict[str, Any]]]:
    # Seed query: compact for Semantic Scholar, tokenized for OpenAlex
    if provider == "semanticscholar" or fallback_provider == "semanticscholar":
        query = build_compact_s2_query(claim_text)
    else:
        query = build_query_from_claim(claim_text)
    results: List[Dict[str, Any]] = []

    def _fetch(p: str) -> Tuple[str, List[Dict[str, Any]]]:
        if p == "openalex":
            mailto = os.environ.get("OPENALEX_MAILTO") or os.environ.get("OPENALEX_EMAIL")
            res = fetch_from_openalex(query=query, per_claim=per_claim, timeout=timeout, mailto=mailto, sleep_between=sleep_seconds)
            return query, res
        if p == "semanticscholar":
            api_key = os.environ.get("S2_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or S2_API_KEY_HARDCODED
            # Build a single compact query and fetch once
            s2_query = build_compact_s2_query(claim_text)
            res = fetch_from_semanticscholar(query=s2_query, per_claim=per_claim, timeout=timeout, api_key=api_key, sleep_between=max(1.05, sleep_seconds))
            used = LAST_S2_QUERY_USED or s2_query
            return used, res
        raise ValueError(f"Unsupported provider: {p}")

    # Decide order: always prioritize Semantic Scholar if available
    fetch_order: List[str] = []
    if provider == "semanticscholar" or fallback_provider == "semanticscholar":
        fetch_order.append("semanticscholar")
        other = provider if provider != "semanticscholar" else fallback_provider
        if other and other in SUPPORTED_PROVIDERS and other != "semanticscholar":
            fetch_order.append(other)
    else:
        fetch_order = [p for p in [provider, fallback_provider] if p in SUPPORTED_PROVIDERS]

    # Fetch and merge with de-duplication (DOI, else title+year)
    seen_keys: set = set()
    merged: List[Dict[str, Any]] = []

    def _make_key(rec: Dict[str, Any]) -> Tuple[str, Optional[int]]:
        doi = (rec.get("doi") or "").strip().lower()
        if doi:
            return (f"doi:{doi}", None)
        title = (rec.get("title") or "").strip().lower()
        year = rec.get("year")
        return (f"title:{title}", int(year) if isinstance(year, int) or (isinstance(year, str) and year.isdigit()) else None)

    for p in fetch_order:
        try:
            used_query, fetched = _fetch(p)
        except Exception:
            # continue to next provider on error
            fetched = []
            # Preserve compact query for S2 even on failure
            used_query = build_compact_s2_query(claim_text) if p == "semanticscholar" else query
        # Always record the exact query attempted, even if no results
        if used_query:
            query = used_query
        for rec in fetched:
            key = _make_key(rec)
            # If using title+year, include both in key uniqueness
            if key[0].startswith("title:"):
                compound = (key[0], key[1])
            else:
                compound = key
            if compound in seen_keys:
                continue
            seen_keys.add(compound)
            merged.append(rec)

    if sleep_seconds > 0:
        time.sleep(sleep_seconds)

    # Attach provider counts to results via a synthetic record if needed by caller
    # We will return merged and let caller add counts into metadata
    return query, merged


# ---------- Main Processing ----------

def process_side(
    side_name: str,
    csv_path: str,
    provider: str,
    fallback_provider: Optional[str],
    per_claim: int,
    timeout: float,
    limit: int,
    skip_fetch: bool,
    sleep_seconds: float,
    out_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    is_republican = side_name.lower().startswith("rep")
    logger = logging.getLogger("structured_refs")
    all_claims = read_claims_csv(csv_path, is_republican=is_republican)
    if limit >= 0:
        all_claims = all_claims[:limit]

    output_rows: List[Dict[str, Any]] = []
    for idx, claim in enumerate(all_claims, start=1):
        claim_text = claim["claim_text"]
        claim_number = claim.get("claim_number")
        press_release = claim["press_release"]

        references: List[Dict[str, Any]]
        search_query: str
        search_error: Optional[str] = None

        logger.info(f"[{side_name}] Claim {idx}/{len(all_claims)} from '{press_release}' (claim_number={claim_number})")
        if skip_fetch:
            search_query = claim_text
            references = []
        else:
            try:
                search_query, references = search_references_for_claim(
                    claim_text=claim_text,
                    provider=provider,
                    per_claim=per_claim,
                    timeout=timeout,
                    fallback_provider=fallback_provider,
                    sleep_seconds=sleep_seconds,
                )
                logger.info(f"Query built: '{search_query[:120]}...' ")
            except Exception:
                search_query = build_query_from_claim(claim_text)
                references = []
                search_error = traceback.format_exc(limit=1)
                logger.error(f"Error fetching references: {search_error}")

        # Provider split for logging
        prov_counts: Dict[str, int] = {}
        for r in references:
            prov = r.get("provider") or "unknown"
            prov_counts[prov] = prov_counts.get(prov, 0) + 1
        if prov_counts:
            logger.info(f"Found {len(references)} references (" + ", ".join(f"{k}={v}" for k, v in prov_counts.items()) + ")")
        else:
            logger.info(f"Found {len(references)} references")
        output_rows.append(
            {
                "press_release": press_release,
                "claim_number": claim_number,
                "claim_text": claim_text,
                "query": search_query,
                "references": references,
                "num_references": len(references),
                "search_metadata": {
                    "provider": provider,
                    "fallback_provider": fallback_provider,
                    "attempted_at": now_iso(),
                    "error": search_error,
                    "s2_api_key_used": bool(os.environ.get("S2_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or S2_API_KEY_HARDCODED),
                    "provider_counts": prov_counts,
                },
            }
        )

        # Incremental write after each claim if an output path is provided
        if out_path:
            try:
                write_json(out_path, output_rows)
            except Exception as e:
                logger.error(f"Failed incremental write to {out_path}: {e}")

    return output_rows


def write_json(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch scientific references for structured claims")
    parser.add_argument("--dem-csv", default=DEFAULT_DEM_CSV, help="Path to Dems claims CSV")
    parser.add_argument("--rep-csv", default=DEFAULT_REP_CSV, help="Path to Rep claims CSV")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory to write JSON outputs")
    parser.add_argument(
        "--provider",
        default="openalex",
        choices=list(SUPPORTED_PROVIDERS),
        help="Primary provider to use for search",
    )
    parser.add_argument(
        "--fallback-provider",
        default=None,
        choices=list(SUPPORTED_PROVIDERS) + [None],
        help="Optional fallback provider if the primary fails",
    )
    parser.add_argument("--per-claim", type=int, default=-1, help="Max references per claim (-1 for all available)")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--limit",
        type=int,
        default=-1,
        help="Limit number of claims per side (-1 for all)",
    )
    parser.add_argument("--skip-fetch", action="store_true", help="Do not perform network calls; write empty refs")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between requests")
    parser.add_argument("--mailto", default=os.environ.get("OPENALEX_MAILTO", "sjr6223@psu.edu"), help="Email for OpenAlex polite pool")
    parser.add_argument("--s2-api-key", default=os.environ.get("S2_API_KEY") or S2_API_KEY_HARDCODED, help="Semantic Scholar API key")
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"), help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--s2-health-check", action="store_true", help="Before running, query S2 with a known-good query to verify availability")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    # Setup logging
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("structured_refs")

    provider = args.provider
    fallback_provider = args.fallback_provider
    if fallback_provider == provider:
        fallback_provider = None

    # Propagate config to env used by fetchers
    if args.mailto:
        os.environ["OPENALEX_MAILTO"] = args.mailto
    if args.s2_api_key:
        os.environ["S2_API_KEY"] = args.s2_api_key

    # Default throttling: respect S2 1 rps automatically if using it in any path
    if args.sleep == 0.0:
        if provider == "semanticscholar" or fallback_provider == "semanticscholar":
            args.sleep = 1.05
        else:
            args.sleep = 0.2

    logger.info(f"Starting with provider={provider} fallback={fallback_provider} per_claim={args.per_claim} limit={args.limit} sleep={args.sleep}")

    # Optional: quick S2 health check
    if provider == "semanticscholar" and args.s2_health_check:
        try:
            api_key = os.environ.get("S2_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or S2_API_KEY_HARDCODED
            probe_query = "deepfake detection"
            probe = fetch_from_semanticscholar(query=probe_query, per_claim=5, timeout=args.timeout, api_key=api_key, sleep_between=1.05)
            logger.info(f"S2 health check: got {len(probe)} items for '{probe_query}'" + (f", e.g., '{probe[0].get('title')}'" if probe else ""))
        except Exception as e:
            logger.error(f"S2 health check failed: {e}")
            # Continue anyway; user may want to run despite error
    # Prepare output paths
    ensure_dir(args.output_dir)
    dem_out_path = os.path.join(args.output_dir, "dem_claim_references.json")
    rep_out_path = os.path.join(args.output_dir, "rep_claim_references.json")

    # Process Democrats
    dem_rows = process_side(
        side_name="Democratic",
        csv_path=args.dem_csv,
        provider=provider,
        fallback_provider=fallback_provider,
        per_claim=args.per_claim,
        timeout=args.timeout,
        limit=args.limit,
        skip_fetch=args.skip_fetch,
        sleep_seconds=args.sleep,
        out_path=dem_out_path,
    )

    # Process Republicans
    rep_rows = process_side(
        side_name="Republican",
        csv_path=args.rep_csv,
        provider=provider,
        fallback_provider=fallback_provider,
        per_claim=args.per_claim,
        timeout=args.timeout,
        limit=args.limit,
        skip_fetch=args.skip_fetch,
        sleep_seconds=args.sleep,
        out_path=rep_out_path,
    )

    # Final write to ensure files reflect complete results
    write_json(dem_out_path, dem_rows)
    write_json(rep_out_path, rep_rows)

    # Console summary
    total_dem = sum(r.get("num_references", 0) for r in dem_rows)
    total_rep = sum(r.get("num_references", 0) for r in rep_rows)
    logger.info("Writing output JSON files")
    print(
        json.dumps(
            {
                "written": {
                    "dem": dem_out_path,
                    "rep": rep_out_path,
                },
                "claims_processed": {
                    "dem": len(dem_rows),
                    "rep": len(rep_rows),
                },
                "references_found": {
                    "dem": total_dem,
                    "rep": total_rep,
                },
                "provider": provider,
                "fallback_provider": fallback_provider,
                "skip_fetch": args.skip_fetch,
            },
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())


