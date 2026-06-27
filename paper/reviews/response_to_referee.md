# Response to the referee

We thank the referee for an unusually sharp and constructive report. It is right on essentially every
point, and the revision is substantial rather than cosmetic. The honest version of the paper is narrower
than the submitted one, exactly as the referee predicted; we have rewritten it to be that paper. Below we
answer each concern; section references are to the revised manuscript.

## The three changes the referee said would most change the assessment

1. **Tell the truth about the proprietary judge; re-scope openness to the surrogate layer.** Done
   throughout. The title is now "A benchmark-validated language-model *judge*…" (not "validated, fully
   autonomous pipeline"). The abstract, Intro contribution (2), Methods §Validators, the Disclosure, and
   Data-and-code availability all state plainly that the gold judge is **Claude Opus 4.8, a proprietary
   frontier model — not local, not free, not reproducible**, and that only the surrogate layer (NLI,
   the open panel, OpenAlex retrieval, the estimator) is open. We also report the finding this implies:
   on the *hard* benchmark the open models fall well short of the proprietary judge, so the openness
   claim is confined to where the task is easy.

2. **Document the retrieval that produced the headline numbers.** Done. Methods §"Evidence retrieval
   (two configurations)" now states that the headline corroboration rates come from a **proprietary
   GPT-5 + web-search generative retrieval inherited from the earlier pipeline** — not reproducible, not
   open — and contrasts it with reproducible OpenAlex keyword retrieval, which is open but too broad to
   reproduce those rates. The dependence of the *level* on retrieval precision is now a headline
   limitation, not a footnote.

3. **Run a few-hundred-pair in-domain human audit.** This is the one request we **cannot** satisfy, and
   we want to be transparent about why rather than appear to dodge it. The project's defining constraint
   — set by the PI — is a *no-human-coder* design: the LLM judge is the gold. There is therefore no
   independent human standard available for an in-domain audit, and we (the judge) cannot audit
   ourselves. We have responded in three ways. (i) We **re-scoped "validated"** so it describes the
   *judging operation on benchmark pairs*, never the pipeline-as-applied (title, abstract, §2.2,
   Discussion). (ii) We **made the curated-vs-application pair gap the foremost limitation** (Discussion
   §"The gap that matters"), and stated explicitly that the no-human design *forecloses* the decisive
   audit — which is itself a cost of going fully autonomous. (iii) We give the **partial reassurance the
   data do support**: Climate-FEVER's NOT-ENOUGH-INFO class consists of exactly the loosely-related,
   often-irrelevant pairings the application produces, and the judge handles it well (silent-class recall
   0.87). If the PI is willing to relax the no-human constraint, the exact audit the referee specifies —
   a few hundred application pairs coded by people, judge accuracy reported against them — is the single
   highest-value next step, and the released harness is built to drop it in. We have flagged this to the
   PI directly.

## Major concerns

- **"No paid API / runs locally" contradicted by the judge.** Fixed; see change 1. The phrase "no API
  key" is gone; we now say the judge is proprietary and paid, and scope openness to the surrogate.

- **Validated at one step, on the wrong pairs.** Fixed in framing; see change 3. We no longer claim the
  pipeline is validated; only the judging step, on curated benchmark pairs, with the transfer to
  keyword-retrieved application pairs named as the open question. We also corrected the Discussion to
  frame the gap as *pair structure* (curated-relevant vs retrieved-possibly-irrelevant), not subject
  matter.

- **Headline numbers from an unspecified retrieval.** Fixed; see change 2.

- **The instrument does not measure evidence "use."** Agreed and fixed. The title now says
  "scientific corroboration of legislators' claims"; §2.4 opens by stating that legislators do not cite
  the papers we retrieve, so the instrument *supplies* the evidence and measures claim–literature
  **corroboration**, not observed use. "Support rate" is now "corroboration rate" throughout the
  application.

- **"Human-level" without a human ceiling.** Fixed. We obtained the benchmarks' reported
  inter-annotator agreement (SciFact Cohen's κ = 0.75; Climate-FEVER Krippendorff's α = 0.334) and now
  compare to them explicitly: the judge's κ-with-gold is **0.71 on SciFact (just below the 0.75 human
  ceiling)** and **0.67 on Climate-FEVER (at or above the weak human ceiling)**. We replaced "human-level"
  with "approaching human agreement" and lead with the frontier-LLM comparison, as suggested.

- **Small judge sample, not comparable to other validators.** Fixed. We re-ran **every validator on the
  exact pairs the judge saw** (SciFact n = 66, Climate-FEVER n = 45) and rebuilt Table 1 and Figure 1
  with **Wilson 95% intervals**. The headline consequence is now stated honestly: on clean SciFact pairs
  the judge (0.80 [0.69, 0.88]) and the open NLI surrogate (0.74–0.76) are **statistically
  indistinguishable**; the judge's advantage is real only on Climate-FEVER (0.78 [0.64, 0.87] vs
  0.49–0.51, non-overlapping). The Climate-FEVER judge n (45) is now stated.

- **PPI anchored on the judge, and buys little.** Fixed and stated plainly (§Methods PPI, §2.4). The
  intervals are valid for the rate the *judge* would assign, not a human-equivalent rate; and because the
  NLI surrogate is near-constant (almost all silent) on the policy corpus, PPI reduces to the judge's
  mean on the gold sample (n = 60 per party). We now present this as valid inference for the judge's
  labels on a small gold sample, not as variance reduction from a strong surrogate.

- **Claim extraction unvalidated and confounding.** Acknowledged with data. Extraction yield is **not**
  balanced — ≈1.4 extracted claims per Democratic AI release vs ≈2.4 per Republican — so the per-claim
  partisan comparison is confounded by extraction before the judge runs (Discussion, Limitation 2). A
  fidelity audit remains undone and is flagged.

- **Abstract claims judge transfers to a second domain.** Fixed. The abstract no longer claims judge
  transfer; §2.5 and the abstract now say only the **extraction-and-attention front end** transfers to
  the education corpus, which is what the data show.

## Specific and smaller comments

- **"Collapses to chance."** Corrected. We supplied the missing TF-IDF floor for Climate-FEVER (0.34 ≈
  3-class chance) and now say NLI **drops to ~0.50, near the lexical floor but above chance**, not
  "collapses to chance." The task is genuinely three-class throughout.
- **Figure 4 caption (0.11 vs 0.21).** Fixed; the Democratic range is now 0.21–0.79 (0.11 was the
  Republican value).
- **"Fully autonomous" vs the audit.** Resolved by re-scoping; "fully autonomous" is gone, and we now
  state that the autonomous design *forecloses* the audit.
- **Panel a weak self-preference control.** Agreed; softened. We now present the panel as
  **corroborating, not an independent guarantee** (independently developed ≠ independently erring; its
  agreement with gold is only moderate, κ = 0.27–0.54), and lean on human-written benchmark text as the
  decisive control.
- **Self-preference via the claim side.** Added. We now state that benchmark validation bounds
  self-preference on the *evidence* side only; in the application the LLM-extracted *claims* are a
  residual channel the human-claim benchmarks do not test.
- **Member-level uncertainty.** Acknowledged (Limitation 4); the engagement gaps are now presented as
  descriptive aggregates without member-clustered intervals, and we no longer call the gap "sharp."
- **Repository 404.** Fixed: the repository is now **public** at
  `github.com/bdesmarais/ai-policy-science-use-public`; the link resolves for anyone, and the paper
  points to it.
- **Refute moot in the application.** Added (Limitation 3): the strong benchmark refute capability is
  nearly idle in the application because relevance-seeking retrieval suppresses disconfirming evidence;
  it is the retrieval design, not the judge, that limits refute rates there.
- **Em dashes.** Rewrote the two flagged constructions ("collapses to chance"; "it is NLI, not the
  judge") into explicit clauses and reduced load-bearing dashes elsewhere.

## On venue

We take the referee's point that the honest paper is narrower and may sit better at a computational-
social-science or measurement venue than at *Nature Communications*. We have written the honest paper and
defer the venue decision to the editor; we would rather under-claim and be right.
