# Response to referee, round 5

We are grateful for the change in recommendation, and for a report that—again—identified exactly the
right remaining things. All three concerns and the two notes on the defense are addressed below; one
required a small new analysis (a human-anchored relevance check), the rest were precision fixes that bring
the text down to what the numbers support.

## Concern 1 — "above the human band" overstates a not-like-for-like comparison

Fixed everywhere. The abstract, intro, discussion, results, figure title, and figure caption now say the
judge sits **within the band of human disagreement** by the alternative-annotator standard, not "above" or
"exceeds." Where the two numbers appear together we now state in-line that the judge's $\kappa$ is against
the adjudicated gold while the human figure is pairwise, so it is a within-band comparison rather than a
claim of exceeding humans. The word "closed" is retired in favour of **"substantially narrowed---on the
pair structure the application produces,"** with the two caveats you named (AVeriTeC is general
fact-checking, and its evidence was assembled to be adjudicable, unlike the application's frequently
off-topic keyword hits—our own seven retrieval misses).

## Concern 2 — retrieval relevance was still self-graded

Addressed with a new check, in the project's own idiom (transfer from existing human labels), since you
note relevance is the one judgment on which humans are reliable. SciFact's human evidence annotations give
relevance labels for free: the cited abstract is on-topic for a claim, a random abstract is not. On 120
such pairs the model's relevance judgment matches the human labels at **96% accuracy with perfect
precision (1.00)**—it never calls an off-topic paper relevant—and the cross-developer panel clears the
lexical floor (Phi-3.5 0.97, OLMo-2 0.94 vs TF--IDF 0.79). The relevance step is therefore independently
human-anchored, not self-asserted (new `relevance_validation.py`, reported in §Results retrieval and
folded into the discussion). This is the small in-domain human check you would still have asked for,
supplied by transfer rather than deferred.

## Concern 3 — the low-human-agreement argument is double-edged

Stated, where you asked, at the point we report the corroboration rate. We now say plainly that the same
weak human agreement on contested claims that bounds a human audit also bounds what "corroborated" can
mean: when annotators agree only moderately (Climate-FEVER $\alpha=0.33$), a rate like 0.71 carries
construct ambiguity, not merely sampling uncertainty, and the argument that humans are noisy must be
applied to the estimate as honestly as to its audit.

## On the defense — the two notes

You judged the alternative-annotator framing and the party-blind design the load-bearing arguments, and
the regenerability argument the weak one. We agree and have **dropped** it explicitly: a validation set is
frozen by nature, our case already rests on three frozen human-labeled benchmarks, so regenerability does
not distinguish benchmark transfer from a frozen in-domain audit. We now state that what the no-human
design buys is not a validation advantage but a deployment one (scale and recency), and rest the case for
not gating on the audit on the band evidence, the party-blind design, and AVeriTeC.

## Net

Every stage is now checked against human labels—extraction (ClaimBuster), stance (SciFact,
Climate-FEVER, and the retrieved-evidence AVeriTeC), and retrieval relevance (SciFact)—and the headline
"band" claim matches the body's own caveat. We are glad this meets the bar, and we have tried to keep the
honesty that carried the work through five rounds.
