# Response to referee, round 4

We thank the referee for verifying the new material against the committed artifacts and for a report that,
once again, is exactly right where it presses. Every concern below is addressed in the revision; none
required new analysis beyond rewording and one figure regeneration, because the referee's point in each
case was that the text over-claimed relative to what the committed numbers support. We have brought the
text down to the numbers. The one thing we have not done is the in-domain human audit, which remains
foreclosed by the project's no-human-coder design; we address that head-on below.

## Concern 1 — the refresh section reintroduced "fully open" language (the most important fix)

Agreed, and embarrassing given the revision history. We have removed it everywhere:
- Section title: "no proprietary component anywhere" → **"no second paid service, no proprietary retrieval."**
- Body: "the *fully open* pipeline" → "the pipeline with **no proprietary retrieval and no second paid
  service**---though, to be exact, the single frontier model still performs the three language steps
  (extraction, query-writing, and judging), so this is the project's *one proprietary model, nothing else
  paid* configuration, not an open one."
- "reproduced... with an entirely open instrument" → "reproduced... with no proprietary retrieval and no
  second paid service."
- Figure caption "the fully-open pipeline" and the figure script's title → corrected to the same
  "no second paid service; the single frontier model still does extraction, query-writing, and judging."
- README and the figure docstring likewise.
The accurate claim the referee states—no proprietary retrieval service, no GPT-5, no second paid service,
a free DOI-grounded index, with the single frontier model still doing the three language steps—is now the
claim the text makes.

## Concern 2 — the decisive in-domain human audit is still missing

We agree this is the binding limitation and have for four rounds. The revision does **not** claim the
refresh supplies it; we now say so explicitly in §res-refresh ("What the refresh adds is *scale, recency,
and index-portability*, not *validity*: 0.57 is the validated judge reading references the same model
retrieved, against no in-domain human labels, so it inherits the two open questions the paper carries
throughout"). The audit is the PI's call on whether to relax the no-human-coder constraint that defines
the project; the paper is honest that this is the decisive missing test and that, absent it, the venue is
a methods/measurement journal rather than Nature Communications. We have flagged the audit as the single
highest-value next step.

## Concern 3 — the 0.68 figure is favorable selection

Agreed. We now **lead with 0.57** as the end-to-end corroboration rate (which counts retrieval failures
as non-corroborations, as it should), and present 0.68 **only as a ceiling under perfect retrieval**, not
a co-equal estimate—"dropping those and quoting 0.68 would be favorable selection—the rate among claims
the retriever happened to serve." The figure now shows 0.57 as the solid, emphasized bar with its Wilson
interval and 0.68 as a hatched, muted "ceiling: perfect retrieval" bar; the caption says the same.

## Concern 4 — thin Republican arm and the yield reconciliation

Both fixed, and the referee's diagnosis was precise. We now separate the two yield quantities we had
conflated and report both: **conditional** on a release with empirical content the extractor is
party-neutral (7.1 vs 7.3 claims/release), but **unconditionally** Democratic releases yield more (2.9 vs
0.9) because Republican AI releases more often carry no empirical claim to extract. We no longer call the
prior "1.4 vs 2.4" a "mis-estimate" (it was a different quantity on a different claim set); we simply
report the correct conditional and unconditional rates. We also now state plainly that the conditional
balance rests on six Republican releases and that the refreshed window has zero Republican AI releases, so
the partisan corroboration contrast is **Democratic-dominated and suggestive rather than tested**.

## Smaller specific comments

- "the human ceiling" (extraction result) → **"the published state of the art,"** with the explicit
  caveats the referee asked for: the sample is balanced whereas the CheckThat! figure is on the natural
  imbalanced distribution; κ=0.53 is *moderate*, not human parity; and we did not compute ClaimBuster's
  own inter-annotator agreement, so we claim state-of-the-art performance, not human parity. The figure
  panel title is updated to match.
- "the two retrieval configurations" → **"the three retrieval configurations"** (consistent with methods).
- "All models run locally on a single consumer GPU" → "All of these *open* models run locally on a single
  consumer GPU—**the proprietary judge, by contrast, does not run locally** and is reached through a paid
  product."

## On what the referee found strong

We are grateful that the extraction validation, the index-portability result, and the recency are
accepted as genuine. They were built in the spirit the referee names—human ClaimBuster labels rather than
self-assessment, an open NLI faithfulness metric rather than the judge, a cross-developer competence
control—and we have tried, in this round, to make the prose match that discipline rather than overrun it.
