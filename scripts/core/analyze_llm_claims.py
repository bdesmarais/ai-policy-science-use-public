#!/usr/bin/env python3
"""
EDA for LLM-extracted claims.

Inputs:
- Aggregated claims: outputs/claims/dem_claims.json, outputs/claims/rep_claims.json
- Per-doc claim files (for enrichment): outputs/claims/llm/<party>/*.json
- Structured references (for coverage): outputs/structured_refs/{dem,rep}_claim_references.json

Outputs:
- Tables (CSV) in outputs/viz_data/claims/:
  - claims_per_party.csv
  - claims_per_press_release.csv
  - claim_lengths.csv
  - top_terms_by_party.csv
  - categories_by_party.csv
  - policy_like_rate.csv
  - duplicates.csv
  - refs_per_claim.csv
  - refs_coverage_by_party.csv
  - claims_enriched.csv
- Figures (PNG) in outputs/figures/claims/:
  - claims_per_press_release_topk.png
  - claim_lengths_boxplot.png
  - top_terms_by_party.png
  - policy_like_rate.png
  - refs_per_claim_distribution.png
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parents[2]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _tokenize(s: str) -> List[str]:
    s2 = "".join(ch.lower() if (ch.isalnum() or ch.isspace()) else " " for ch in (s or ""))
    toks = [t for t in s2.split() if t]
    stop = {
        "the","a","an","and","or","of","to","in","on","for","with","by","from","that","this","as","at","be",
        "is","are","was","were","it","its","their","our","your","we","they","these","those","about","into","over",
        "not","but","can","could","would","should","may","might","also","more","most","some","any","all"
    }
    return [t for t in toks if t not in stop and len(t) > 2]


def load_aggregated_claims(claims_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for party, fn in (("Democratic", "dem_claims.json"), ("Republican", "rep_claims.json")):
        p = claims_dir / fn
        if not p.exists():
            continue
        data = _load_json(p)
        for r in data:
            rows.append({
                "party": party,
                "press_release": r.get("press_release"),
                "claim_number": r.get("claim_number"),
                "claim_text": r.get("claim_text") or "",
                "claim_desc": r.get("claim_desc") or "",
            })
    return rows


def enrich_from_perdoc(rows: List[Dict[str, Any]], perdoc_base: Path) -> None:
    """
    Augment rows with category and is_policy_like when available
    by reading outputs/claims/llm/<party>/<press_release>.json
    """
    if not perdoc_base.exists():
        return
    for r in rows:
        party = r["party"]
        pr = str(r["press_release"])
        doc_path = perdoc_base / party / f"{pr}.json"
        if not doc_path.exists():
            r["category"] = ""
            r["is_policy_like"] = None
            continue
        try:
            doc = _load_json(doc_path)
        except Exception:
            r["category"] = ""
            r["is_policy_like"] = None
            continue
        claims = doc.get("claims") or []
        try:
            idx = int(r.get("claim_number") or 1) - 1
        except Exception:
            idx = 0
        cat = ""
        policy_like = None
        if 0 <= idx < len(claims) and isinstance(claims[idx], dict):
            cat = (claims[idx].get("category") or "")[:100]
            policy_like = claims[idx].get("is_policy_like")
        r["category"] = cat
        r["is_policy_like"] = policy_like


def load_refs_map(structured_refs_dir: Path) -> Dict[Tuple[str, str, Any], int]:
    """
    Returns mapping: (party, press_release, claim_number) -> references count
    """
    out: Dict[Tuple[str, str, Any], int] = {}
    for party, fn in (("Democratic", "dem_claim_references.json"), ("Republican", "rep_claim_references.json")):
        p = structured_refs_dir / fn
        if not p.exists():
            continue
        try:
            data = _load_json(p)
        except Exception:
            data = []
        for row in data:
            pr = str(row.get("press_release"))
            cn = row.get("claim_number")
            refs = row.get("references") or []
            out[(party, pr, cn)] = len(refs)
    return out


def build_tables(rows: List[Dict[str, Any]], refs_map: Dict[Tuple[str, str, Any], int], top_k_press_releases: int = 25, top_terms_n: int = 40) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}

    # claims_per_party
    cpp = Counter(r["party"] for r in rows)
    out["claims_per_party"] = [{"party": p, "claims": cpp[p]} for p in sorted(cpp.keys())]

    # claims_per_press_release
    cpr: Dict[Tuple[str, str], int] = Counter()
    for r in rows:
        key = (r["party"], str(r["press_release"]))
        cpr[key] += 1
    cpr_rows = [{"party": k[0], "press_release": k[1], "claims": v} for k, v in sorted(cpr.items(), key=lambda x: (x[0][0], -x[1]))]
    out["claims_per_press_release"] = cpr_rows

    # claim_lengths
    clen_rows: List[Dict[str, Any]] = []
    for r in rows:
        text = r.get("claim_text") or ""
        toks = _tokenize(text)
        clen_rows.append({
            "party": r["party"],
            "press_release": r["press_release"],
            "claim_number": r["claim_number"],
            "chars": len(text),
            "words": len(toks),
        })
    out["claim_lengths"] = clen_rows

    # top_terms_by_party
    term_counts: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        for t in _tokenize(r.get("claim_text") or ""):
            term_counts[r["party"]][t] += 1
    tt_rows: List[Dict[str, Any]] = []
    for party in sorted(term_counts.keys()):
        for term, cnt in term_counts[party].most_common(top_terms_n):
            tt_rows.append({"party": party, "term": term, "count": cnt})
    out["top_terms_by_party"] = tt_rows

    # categories_by_party
    cat_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for r in rows:
        cat = (r.get("category") or "").strip() or "Unknown"
        cat_counts[(r["party"], cat)] += 1
    cat_rows: List[Dict[str, Any]] = [{"party": k[0], "category": k[1], "count": v} for k, v in sorted(cat_counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))]
    out["categories_by_party"] = cat_rows

    # policy_like_rate
    pol_totals: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
    for r in rows:
        p = r["party"]
        pos, total = pol_totals[p]
        val = r.get("is_policy_like")
        if val is True:
            pos += 1
        pol_totals[p] = (pos, total + 1)
    pol_rows: List[Dict[str, Any]] = []
    for party, (pos, total) in sorted(pol_totals.items()):
        rate = round(pos / max(1, total), 4)
        pol_rows.append({"party": party, "policy_like_true": pos, "total": total, "rate": rate})
    overall_pos = sum(pos for pos, _ in pol_totals.values())
    overall_total = sum(total for _, total in pol_totals.values())
    pol_rows.append({"party": "Overall", "policy_like_true": overall_pos, "total": overall_total, "rate": round(overall_pos / max(1, overall_total), 4)})
    out["policy_like_rate"] = pol_rows

    # duplicates (normalized)
    def norm_text(s: str) -> str:
        return " ".join((s or "").lower().split())
    dup_counts: Dict[Tuple[str, str], int] = defaultdict(int)  # (party, norm_text)
    for r in rows:
        dup_counts[(r["party"], norm_text(r.get("claim_text") or ""))] += 1
    dup_rows: List[Dict[str, Any]] = [{"party": k[0], "norm_text": k[1], "count": v} for k, v in sorted(dup_counts.items(), key=lambda x: x[1], reverse=True) if v > 1]
    out["duplicates"] = dup_rows

    # references per claim + coverage by party
    refs_rows: List[Dict[str, Any]] = []
    cov_totals: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))  # party -> (covered, total)
    for r in rows:
        party = r["party"]
        key = (party, str(r["press_release"]), r["claim_number"])
        n = refs_map.get(key, 0)
        refs_rows.append({"party": party, "press_release": r["press_release"], "claim_number": r["claim_number"], "references": n})
        covered, total = cov_totals[party]
        if n > 0:
            covered += 1
        cov_totals[party] = (covered, total + 1)
    cov_rows: List[Dict[str, Any]] = []
    for party, (covered, total) in sorted(cov_totals.items()):
        cov_rows.append({"party": party, "covered_claims": covered, "total_claims": total, "coverage_rate": round(covered / max(1, total), 4)})
    out["refs_per_claim"] = refs_rows
    out["refs_coverage_by_party"] = cov_rows

    # claims_enriched (flat)
    enr_fields = ["party","press_release","claim_number","claim_text","claim_desc","category","is_policy_like"]
    out["claims_enriched"] = [{k: r.get(k) for k in enr_fields} for r in rows]

    # limit: top K press releases overall by claims for figure
    out["top_press_releases"] = sorted(cpr_rows, key=lambda r: int(r["claims"]), reverse=True)[: max(1, top_k_press_releases)]
    return out


def write_tables(tables: Dict[str, List[Dict[str, Any]]], viz_dir: Path) -> Dict[str, Path]:
    paths: Dict[str, Path] = {}
    for name, rows in tables.items():
        if not rows:
            continue
        fn = viz_dir / f"{name}.csv"
        fieldnames = list(rows[0].keys())
        _write_csv(fn, rows, fieldnames)
        paths[name] = fn
    return paths


def build_figures(viz_dir: Path, fig_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not available; skipping figures.")
        return

    # claims per press release (topk)
    try:
        with open(viz_dir / "top_press_releases.csv", "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        labels = [f"{r['party']} | {r['press_release']}" for r in rows]
        values = [int(r["claims"]) for r in rows]
        plt.figure(figsize=(10, 6))
        plt.barh(labels[::-1], values[::-1], color="#6C8EBF")
        plt.title("Top press releases by claims")
        plt.xlabel("Claims")
        plt.tight_layout()
        _ensure_dir(fig_dir)
        plt.savefig(fig_dir / "claims_per_press_release_topk.png", dpi=150)
        plt.close()
    except Exception:
        pass

    # claim length boxplot (by party)
    try:
        with open(viz_dir / "claim_lengths.csv", "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        by_party: Dict[str, List[int]] = defaultdict(list)
        for r in rows:
            if str(r.get("words", "")).isdigit():
                by_party[r["party"]].append(int(r["words"]))
        parties = sorted(by_party.keys())
        data = [by_party[p] for p in parties]
        plt.figure(figsize=(7, 5))
        # matplotlib 3.9: tick_labels instead of labels
        try:
            plt.boxplot(data, tick_labels=parties, patch_artist=True)
        except TypeError:
            plt.boxplot(data, labels=parties, patch_artist=True)
        plt.title("Claim length (words) by party")
        plt.ylabel("Words")
        plt.tight_layout()
        plt.savefig(fig_dir / "claim_lengths_boxplot.png", dpi=150)
        plt.close()
    except Exception:
        pass

    # top terms by party (bar chart per party)
    try:
        with open(viz_dir / "top_terms_by_party.csv", "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        parties = sorted(set(r["party"] for r in rows))
        cols = len(parties) if parties else 1
        fig, axes = plt.subplots(1, cols, figsize=(6 * cols, 5), squeeze=False)
        for idx, party in enumerate(parties):
            ax = axes[0][idx]
            terms = [r["term"] for r in rows if r["party"] == party][:20][::-1]
            counts = [int(r["count"]) for r in rows if r["party"] == party][:20][::-1]
            ax.barh(terms, counts, color="#6C8EBF")
            ax.set_title(f"Top terms: {party}")
        plt.tight_layout()
        plt.savefig(fig_dir / "top_terms_by_party.png", dpi=150)
        plt.close()
    except Exception:
        pass

    # policy-like rate
    try:
        with open(viz_dir / "policy_like_rate.csv", "r", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["party"] != "Overall"]
        parties = [r["party"] for r in rows]
        rates = [float(r["rate"]) for r in rows]
        plt.figure(figsize=(6, 4))
        plt.bar(parties, rates, color=["#2E86AB", "#C14953"][: len(parties)])
        plt.title("Policy-like claim rate by party")
        plt.ylabel("Rate")
        plt.ylim(0, 1)
        for i, v in enumerate(rates):
            plt.text(i, v, f"{v:.2f}", ha="center", va="bottom")
        plt.tight_layout()
        plt.savefig(fig_dir / "policy_like_rate.png", dpi=150)
        plt.close()
    except Exception:
        pass

    # refs per claim distribution (by party)
    try:
        with open(viz_dir / "refs_per_claim.csv", "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        by_party: Dict[str, List[int]] = defaultdict(list)
        for r in rows:
            if str(r.get("references", "")).isdigit():
                by_party[r["party"]].append(int(r["references"]))
        parties = sorted(by_party.keys())
        fig, axes = plt.subplots(1, len(parties), figsize=(6 * len(parties), 4), squeeze=False)
        for idx, party in enumerate(parties):
            ax = axes[0][idx]
            vals = by_party[party]
            bins = range(0, max(vals) + 2) if vals else range(0, 2)
            ax.hist(vals, bins=bins, color="#6C8EBF", alpha=0.8, edgecolor="white")
            ax.set_title(f"Refs/claim: {party}")
            ax.set_xlabel("References")
            ax.set_ylabel("Count")
        plt.tight_layout()
        plt.savefig(fig_dir / "refs_per_claim_distribution.png", dpi=150)
        plt.close()
    except Exception:
        pass


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="EDA for LLM claims")
    ap.add_argument("--claims-dir", default=str(WORKSPACE / "outputs" / "claims"))
    ap.add_argument("--perdoc-dir", default=str(WORKSPACE / "outputs" / "claims" / "llm"))
    ap.add_argument("--structured-refs-dir", default=str(WORKSPACE / "outputs" / "structured_refs"))
    ap.add_argument("--viz-data-dir", default=str(WORKSPACE / "outputs" / "viz_data" / "claims"))
    ap.add_argument("--figures-dir", default=str(WORKSPACE / "outputs" / "figures" / "claims"))
    ap.add_argument("--top-k-press-releases", type=int, default=25)
    ap.add_argument("--top-terms", type=int, default=40)
    return ap.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    claims_dir = Path(args.claims_dir)
    perdoc_dir = Path(args.perdoc_dir)
    refs_dir = Path(args.structured_refs_dir)
    viz_dir = Path(args.viz_data_dir)
    fig_dir = Path(args.figures_dir)
    _ensure_dir(viz_dir)
    _ensure_dir(fig_dir)

    rows = load_aggregated_claims(claims_dir)
    if not rows:
        print("No aggregated LLM claims found. Run llm_claims.py first.", flush=True)
        return 2
    enrich_from_perdoc(rows, perdoc_dir)
    refs_map = load_refs_map(refs_dir)

    tables = build_tables(rows, refs_map, top_k_press_releases=max(1, args.top_k_press_releases), top_terms_n=max(1, args.top_terms))
    paths = write_tables(tables, viz_dir)
    build_figures(viz_dir, fig_dir)

    # Print summary paths
    print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))
    print(f"Figures written to: {fig_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


