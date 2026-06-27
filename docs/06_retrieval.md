# Model-guided retrieval: removing the second paid dependency

**One-line:** the same frontier model that judges stance can also do the *retrieval* step that
previously required a separate paid web-search service (GPT-5) — by guiding the **free OpenAlex**
index — and it does so reproducibly, with appropriate abstention, and with a fully DOI-grounded
evidence base.

## Why this matters

Earlier versions of the pipeline found claim-relevant papers with GPT-5 + web search. That is a
*second* paid dependency on top of the judge, it is not reproducible, and only **27–35%** of the
references it returned carried a DOI — so the evidence base behind the headline corroboration rates
was itself only partly verifiable. The reproducible alternative we had — **naive keyword search**
over OpenAlex — returns real DOI-bearing papers but is not claim-targeted: it returns broad,
topically-adjacent works for *every* claim (it cannot abstain), so nearly all (claim, reference)
pairs are judged "silent."

Model-guided retrieval closes that gap with **no second paid service**.

## How it works

1. **Query / abstain** (`data/claude_retrieval_queries.json`). The frontier model reads each claim
   and either emits a concise, claim-targeted OpenAlex query (when the claim has a scientific
   empirical core) or **abstains** (when it is legal, procedural, political, or a value statement
   with no scientific literature to retrieve). These decisions are committed as static data —
   regenerating them needs the same model, exactly as the judge labels do.
2. **Retrieve** (`scripts/core/claude_retrieval.py`). OpenAlex returns the references, so every one
   is a real, dereferenceable record (no fabrication). We run two arms on the same claims: **naive
   keyword** vs **model-guided**.
3. **Score** (`scripts/core/score_retrieval_arms.py`, `retrieval_experiment_report.py`). Relevance
   and stance are judged by the benchmark-validated judge (NLI underdetects relevance on policy text,
   so we anchor on the judge and report NLI as a cross-check). Labels are committed in
   `data/retrieval_relevance_labels.json`.

## Result (balanced 50-claim sample: 30 empirical, 20 non-empirical)

| metric | naive keyword | **model-guided** | GPT-5 generative |
|---|---|---|---|
| relevance yield (top-3, empirical) | 0.40 (12/30) | **0.97 (29/30)** | — |
| correct abstention (non-empirical) | 0.05 (1/20) | **1.00 (20/20)** | (selective) |
| DOI / verifiability | 0.91 | 0.89 | 0.27–0.35 |
| end-to-end corroboration (validated judge) | — | **0.80** (24/30 support, 0 refute) | 0.71 (headline) |

The naive failures are not subtle: for *"sea level is expected to climb… by 2100"* keyword search
returns papers on **sea stars**, a **rock-climbing** vision aid, and **soft robotics**; for the
electrical grid it returns the **Gaia space mission**. Model guidance instead retrieves sea-level-rise
projections and EV-charging grid-impact studies. The end-to-end corroboration is symmetric across
parties (0.80 Dem vs 0.80 Rep), consistent with the paper's finding that the partisan difference is in
*engagement volume*, not corroboration rate.

**Honest caveats.** This is a 50-claim demonstration, not a full-corpus population estimate; stance is
read from abstracts. One genuine miss: neither arm found support for *"80% of California vehicle trips
are under ten miles,"* a travel-survey statistic with no referent in the article literature OpenAlex
indexes. Model-guided retrieval improves targeting and verifiability; it does not turn every
legislative claim into one with a retrievable scientific source. Scaling it to the full corpus and
auditing precision against human relevance judgments is the natural next step.

See `paper/sections/results.tex` §"A single model does the retrieval" and `benchmarks/results/retrieval_experiment.json`.
