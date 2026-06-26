# Critical peer review #2 — The paper as AI-produced artifact

*A review of our own paper through the lens of the literature criticizing AI-generated research and
AI-as-evaluator. This paper was drafted and analyzed by an LLM (Claude Opus 4.8); that fact is not
incidental to its validity — it is central.*

## The core problem: the method is AI evaluating AI, and the paper is AI evaluating AI evaluating AI
The study's pipeline uses LLMs to extract claims and to retrieve "relevant" references, and then
uses an LLM (Claude) as the gold judge of whether that LLM-surfaced evidence supports the claim. The
manuscript reporting this was itself written by the same model. The AI-evaluation literature shows
this is exactly the configuration most likely to produce inflated, self-confirming results:

- **Self-preference is real and large.** LLM evaluators favor their own and similar models' outputs by
  ~10–25%, can recognize their own generations, and assign higher scores to lower-perplexity text —
  which their own and other models' outputs tend to be (Panickssery et al. 2024, arXiv:2404.13076).
  When Claude rates LLM-retrieved references as "supportive," part of that signal may be a model
  agreeing with model-shaped text, not a judgment about science. The paper's headline ("most claims
  are supported") is precisely the result self-preference would manufacture, and the paper does not
  measure or correct for it. The naive-vs-PPI gap (0.21 → 0.71) could be read, uncharitably but
  fairly, as "the amount by which an LLM upgrades evidence that other LLMs produced."

- **No external anchor breaks the circularity.** Because there is no human (or non-self model) check
  anywhere in the loop, every number is internal to a single model's worldview. Self-recognition →
  self-preference means the circularity cannot be assumed benign.

## Citation integrity
LLMs fabricate or corrupt citations at high and variable rates — from ~14% to ~95% across studies,
with GPT-4 around 18% in literature-review settings, and fabricated references have evaded expert
peer review at top venues (e.g., a documented set of 100 hallucinated citations at NeurIPS 2025).
A paper drafted by an LLM must therefore treat its own bibliography as suspect until verified.
**Action taken:** every entry in `references.bib` was checked against a primary source; details and
any corrections are logged in `paper/reviews/refcheck.md`. Any citation that could not be confirmed
must be removed, not left in on the model's say-so.

## Homogenization, over-confidence, and "AI slop"
- **Stylistic tells.** AI-written scientific text overuses a small set of markers ("delve," "realm,"
  "underscore," "Importantly," tricolons, heavy em-dash use, "Our contribution is twofold") and is on
  average more syntactically complex and less readable. The current draft contains several of these
  and reads in places like competent boilerplate rather than an argument; it should be edited for
  plainer, more specific prose and the AI-tell vocabulary removed.
- **Over-confidence.** AI text tends to be confident even when wrong. The draft's strong register —
  "required," "the true rate," "systematically under-detect" — overstates what an unvalidated,
  single-model, self-judging measurement can support, and should be downgraded to hedged,
  evidence-proportional language.
- **Generic novelty.** The "reusable template for computational social science" framing is the kind
  of broad, agreeable claim AI writing gravitates toward; the genuine, narrower contribution (a
  feasibility demonstration plus a cautionary finding about zero-shot NLI) should be stated instead.

## Reproducibility theater
"Reproducible with one command, no API key" is true and good, but it can lend false solidity: perfect
computational reproducibility of an **unvalidated** measurement reproduces the bias exactly. The paper
should be explicit that reproducibility is necessary, not sufficient, and that the open question is
validity against a human standard, not re-runnability.

## Disclosure
Given that the analysis and the writing are AI-produced, disclosure should be prominent and specific
(which model, which steps), not a one-line acknowledgment — both for honesty and because it is
material to how a reader should weight the self-preference threat.

## What the revision must do (AI-writing review)
1. Promote self-preference/circularity from a caveat to a **first-order threat to validity**, stated
   in the abstract and discussion; ideally add a non-self check (a different model or a human anchor).
2. **Verify and prune the bibliography**; document the check.
3. Cut AI-tell vocabulary; reduce confidence to match evidence; replace the grand framing with the
   precise contribution.
4. Add an explicit, specific **AI-assistance disclosure** and a note that reproducibility ≠ validity.
