# Pilot Annotation Guidelines (v1)

## 1) Document AI Relevance (press release level)
- ai_relevance:
  - 0 = None: no meaningful mention of AI or related technologies.
  - 1 = Tangential: AI is mentioned but not the main focus (e.g., a passing reference).
  - 2 = Clearly about AI: the document substantively discusses AI (policy, risks, benefits, regulation, programs).
- notes: optional clarifications, edge cases, or uncertainty.
- Unit: one press release (identified by `source` and `filename`).
- Tips:
  - Mentions of analytics, statistics, or general “technology” alone do not imply AI.
  - Terms like “artificial intelligence”, “machine learning”, “LLM/ChatGPT”, “algorithmic transparency/bias/fairness” usually indicate AI salience.

## 2) Claim Extraction Quality
- is_claim:
  - 1 = The text is a policy-relevant proposition (states a position, fact, or intended action).
  - 0 = Not a claim (e.g., pure background, rhetorical flourish, fragment).
- claim_boundary_ok:
  - 1 = The extracted span is self-contained, not truncated, and not merged across distinct claims.
  - 0 = Needs boundary adjustment.
- rewrite_minimal: optional, provide the smallest edit to fix boundary issues (e.g., remove leading clause).
- topic_ai_relevant: reuse scale {0 none, 1 tangential, 2 clearly about AI} at the claim level.
- notes: optional.
- Unit: one extracted claim (press_release + claim_number).
- Tips:
  - Prefer atomicity: if one sentence clearly contains two separate claims, they should be separate.
  - Keep edits minimal (do not paraphrase the meaning).

## 3) Claim–Reference Relevance and Coverage
- relevance:
  - 2 = Directly relevant: the study addresses the main proposition/topic of the claim.
  - 1 = Somewhat relevant: related domain but not the core proposition.
  - 0 = Not relevant.
- coverage:
  - 2 = Core coverage: the study directly tests/evaluates the proposition or the mechanism central to it.
  - 1 = Partial coverage: peripheral aspect only.
  - 0 = No coverage.
- metadata_ok:
  - 1 = Venue/year/title appear correct; 0 = obvious mismatch.
- Unit: one pair (claim_text, reference metadata).
- Tips:
  - Focus on title/abstract for speed; do not deep-read unless necessary in the pilot.
  - If metadata suggests a different topic, set relevance=0 and move on.

## 4) Stance of Science Relative to the Claim
- stance:
  - support = Evidence supports the claim’s proposition.
  - refute = Evidence contradicts the claim’s proposition.
  - mixed/conditional = Evidence is mixed or supports/refutes under specific conditions not asserted in the claim.
  - unclear = Insufficient information to decide.
- confidence: 1 (low) to 5 (high).
- evidence_snippet (optional): short quote from abstract or a precise paraphrase indicating the rationale.
- Unit: same pair as above; only apply stance when relevance ≥ 1.
- Tips:
  - Support/refute should reference the core proposition of the claim.
  - If the reference is a survey/review, stance may be “mixed/conditional” unless the review draws a clear conclusion aligned with the claim.

## Calibrated Examples (added)
- Tangential vs AI‑central (doc):
  - Tangential: “Digital modernization and IT upgrades” with one offhand “AI” mention → 1_tangential.
  - AI‑central: “LLM guardrails for state agencies,” “Deepfake provenance standards” → 2_ai_central.
- Not a claim vs claim:
  - Not a claim: “Experts discussed AI at a town hall.” (description)
  - Claim: “We will require algorithmic impact assessments for ADS.” (policy commitment)
- Relevance/coverage gating:
  - Claim: “LLMs hallucinate factual content.” Reference: “Measuring LLM factuality” → relevance=2, coverage=2.
  - Claim: “Ban facial recognition in schools.” Reference: “Vision transformer robustness” → relevance=0.
- Stance:
  - Support: Empirical evidence aligns with claim’s proposition.
  - Refute: Results contradict proposition.
  - Mixed/conditional: Findings vary by dataset/setting not stated in the claim.

## Double Annotation
- 15% of items are double-annotated:
  - You may see the same item assigned to both Zack and Sai (marked `double_annotate=1`).
  - Complete independently; do not consult the other annotator before submission.

## Recording Labels
- Use the provided CSV/Sheet columns; do not alter keys or reorder header columns.
- If unsure, leave notes; avoid leaving label cells blank—use the “unclear” option where provided.


## Examples (abbreviated)
- Doc relevance:
  - “Governor announces AI Safety Initiative to assess deepfake risks.” → 2 (clearly about AI)
  - “Budget update; modernizing IT systems” (no AI mentioned) → 0
- Claim extraction:
  - “We must require algorithmic impact assessments for ADS.” → is_claim=1; boundary_ok=1; topic_ai_relevant=2
  - “Experts say the technology is improving.” (vague, no policy tie) → is_claim=0
- Pair relevance + stance:
  - Claim: “LLMs frequently hallucinate factual content.”
  - Reference: “Measuring factuality in LLM outputs” → relevance=2, coverage=2; stance=support (confidence 4)
  - Reference: “Vision transformer robustness to rotations” → relevance=0


