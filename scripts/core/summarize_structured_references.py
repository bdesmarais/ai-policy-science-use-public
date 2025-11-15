#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

"""
Summarize structured claim references (from gpt_references.py) into analysis-ready tables,
JSON summaries, and optional figures. Also flattens references to a long CSV for Tableau.

Inputs (from outputs/structured_refs/):
- dem_claim_references.json
- rep_claim_references.json

Outputs (to outputs/viz_data/references/ by default):
- references_flat.csv                  # one row per reference with claim metadata
- references_per_claim.csv             # count per claim (+ by party)
- venues.csv                           # normalized venue distribution (+ by party)
- years.csv                            # reference year distribution (+ by party)
- open_access_rate.csv                 # OA rate for party and overall
- references_by_press_release.csv      # references per press release (+ by party)
- duplicates_report.csv                # duplicate keys and counts (DOI, title+year)
- provider_counts.csv                  # provider counts (+ by party)
- summary.json                         # aggregate statistics in JSON

Optional figures (to outputs/figures/references/):
- refs_per_claim_distribution.png      # boxplot by party
- top_venues.png                       # top-N venues per party (horizontal bars)
- years_hist.png                       # histogram of reference years by party
- oa_rate_for_party.png                # OA rate for party (bar)
- refs_per_press_release_topk.png      # bar: top-K press releases by total refs
"""


WORKSPACE = Path(__file__).resolve().parents[2]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _normalize_venue(name: Optional[str]) -> Optional[str]:
    if not name:
        return name
    s = str(name).strip()
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


def _key_for_ref(rec: Dict[str, Any]) -> Tuple[str, Optional[int]]:
    doi = (rec.get("doi") or "").strip().lower()
    if doi:
        return (f"doi:{doi}", None)
    title = (rec.get("title") or "").strip().lower()
    year = rec.get("year")
    try:
        y = int(year) if year is not None and str(year).isdigit() else None
    except Exception:
        y = None
    return (f"title:{title}", y)


def flatten_references(dem_path: Path, rep_path: Path) -> List[Dict[str, object]]:
    flat: List[Dict[str, object]] = []
    for party, path in (("Democratic", dem_path), ("Republican", rep_path)):
        data = _read_json(path)
        for row in data:
            press_release = row.get("press_release")
            claim_number = row.get("claim_number")
            claim_text = row.get("claim_text")
            refs = row.get("references") or []
            for ref in refs:
                authors = ref.get("authors") if isinstance(ref.get("authors"), list) else []
                flat.append({
                    "party": party,
                    "press_release": press_release,
                    "claim_number": claim_number,
                    "claim_text": claim_text,
                    "provider": ref.get("provider"),
                    "id": ref.get("id"),
                    "doi": ref.get("doi"),
                    "title": ref.get("title"),
                    "abstract": ref.get("abstract"),
                    "year": ref.get("year"),
                    "venue": _normalize_venue(ref.get("venue")),
                    "authors": "; ".join(a for a in authors if a),
                    "url": ref.get("url"),
                    "is_open_access": bool(ref.get("is_open_access")) if ref.get("is_open_access") is not None else None,
                })
    return flat


def build_tables(flat: List[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    out: Dict[str, List[Dict[str, object]]] = {}

    # references_per_claim
    rpc_map: Dict[Tuple[str, str, str], int] = defaultdict(int)  # (party, press_release, claim_number)
    for r in flat:
        key = (str(r.get("party")), str(r.get("press_release")), str(r.get("claim_number")))
        rpc_map[key] += 1
    rpc_rows: List[Dict[str, object]] = []
    for (party, pr, cn), cnt in sorted(rpc_map.items(), key=lambda x: (x[0][0], x[1]), reverse=False):
        rpc_rows.append({
            "party": party,
            "press_release": pr,
            "claim_number": cn,
            "references": cnt,
        })
    out["references_per_claim"] = rpc_rows

    # venues
    v_counts: Dict[Tuple[str, str], int] = defaultdict(int)  # (party, venue)
    for r in flat:
        venue = (r.get("venue") or "").strip() or "Unknown"
        v_counts[(str(r.get("party")), venue)] += 1
    v_rows: List[Dict[str, object]] = []
    for (party, venue), cnt in sorted(v_counts.items(), key=lambda x: x[1], reverse=True):
        v_rows.append({"party": party, "venue": venue, "count": cnt})
    out["venues"] = v_rows

    # years
    y_counts: Dict[Tuple[str, str], int] = defaultdict(int)  # (party, year)
    for r in flat:
        y = r.get("year")
        year = str(y) if y is not None else "Unknown"
        y_counts[(str(r.get("party")), year)] += 1
    y_rows: List[Dict[str, object]] = []
    for (party, year), cnt in sorted(y_counts.items(), key=lambda x: (x[0][0], x[0][1])):
        y_rows.append({"party": party, "year": year, "count": cnt})
    out["years"] = y_rows

    # OA rate for party
    oa_totals: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))  # party -> (oa_count, total)
    for r in flat:
        p = str(r.get("party"))
        oa, total = oa_totals[p]
        if r.get("is_open_access") is True:
            oa += 1
        oa_totals[p] = (oa, total + 1)
    oa_rows: List[Dict[str, object]] = []
    for party, (oa, total) in oa_totals.items():
        rate = round(oa / max(1, total), 4)
        oa_rows.append({"party": party, "open_access": oa, "total": total, "oa_rate_for_party": rate})
    # overall
    total_oa = sum(oa for oa, _ in oa_totals.values())
    total_refs = sum(t for _, t in oa_totals.values())
    oa_rows.append({"party": "Overall", "open_access": total_oa, "total": total_refs, "oa_rate_for_party": round(total_oa / max(1, total_refs), 4)})
    out["open_access_rate"] = oa_rows

    # references_by_press_release
    pr_counts: Dict[Tuple[str, str], int] = defaultdict(int)  # (party, press_release)
    for r in flat:
        pr_counts[(str(r.get("party")), str(r.get("press_release")))] += 1
    pr_rows: List[Dict[str, object]] = []
    for (party, pr), cnt in sorted(pr_counts.items(), key=lambda x: x[1], reverse=True):
        pr_rows.append({"party": party, "press_release": pr, "references": cnt})
    out["references_by_press_release"] = pr_rows

    # duplicates_report
    dup_counts: Dict[Tuple[str, Optional[int]], int] = defaultdict(int)
    for r in flat:
        key = _key_for_ref(r)
        dup_counts[key] += 1
    dup_rows: List[Dict[str, object]] = []
    for (key, year), cnt in sorted(dup_counts.items(), key=lambda x: x[1], reverse=True):
        if cnt <= 1:
            continue
        dup_rows.append({"key": key, "year": year if year is not None else "", "count": cnt})
    out["duplicates_report"] = dup_rows

    # provider_counts
    p_counts: Dict[Tuple[str, str], int] = defaultdict(int)  # (party, provider)
    for r in flat:
        prov = (r.get("provider") or "").strip() or "Unknown"
        p_counts[(str(r.get("party")), prov)] += 1
    pc_rows: List[Dict[str, object]] = []
    for (party, prov), cnt in sorted(p_counts.items(), key=lambda x: x[1], reverse=True):
        pc_rows.append({"party": party, "provider": prov, "count": cnt})
    out["provider_counts"] = pc_rows

    return out


def write_tables(tables: Dict[str, List[Dict[str, object]]], viz_dir: Path) -> Dict[str, Path]:
    paths: Dict[str, Path] = {}
    for name, rows in tables.items():
        if not rows:
            continue
        fn = viz_dir / f"{name}.csv"
        # derive fieldnames from first row
        fieldnames = list(rows[0].keys())
        _write_csv(fn, rows, fieldnames)
        paths[name] = fn
    return paths


def write_flat(flat: List[Dict[str, object]], viz_dir: Path) -> Path:
    fn = viz_dir / "references_flat.csv"
    if flat:
        fieldnames = list(flat[0].keys())
    else:
        fieldnames = ["party","press_release","claim_number","claim_text","provider","id","doi","title","abstract","year","venue","authors","url","is_open_access"]
    _write_csv(fn, flat, fieldnames)
    return fn


def build_figures(viz_dir: Path, fig_dir: Path, top_venues_n: int, top_press_releases_k: int) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not available; skipping figure generation.")
        return

    # Load tables
    rpc = _read_json_csv(viz_dir / "references_per_claim.csv")
    venues = _read_json_csv(viz_dir / "venues.csv")
    years = _read_json_csv(viz_dir / "years.csv")
    oa = _read_json_csv(viz_dir / "open_access_rate.csv")
    pr = _read_json_csv(viz_dir / "references_by_press_release.csv")

    fig_dir.mkdir(parents=True, exist_ok=True)

    # refs per claim distribution (boxplot by party)
    data_by_party: Dict[str, List[int]] = defaultdict(list)
    for r in rpc:
        data_by_party[r["party"]].append(int(r["references"]))
    parties = sorted(data_by_party.keys())
    data = [data_by_party[p] for p in parties]
    plt.figure(figsize=(7, 5))
    plt.boxplot(data, labels=parties, patch_artist=True)
    plt.title("References per claim")
    plt.ylabel("References")
    plt.tight_layout()
    plt.savefig(fig_dir / "refs_per_claim_distribution.png", dpi=150)
    plt.close()

    # top venues per party (top N)
    top_rows = _topn_by_group(venues, group="party", name="venue", value="count", n=top_venues_n)
    parties_tv = sorted(set(r["party"] for r in top_rows))
    cols = len(parties_tv)
    fig, axes = plt.subplots(1, cols, figsize=(6 * cols, 5), squeeze=False)
    for idx, party in enumerate(parties_tv):
        ax = axes[0][idx]
        rows = [r for r in top_rows if r["party"] == party]
        terms = [r["venue"] for r in rows][::-1]
        counts = [int(r["count"]) for r in rows][::-1]
        ax.barh(terms, counts, color="#6C8EBF")
        ax.set_title(f"Top venues: {party}")
    plt.tight_layout()
    plt.savefig(fig_dir / "top_venues.png", dpi=150)
    plt.close()

    # years histogram by party
    year_vals: Dict[str, List[int]] = defaultdict(list)
    for r in years:
        party = r["party"]
        y = r["year"]
        if str(y).isdigit():
            year_vals[party].append(int(y))
    plt.figure(figsize=(8, 5))
    colors = ["#2E86AB", "#C14953", "#888888"]
    for i, (party, vals) in enumerate(sorted(year_vals.items())):
        if not vals:
            continue
        plt.hist(vals, bins=25, alpha=0.5, color=colors[i % len(colors)], label=party)
    plt.title("Reference years distribution")
    plt.xlabel("Year")
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "years_hist.png", dpi=150)
    plt.close()

    # OA rate for party
    oa_rows = [r for r in oa if r["party"] != "Overall"]
    parties_oa = [r["party"] for r in oa_rows]
    rates = [float(r["oa_rate_for_party"]) for r in oa_rows]
    plt.figure(figsize=(6, 4))
    plt.bar(parties_oa, rates, color=["#2E86AB", "#C14953"][: len(parties_oa)])
    plt.title("Open access (OA) rate for party")
    plt.ylabel("Rate")
    plt.ylim(0, 1)
    for i, v in enumerate(rates):
        plt.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(fig_dir / "oa_rate_for_party.png", dpi=150)
    plt.close()

    # refs per press release (top K overall)
    pr_sorted = sorted(pr, key=lambda r: int(r["references"]), reverse=True)[: max(1, top_press_releases_k)]
    labels = [f"{r['party']} | {r['press_release']}" for r in pr_sorted]
    counts = [int(r["references"]) for r in pr_sorted]
    plt.figure(figsize=(10, 6))
    plt.barh(labels[::-1], counts[::-1], color="#6C8EBF")
    plt.title("Top press releases by references")
    plt.xlabel("References")
    plt.tight_layout()
    plt.savefig(fig_dir / "refs_per_press_release_topk.png", dpi=150)
    plt.close()


def build_summary(flat: List[Dict[str, object]], tables: Dict[str, List[Dict[str, object]]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    summary["total_references"] = len(flat)

    # References per party
    ref_counts: Dict[str, int] = defaultdict(int)
    for row in flat:
        ref_counts[str(row.get("party"))] += 1
    summary["references_per_party"] = [{"party": p, "references": ref_counts[p]} for p in sorted(ref_counts.keys())]

    # Claims coverage stats
    refs_per_claim = tables.get("references_per_claim", [])
    total_claims = len(refs_per_claim)
    nonzero_claims = sum(1 for row in refs_per_claim if int(row.get("references", 0)) > 0)
    avg_refs_overall = round(sum(int(row.get("references", 0)) for row in refs_per_claim) / max(1, total_claims), 3)
    summary["claim_coverage"] = {
        "total_claims": total_claims,
        "claims_with_references": nonzero_claims,
        "coverage_rate": round(nonzero_claims / max(1, total_claims), 4),
        "avg_references_per_claim": avg_refs_overall,
    }

    # Coverage by party
    summary["coverage_by_party"] = tables.get("refs_coverage_by_party", [])

    # Open access rates
    summary["open_access_rates"] = tables.get("open_access_rate", [])

    # Venues and providers (top 10 each per party)
    venues = tables.get("venues", [])
    venues_by_party: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in venues:
        venues_by_party[row["party"]].append(row)
    summary["top_venues_by_party"] = {party: rows[:10] for party, rows in venues_by_party.items()}

    providers = tables.get("provider_counts", [])
    providers_by_party: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in providers:
        providers_by_party[row["party"]].append(row)
    summary["top_providers_by_party"] = {party: rows[:10] for party, rows in providers_by_party.items()}

    # Reference year distribution (aggregate)
    years = tables.get("years", [])
    year_totals: Dict[str, int] = defaultdict(int)
    for row in years:
        year_totals[row["year"]] += int(row.get("count", 0))
    summary["references_by_year_overall"] = [{"year": y, "count": year_totals[y]} for y in sorted(year_totals.keys())]

    # Duplicate references
    duplicates = tables.get("duplicates_report", [])
    summary["duplicates"] = {
        "duplicate_entries": len(duplicates),
        "top_duplicates": duplicates[:10],
    }

    return summary


def _read_json_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def _topn_by_group(rows: List[Dict[str, str]], group: str, name: str, value: str, n: int) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    groups = defaultdict(list)
    for r in rows:
        groups[r[group]].append(r)
    for g, rs in groups.items():
        rs_sorted = sorted(rs, key=lambda x: int(x[value]) if str(x[value]).isdigit() else 0, reverse=True)[: max(1, n)]
        out.extend(rs_sorted)
    return out


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Summarize structured claim references into tables and figures")
    ap.add_argument("--structured-refs-dir", default=str(WORKSPACE / "outputs" / "structured_refs"))
    ap.add_argument("--viz-data-dir", default=str(WORKSPACE / "outputs" / "viz_data" / "references"))
    ap.add_argument("--figures-dir", default=str(WORKSPACE / "outputs" / "figures" / "references"))
    ap.add_argument("--top-venues", type=int, default=15)
    ap.add_argument("--top-press-releases", type=int, default=20)
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--summary-json", default=str(WORKSPACE / "outputs" / "viz_data" / "references" / "summary.json"))
    args = ap.parse_args(list(argv) if argv is not None else None)

    sdir = Path(args.structured_refs_dir)
    vdir = Path(args.viz_data_dir)
    fdir = Path(args.figures_dir)
    _ensure_dir(vdir)
    _ensure_dir(fdir)

    dem_path = sdir / "dem_claim_references.json"
    rep_path = sdir / "rep_claim_references.json"
    if not dem_path.exists() or not rep_path.exists():
        print("Structured references not found. Run gpt_references.py first.", file=sys.stderr)
        return 2

    flat = flatten_references(dem_path, rep_path)
    flat_path = write_flat(flat, vdir)

    tables = build_tables(flat)
    table_paths = write_tables(tables, vdir)

    summary = build_summary(flat, tables)
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    output_info = {"flat": str(flat_path), **{k: str(p) for k, p in table_paths.items()}, "summary_json": str(summary_path)}
    print(json.dumps(output_info))

    if not args.no_figures:
        build_figures(vdir, fdir, top_venues_n=max(1, args.top_venues), top_press_releases_k=max(1, args.top_press_releases))
        print(f"Figures written to: {fdir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


