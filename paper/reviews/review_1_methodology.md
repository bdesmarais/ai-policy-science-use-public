# Critical peer review #1 — Methodology (expert reviewer report)

*Reviewing: "Does the Science Support the Claim? Autonomously Measuring Scientific-Evidence Use in
State Legislative Communication with LLM Judges and Prediction-Powered Inference."*

## Summary
The paper builds a pipeline that extracts empirical claims from California legislators' press
releases, retrieves candidate scientific references, and assigns each (claim, reference) pair a
stance (support/refute/silent). Its headline methodological claim is that discriminative NLI
classifiers systematically *under-detect* scientific support, so a generative LLM judge is required;
combining the LLM judge (gold) with NLI (surrogate) via prediction-powered inference (PPI) moves the
estimated support rate from a naive 0.21/0.11 (D/R) to 0.71/0.58. The substantive claim is that
evidence use is high for both parties and the partisan gap is modest.

## Overall assessment
The engineering is clean and the framing is timely, but **the central empirical claim is not
established by the standard this very literature requires, and the headline numbers do not match
what is typical in the field.** As written, the paper's key result ("NLI under-detects; the LLM
judge recovers the truth") is confounded with two alternative explanations it cannot rule out: (a)
the NLI baseline is mis-applied, and (b) the LLM judge over-calls support. The contribution should be
reframed as a proof-of-concept and the strong claims withdrawn or conditioned, **or** a human
validation must be added. Major revisions required.

## Major concerns

**1. There is no human validation — yet every method the paper relies on demands it.**
The paper treats the Claude judge as "gold" and never compares it to human coders. But the cited
foundations are explicit that the trusted labels must be human (or at least independently validated):
Gilardi et al. (2023) measure LLM accuracy *against trained human annotators*; the alt-test
(Calderon et al. 2025) is *defined* as a comparison to multiple human annotators and "fundamentally
requires human-annotated data"; DSL (Egami et al. 2023) and PPI (Angelopoulos et al. 2023) deliver
valid inference only when the gold sample is trustworthy ground truth, sampled by a known design.
The paper cites all four as justification while doing the one thing they forbid: using an unvalidated
model as the gold. **The PPI confidence intervals are therefore not valid in the sense claimed** —
they quantify sampling of Claude's labels, not error relative to truth. *This is the paper's most
serious problem.*

**2. The measurement performance is atypical in a way that signals a confound.** In the PPI/DSL
literature, surrogates are usually 80–90% accurate and the rectification is modest. Here the
correction is roughly **3×** (0.21 → 0.71). A correction that large does not indicate "a good judge
fixing a slightly-off surrogate"; it indicates the surrogate and the judge disagree about the
*majority* of pairs. The paper interprets this entirely as NLI error, but offers no evidence to rule
out the opposite — that the generative judge is over-calling "support." Without a human anchor, the
direction of the 3× gap is an assumption, not a finding.

**3. The NLI baseline is a strawman.** Zero-shot entailment between a paper's title+abstract and a
press-release claim is known to default to "neutral," because abstracts rarely restate a claim in
entailing language. Serious scientific claim verification (Wadden et al. 2020, SciFact) uses
fine-tuning and rationale selection and is benchmarked accordingly; it does not equate
"non-entailment" with "no support." The paper's sweeping conclusion — *"strict-entailment NLI
systematically under-detects scientific support"* — overgeneralizes from one poorly-configured
zero-shot setup. At minimum the claim must be narrowed to "our zero-shot NLI configuration," and a
fairer baseline (a fine-tuned claim-verification model, or zero-shot classification with proper label
verbalization) should be tried before declaring NLI inadequate as a class.

**4. Self-preference / circularity is unmeasured.** The Claude judge evaluates a pipeline whose
claims were extracted by an LLM and whose candidate references were retrieved by an LLM; Zheng et al.
(2023) document that LLM judges exhibit self-enhancement bias. An LLM rating LLM-surfaced evidence as
"supportive" is exactly the failure mode to worry about, and it would inflate the support rate. The
paper neither measures nor discusses this.

**5. Construct validity of "support."** A stance read from a title and a ≤600-character abstract is a
shallow proxy for whether a study's design, sample, and findings actually bear on a policy claim.
Many "support" judgments here are for press releases that cite the bill text or a government page
(not peer-reviewed science at all), which conflates "a document corroborates the claim" with "the
scientific record supports the claim."

**6. Inference details.** (a) The PPI variance uses the consensus/LLM gold and a Wald interval; with
n≈120 and a binary outcome near 0.6, normal-approximation intervals are optimistic — report a method
appropriate to small n. (b) Duplicate (party, press-release, claim, ref) keys inflate the effective
n (the run reports 124 matched for 120 judged); de-duplicate. (c) Retrieval bounds everything: a
claim scored "supported" is supported *by what the LLM chose to retrieve*, with no disconfirming
search, so the support rate is upward-biased by construction.

## Does the performance match the literature? (the editor's specific question)
**No.** The field reports LLM-vs-human agreement around 80% (Zheng) and LLM-vs-human accuracy of
~0.6–0.85 (Gilardi); this paper reports *no* such number and substitutes model-vs-model κ≈0.2, which
is uninterpretable as a quality metric without a human reference. The 3× PPI correction is far larger
than is typical when surrogates are competent. Both facts point the same way: the measurement has not
been shown to perform at the level the literature treats as the bar for replacing human coders.

## Required revisions
1. **Reframe** as a methods demonstration / feasibility study, not a validated population estimate;
   withdraw or condition the substantive "support rate by party" claims.
2. **Add human validation** of at least ~100–150 pairs (even by the authors), report LLM-judge–human
   and NLI–human agreement, and run the alt-test; *or* state plainly that this is not done and that
   the estimates are therefore not validated.
3. **Fix the baseline**: try a proper claim-verification configuration before any "NLI under-detects"
   claim; narrow that claim to the specific setup tested.
4. **Address self-preference/circularity** explicitly (ideally with a non-self judge as a check).
5. **Tighten inference**: de-duplicate keys; use small-n intervals; foreground retrieval bias and the
   bill-text/non-science contamination of "support."
6. **Soften all causal/strong language** ("the true rate," "required," "systematically") to match the
   evidence actually presented.

## Recommendation
Major revision. The idea (LLM-judge gold + cheap surrogate + PPI, run autonomously) is genuinely
interesting and worth publishing as a *template with honest limitations*, but the current draft
over-claims a validated finding it has not earned.
