# Response to the referee, round 2

We thank the referee for cloning the repository, recomputing the validation table and the headline
application result from the committed artifacts, and confirming that the numerical core reproduces. That
verification is exactly the standard we wanted the work held to. We have fixed every specific point; the
venue question we treat separately at the end, because it is the substantive one.

## Specific corrections (all verified against the committed data)

1. **"Open models match the judge" overstated.** Corrected in the abstract and intro contribution (2):
   only the **NLI surrogate** matches the judge, and only on clean SciFact pairs (0.74–0.76 vs 0.80);
   the **panel trails** there (Qwen 0.70; Phi, OLMo 0.53) and all open models fall short on
   Climate-FEVER. The results section already said this; the headline now agrees with it.
2. **"Judge is fully reproducible" (§2.5 leftover).** Replaced. The text now says the judge's **labels
   are committed and frozen** (making the downstream analysis reproducible, as frozen human labels
   would), while the proprietary judging *process* is not reproducible.
3. **Panel-vs-gold κ wrong/inconsistent.** Recomputed from the committed predictions: panel-vs-gold
   Cohen's κ is 0.44/0.29/0.34 (SciFact) and 0.34/0.44/0.28 (Climate-FEVER), range **0.28–0.44**. Both
   sections now report 0.28–0.44; the spurious 0.54 (which was the DeBERTa–BART inter-NLI value) is
   removed.
4. **Headline = the all-LLM loop the paper warns about.** Added a plain statement where the headline
   lives (§2.4): the corroboration rate is the **least-validated number** in the paper, because it is
   the one place LLM-extracted claims, LLM-generated references, and the LLM judge stack, and the
   benchmark anchor (human claims, human/relevance-retrieved evidence) does not reach that loop.
5. **Generative-reference DOI rate.** Reported (§2.5): only **27–35%** of the GPT-5 references carry a
   DOI (Dem 115/333, Rep 122/452), so the fabrication-free guarantee applies to OpenAlex, **not** to the
   generative path the headline uses.
6. **"Statistically indistinguishable."** Replaced with "**not separated at n=66** (underpowered to
   resolve even a sizeable gap)"; overlapping intervals are now described as non-resolution, not
   equivalence. We also flag that the central Climate-FEVER distinction rests on **45 judge pairs** and
   mark enlarging it as the first robustness step.
7. **Public README contradicted the paper.** Rewritten to match: it now states the judge is proprietary,
   that only NLI (not the panel) matches it and only on clean pairs, that the headline depends on
   proprietary generative retrieval, that only the judging step is validated, and that some original-
   pipeline scripts need a paid key.
8. **Naive-vs-PPI gap.** Now in the body (§2.4): naive NLI 0.21 vs PPI 0.71, a ~3× rectification driven
   almost entirely by the 60 judge anchor labels per party.

## On the venue, and the two routes

We accept the referee's central judgment: as it honestly stands, this is a validation protocol plus a
careful map of where the open, autonomous approach breaks, and that is a computational-social-science /
methods contribution, not a stand-alone Nature Communications advance. We would rather publish it
correct at the right venue than stretch it.

Both routes the referee names are real research, and we are acting on them as follows:

- **Route 2 (build a claim-targeted reproducible retriever).** This is the one we can execute without
  changing the project's constraints, and it directly attacks the binding limitation the paper
  identifies, so we are pursuing it: query reformulation with an open model, wider OpenAlex candidate
  retrieval, and reranking toward claim-specific (not merely topical) evidence, with the goal of having
  the *open* pipeline reproduce meaningful corroboration rates instead of collapsing to ~1%. If it
  works, the central negative result becomes a positive one.
- **Route 1 (in-domain human audit).** We agree this is the highest-leverage move and the one that would
  most change the recommendation. It is foreclosed only by the project's self-imposed no-human-coder
  constraint, which the PI can relax. If a few hundred application pairs are human-coded, the judge can
  be scored in the regime where it is actually used, the generative-vs-OpenAlex retrieval question can
  be checked against truth, and the extraction imbalance's effect on the partisan comparison can be
  measured. That decision rests with the PI.
