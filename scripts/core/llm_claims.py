#!/usr/bin/env python3
"""
LLM-first claim extraction for California legislative press releases.

Features:
- Per-press-release extraction using OpenAI Responses API (gpt-4o-mini)
- Strict JSON schema for claims
- Chunking for long documents (simple paragraph-based)
- Caching and resume (skip unchanged docs by content hash)
- Optional restriction to pilot document lists from outputs/pilot/docs_*.csv
- Aggregation to outputs/claims/{dem,rep}_claims.json compatible with gpt_references.py

Environment:
- OPENAI_API_KEY must be set
"""
import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    raise RuntimeError("Please install openai >= 1.0.0") from e


# Resolve project root (two levels up from scripts/core/), fallback to CWD
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
except Exception:
    PROJECT_ROOT = Path.cwd()

DATA_DIR = PROJECT_ROOT / "data" / "press_releases"
OUT_BASE = PROJECT_ROOT / "outputs" / "claims" / "llm"
RAW_DIR = OUT_BASE / "_raw"
LOG_DIR = PROJECT_ROOT / "outputs" / "logs"


# ------------------------------
# Utilities
# ------------------------------
def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def sha1_text(s: str) -> str:
    h = hashlib.sha1()
    h.update(s.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def first_line_as_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        t = line.strip()
        if t:
            return t[:180]
    return fallback


def chunk_paragraphs(text: str, max_chars: int = 14000, overlap_chars: int = 400) -> List[str]:
    """
    Simple paragraph-based chunking to stay within model context.
    """
    if len(text) <= max_chars:
        return [text]
    paras = text.split("\n\n")
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0
    for p in paras:
        p2 = p if p.endswith("\n\n") else p + "\n\n"
        if cur_len + len(p2) > max_chars and cur:
            chunk = "".join(cur)
            chunks.append(chunk)
            # add overlap from end of previous chunk
            if overlap_chars > 0 and len(chunk) > overlap_chars:
                overlap = chunk[-overlap_chars:]
                cur = [overlap]
                cur_len = len(overlap)
            else:
                cur = []
                cur_len = 0
        cur.append(p2)
        cur_len += len(p2)
    if cur:
        chunks.append("".join(cur))
    return chunks


# ------------------------------
# Schema and prompting
# ------------------------------
CLAIMS_JSON_SCHEMA: Dict[str, Any] = {
    "name": "claims_schema",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_text": {"type": "string"},
                        "rationale": {"type": ["string", "null"]},
                        "category": {"type": ["string", "null"]},
                        "is_policy_like": {"type": ["boolean", "null"]},
                        "who_asserts": {"type": ["string", "null"]},
                        "scope": {"type": ["string", "null"]},
                        "evidence_needed": {"type": ["string", "null"]},
                        "source_span": {
                            "type": ["object", "null"],
                            "properties": {
                                "start": {"type": "integer"},
                                "end": {"type": "integer"},
                            },
                        },
                    },
                    "required": ["claim_text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    },
}


SYSTEM_PROMPT = (
    "You are a precise extraction assistant. Extract only distinct, verifiable claims about AI or emerging technology "
    "from the press release text. Claims should be standalone sentences that could plausibly be supported or refuted by "
    "scientific literature. Exclude purely procedural/logistical statements (e.g., bill numbers without assertions), "
    "slogans with no concrete assertion, and duplicated paraphrases. Output JSON only, matching the provided schema."
)


def build_user_prompt(title: str, doc_id: str, text: str) -> str:
    return (
        "Task: Extract all distinct claims about AI or emerging technology in this press release. Do NOT assume a fixed number.\n"
        "Output JSON only matching the provided schema.\n"
        "Return concise, standalone claim_texts that could be tested against scientific literature. "
        "Exclude purely procedural statements and vague slogans.\n"
        f"<document_title>: {title}\n"
        f"<document_id>: {doc_id}\n"
        "<text>\n"
        f"{text}\n"
        "</text>\n"
    )


# ------------------------------
# OpenAI call helpers
# ------------------------------
def _response_to_text(resp: Any) -> str:
    text = getattr(resp, "output_text", None)
    if isinstance(text, str) and text:
        return text
    try:
        output = getattr(resp, "output", None)
        if output and isinstance(output, list):
            parts: List[str] = []
            for item in output:
                content = getattr(item, "content", None)
                if content and isinstance(content, list):
                    for c in content:
                        t = getattr(getattr(c, "text", None), "value", None)
                        if isinstance(t, str):
                            parts.append(t)
            if parts:
                return "\n".join(parts)
    except Exception:
        pass
    try:
        return str(resp)
    except Exception:
        return ""


def call_openai_claims(client: OpenAI, model: str, prompt: str) -> str:
    variants = [
        {"response_format": {"type": "json_schema", "json_schema": CLAIMS_JSON_SCHEMA}},
        {},
    ]
    last_err: Optional[Exception] = None
    for extra in variants:
        try:
            resp = client.responses.create(model=model, input=(SYSTEM_PROMPT + "\n\n" + prompt), **extra)
            return _response_to_text(resp)
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return ""


def _extract_json_payload(text: str) -> Optional[str]:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        cand = text[start : end + 1]
        try:
            json.loads(cand)
            return cand
        except Exception:
            pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        cand = text[start : end + 1]
        try:
            json.loads(cand)
            return cand
        except Exception:
            pass
    return None


def parse_claims(json_text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(json_text)
    except Exception:
        payload = _extract_json_payload(json_text)
        if not payload:
            return []
        try:
            data = json.loads(payload)
        except Exception:
            return []
    items: List[Dict[str, Any]] = []
    if isinstance(data, dict) and isinstance(data.get("claims"), list):
        for it in data["claims"]:
            if isinstance(it, dict):
                claim_text = (it.get("claim_text") or "").strip()
                if claim_text:
                    items.append(
                        {
                            "claim_text": claim_text,
                            "rationale": it.get("rationale"),
                            "category": it.get("category"),
                            "is_policy_like": it.get("is_policy_like"),
                            "who_asserts": it.get("who_asserts"),
                            "scope": it.get("scope"),
                            "evidence_needed": it.get("evidence_needed"),
                            "source_span": it.get("source_span"),
                        }
                    )
    elif isinstance(data, list):
        # fallback: array of strings
        for val in data:
            if isinstance(val, str) and val.strip():
                items.append({"claim_text": val.strip()})
    return items


def normalize_claim_text(s: str) -> str:
    return " ".join(s.strip().split()).lower()


def dedupe_claims(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        t = normalize_claim_text(it.get("claim_text", ""))
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(it)
    return out


# ------------------------------
# Pilot restriction
# ------------------------------
def _read_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def docs_from_pilot(pilot_dir: Path) -> List[Tuple[str, str]]:
    """
    Returns list of (party, filename) from pilot docs csvs.
    """
    out: List[Tuple[str, str]] = []
    for fn in [
        pilot_dir / "docs_dem_ai.csv",
        pilot_dir / "docs_dem_nonai.csv",
        pilot_dir / "docs_rep_ai.csv",
        pilot_dir / "docs_rep_nonai.csv",
    ]:
        rows = _read_csv(fn)
        for r in rows:
            party = (r.get("party") or "").strip()
            fnm = (r.get("filename") or "").strip()
            if party and fnm:
                out.append((party, fnm))
    # de-duplicate
    out = sorted(set(out))
    return out


def resolve_path(party: str, filename: str) -> Path:
    sub = "Democratic" if party == "Democratic" else "Republican"
    p = DATA_DIR / sub / filename
    return p


# ------------------------------
# Main processing
# ------------------------------
@dataclass
class DocSpec:
    party: str
    filename: str
    path: Path
    title: str
    text: str
    sha1: str


def collect_docs_all(parties: List[str], limit: int) -> List[DocSpec]:
    docs: List[DocSpec] = []
    for party in parties:
        sub = "Democratic" if party == "Democratic" else "Republican"
        for p in (DATA_DIR / sub).glob("*.txt"):
            try:
                text = read_text(p)
            except Exception:
                continue
            title = first_line_as_title(text, p.name)
            docs.append(
                DocSpec(
                    party=party,
                    filename=p.name,
                    path=p,
                    title=title,
                    text=text,
                    sha1=sha1_text(text),
                )
            )
            if limit >= 0 and len(docs) >= limit:
                break
        if limit >= 0 and len(docs) >= limit:
            break
    return docs


def collect_docs_from_pilot(pilot_dir: Path, parties: List[str], limit: int) -> List[DocSpec]:
    pairs = docs_from_pilot(pilot_dir)
    # filter by requested parties
    keep = {p for p in parties}
    pairs = [pr for pr in pairs if pr[0] in keep]
    docs: List[DocSpec] = []
    for party, filename in pairs[: (None if limit < 0 else limit)]:
        p = resolve_path(party, filename)
        if not p.exists():
            continue
        try:
            text = read_text(p)
        except Exception:
            continue
        title = first_line_as_title(text, p.name)
        docs.append(DocSpec(party=party, filename=filename, path=p, title=title, text=text, sha1=sha1_text(text)))
    return docs


def should_skip_by_cache(out_doc_path: Path, doc_sha1: str, resume: bool) -> bool:
    if not resume:
        return False
    if not out_doc_path.exists():
        return False
    try:
        with open(out_doc_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("doc_sha1") == doc_sha1
    except Exception:
        return False


def write_doc_output(doc: DocSpec, model: str, prompt: str, raw_text: Optional[str], claims: List[Dict[str, Any]]) -> None:
    ensure_dir(OUT_BASE / doc.party)
    ensure_dir(RAW_DIR / doc.party)
    out_doc = OUT_BASE / doc.party / f"{doc.filename}.json"
    raw_out = RAW_DIR / doc.party / f"{doc.filename}.jsonl"

    rec = {
        "press_release": doc.filename,
        "party": doc.party,
        "title": doc.title,
        "model": model,
        "attempted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prompt_preview": prompt[:300],
        "raw_preview": (raw_text or "")[:300] if raw_text else None,
        "raw_text": raw_text,
        "claims": claims,
        "num_claims": len(claims),
        "doc_sha1": doc.sha1,
    }
    with open(out_doc, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    # append raw line
    try:
        with open(raw_out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def aggregate_compact_claims() -> Tuple[Path, Path]:
    """
    Aggregate per-doc outputs into compact dem/rep claims JSONs for gpt_references.py
    """
    dem_rows: List[Dict[str, Any]] = []
    rep_rows: List[Dict[str, Any]] = []
    for party in ["Democratic", "Republican"]:
        party_dir = OUT_BASE / party
        if not party_dir.exists():
            continue
        for p in sorted(party_dir.glob("*.json")):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            pr = data.get("press_release") or p.stem
            claims = data.get("claims") or []
            for idx, c in enumerate(claims, start=1):
                claim_text = (c.get("claim_text") or "").strip()
                if not claim_text:
                    continue
                row = {
                    "press_release": pr,
                    "claim_number": idx,
                    "claim_text": claim_text,
                    "claim_desc": c.get("category") or "",
                }
                if party == "Democratic":
                    dem_rows.append(row)
                else:
                    rep_rows.append(row)
    out_claims_dir = PROJECT_ROOT / "outputs" / "claims"
    ensure_dir(out_claims_dir)
    dem_path = out_claims_dir / "dem_claims.json"
    rep_path = out_claims_dir / "rep_claims.json"
    with open(dem_path, "w", encoding="utf-8") as f:
        json.dump(dem_rows, f, ensure_ascii=False, indent=2)
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(rep_rows, f, ensure_ascii=False, indent=2)
    return dem_path, rep_path


def process_doc(client: OpenAI, model: str, doc: DocSpec, resume: bool) -> Tuple[str, str, int]:
    """
    Returns (party, filename, num_claims)
    """
    logger = logging.getLogger("llm_claims")
    out_doc = OUT_BASE / doc.party / f"{doc.filename}.json"
    if should_skip_by_cache(out_doc, doc.sha1, resume=resume):
        logger.debug("Skip (cache hit): %s | %s", doc.party, doc.filename)
        return (doc.party, doc.filename, -1)  # -1 indicates skipped
    logger.info("Processing: %s | %s", doc.party, doc.filename)
    chunks = chunk_paragraphs(doc.text)
    all_claims: List[Dict[str, Any]] = []
    raw_merged = ""
    for i, ch in enumerate(chunks, start=1):
        prompt = build_user_prompt(doc.title, doc.filename, ch)
        raw_text = None
        claims: List[Dict[str, Any]] = []
        err: Optional[Exception] = None
        for attempt in range(2):
            try:
                raw = call_openai_claims(client, model=model, prompt=prompt)
                raw_text = raw
                parsed = parse_claims(raw)
                if parsed:
                    claims = parsed
                    break
            except Exception as e:
                err = e
                time.sleep(0.8 * (attempt + 1))
        if err and not claims:
            # write an empty chunk attempt record but continue (we aggregate across chunks)
            pass
        raw_merged += (raw_text or "") + "\n"
        all_claims.extend(claims)
    all_claims = dedupe_claims(all_claims)
    write_doc_output(doc, model=model, prompt=f"[{len(chunks)} chunks] " + build_user_prompt(doc.title, doc.filename, doc.text[:2000]), raw_text=raw_merged, claims=all_claims)
    logger.info("Finished: %s | %s | chunks=%d | claims=%d", doc.party, doc.filename, len(chunks), len(all_claims))
    return (doc.party, doc.filename, len(all_claims))


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Extract claims from press releases using an LLM (gpt-4o-mini)")
    ap.add_argument("--from-pilot", default="", help="Path to outputs/pilot to restrict to pilot docs")
    ap.add_argument("--party", default="both", choices=["both", "Democratic", "Republican"])
    ap.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--limit", type=int, default=-1, help="Limit number of docs (after filtering)")
    ap.add_argument("--resume", action="store_true", help="Skip unchanged docs by comparing content hash")
    ap.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"), help="Logging level (e.g., DEBUG, INFO)")
    ap.add_argument("--log-file", default=str(LOG_DIR / "llm_claims.log"), help="Path to write rotating log file")
    ap.add_argument("--progress-every", type=int, default=50, help="Log a progress summary every N documents")
    return ap.parse_args(list(argv) if argv is not None else None)


def configure_logging(level: str, log_file: str) -> None:
    # Ensure both default logs dir and the passed log file's parent exist
    ensure_dir(LOG_DIR)
    try:
        ensure_dir(Path(log_file).parent)
    except Exception:
        pass
    logger = logging.getLogger("llm_claims")
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    logger.handlers = []
    # Console handler
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(ch)
    # Rotating file handler
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level, args.log_file)
    logger = logging.getLogger("llm_claims")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set", file=sys.stderr)
        return 2
    client = OpenAI()

    ensure_dir(OUT_BASE)
    ensure_dir(RAW_DIR)

    parties = ["Democratic", "Republican"] if args.party == "both" else [args.party]

    # Collect documents
    if args.from_pilot:
        docs = collect_docs_from_pilot(Path(args.from_pilot), parties=parties, limit=args.limit)
    else:
        docs = collect_docs_all(parties=parties, limit=args.limit)
    if not docs:
        print("No documents found to process.", file=sys.stderr)
        return 1
    logger.info("Starting extraction | parties=%s | total_docs=%d | model=%s | parallel=%d | resume=%s",
                ",".join(parties), len(docs), args.model, args.parallel, bool(args.resume))

    # Process in parallel
    results: List[Tuple[str, str, int]] = []
    processed = 0
    skipped = 0
    errored = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        fut_to_doc = {ex.submit(process_doc, client, args.model, d, bool(args.resume)): d for d in docs}
        for fut in concurrent.futures.as_completed(fut_to_doc):
            d = fut_to_doc[fut]
            try:
                res = fut.result()
            except Exception as e:
                logger.error("Error processing %s | %s: %s", d.party, d.filename, e)
                res = (d.party, d.filename, -2)  # -2 error
            results.append(res)
            processed += 1
            if res[2] == -1:
                skipped += 1
            elif res[2] == -2:
                errored += 1
            if args.progress_every > 0 and (processed % args.progress_every == 0):
                logger.info("Progress: %d/%d processed | skipped=%d | errors=%d", processed, len(docs), skipped, errored)

    # Aggregate to compact JSONs
    dem_path, rep_path = aggregate_compact_claims()
    logger.info("Completed extraction | processed=%d | skipped=%d | errors=%d", processed, skipped, errored)
    print(json.dumps({"processed": len(results), "outputs": {"dem": str(dem_path), "rep": str(rep_path)}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


