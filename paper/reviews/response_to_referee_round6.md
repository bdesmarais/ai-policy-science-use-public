# Response to referee, round 6

We are grateful for the round-6 report and for the clear recommendation. Both remaining points were
minor, and rather than caveat them we have done the analyses they pointed to. The application is now wider
and the relevance claim is stated at exactly the strength the evidence supports.

## Point 2 — the application had thinned to a demonstration

Addressed by widening it, as you suggested, using the full historical corpus and the prediction-powered
machinery already in hand. We judged a stratified gold sample of **56 claims spanning the full AI corpus**
— 45 Democratic claims drawn at random and **all 11 Republican** empirical claims for which the index
returned references — with the benchmark-validated judge reading the best on-topic model-retrieved
reference. Results (`benchmarks/results/historical_corroboration.json`, new
`make_corroboration_figure.py` → Fig. 6):

- **Corpus-wide corroboration 0.61 (95% CI [0.48, 0.72])**, no refutations, retrieval misses counted as
  non-corroborations.
- **Similar across parties**: Democratic 0.60 [0.46, 0.73], Republican 0.64 [0.35, 0.85]. The Republican
  arm is thin (n=11), so we read the cross-party *comparison* as suggestive rather than tested, but we can
  now report a both-party estimate rather than a single Democratic rate.
- The **current twelve-month window reproduces the level independently** (0.57 [0.42, 0.70]); that section
  is now framed as a replication on unseen data, not a standalone headline.

So the substantive application is no longer "engagement plus 44 Democratic claims." It is a partisan
engagement asymmetry plus a both-party corroboration estimate over the full corpus, replicated on fresh
data. The figure carries it.

## Point 1 — the 96% relevance check uses easy negatives

You are right that random-abstract negatives exercise the easy discrimination (cited vs. unrelated), not
the hard one the application meets (on-point vs. topically-adjacent), and that the honest indicator of the
hard case is already in the paper. We have stated it exactly as you framed it, in three places:

- **Results (retrieval).** We now say the 96%/precision-1.00 result certifies that the model reliably
  rejects obvious mismatches and rules out the worst failure mode, but does *not* certify the
  retrieved-but-adjacent boundary; that boundary is where the application's misses live, and the honest
  indicator is AVeriTeC's not-enough-evidence class, on which the judge's errors concentrate (9 of 15). We
  name the clean closing test — cited-versus-same-topic-noncited — as the next step.
- **Abstract.** The bare "96%" no longer stands as if it validated relevance on the hard case; the abstract
  now says retrieval "recovers relevant, DOI-grounded references, reliably rejecting off-topic matches,"
  which is what the easy-negative test actually establishes.
- **Discussion.** The relevance paragraph now pairs the easy-case certification with the AVeriTeC hard-case
  uncertainty and points to the same-topic test.

We would run the cited-versus-same-topic test for the camera-ready and would welcome it, but, as you noted,
it is not a condition.

## On significance and breadth

We have also taken the editor's-call point seriously and foregrounded the breadth proactively. The
introduction now opens on the general task — adjudicating whether evidence supports, refutes, or is silent
on a claim, the judgment behind fact-checking, evidence synthesis, misinformation surveillance, and the
study of science in public decisions — and frames the policy case as the deliberately hard demonstration
(contested claims, retrieved evidence, high stakes for partisan error) that licenses transfer to easier
settings. A closing paragraph states the contribution we most want read: a transferable, honestly bounded
recipe for trusting an autonomous LLM measurement instrument without fresh in-domain human coding, plus a
party-blind design that neutralizes the specific failure mode that makes LLM judging of political text
hazardous.

## Net

Paper is 24 pp, compiles clean, no undefined references. Every stage remains validated against existing
human labels; the application is now both-party and corpus-wide with a fresh-data replication; the
relevance claim is bounded to what its test supports; and the breadth is stated up front for the venue.
