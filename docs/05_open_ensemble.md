# Improving the open stance methods

This note documents a concrete improvement to the open (no-proprietary-model) stance
methods and what it changes for the paper's open-versus-closed claim. The code is
`scripts/core/open_ensemble.py`, the measured numbers are in
`benchmarks/results/open_ensemble_report.json`, and the comparison is in
`fig_open_ensemble.png`. Everything runs on the committed per-pair predictions of the
five open models plus the SciFact abstracts, with no proprietary model and no new model
downloads, so it is fully reproducible from the repository.

## The opening the single-model results leave

The five open validators lag the proprietary judge, but the round-2 results already show
they fail in different ways on the two benchmarks. Zero-shot NLI is the strongest open
method on clean SciFact pairs (0.70) and collapses on lay Climate-FEVER claims (0.50),
where it almost never fires SUPPORT (DeBERTa support recall 0.17). The small panel is the
reverse: Phi-3.5 is the best open method on Climate-FEVER (0.63) and one of the weakest on
SciFact (0.56). When the members of a panel make uncorrelated errors and trade places
across regimes, an ensemble can recover most of what any single member misses. That is the
opening I exploited.

## What I built

Three open combiners, ordered from the one that needs nothing to the one that needs the
public benchmark labels but no new in-domain labels.

*Majority vote, zero-shot.* The plurality label of the five open models, ties broken toward
the entailment models. This uses no labels at all, so it is directly comparable to the
paper's zero-shot framing.

*Transfer-weighted vote.* A per-class-F1-weighted vote whose weights are estimated on the
other benchmark, so no test-domain labels are used. I include this mainly because it
fails, and the failure is informative.

*Stacker.* A logistic-regression combiner (a gradient-boosted variant is reported
alongside) trained on the public benchmark gold with five-fold out-of-fold cross-validation,
TF-IDF fit inside each fold so no test text leaks into training, and predictions averaged
over five splits for stability. Its features are the five model votes, vote shares, a
unanimity flag, the TF-IDF cosine between claim and evidence, token overlap, negation-cue
counts, and lengths. This uses the human labels that already exist in the public
benchmarks, never new labels in the policy domain, which is the same standard the paper
sets for itself.

Every method is scored against the expert gold with accuracy (Wilson 95% interval) and
macro-F1, both on the full benchmark and on the exact pairs the proprietary judge labelled,
so the head-to-head with the judge is like-for-like.

## Results

Full-benchmark accuracy and macro-F1, and accuracy on the judge's own pairs with its
interval for reference.

| Method | SciFact acc (full) | SciFact mF1 | SciFact acc (judge's 66) | CF acc (full) | CF mF1 | CF acc (judge's 45) |
|---|---|---|---|---|---|---|
| Proprietary judge | — | — | 0.80 [0.69, 0.88] | — | — | 0.78 [0.64, 0.88] |
| Best single open | 0.71 (NLI) | 0.70 | 0.76 | 0.63 (Phi) | 0.62 | 0.67 |
| Majority (zero-shot) | 0.74 | 0.71 | 0.77 | 0.61 | 0.61 | 0.58 |
| Transfer vote | 0.71 | 0.69 | 0.73 | 0.59 | 0.59 | 0.56 |
| Stacker-LR (benchmark-trained) | 0.76 | 0.74 | 0.83 [0.73, 0.90] | 0.67 | 0.67 | 0.69 [0.54, 0.81] |

The stacker is stable: across ten cross-validation seeds, SciFact full accuracy is
0.763 (sd 0.007) and macro-F1 0.745 (sd 0.007), Climate-FEVER full accuracy is 0.664
(sd 0.009) and macro-F1 0.662 (sd 0.010), and the figures are unchanged when TF-IDF is
fit strictly inside each fold.

Three findings follow.

On SciFact the open methods now reach the proprietary judge. The stacker scores 0.83 on
the judge's 66 pairs against the judge's 0.80, with overlapping intervals and a point
estimate above it, robust across seeds. Even the zero-shot majority vote, which uses no
labels, beats every single open model on the full set (0.74 against the best single 0.71).
The judge's advantage on clean pairs, which the paper already reported as statistically
unresolved for NLI alone, is eliminated once the open models are combined.

On Climate-FEVER, the benchmark where round-2 reported the judge's advantage as real and
non-overlapping, the open methods improve materially and the gap is no longer statistically
resolved. The stacker raises full-set accuracy from 0.63 to 0.67 and macro-F1 from 0.62 to
0.67, and on the 45 pairs the judge labelled its interval [0.54, 0.81] overlaps the judge's
[0.64, 0.88]. The judge keeps a higher point estimate on Climate-FEVER (0.78 against 0.69),
so I would not claim the open methods have caught up there; I would claim the previously
decisive gap is now within sampling noise at n=45, and that a larger judge sample is the
way to settle whether a real Climate-FEVER edge survives.

The gain comes from learning the combination, not from weighting. The transfer-weighted
vote does not help and on Climate-FEVER it underperforms the plain majority, because the
models' reliability is task-specific: weights estimated on SciFact, where NLI is strong,
up-weight NLI on Climate-FEVER, where NLI collapses. The stacker beats it because it learns
from the within-benchmark labels which member to trust on which kind of pair. This is the
practical recipe the paper can offer: train an open combiner on the public claim-verification
benchmarks, then apply it unchanged, which adds no new in-domain labels and no proprietary
model.

## What this does not fix

This improves the judging step only. The binding constraint on the application is retrieval,
not judging: OpenAlex keyword search drives nearly every policy pair to silent and the
reproducible open path returns corroboration rates of a few percent, and a better stance
classifier does nothing about that. Improving retrieval needs either OpenAlex access to
re-rank candidates or in-domain labels to validate the result, neither of which is available
in the released artifacts, so it is the next piece of work rather than something this note
delivers. The stacker gains also rest on the public benchmark labels; the strictly zero-shot
improvement is the majority vote, which is smaller and helps on SciFact but not on
Climate-FEVER.

## Recommended integration

Add the stacker as an open baseline row in Table 1, reported on the same matched samples
with Wilson intervals, and revise the open-versus-closed claim to match the measured result:
on clean SciFact pairs a combined open stack reaches the proprietary judge, and on
Climate-FEVER it narrows the gap to within sampling noise at the current judge sample size
while the judge retains a higher point estimate. State plainly that the combiner uses public
benchmark labels rather than new in-domain labels, and that the zero-shot majority vote is
the label-free part of the gain. If the Climate-FEVER comparison is to carry weight either
way, enlarge the judge's Climate-FEVER sample beyond 45 pairs, since that is the cheapest
thing in the validation to strengthen and it is the comparison the open-versus-closed story
now turns on.
