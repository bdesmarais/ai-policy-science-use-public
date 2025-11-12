#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Tuple, Any

"""
Compute agreement and baseline metrics for pilot annotations.
Expects pilot assignment CSVs with labels filled by annotators.
Outputs metrics JSON and simple confusion matrices per task.
"""

WORKSPACE = Path(__file__).parent


def read_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def cohen_kappa(counts: Dict[Tuple[str, str], int]) -> float:
    """
    counts: mapping (label_annot1, label_annot2) -> count
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    # observed agreement
    agree = sum(c for (a, b), c in counts.items() if a == b)
    p_o = agree / total
    # expected agreement
    marg_a: Counter = Counter()
    marg_b: Counter = Counter()
    for (a, b), c in counts.items():
        marg_a[a] += c
        marg_b[b] += c
    p_e = 0.0
    for label in set(list(marg_a.keys()) + list(marg_b.keys())):
        p_a = marg_a[label] / total
        p_b = marg_b[label] / total
        p_e += p_a * p_b
    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


def pairwise_counts(rows: List[Tuple[str, str]]) -> Dict[Tuple[str, str], int]:
    c: Dict[Tuple[str, str], int] = defaultdict(int)
    for a, b in rows:
        c[(a, b)] += 1
    return c


def eval_docs(docs_csv: Path) -> Dict[str, Any]:
    rows = read_csv(docs_csv)
    # group by doc id (source+filename) and collect labels by assigned_to where double_annotate == 1
    key_to_labels: Dict[Tuple[str, str], Dict[str, str]] = defaultdict(dict)
    for r in rows:
        if str(r.get("double_annotate", "0")) not in ("1", "True", "true"):
            continue
        key = (r.get("source",""), r.get("filename",""))
        annot = r.get("assigned_to","")
        lab = r.get("ai_relevance","")
        if lab != "":
            key_to_labels[key][annot] = lab
    pairs: List[Tuple[str, str]] = []
    for k, labs in key_to_labels.items():
        if len(labs) == 2:
            a, b = list(labs.values())
            pairs.append((a, b))
    counts = pairwise_counts(pairs)
    return {
        "n_double": len(pairs),
        "kappa_ai_relevance": cohen_kappa(counts) if pairs else None,
        "confusion_counts": counts,
    }


def eval_claims(claims_csv: Path) -> Dict[str, Any]:
    rows = read_csv(claims_csv)
    # key: (press_release, claim_number)
    agg: Dict[Tuple[str, str], Dict[str, Dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        if str(r.get("double_annotate","0")) not in ("1","True","true"):
            continue
        key = (r.get("press_release",""), str(r.get("claim_number","")))
        annot = r.get("assigned_to","")
        agg[key][annot] = {
            "is_claim": r.get("is_claim",""),
            "claim_boundary_ok": r.get("claim_boundary_ok",""),
            "topic_ai_relevant": r.get("topic_ai_relevant",""),
        }
    def metric(field: str) -> Dict[str, Any]:
        pairs: List[Tuple[str, str]] = []
        for k, labmap in agg.items():
            if len(labmap) == 2:
                vals = list(labmap.values())
                a, b = vals[0].get(field,""), vals[1].get(field,"")
                if a != "" and b != "":
                    pairs.append((a, b))
        counts = pairwise_counts(pairs)
        return {"n_double": len(pairs), f"kappa_{field}": cohen_kappa(counts) if pairs else None, "confusion_counts": counts}
    return {
        **metric("is_claim"),
        **metric("claim_boundary_ok"),
        **metric("topic_ai_relevant"),
    }


def eval_pairs(pairs_csv: Path) -> Dict[str, Any]:
    rows = read_csv(pairs_csv)
    # key: (press_release, claim_number, ref_uid)
    agg: Dict[Tuple[str, str, str], Dict[str, Dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        if str(r.get("double_annotate","0")) not in ("1","True","true"):
            continue
        key = (r.get("press_release",""), str(r.get("claim_number","")), r.get("ref_uid",""))
        annot = r.get("assigned_to","")
        agg[key][annot] = {
            "relevance": r.get("relevance",""),
            "coverage": r.get("coverage",""),
            "stance": r.get("stance",""),
        }
    def metric(field: str) -> Dict[str, Any]:
        pairs: List[Tuple[str, str]] = []
        for k, labmap in agg.items():
            if len(labmap) == 2:
                vals = list(labmap.values())
                a, b = vals[0].get(field,""), vals[1].get(field,"")
                if a != "" and b != "":
                    pairs.append((a, b))
        counts = pairwise_counts(pairs)
        return {"n_double": len(pairs), f"kappa_{field}": cohen_kappa(counts) if pairs else None, "confusion_counts": counts}
    return {
        **metric("relevance"),
        **metric("coverage"),
        **metric("stance"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze pilot annotations for agreement and baseline metrics")
    ap.add_argument("--pilot-dir", default=str(WORKSPACE / "outputs" / "pilot"))
    args = ap.parse_args()
    pdir = Path(args.pilot_dir)
    out_json = pdir / "pilot_metrics.json"
    out = {
        "docs": None,
        "claims": None,
        "pairs": None,
    }
    docs_csv = pdir / "pilot_docs_assignments.csv"
    claims_csv = pdir / "pilot_claims_assignments.csv"
    pairs_csv = pdir / "pilot_pairs_assignments.csv"
    if docs_csv.exists():
        out["docs"] = eval_docs(docs_csv)
    if claims_csv.exists():
        out["claims"] = eval_claims(claims_csv)
    if pairs_csv.exists():
        out["pairs"] = eval_pairs(pairs_csv)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


