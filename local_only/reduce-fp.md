# Reducing False Positives: Triage → Tighten → Resample

## 1) Triage and quantify

- Review Sai’s flagged items; tag each FP’s origin: (A) doc AI relevance, (B) claim extraction, (C) claim–reference relevance.
- Compute quick rates on the current pilot assignments (ours + Sai’s subset) to locate the main source of FPs.

## 2) Immediate filter tightening (no ML)

- Doc AI relevance (press releases):
- Raise threshold: AI-relevant only if ai_statement_count ≥ 2 OR (≥1 and contains a strong AI lexicon term: LLM/ChatGPT/foundation model/deepfake/watermark/ADS/etc.).
- Add negative/boilerplate filters: public event notices, staff announcements, generic “technology modernization”, acronyms overlapping with AI.
- Weight title/lede: single late mention → non‑AI unless strong lexicon present.
- Claim extraction:
- Keep only sentences that satisfy claim patterns: modal/commitment (will/shall/should/must/prohibits/requires/funds), or factual assertions tied to policy impact.
- Exclude purely descriptive/attribution-only sentences.
- Claim–reference gating:
- Apply a minimal overlap screen: require small token overlap between claim and reference title/abstract (e.g., ≥2 anchors) before sending pairs to stance.

## 3) Guideline calibration (15–30 mins)

- Meet with Sai to review 10–15 borderline examples per stage; add positive/negative examples to guidelines.md.
- Clarify distinctions: tangential vs AI‑central; is_claim vs info; relevance vs coverage; stance definitions.

## 4) Resample and continue pilot

- Rebuild the 25×4 doc cells using tightened filters (same seed); if shortfalls occur, backfill with next best candidates.
- Regenerate claim samples (≤3 per AI‑doc) and pairs (top‑K refs) with the new gating.
- Keep double_annotate at 15%.

## 5) Optional: lightweight classifier (if FPs remain high)

- Train a simple logistic‑regression/linear‑SVM on doc‑level labels (bag‑of‑words + strong lexicon features) to replace/augment rules.
- 5‑fold CV; deploy only if it beats the rule-based baseline on precision at target recall.

## 6) Transport domain

- Apply the same tightened filters and pilot sampling to transportation (keyword list + strong terms; same thresholds), then run a smaller pilot (e.g., 15×4) for validation.

## 7) Reporting

- Before/after FP rates by stage; confusion matrices; examples added to the appendix.
- Document the final thresholds and any classifier configuration for reproducibility.