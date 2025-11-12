1. What scale fits your time/annotator capacity for the first pass?
   - a) Pilot (≈200 claims; ≈1,000 claim–reference pairs)
   - b) Medium (≈400 claims; ≈2,000–3,000 pairs)
   - c) Large (all claims and all pairs)

- Clear, adjudicated labels for four pipeline checkpoints, with minimal, consistent schemas we can use for validation, error analysis, and training/tuning.

What to annotate and how

1) Document AI-relevance validation (press release-level)
- Unit: one press release.
- Labels:
  - ai_relevance: 0 = none, 1 = tangential mention only, 2 = clearly about AI.
  - notes: free-text (optional).
- Sampling suggestion: 300 docs total (balanced by party/date/source if possible). Keep IDs: source, filename.
- Purpose: validate the doc-level AI filter, estimate false positives/negatives, set thresholds.

2) Claim extraction quality (within-press-release “claims” used in our structured_claims)
- Unit: one extracted claim.
- Labels:
  - is_claim: 0 = not a claim, 1 = is a claim (policy-relevant proposition).
  - claim_boundary_ok: 0/1 (is the text span complete and not merged/split incorrectly).
  - rewrite_minimal: suggested minimal edit if boundary not OK (optional).
  - topic_ai_relevant: 0/1/2 (same scale as above but applied to the claim).
  - notes (optional).
- Sampling suggestion: annotate all 41 Republican claims + 200 Democratic claims (stratify by press release); keep keys: press_release, claim_number, claim_text.
- Purpose: precision/recall of claim extraction and boundary quality; informs prompt adjustments and potential post-processing.

3) Evidence relevance (claim–reference pair)
- Unit: one pair: (claim_text, reference_title+abstract+venue+year).
- Labels:
  - relevance: 2 = directly relevant, 1 = somewhat/indirectly relevant, 0 = not relevant.
  - coverage: 2 = addresses the core proposition, 1 = peripheral aspect only, 0 = doesn’t address.
  - metadata_ok: 0/1 (venue/year/title look correct; obvious mismatches).
  - notes (optional).
- Sampling suggestion: for each annotated claim above, judge up to the top 5 references (by list order) → ≈ (241 claims × up to 5) ≈ 1,200 pairs.
- Purpose: quantify GPT reference quality, guide prompt/schema tweaks, and set filters (e.g., exclude relevance=0/coverage=0 before stance).

4) Stance classification (support/refute) for relevant pairs
- Precondition: only where relevance ≥1.
- Unit: same pair (claim, reference).
- Labels:
  - stance: support, refute, mixed/conditional, unclear (insufficient info).
  - confidence: 1–5.
  - evidence_snippet: short quote (optional) or line number if available.
- Purpose: core deliverable to assess whether the scientific literature supports or contradicts the claim; enables party-level comparisons (“OA rate for party” and “support rate for party”).

Transportation domain extension (second policy area)
- Data: reuse our press-release corpus; filter a transportation subset (we can provide a candidate list by keyword: “traffic”, “transit”, “highway”, “bridge”, “rail”, “EV infrastructure”, “road safety”, “Vision Zero”, “congestion”, “freight”, etc.).
- Annotations:
  - Apply the same four layers above to a smaller, stratified sample (e.g., 150 docs; 200 claims; top 5 references per claim).
  - This lets us test generality outside AI.

Quality control (keep this light but effective)
- Double annotation: at least 10–20% of items per task labeled by two annotators.
- Adjudication: one pass to resolve disagreements; record final labels.
- Brief calibration: start with 20 items, refine the guideline with concrete positive/negative examples.
- Agreement metrics: report Cohen’s kappa/percent agreement by task.

What we need (concrete deliverables)
- One CSV per task with stable keys and label columns:
  - Doc relevance CSV: source, filename, ai_relevance, notes
  - Claim quality CSV: press_release, claim_number, claim_text, is_claim, claim_boundary_ok, rewrite_minimal, topic_ai_relevant, notes
  - Pair relevance CSV: press_release, claim_number, reference_id_or_doi_or_url, relevance, coverage, metadata_ok, notes
  - Stance CSV: press_release, claim_number, reference_id_or_doi_or_url, stance, confidence, evidence_snippet
- ID policy:
  - Use exactly the keys present in our data: press_release, claim_number; for references use doi if present, else id or url (we can supply a “references_flat.csv” with a stable reference_uid you can copy into labels).
- Minimal guideline PDF/Doc:
  - 2–3 pages with positive/negative examples for each label, especially for stance and relevance/coverage.
- Optional: time tracking (minutes per task) during pilot to refine scale/cost estimates.

Suggested initial scales and time estimates (order-of-magnitude)
- Doc AI relevance: 300 docs; 30–60 sec/doc → 3–5 hours total.
- Claim quality: 241 claims; 45–90 sec/claim → 3–6 hours.
- Pair relevance: 1,200 pairs; 45–90 sec/pair (abstract skim) → 15–30 hours.
- Stance: subset of relevant pairs (say 60–70% of pairs) → 10–25 hours depending on depth and snippet extraction.
- Double-annotate ~15% of items in each task for agreement.

How we’ll use these labels
- Validation: compute precision/recall and confidence intervals for each stage; produce confusion matrices; detect systematic errors (party/source/topic).
- Tuning:
  - Adjust GPT prompts and filters (e.g., require “venue not arXiv unless preprint-only”, discard coverage=0).
  - Fine-tune stance prompts or add a lightweight classifier (optionally trained on your stance labels) to stabilize outputs.
- Reporting: include inter-annotator agreement, sampling, and error analysis in the paper appendix.

