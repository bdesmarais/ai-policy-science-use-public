#!/usr/bin/env python3
"""
LLM-backed reference finder using OpenAI GPT-5 (or compatible).

Workflow:
1) Read claim lists from outputs/claims/dem_claims.json and rep_claims.json
2) For each claim, ask the model to return compact, structured references
3) De-duplicate by DOI or title+year
4) Write outputs/structured_refs/dem_claim_references.json and rep_claim_references.json

Environment:
- OPENAI_API_KEY must be set

Usage:
  python gpt_references.py --limit 50 --model gpt-5 --per-claim 50
"""

import argparse
import json
import os
import random
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import logging

try:
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    raise RuntimeError("Please install openai >= 1.0.0")


DEFAULT_CLAIMS_DIR = os.path.join("outputs", "claims")
DEFAULT_OUTPUT_DIR = os.path.join("outputs", "structured_refs")


def ensure_dir(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


SYSTEM_PROMPT = (
    "You are a concise research assistant. Given a policy claim, return a list of scientific references (peer-reviewed papers or trusted preprints). "
    "Prioritize precision over quantity: include only references that directly address, support, or challenge the claim. "
    "If no relevant evidence is found, return an empty list. "
    "Return ONLY a JSON object with key 'references' whose value is an array of objects with fields: "
    "provider (discovery source such as 'arXiv', 'publisher', 'Crossref', 'OpenAlex'), id (best persistent id), doi, title, abstract (1-2 sentence summary if not available), year, venue (actual journal or conference; use 'arXiv' only if preprint-only), authors, url, is_open_access. "
    "Rules: (1) Do not fabricate DOIs or venues. (2) If DOI is unknown, set doi=null and provide a reputable URL (publisher or arXiv). "
    "(3) Keep titles factual (no invented titles). (4) Omit references that do not meaningfully pertain to the claim even if they mention similar keywords. "
    "Venue naming: prefer standard short forms where applicable (NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV, AAAI, IJCAI, ACL, EMNLP, NAACL, KDD, The Web Conference, SIGIR; journals like Nature, Science, PNAS, JMLR). "
    "Do not include any text outside the JSON."
)


def build_user_prompt(claim: Dict[str, Any], per_claim: int) -> str:
    # Keep prompt short to minimize tokens
    press_release = claim.get("press_release")
    claim_number = claim.get("claim_number")
    claim_text = claim.get("claim_text")
    claim_desc = claim.get("claim_desc")
    prompt = (
        "Task: Provide up to {k} scientific references that are directly relevant to the claim. If none are appropriate, return an empty list.\n"
        "Context: California legislative press release analysis.\n"
        "Claim ({press_release} / #{num}): {text}\n"
        "{maybe_desc}"
        "Constraints:\n"
        "- Prioritize peer-reviewed sources.\n"
        "- Include DOI when available.\n"
        "- Keep abstracts to 1-2 sentence summaries if exact abstracts not available.\n"
        "- Prefer recency for fast-moving topics (e.g., deepfakes, LLMs), else include seminal works.\n"
        "- provider = discovery source (e.g., 'arXiv' if link is on arxiv.org; 'publisher' for publisher site);\n"
        "- venue = actual journal or conference (use 'arXiv' only if there is no published venue).\n"
        "- Normalize venue names to standard short forms (e.g., NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV, AAAI, IJCAI, ACL, EMNLP, NAACL).\n"
        "Output: JSON object {{\"references\": [{{provider,id,doi,title,abstract,year,venue,authors,url,is_open_access}}...]}}.\n"
    ).format(
        k=per_claim,
        press_release=press_release,
        num=claim_number,
        text=claim_text,
        maybe_desc=(f"Claim description: {claim_desc}\n" if claim_desc else ""),
    )
    return prompt


def build_user_prompt_force(claim: Dict[str, Any], per_claim: int) -> str:
    press_release = claim.get("press_release")
    claim_number = claim.get("claim_number")
    claim_text = claim.get("claim_text")
    return (
        "Return references relevant to the claim (only if they genuinely match the topic; otherwise return an empty list).\n"
        "Claim ({press_release} / #{num}): {text}\n"
        "Focus on pinpointing rigorous evidence; avoid filler citations.\n"
        "Set doi=null if unknown and include a reliable URL (publisher/arXiv).\n"
        "Use provider as discovery source (e.g., arXiv/publisher) and venue as the actual journal/conference (or 'arXiv' if preprint-only).\n"
        "Normalize venue names (e.g., NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV, AAAI, IJCAI, ACL, EMNLP, NAACL).\n"
        "Output only: {{\"references\": [...]}}\n"
    ).format(k=per_claim, press_release=press_release, num=claim_number, text=claim_text)


def _response_to_text(resp: Any) -> str:
    # Try modern Responses API convenience
    text = getattr(resp, "output_text", None)
    if isinstance(text, str) and text:
        return text
    # Fallback: some clients expose .output with .content[].text[]
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
    # Last resort: stringify
    try:
        return str(resp)
    except Exception:
        return ""


def call_openai(client: OpenAI, model: str, prompt: str, search_context_size: str) -> str:
    # Responses API with web_search tool and JSON schema
    schema = {
        "name": "references_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "provider": {"type": ["string", "null"]},
                            "id": {"type": ["string", "null"]},
                            "doi": {"type": ["string", "null"]},
                            "title": {"type": ["string", "null"]},
                            "abstract": {"type": ["string", "null"]},
                            "year": {"type": ["integer", "string", "null"]},
                            "venue": {"type": ["string", "null"]},
                            "authors": {"type": ["array", "null"], "items": {"type": "string"}},
                            "url": {"type": ["string", "null"]},
                            "is_open_access": {"type": ["boolean", "null"]},
                        },
                        "required": ["title"],
                        "additionalProperties": True,
                    },
                }
            },
            "required": ["references"],
            "additionalProperties": False,
        },
    }

    tool = {"type": "web_search", "search_context_size": search_context_size}
    variants = [
        {"tools": [tool], "response_format": {"type": "json_schema", "json_schema": schema}},
        {"tools": [tool]},
        {"response_format": {"type": "json_schema", "json_schema": schema}},
        {},
    ]

    last_err: Optional[Exception] = None
    for extra in variants:
        try:
            resp = client.responses.create(
                model=model,
                input=(SYSTEM_PROMPT + "\n\n" + prompt),
                **extra,
            )
            return _response_to_text(resp)
        except Exception as e:
            last_err = e
            continue
    raise last_err  # type: ignore[misc]


def _extract_json_payload(text: str) -> Optional[str]:
    # Try to find a balanced JSON object first
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass
    # Try to find a JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass
    return None


def parse_references(json_text: str) -> List[Dict[str, Any]]:
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
    # Accept either top-level array or object with 'references'
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("references"), list):
        items = data.get("references")
    else:
        # Try to find a list anywhere
        items = []
        for v in data.values() if isinstance(data, dict) else []:
            if isinstance(v, list):
                items = v
                break
    norm: List[Dict[str, Any]] = []
    def _normalize_venue(name: Optional[str]) -> Optional[str]:
        if not name:
            return name
        s = str(name).strip()
        # Map common variants to canonical short forms
        mapping = {
            "neurips": "NeurIPS",
            "nips": "NeurIPS",
            "icml": "ICML",
            "iclr": "ICLR",
            "aaai": "AAAI",
            "ijcai": "IJCAI",
            "cvpr": "CVPR",
            "iccv": "ICCV",
            "eccv": "ECCV",
            "acl": "ACL",
            "emnlp": "EMNLP",
            "naacl": "NAACL",
            "kdd": "KDD",
            "www": "The Web Conference",
            "sigir": "SIGIR",
            "journal of machine learning research": "JMLR",
            "proceedings of the national academy of sciences": "PNAS",
        }
        key = s.lower()
        return mapping.get(key, s)
    for it in items:
        if not isinstance(it, dict):
            continue
        norm.append(
            {
                "provider": it.get("provider"),
                "id": it.get("id"),
                "doi": it.get("doi"),
                "title": it.get("title"),
                "abstract": it.get("abstract"),
                "year": it.get("year"),
                "venue": _normalize_venue(it.get("venue")),
                "authors": it.get("authors") if isinstance(it.get("authors"), list) else [],
                "url": it.get("url"),
                "is_open_access": bool(it.get("is_open_access")) if it.get("is_open_access") is not None else None,
            }
        )
    return norm


def dedupe_references(refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for r in refs:
        doi = (r.get("doi") or "").strip().lower()
        if doi:
            key = ("doi", doi)
        else:
            title = (r.get("title") or "").strip().lower()
            year = r.get("year")
            key = ("title", title, str(year) if year is not None else "")
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


ANCHOR_TOKENS = {
    "ai", "artificial", "intelligence", "ml", "machine", "learning", "deepfake", "deepfakes",
    "watermark", "watermarking", "provenance", "algorithm", "algorithms", "automated", "automation",
    "decision", "decisions", "bias", "fairness", "safety", "risk", "privacy", "data", "surveillance",
    "facial", "recognition", "content", "moderation", "llm", "gpt", "chatgpt", "foundation", "model",
    "generative", "genai", "robotics", "autonomous", "predictive", "analytics"
}


def _tokenize_set(text: Optional[str]) -> set:
    if not text:
        return set()
    cleaned = "".join(ch.lower() if (ch.isalnum() or ch.isspace()) else " " for ch in text)
    toks = {tok for tok in cleaned.split() if tok and len(tok) > 2}
    return toks


def filter_references(claim_text: str, references: List[Dict[str, Any]], min_overlap: int) -> Tuple[List[Dict[str, Any]], int]:
    claim_tokens = _tokenize_set(claim_text)
    kept: List[Dict[str, Any]] = []
    dropped = 0
    for ref in references:
        title_tokens = _tokenize_set(ref.get("title"))
        abstract_tokens = _tokenize_set(ref.get("abstract"))
        overlap = len(claim_tokens & title_tokens)
        extra_overlap = len((claim_tokens - title_tokens) & abstract_tokens)
        total_overlap = overlap + extra_overlap
        anchor_hit = len((claim_tokens & ANCHOR_TOKENS) & (title_tokens | abstract_tokens)) > 0
        if total_overlap >= min_overlap or (anchor_hit and total_overlap >= 1):
            kept.append(ref)
        else:
            dropped += 1
    return kept, dropped


def load_json_list(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _key_for_claim(claim: Dict[str, Any]) -> Tuple[str, Any]:
    return (str(claim.get("press_release")), claim.get("claim_number"))


def _load_existing_by_key(path: str) -> Dict[Tuple[str, Any], Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result: Dict[Tuple[str, Any], Dict[str, Any]] = {}
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    k = (str(row.get("press_release")), row.get("claim_number"))
                    result[k] = row
        return result
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def process_side(
    client: OpenAI,
    model: str,
    claims_path: str,
    out_path: str,
    limit: int,
    per_claim: int,
    timeout: float,
    sleep_s: float,
    resume: bool,
    sample_size: int,
    sample_seed: int,
    min_overlap: int,
) -> None:
    logger = logging.getLogger("gpt_refs")
    claims = load_json_list(claims_path)
    if limit >= 0:
        claims = claims[:limit]

    if sample_size > 0 and len(claims) > sample_size:
        indexed = list(enumerate(claims))
        rng = random.Random(sample_seed)
        selected = rng.sample(indexed, sample_size)
        selected.sort(key=lambda x: x[0])
        claims = [item for _, item in selected]
        logger.info("Sampled %d claims (of %d) from %s", len(claims), len(indexed), claims_path)

    existing_by_key: Dict[Tuple[str, Any], Dict[str, Any]] = _load_existing_by_key(out_path) if resume else {}
    out_rows: List[Dict[str, Any]] = []
    for idx, claim in enumerate(claims, start=1):
        press_release = claim.get("press_release")
        claim_number = claim.get("claim_number")
        claim_text = claim.get("claim_text")
        logger.info(f"Claim {idx}/{len(claims)} from '{press_release}' (claim_number={claim_number})")

        # If resuming and we already have this claim, reuse it without another API call
        k = _key_for_claim(claim)
        if resume and k in existing_by_key:
            out_rows.append(existing_by_key[k])
            # Write incrementally to keep progress
            write_json(out_path, out_rows)
            continue

        error: Optional[str] = None
        references: List[Dict[str, Any]] = []
        raw_preview: Optional[str] = None
        raw_text: Optional[str] = None
        attempts_meta: List[Dict[str, Any]] = []
        prompts = [
            ("medium", build_user_prompt(claim, per_claim=per_claim)),
            ("high", build_user_prompt_force(claim, per_claim=per_claim)),
        ]
        for attempt_idx, (search_size, prompt) in enumerate(prompts, start=1):
            try:
                raw = call_openai(client, model=model, prompt=prompt, search_context_size=search_size)
                raw_text = raw
                raw_preview = (raw or "")[:300]
                refs = dedupe_references(parse_references(raw))
                references = refs[: per_claim if per_claim > 0 else None]
                attempts_meta.append({"attempt": attempt_idx, "search_context_size": search_size, "references": len(references)})
                if references or attempt_idx == len(prompts):
                    break
            except Exception as e:
                error = (error or "") + f"; attempt_{attempt_idx}_error={e}"
                attempts_meta.append({"attempt": attempt_idx, "search_context_size": search_size, "error": str(e)})
                logger.error(f"Error fetching refs (attempt {attempt_idx}): {e}")

        filtered_refs, dropped = filter_references(claim_text or "", references, min_overlap=min_overlap) if references else ([], 0)

        out_rows.append(
            {
                "press_release": press_release,
                "claim_number": claim_number,
                "claim_text": claim_text,
                "query": prompts[0][1],
                "references": filtered_refs,
                "num_references": len(filtered_refs),
                "search_metadata": {
                    "provider": "openai",
                    "attempted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "error": error,
                    "model": model,
                    "raw_preview": raw_preview,
                    "attempts": attempts_meta,
                    "post_filter_kept": len(filtered_refs),
                    "post_filter_dropped": dropped,
                    "raw_text": raw_text,
                },
            }
        )
        write_json(out_path, out_rows)
        time.sleep(max(0.0, sleep_s))


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Find references with GPT-5")
    ap.add_argument("--claims-dir", default=DEFAULT_CLAIMS_DIR)
    ap.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--limit", type=int, default=-1)
    ap.add_argument("--per-claim", type=int, default=25)
    ap.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-5"))
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    ap.add_argument("--resume", action="store_true", help="Reuse already-written claim rows in output files and skip new API calls for them")
    ap.add_argument("--sample-per-party", type=int, default=-1, help="Sample N claims per party (after limit)")
    ap.add_argument("--sample-seed", type=int, default=20251113, help="Random seed for sampling")
    ap.add_argument("--min-overlap", type=int, default=2, help="Minimum token overlap between claim and reference title/abstract to keep a reference")
    return ap.parse_args(argv if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("gpt_refs")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI()

    dem_claims = os.path.join(args.claims_dir, "dem_claims.json")
    rep_claims = os.path.join(args.claims_dir, "rep_claims.json")
    dem_out = os.path.join(args.output_dir, "dem_claim_references.json")
    rep_out = os.path.join(args.output_dir, "rep_claim_references.json")

    logger.info("Processing Democratic claims")
    process_side(
        client,
        model=args.model,
        claims_path=dem_claims,
        out_path=dem_out,
        limit=args.limit,
        per_claim=args.per_claim,
        timeout=args.timeout,
        sleep_s=args.sleep,
        resume=args.resume,
        sample_size=args.sample_per_party,
        sample_seed=args.sample_seed,
        min_overlap=max(0, args.min_overlap),
    )
    logger.info("Processing Republican claims")
    process_side(
        client,
        model=args.model,
        claims_path=rep_claims,
        out_path=rep_out,
        limit=args.limit,
        per_claim=args.per_claim,
        timeout=args.timeout,
        sleep_s=args.sleep,
        resume=args.resume,
        sample_size=args.sample_per_party,
        sample_seed=args.sample_seed,
        min_overlap=max(0, args.min_overlap),
    )
    logger.info("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


