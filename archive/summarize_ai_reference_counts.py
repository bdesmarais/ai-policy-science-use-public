import csv
import json
import sys
from pathlib import Path


"""
Summarize scientific reference counts per AI statement from existing evaluation JSON.

Reads: outputs/v3_eval/ai_statement_candidate_evidence.json
Writes (to outputs/v3_eval/):
- ai_statement_reference_counts.csv
- ai_statement_reference_counts.json

This script does not perform any API calls; it is fast and safe to re-run.
"""


WORKSPACE = Path(__file__).parent


def main() -> None:
    eval_dir = WORKSPACE / "outputs" / "v3_eval"
    in_json = eval_dir / "ai_statement_candidate_evidence.json"
    if not in_json.exists():
        print("ai_statement_candidate_evidence.json not found in outputs/v3_eval. Run evaluate_ai_statements.py first.", file=sys.stderr)
        sys.exit(2)

    with open(in_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for e in data:
        existing_dois = e.get("existing_dois", []) or []
        existing_arxiv = e.get("existing_arxiv", []) or []
        candidates = e.get("candidates", []) or []

        num_existing_dois = len([d for d in existing_dois if d])
        num_existing_arxiv = len([a for a in existing_arxiv if a])
        num_candidates = len(candidates)
        total_scientific_refs = num_existing_dois + num_existing_arxiv + num_candidates

        rows.append({
            "source": e.get("source", ""),
            "filename": e.get("filename", ""),
            "sentence_index": e.get("sentence_index", 0),
            "matched_ai_terms": "; ".join(e.get("matched_ai_terms", []) or []),
            "num_existing_dois": num_existing_dois,
            "num_existing_arxiv": num_existing_arxiv,
            "num_candidates": num_candidates,
            "total_scientific_refs": total_scientific_refs,
            "sentence_text": e.get("sentence_text", ""),
        })

    rows.sort(key=lambda r: (r["total_scientific_refs"], r["num_candidates"]), reverse=True)

    out_csv = eval_dir / "ai_statement_reference_counts.csv"
    out_json = eval_dir / "ai_statement_reference_counts.json"

    with open(out_csv, "w", encoding="utf-8", newline="") as rf:
        fieldnames = [
            "source",
            "filename",
            "sentence_index",
            "matched_ai_terms",
            "num_existing_dois",
            "num_existing_arxiv",
            "num_candidates",
            "total_scientific_refs",
            "sentence_text",
        ]
        writer = csv.DictWriter(rf, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    with open(out_json, "w", encoding="utf-8") as jf:
        json.dump(rows, jf, ensure_ascii=False, indent=2)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_json}")


if __name__ == "__main__":
    main()


