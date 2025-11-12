#!/usr/bin/env python3
import argparse
import random
from pathlib import Path
from typing import Dict, List, Tuple

"""
Sample transport-domain press releases (Dem/Rep × transport/non-transport) using keyword rules.
Writes 15×4 pilot CSVs to outputs/pilot_transport/ and splits per assignee (Zack/Sai).
"""

import csv

WORKSPACE = Path(__file__).parent
SEED = 20250102
ASSIGNEES = ["Zack", "Sai"]

TRANSPORT_TERMS = {
    "transportation","transit","bus","rail","railway","train","metro","subway",
    "highway","freeway","bridge","interchange","interstate","lane","pavement","paving",
    "traffic","congestion","signal","intersection","roundabout","stoplight",
    "road","street","sidewalk","bike","bicycle","pedestrian","crosswalk","vision zero",
    "dmv","vehicle","ev","electric vehicle","charging","charger","infrastructure",
    "freight","port","airport","aviation","safety","crash","collision"
}


def read_text(path: Path) -> str:
    for enc in ("utf-8","utf-16","latin-1","cp1252"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def map_party_from_dir(dir_name: str) -> str:
    d = dir_name.lower()
    if "democratic" in d:
        return "Democratic"
    if "republican" in d:
        return "Republican"
    return "Unknown"


def has_transport(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in TRANSPORT_TERMS)


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    ap = argparse.ArgumentParser(description="Sample transport-domain pilot docs")
    ap.add_argument("--press-root", default=str(WORKSPACE / "data" / "press_releases"))
    ap.add_argument("--out-dir", default=str(WORKSPACE / "outputs" / "pilot_transport"))
    ap.add_argument("--docs-per-cell", type=int, default=15)
    args = ap.parse_args()

    root = Path(args.press_root)
    out_dir = Path(args.out_dir)
    rng = random.Random(SEED)

    all_docs: List[Tuple[str, str, Path]] = []  # (party, subdir, path)
    for sub in ("Democratic","Republican"):
        subdir = root / sub
        if not subdir.exists():
            continue
        for p in subdir.rglob("*.txt"):
            all_docs.append((map_party_from_dir(sub), sub, p))

    cells: Dict[Tuple[str, str], List[Dict[str, str]]] = {("Democratic","transport"): [], ("Democratic","nontransport"): [], ("Republican","transport"): [], ("Republican","nontransport"): []}
    for party, sub, path in all_docs:
        try:
            text = read_text(path)
        except Exception:
            continue
        cat = "transport" if has_transport(text) else "nontransport"
        cells[(party, cat)].append({"party": party, "filename": path.name, "subdir": sub, "rel_path": str(path.relative_to(root))})

    # sample per cell and split to assignees
    for (party, cat), rows in cells.items():
        rng.shuffle(rows)
        sel = rows[: args.docs_per_cell] if args.docs_per_cell >= 0 else rows
        # alternating assignment
        for i, r in enumerate(sel):
            r["assigned_to"] = ASSIGNEES[i % len(ASSIGNEES)]
        fieldnames = ["party","filename","subdir","rel_path","assigned_to"]
        tag = "dem" if party == "Democratic" else "rep"
        write_csv(out_dir / f"docs_{tag}_{cat}.csv", sel, fieldnames)
        # per-assignee splits
        zack = [r for r in sel if r["assigned_to"].lower().startswith("zack")]
        sai = [r for r in sel if r["assigned_to"].lower().startswith("sai")]
        write_csv(out_dir / "zack" / f"docs_{tag}_{cat}_zack.csv", zack, fieldnames)
        write_csv(out_dir / "sai" / f"docs_{tag}_{cat}_sai.csv", sai, fieldnames)

    print(f"Wrote samples to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


