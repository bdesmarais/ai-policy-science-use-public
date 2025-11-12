#!/usr/bin/env python3
"""
Build claim-only JSON lists from structured_claims CSVs.

Outputs:
- outputs/claims/dem_claims.json
- outputs/claims/rep_claims.json

Each JSON is a list of objects with: press_release, claim_number, claim_text
"""

import argparse
import csv
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_DEM_CSV = os.path.join("data", "structured_claims", "Demsfull_AI_LMclaims.csv")
DEFAULT_REP_CSV = os.path.join("data", "structured_claims", "Rep_AI_LMclaims.csv")
DEFAULT_OUT_DIR = os.path.join("outputs", "claims")


def ensure_dir(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(str(value).strip())
    except Exception:
        return None


def read_claims_csv(csv_path: str, is_republican: bool) -> List[Dict[str, Any]]:
    claims: List[Dict[str, Any]] = []
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            press_release = (row.get("press_release") or "").strip()
            claim_number = safe_int(row.get("claim_number"))
            claim_text = (row.get("claim_text") or "").strip()
            # Extract bracketed description at end as claim_desc
            claim_desc: Optional[str] = None
            try:
                m = re.search(r"\(([^()]*)\)\s*\.?\s*$", claim_text)
                if m:
                    claim_desc = m.group(1).strip()
            except Exception:
                claim_desc = None

            if is_republican:
                note_val = (row.get("note") or "").strip()
                if note_val == "This source does not contain any AI/Emergent Technology claims.":
                    continue

            if not press_release or not claim_text:
                continue

            claims.append(
                {
                    "press_release": press_release,
                    "claim_number": claim_number,
                    "claim_text": claim_text,
                    "claim_desc": claim_desc,
                }
            )
    return claims


def write_json(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export claim-only JSONs from CSVs")
    ap.add_argument("--dem-csv", default=DEFAULT_DEM_CSV)
    ap.add_argument("--rep-csv", default=DEFAULT_REP_CSV)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    ap.add_argument("--limit", type=int, default=-1, help="Limit number of claims per side (-1 for all)")
    return ap.parse_args(argv if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    dem = read_claims_csv(args.dem_csv, is_republican=False)
    rep = read_claims_csv(args.rep_csv, is_republican=True)
    if args.limit >= 0:
        dem = dem[: args.limit]
        rep = rep[: args.limit]

    dem_out = os.path.join(args.out_dir, "dem_claims.json")
    rep_out = os.path.join(args.out_dir, "rep_claims.json")
    write_json(dem_out, dem)
    write_json(rep_out, rep)
    print(json.dumps({"written": {"dem": dem_out, "rep": rep_out}, "counts": {"dem": len(dem), "rep": len(rep)}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


