#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple

"""
Optional: Train a simple doc-level classifier for AI relevance to reduce FPs.
Requirements: scikit-learn (if unavailable, exits gracefully).
Labels expected in pilot docs CSVs under 'ai_relevance' (values: 0_none/1_tangential/2_ai_central or 0/1/2).
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Train simple doc-level AI relevance classifier (optional)")
    ap.add_argument("--pilot-docs", default=str(WORKSPACE / "outputs" / "pilot" / "pilot_docs_assignments.csv"))
    ap.add_argument("--model-out", default=str(WORKSPACE / "outputs" / "pilot" / "doc_model.json"))
    args = ap.parse_args()

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score
    except Exception:
        print("scikit-learn not available; skipping optional ML.")
        return 0

    rows = read_csv(Path(args.pilot_docs))
    X_text: List[str] = []
    y: List[int] = []
    for r in rows:
        lab = (r.get("ai_relevance") or "").strip()
        if lab == "":
            continue
        if "_" in lab:
            lab = lab.split("_")[0]
        if lab not in ("0","1","2"):
            continue
        text = " ".join([
            r.get("source",""),
            r.get("filename",""),
            r.get("matched_ai_terms",""),
        ])
        X_text.append(text)
        y.append(int(lab))
    if len(y) < 20:
        print("Not enough labeled docs to train; need >=20. Skipping.")
        return 0

    vec = TfidfVectorizer(ngram_range=(1,2), min_df=2)
    X = vec.fit_transform(X_text)
    clf = LogisticRegression(max_iter=200, class_weight="balanced")
    scores = cross_val_score(clf, X, y, cv=5, scoring="precision_weighted")
    clf.fit(X, y)
    model = {
        "vectorizer": {"vocabulary": vec.vocabulary_, "idf": vec.idf_.tolist()},
        "classes": sorted(set(y)),
        "coef": clf.coef_.tolist(),
        "intercept": clf.intercept_.tolist(),
        "cv_precision_weighted_mean": float(scores.mean()),
    }
    Path(args.model_out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.model_out, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.model_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


