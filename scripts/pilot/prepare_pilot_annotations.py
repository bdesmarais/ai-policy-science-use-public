#!/usr/bin/env python3
import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

"""
Prepare pilot annotation assignments:
- Sample 25 documents per cell (Dem/Rep × AI/Non-AI) deterministically
- Split evenly into Zack/Sai (with duplication for double-annotate)
- From AI-relevant sampled docs, sample up to 3 claims/doc
- Join sampled claims to structured references and take top-K refs per claim
- Write outputs to outputs/pilot/

Claims source can be chosen:
- csv (default): data/structured_claims/{Demsfull_AI_LMclaims.csv, Rep_AI_LMclaims.csv}
- llm: outputs/claims/{dem_claims.json, rep_claims.json}
"""

WORKSPACE = Path(__file__).parent
SEED = 20250101
ASSIGNEES = ["Zack", "Sai"]


def read_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def assign_with_double(rows: List[Dict[str, Any]], double_ratio: float) -> List[Dict[str, Any]]:
    """
    Assigns rows alternately to Zack/Sai and duplicates ~double_ratio for double annotation.
    """
    out: List[Dict[str, Any]] = []
    rng = random.Random(SEED + 17)
    n = len(rows)
    # Choose a deterministic subset for double annotation
    k = max(1, int(round(n * double_ratio))) if n > 0 else 0
    double_indices = set()
    if n > 0:
        double_indices = set(rng.sample(range(n), min(k, n)))
    # Alternating assignment
    for i, row in enumerate(rows):
        assignee = ASSIGNEES[i % len(ASSIGNEES)]
        r1 = dict(row)
        r1["assigned_to"] = assignee
        r1["double_annotate"] = 1 if i in double_indices else 0
        out.append(r1)
        if i in double_indices:
            other = ASSIGNEES[1 - (i % len(ASSIGNEES))]
            r2 = dict(row)
            r2["assigned_to"] = other
            r2["double_annotate"] = 1
            out.append(r2)
    return out


def map_party(source_val: str) -> str:
    s = (source_val or "").strip().lower()
    if "democratic" in s:
        return "Democratic"
    if "republican" in s:
        return "Republican"
    return "Unknown"


def load_claims(claims_source: str = "csv", llm_claims_dir: Optional[Path] = None) -> Dict[Tuple[str, str], List[Dict[str, str]]]:
    """
    Returns mapping: (party, press_release) -> list of claim rows.
    claims_source: 'csv' (default) or 'llm'
    """
    claims_map: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    source = (claims_source or "csv").strip().lower()
    if source == "llm":
        base = llm_claims_dir if llm_claims_dir is not None else (WORKSPACE / "outputs" / "claims")
        dem_path = base / "dem_claims.json"
        rep_path = base / "rep_claims.json"
        for party, path in (("Democratic", dem_path), ("Republican", rep_path)):
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    rows = json.load(f)
            except Exception:
                rows = []
            for r in rows:
                pr = (r.get("press_release") or "").strip()
                if not pr:
                    continue
                claims_map.setdefault((party, pr), []).append(r)
        return claims_map
    # default: CSV source
    dem_csv = WORKSPACE / "data" / "structured_claims" / "Demsfull_AI_LMclaims.csv"
    rep_csv = WORKSPACE / "data" / "structured_claims" / "Rep_AI_LMclaims.csv"
    for party, path in (("Democratic", dem_csv), ("Republican", rep_csv)):
        if not path.exists():
            continue
        rows = read_csv(path)
        for r in rows:
            pr = (r.get("press_release") or "").strip()
            if not pr:
                continue
            claims_map.setdefault((party, pr), []).append(r)
    return claims_map


def load_structured_refs() -> Dict[Tuple[str, Any], List[Dict[str, Any]]]:
    """
    Returns mapping: (press_release, claim_number) -> references list
    """
    refs_map: Dict[Tuple[str, Any], List[Dict[str, Any]]] = {}
    for path in [
        WORKSPACE / "outputs" / "structured_refs" / "dem_claim_references.json",
        WORKSPACE / "outputs" / "structured_refs" / "rep_claim_references.json",
    ]:
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for row in data:
            pr = row.get("press_release")
            cn = row.get("claim_number")
            refs = row.get("references") or []
            refs_map[(str(pr), cn)] = refs
    return refs_map


def prepare_pilot(
    outputs_v3_dir: Path,
    out_dir: Path,
    docs_per_cell: int,
    top_refs_per_claim: int,
    tighten_docs: bool = False,
    tighten_claims: bool = False,
    tighten_pairs: bool = False,
    double_ratio_docs: float = 0.15,
    double_ratio_claims: float = 0.15,
    double_ratio_pairs: float = 0.15,
    claims_source: str = "csv",
    llm_claims_dir: Optional[Path] = None,
) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ai_docs_csv = outputs_v3_dir / "ai_documents_v3.csv"
    if not ai_docs_csv.exists():
        print("ai_documents_v3.csv not found. Run analyze_press_releases_v3.py first.", file=sys.stderr)
        sys.exit(2)
    docs = read_csv(ai_docs_csv)

    # Helper: strong AI lexicon presence from matched_ai_terms
    def has_strong_ai_terms(term_str: str) -> bool:
        strong = {
            "large language model","llm","chatgpt","foundation model",
            "deepfake","watermark","watermarking","content authenticity","provenance",
            "automated decision","algorithmic decision","ads","adt",
            "facial recognition","voice cloning","hallucination","hallucinations","csam"
        }
        terms = [t.strip().lower() for t in (term_str or "").split(";") if t.strip()]
        term_set = set(terms)
        return any(s in term_set for s in strong)

    # build four cells
    cells: Dict[Tuple[str, str], List[Dict[str, Any]]] = {("Democratic", "ai"): [], ("Democratic", "nonai"): [], ("Republican", "ai"): [], ("Republican", "nonai"): []}
    for d in docs:
        party = map_party(d.get("source", ""))
        try:
            ai_count = int(d.get("ai_statement_count", "0") or 0)
        except Exception:
            ai_count = 0
        ai_cat = "ai" if ai_count > 0 else "nonai"
        if tighten_docs:
            # Require >=2 statements, or >=1 with strong terms
            matched_terms = d.get("matched_ai_terms", "")
            strong_hit = has_strong_ai_terms(matched_terms)
            if ai_count >= 2 or (ai_count >= 1 and strong_hit):
                ai_cat = "ai"
            else:
                ai_cat = "nonai"
        if party not in ("Democratic", "Republican"):
            continue
        row = dict(d)
        row["party"] = party
        row["ai_category"] = ai_cat
        cells[(party, ai_cat)].append(row)

    rng = random.Random(SEED)
    sampled_cells: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for key, rows in cells.items():
        rows_shuffled = list(rows)
        rng.shuffle(rows_shuffled)
        sampled_cells[key] = rows_shuffled[:docs_per_cell] if docs_per_cell >= 0 else rows_shuffled

    # write per-cell docs files and combined assignments (with assignment + double annotation duplication)
    combined: List[Dict[str, Any]] = []
    cell_paths: Dict[str, Path] = {}
    for (party, cat), rows in sampled_cells.items():
        assigned = assign_with_double(rows, double_ratio_docs)
        fn = out_dir / f"docs_{'dem' if party=='Democratic' else 'rep'}_{cat}.csv"
        fieldnames = list(rows[0].keys()) + ["assigned_to", "double_annotate"] if rows else ["source","filename","party","ai_category","assigned_to","double_annotate"]
        write_csv(fn, assigned, fieldnames)
        cell_paths[f"{party}_{cat}"] = fn
        combined.extend(assigned)
    # Combined file
    combined_fields = sorted({k for r in combined for k in r.keys()})
    docs_assign_path = out_dir / "pilot_docs_assignments.csv"
    write_csv(docs_assign_path, combined, combined_fields)

    # Claims sampling only for AI-relevant docs (use up to 3 claims/doc), retain assignee + double
    claims_map = load_claims(claims_source=claims_source, llm_claims_dir=llm_claims_dir)
    claims_out: List[Dict[str, Any]] = []
    def is_policy_claim(text: str) -> bool:
        t = (text or "").lower()
        patterns = [
            " should ", " must ", " shall ", " will ",
            " prohibits ", " ban ", " bans ", " prohibit ",
            " require ", " requires ", " mandated ", " mandate ",
            " fund ", " funds ", " funding ",
            " establish ", " establishs ", " establishes ",
            " ensure ", " ensures ",
            " prohibit ", " restrict ", " restricts ",
        ]
        return any(p in f" {t} " for p in patterns)
    # Build mapping of doc->assignees for double-duplication logic
    doc_assignments: Dict[Tuple[str, str], List[str]] = {}
    for r in combined:
        pr = r.get("filename")
        party = r.get("party")
        if not pr or party not in ("Democratic", "Republican"):
            continue
        key = (party, str(pr))
        doc_assignments.setdefault(key, []).append(r.get("assigned_to", ""))
    for (party, cat), rows in sampled_cells.items():
        if cat != "ai":
            continue
        for d in rows:
            pr = str(d.get("filename"))
            key = (party, pr)
            claim_rows = claims_map.get(key, [])
            if not claim_rows:
                continue
            rng2 = random.Random(SEED + hash((party, pr)) % 100000)
            rng2.shuffle(claim_rows)
            # optionally filter claims by policy patterns before sampling
            filtered = claim_rows
            if tighten_claims:
                filtered = [c for c in claim_rows if is_policy_claim(c.get("claim_text",""))]
                if not filtered:
                    filtered = claim_rows
            selected = filtered[:3]
            # for each selected claim, duplicate rows per assignee (handles double-annotate duplication)
            assignees = doc_assignments.get(key, ["Zack"])
            for c in selected:
                for who in assignees:
                    claims_out.append({
                        "press_release": pr,
                        "party": party,
                        "claim_number": c.get("claim_number"),
                        "claim_text": c.get("claim_text"),
                        "claim_desc": c.get("claim_desc") or "",
                        "assigned_to": who or "",
                        "double_annotate": 1 if len(assignees) > 1 else 0,
                    })
    claim_fields = ["press_release","party","claim_number","claim_text","claim_desc","assigned_to","double_annotate"]
    claims_assign_path = out_dir / "pilot_claims_assignments.csv"
    write_csv(claims_assign_path, claims_out, claim_fields)

    # Pairs (stance): join claims to references; take top-K
    refs_map = load_structured_refs()
    pairs_out: List[Dict[str, Any]] = []
    for cr in claims_out:
        pr = str(cr["press_release"])
        cn = cr["claim_number"]
        refs = refs_map.get((pr, cn), [])
        top_refs = refs[:top_refs_per_claim] if top_refs_per_claim >= 0 else refs
        # gating: minimal token overlap between claim and ref
        def passes_overlap(claim_text: str, ref: Dict[str, Any]) -> bool:
            if not tighten_pairs:
                return True
            def toks(s: str) -> set:
                return set("".join(ch if (ch.isalnum() or ch == " ") else " " for ch in (s or "").lower()).split())
            c = toks(claim_text)
            t = toks(ref.get("title",""))
            a = toks(ref.get("abstract",""))
            anchors = {"ai","ml","llm","gpt","deepfake","watermark","provenance","facial","recognition","algorithm","bias","fairness","hallucination","csam","automated","decision"}
            # Require at least 2 overlaps with title or (1 anchor & 1 other)
            overlap = len(c & t) + len((c - t) & a)
            anchor_hit = len((c & anchors) & (t | a)) > 0
            return overlap >= 2 or (anchor_hit and overlap >= 1)
        # construct a stable ref uid
        for ref in top_refs:
            if tighten_pairs and not passes_overlap(cr.get("claim_text",""), ref):
                continue
            doi = (ref.get("doi") or "").strip()
            rid = None
            if doi:
                rid = f"doi:{doi.lower()}"
            else:
                rid = ref.get("id") or ref.get("url") or ""
            pairs_out.append({
                "press_release": pr,
                "party": cr["party"],
                "claim_number": cn,
                "claim_text": cr.get("claim_text",""),
                "ref_uid": rid,
                "title": ref.get("title"),
                "abstract": ref.get("abstract"),
                "venue": ref.get("venue"),
                "year": ref.get("year"),
                "doi": ref.get("doi"),
                "url": ref.get("url"),
                "assigned_to": cr["assigned_to"],
                "double_annotate": cr["double_annotate"],
            })
    pair_fields = ["press_release","party","claim_number","claim_text","ref_uid","title","abstract","venue","year","doi","url","assigned_to","double_annotate"]
    pairs_assign_path = out_dir / "pilot_pairs_assignments.csv"
    write_csv(pairs_assign_path, pairs_out, pair_fields)

    # Per-assignee splits
    zack_dir = out_dir / "zack"
    sai_dir = out_dir / "sai"
    zack_dir.mkdir(parents=True, exist_ok=True)
    sai_dir.mkdir(parents=True, exist_ok=True)

    def _split_and_write(rows: List[Dict[str, Any]], fields: List[str], basename: str) -> Tuple[Path, Path]:
        z_rows = [r for r in rows if (r.get("assigned_to") or "").lower().startswith("zack")]
        s_rows = [r for r in rows if (r.get("assigned_to") or "").lower().startswith("sai")]
        z_path = zack_dir / f"{basename}_zack.csv"
        s_path = sai_dir / f"{basename}_sai.csv"
        write_csv(z_path, z_rows, fields)
        write_csv(s_path, s_rows, fields)
        return z_path, s_path

    # Documents
    _ = _split_and_write(combined, combined_fields, "docs_assignments")
    # Claims
    _ = _split_and_write(claims_out, claim_fields, "claims_assignments")
    # Pairs
    _ = _split_and_write(pairs_out, pair_fields, "pairs_assignments")

    return {
        "docs_assignments": docs_assign_path,
        "claims_assignments": claims_assign_path,
        "pairs_assignments": pairs_assign_path,
        **cell_paths,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare pilot annotation assignments for docs, claims, and pairs")
    ap.add_argument("--outputs-v3-dir", default=str(WORKSPACE / "outputs" / "v3"))
    ap.add_argument("--out-dir", default=str(WORKSPACE / "outputs" / "pilot"))
    ap.add_argument("--docs-per-cell", type=int, default=25)
    ap.add_argument("--top-refs-per-claim", type=int, default=5)
    ap.add_argument("--tighten-docs", action="store_true", help="Use stricter AI doc relevance threshold")
    ap.add_argument("--tighten-claims", action="store_true", help="Filter claims by policy pattern rules")
    ap.add_argument("--tighten-pairs", action="store_true", help="Gate claim–reference pairs by minimal token overlap")
    ap.add_argument("--claims-source", choices=["csv", "llm"], default="csv", help="Source of claims used for sampling")
    ap.add_argument("--llm-claims-dir", default=str(WORKSPACE / "outputs" / "claims"), help="Directory containing dem_claims.json and rep_claims.json when using --claims-source llm")
    args = ap.parse_args()

    paths = prepare_pilot(
        Path(args.outputs_v3_dir),
        Path(args.out_dir),
        args.docs_per_cell,
        args.top_refs_per_claim,
        tighten_docs=bool(args.tighten_docs),
        tighten_claims=bool(args.tighten_claims),
        tighten_pairs=bool(args.tighten_pairs),
        claims_source=str(args.claims_source),
        llm_claims_dir=Path(args.llm_claims_dir) if args.claims_source == "llm" else None,
    )
    print({k: str(v) for k, v in paths.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


