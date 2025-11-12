#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Any, Tuple

"""
Triage false positives by stage using pilot annotation CSVs (per-assignee).
Stages:
  A) Doc AI relevance: ai_category vs ai_relevance
  B) Claim extraction: is_claim, claim_boundary_ok, topic_ai_relevant
  C) Claim–reference: relevance, coverage (and stance distribution)

Writes JSON and CSV summaries under outputs/pilot/triage/.
"""

WORKSPACE = Path(__file__).parent


def read_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def triage_docs(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    # FP if sampler marked AI (ai_category == 'ai') but annotator says 0_none or 1_tangential
    total = 0
    fps = 0
    bins = Counter()
    examples: List[Dict[str, str]] = []
    for r in rows:
        ai_cat = (r.get("ai_category") or "").strip().lower()
        lab = (r.get("ai_relevance") or r.get("ai_relevance_pred") or "").strip()
        if lab == "":
            continue
        total += 1
        # normalize labels
        lab_norm = lab.split("_")[0] if "_" in lab else lab
        if ai_cat == "ai" and lab_norm in ("0", "1", "0none", "1tangential"):
            fps += 1
            if len(examples) < 25:
                examples.append({"source": r.get("source",""), "filename": r.get("filename",""), "ai_category": ai_cat, "ai_relevance": lab})
        bins[lab_norm] += 1
    rate = round(fps / total, 4) if total else None
    return {"total_scored": total, "false_positives": fps, "fp_rate": rate, "label_hist": dict(bins), "examples": examples}


def triage_claims(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    total = 0
    fps = 0
    reasons = Counter()
    examples: List[Dict[str, str]] = []
    for r in rows:
        is_claim = (r.get("is_claim") or "").strip()
        boundary = (r.get("claim_boundary_ok") or "").strip()
        topic = (r.get("topic_ai_relevant") or "").strip()
        if is_claim == "" and boundary == "" and topic == "":
            continue
        total += 1
        bad = False
        if is_claim == "0":
            reasons["not_claim"] += 1
            bad = True
        if boundary == "0":
            reasons["boundary_bad"] += 1
            bad = True
        if topic in ("0", "1"):  # not AI or tangential at claim level
            reasons["topic_not_central"] += 1
            bad = True
        if bad:
            fps += 1
            if len(examples) < 25:
                examples.append({"press_release": r.get("press_release",""), "claim_number": r.get("claim_number",""), "claim_text": r.get("claim_text","")})
    rate = round(fps / total, 4) if total else None
    return {"total_scored": total, "flagged": fps, "flag_rate": rate, "reason_hist": dict(reasons), "examples": examples}


def triage_pairs(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    total = 0
    fps = 0
    stance_hist = Counter()
    examples: List[Dict[str, str]] = []
    for r in rows:
        rel = (r.get("relevance") or "").strip()
        cov = (r.get("coverage") or "").strip()
        stance = (r.get("stance") or "").strip()
        if rel == "" and cov == "" and stance == "":
            continue
        total += 1
        if rel == "0" or cov == "0":
            fps += 1
            if len(examples) < 25:
                examples.append({"press_release": r.get("press_release",""), "claim_number": r.get("claim_number",""), "title": r.get("title","")})
        if stance:
            stance_hist[stance] += 1
    rate = round(fps / total, 4) if total else None
    return {"total_scored": total, "flagged": fps, "flag_rate": rate, "stance_hist": dict(stance_hist), "examples": examples}


def main() -> int:
    ap = argparse.ArgumentParser(description="Triage false positives by stage using pilot annotation CSVs")
    ap.add_argument("--pilot-dir", default=str(WORKSPACE / "outputs" / "pilot"))
    args = ap.parse_args()
    pdir = Path(args.pilot_dir)
    out_dir = pdir / "triage"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Aggregate both assignees if present
    inputs = {
        "docs": [pdir / "pilot_docs_assignments.csv", pdir / "zack" / "docs_assignments_zack.csv", pdir / "sai" / "docs_assignments_sai.csv"],
        "claims": [pdir / "pilot_claims_assignments.csv", pdir / "zack" / "claims_assignments_zack.csv", pdir / "sai" / "claims_assignments_sai.csv"],
        "pairs": [pdir / "pilot_pairs_assignments.csv", pdir / "zack" / "pairs_assignments_zack.csv", pdir / "sai" / "pairs_assignments_sai.csv"],
    }
    docs_rows: List[Dict[str, str]] = []
    claims_rows: List[Dict[str, str]] = []
    pairs_rows: List[Dict[str, str]] = []
    for p in inputs["docs"]:
        docs_rows.extend(read_csv(p))
    for p in inputs["claims"]:
        claims_rows.extend(read_csv(p))
    for p in inputs["pairs"]:
        pairs_rows.extend(read_csv(p))

    summary = {
        "docs": triage_docs(docs_rows),
        "claims": triage_claims(claims_rows),
        "pairs": triage_pairs(pairs_rows),
    }
    with open(out_dir / "triage_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


