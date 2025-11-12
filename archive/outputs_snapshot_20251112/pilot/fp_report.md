# False Positive Reduction Report (Pilot)

This report summarizes before/after configurations, triage counts (if labels present), and the tightened rules deployed.

## Configuration
- Doc AI relevance (tightened):
  - AI if ai_statement_count ≥ 2, or (≥1 and contains strong AI lexicon: LLM/ChatGPT/foundation model/deepfake/watermark/ADS/etc.).
- Claim extraction (tightened):
  - Prefer policy patterns (should/must/shall/will/prohibit/ban/require/fund/establish/ensure/restrict); exclude purely descriptive/attribution-only.
- Claim–reference gating (tightened):
  - Minimal token overlap required between claim and reference title/abstract (≥2 overlaps, or ≥1 anchor + ≥1 other).

## Triage summary
- See JSON: outputs/pilot/triage/triage_summary.json
- Note: If label columns are not yet filled, triage counts may be zero and will update after annotations.

## Next steps
- Complete pilot labels; rerun triage_false_positives.py.
- If FP rate remains high, consider enabling the optional doc-level classifier once ≥20 labeled docs are available (train_doc_classifier.py).


