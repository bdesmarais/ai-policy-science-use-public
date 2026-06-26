# Autonomous validation — open-source LLMs + classifiers as validators

**Directive (Bruce, June 2026):** *"Figure out how to execute on this project fully autonomously,
treating established classifiers and LLM tools as validators. See some recent research on how LLMs
can replace human coders…"* and *"forget about openai. Use open-source models only… Revise and
execute the production pipeline."*

This re-architects the project's validation step (the open "does the science *support* the claim?"
problem — checkpoint #4 in [`../local_only/validation-ideas.md`](../local_only/validation-ideas.md))
so it runs with **no human RAs and no proprietary APIs** — open-source models only. It has been
**implemented and executed** ([`../scripts/core/autonomous_validation.py`](../scripts/core/autonomous_validation.py)).

## Why this is defensible — the recent research

- **LLMs match or beat crowd coders.** Gilardi, Alizadeh & Kubli (2023, *PNAS*; arXiv:2303.15056):
  zero-shot ChatGPT beats MTurk by ~25 pts on relevance/stance/frame tasks, at far lower cost and
  higher consistency. **Open-source LLMs reach similar territory** (Alizadeh et al. 2023,
  arXiv:2307.02179) — directly relevant given the open-source-only constraint.
- **When may a model replace the annotator?** The **alt-test** (Calderon, Reichart et al. 2025,
  *ACL*; arXiv:2501.10970): a model can replace human annotators if it is at least as good a
  stand-in as the humans are for each other, needing only a modest labeled subset.
- **Naive model labels bias downstream estimates — and the fix.** Egami et al. (2023, *NeurIPS*;
  arXiv:2306.04746, **DSL**) show surrogate labels bias regressions/CIs even at 80–90% accuracy;
  **Prediction-Powered Inference** (Angelopoulos et al. 2023, *Science*) gives the equivalent fix
  for means/CIs. We apply a PPI-style correction.
- **Judge biases** (position/verbosity/self-preference; Zheng et al. 2023) → never trust one model;
  combine methodologically *different* validators and report agreement.

## Architecture

Each checkpoint that needed a human RA is decided by **≥2 independent open-source validators**, and
their agreement is the autonomous analogue of inter-annotator reliability.

```
claim–reference pair
   ├── Validator A: NLI classifier #1  (MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli)
   ├── Validator B: NLI classifier #2  (facebook/bart-large-mnli)           ← different arch/training
   └── (optional) Validator C: open generative LLM judge (Qwen2.5-Instruct)
        ▼   premise = reference (title+abstract), hypothesis = claim
   entailment→support · contradiction→refute · neutral→silent
        ▼
   cross-validator AGREEMENT (Cohen's κ / %)  →  autonomous inter-annotator reliability
        ▼
   high-agreement CONSENSUS subset  →  internal anchor
        ▼
   PPI / DSL debiasing  →  valid party-level support-rate estimates with CIs
```

All validators share one interface (`pair → {relevance, stance, confidence}`); the baselines
(`tfidf`, `lexical`, dependency-free) let the same harness run with zero installs / in CI.

## Executed production run (open-source only, June 2026)

`python3 scripts/core/autonomous_validation.py --validators nli_deberta nli_bart --max-pairs 0`
over **all 621 claim–reference pairs** in `outputs/structured_refs/` (292 Dem / 329 Rep), on
Apple-Silicon MPS in ~33 s:

| Metric | Result |
|---|---|
| Cross-validator agreement (DeBERTa ~ BART) | **86.3% , Cohen's κ = 0.654** (substantial) |
| Consensus stance | silent 77.1% · support 15.6% · refute 7.2% |
| Support rate by party (PPI-debiased) | **Dem 0.209** [0.16, 0.26] · **Rep 0.109** [0.08, 0.14] |
| High-agreement (unanimous) anchor | 536 / 621 pairs (86.3%) |

Substantive read (proxy, on this reference set): the retrieved peer-reviewed science **supports
Democratic legislators' technical claims at roughly twice the rate of Republican claims**, with
nearly non-overlapping CIs — a hypothesis worth confirming at scale. Outputs: `outputs/stance/`
(`pairs_labeled.csv`, `validation_report.{md,json}`, `validation_overview.png`).

### What the agreement analysis caught (a feature, not a bug)
Adding a **small open generative LLM judge (Qwen2.5-1.5B-Instruct)** on a 30-pair subset produced
near-zero agreement with both NLI classifiers (κ ≈ 0.0 / −0.04). Per the alt-test/agreement logic,
a 1.5B generative model **fails the validator bar here** and is excluded — exactly the kind of
unreliable validator the framework is designed to flag. A *larger* open model (e.g., Qwen2.5-32B,
Llama-3.3-70B) would be needed to serve as a generative judge; the two purpose-built NLI classifiers
are the reliable validators on this task.

## The one honest caveat (and its cheap fix)

DSL/PPI/alt-test are *formally* valid with a small set of trusted gold labels. To stay fully
autonomous we use the **high-agreement consensus** as the anchor — reasonable, but if all validators
share a blind spot consensus can be confidently wrong. The harness keeps the anchor explicit, reports
agreement so blind spots show, and will accept a ~100–200-pair verified anchor to upgrade to a
*formally* valid DSL/PPI estimate. That anchor can itself be a one-time high-confidence pass — still
no human RAs.

## Scope note — upstream stages
This run validates every pair for which references were already retrieved (`outputs/structured_refs/`,
generated earlier with the original OpenAI claim/reference code). The **validation** stage is now
fully open-source. Regenerating the *upstream* claim-extraction + reference-retrieval for all ~7,100
claims with open-source models (an open instruct LLM for extraction; open retrieval for references)
is the next conversion if a fully open-source end-to-end rebuild is wanted.

## Run it
```bash
pip install torch transformers sentencepiece          # open-source stack; no API key
python3 scripts/core/autonomous_validation.py --validators nli_deberta nli_bart --max-pairs 0
# add the generative judge on a subset:  --validators nli_deberta nli_bart osllm --osllm-items 40
```

## References
- Gilardi, Alizadeh, Kubli (2023). *ChatGPT outperforms crowd workers for text-annotation tasks.* PNAS 120(30). arXiv:2303.15056.
- Alizadeh et al. (2023). *Open-source LLMs outperform crowd workers…* arXiv:2307.02179.
- Calderon, Reichart et al. (2025). *The Alternative Annotator Test for LLM-as-a-Judge.* ACL. arXiv:2501.10970.
- Egami, Hinck, Stewart, Wei (2023). *Using Imperfect Surrogates… Design-based Supervised Learning.* NeurIPS. arXiv:2306.04746.
- Angelopoulos, Bates, Fannjiang, Jordan, Zrnic (2023). *Prediction-powered inference.* Science 382.
- Zheng et al. (2023). *Judging LLM-as-a-judge with MT-Bench…* NeurIPS.
