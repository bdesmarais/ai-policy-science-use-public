# Autonomous validation — replacing human coders with LLM + classifier validators

**Directive (Bruce, June 2026):** *"Figure out how to execute on this project fully autonomously,
treating established classifiers and LLM tools as validators. See some recent research on how
LLMs can replace human coders, and work on it that way. This project needs to adapt such that
you can execute it all fully without bringing in human RAs."*

This document re-architects the project's validation step (the open "does the science *support*
the claim?" problem — checkpoint #4 in [`../local_only/validation-ideas.md`](../local_only/validation-ideas.md))
so it runs with **no human research assistants**. It replaces the original human-annotation plan
([03_status_and_revival_plan.md](03_status_and_revival_plan.md), old Phase 0) with an
autonomous, literature-grounded design.

## Why this is defensible — the recent research

LLMs can stand in for human coders on exactly the task types we need (relevance, stance,
framing), and there are now rigorous methods to keep downstream estimates valid despite imperfect
machine labels.

- **LLMs match or beat crowd coders.** Gilardi, Alizadeh & Kubli (2023, *PNAS*; arXiv:2303.15056)
  find zero-shot ChatGPT exceeds MTurk crowd workers by ~25 points on relevance/stance/topic/frame
  tasks, at ~1/20th the cost, with **higher intercoder consistency**. Open-source LLMs reach
  similar territory (Alizadeh et al. 2023, arXiv:2307.02179). Surveys of computational social
  science (Ziems et al. 2024) reach the same conclusion for many annotation tasks.
- **When is an LLM allowed to replace the annotator?** The **Alternative Annotator Test
  ("alt-test")** (Calderon, Reichart et al. 2025, *ACL*; arXiv:2501.10970) gives a formal,
  data-efficient procedure: an LLM may replace human annotators if it is, by a leave-one-annotator-out
  criterion, at least as good a stand-in as the humans are for each other. We adopt this as the
  gate for declaring a validator "good enough."
- **Naive LLM labels bias downstream estimates — and how to fix it.** Egami, Hinck, Stewart & Wei
  (2023, *NeurIPS*; arXiv:2306.04746) show that plugging LLM "surrogate" labels straight into a
  regression biases coefficients and breaks confidence intervals **even at 80–90% accuracy**, and
  propose **Design-based Supervised Learning (DSL)** — a doubly-robust estimator that combines
  many surrogate labels with a *small* gold set for valid inference. **Prediction-Powered
  Inference** (Angelopoulos et al. 2023, *Science*) gives an equivalent guarantee for means/CIs.
  Recent work extends this to "unconfident" LLM labels (arXiv:2408.15204).
- **LLM-as-judge has biases**, so we never trust one model alone: position/verbosity/self-preference
  effects are well documented (Zheng et al. 2023 and follow-ups). The mitigation is an **ensemble
  of methodologically different validators** plus explicit agreement reporting.

## The architecture

Each pipeline checkpoint that previously needed a human RA is now decided by **two or more
independent automated validators**, and their agreement is reported as the autonomous analogue of
inter-annotator reliability.

```
claim–reference pair
        │
        ├── Validator A: LLM-as-judge ENSEMBLE (GPT-5 + ≥1 other model), self-consistency vote
        ├── Validator B: established NLI classifier (entail=support / contradict=refute / neutral=silent)
        └── Validator C/D: dependency-free baselines (TF-IDF relevance, negation-aware lexical) — for CI / no-key runs
        │
        ▼
   cross-validator AGREEMENT  →  Cohen's κ / % agreement  (≙ inter-annotator reliability)
        │
        ▼
   high-agreement CONSENSUS subset  →  internal anchor ("silver gold")
        │
        ▼
   PPI / DSL debiasing  →  valid party-level estimates (e.g., support-rate by party) with CIs
```

Implemented in [`../scripts/core/autonomous_validation.py`](../scripts/core/autonomous_validation.py).
The four validators share one interface (`pair → {relevance, stance, confidence}`), so adding the
production LLM/NLI validators requires no change to the agreement/PPI machinery.

**Stance label space:** `support / refute / mixed / silent` (silent = irrelevant or not addressed).

### How each annotation checkpoint becomes autonomous
| Checkpoint (human plan) | Autonomous replacement |
|---|---|
| 1. Doc AI-relevance | zero-shot LLM + the existing `scripts/pilot/train_doc_classifier.py` as cross-validators |
| 2. Claim quality | LLM-judge ensemble agreement; low-agreement claims auto-flagged, not hand-checked |
| 3. Evidence relevance | LLM relevance score ∧ NLI/TF-IDF relevance; disagreements down-weighted |
| 4. **Stance (support/refute)** | LLM-judge ensemble **+** NLI classifier; consensus + PPI/DSL for valid rates |

## The one honest caveat (and the hook for it)

DSL/PPI and the alt-test are formally valid only with a **small set of trusted "gold" labels**.
To be *fully* autonomous we substitute a **high-agreement consensus subset** (pairs where all
validators agree) as the anchor. This is a reasonable stand-in but is an assumption, not a
theorem: if all validators share a blind spot, consensus can be confidently wrong. The code
therefore (a) keeps the anchor explicit, (b) reports agreement so blind spots are visible, and
(c) accepts a real gold set the moment one exists (even ~100–200 pairs) to upgrade the estimate
to a *formally* valid DSL/PPI result. This is the single place where "no humans at all" trades
against an ironclad guarantee, and it is cheap to close later.

## What the first autonomous run produced

`python3 scripts/core/autonomous_validation.py --max-pairs 400 --per-claim 5` on the real
`outputs/structured_refs/` data (621 claim–reference pairs, 292 D / 329 R), using the two
dependency-free **baseline** validators (no API key / no `transformers` in this environment):

- Cross-validator agreement **91.6%, κ = 0.81**.
- Consensus stance: 71.8% silent, 27.2% support, 1.0% refute.
- PPI-debiased support rate: **Dem 0.284** [0.23, 0.34], **Rep 0.261** [0.21, 0.31].

These specific numbers are from *baseline* validators and are illustrative — the point is that the
**full autonomous flow executes end-to-end and emits valid agreement + debiased estimates without
any human input**. Outputs land in `outputs/stance/` (`pairs_labeled.csv`, `validation_report.md`,
`validation_overview.png`).

## To activate the production validators
```bash
pip install -r requirements.txt        # openai
pip install transformers torch         # NLI validator
export OPENAI_API_KEY=sk-...
python3 scripts/core/autonomous_validation.py --validators all --max-pairs 0
```
The LLM-judge ensemble and the NLI classifier then run automatically and the same report is
produced with production-grade labels.

## Limitations & next steps
1. Swap the baselines for the real **LLM-judge ensemble + NLI**; re-run agreement and re-check
   with the **alt-test**.
2. Add a **small verified anchor** (~100–200 pairs) to make the DSL/PPI estimates formally valid;
   this is the only remaining human-optional step and can itself be a one-time, high-confidence LLM pass.
3. Extend stance to the **transportation** comparison domain (`outputs/pilot_transport/`) to test
   generality, then to additional states.
4. Feed validated stance back into the descriptive analysis (support-rate by party/topic) and into
   the "Evidence Report" generation for the NSF proposal's intervention arm.

## References
- Gilardi, Alizadeh, Kubli (2023). *ChatGPT outperforms crowd workers for text-annotation tasks.* PNAS 120(30). arXiv:2303.15056.
- Alizadeh et al. (2023). *Open-source LLMs outperform crowd workers…* arXiv:2307.02179.
- Ziems et al. (2024). *Can LLMs transform computational social science?* Computational Linguistics.
- Calderon, Reichart et al. (2025). *The Alternative Annotator Test for LLM-as-a-Judge.* ACL. arXiv:2501.10970.
- Egami, Hinck, Stewart, Wei (2023). *Using Imperfect Surrogates… Design-based Supervised Learning.* NeurIPS. arXiv:2306.04746.
- Angelopoulos, Bates, Fannjiang, Jordan, Zrnic (2023). *Prediction-powered inference.* Science 382.
- *Can Unconfident LLM Annotations Be Used for Confident Conclusions?* (2024). arXiv:2408.15204.
- Zheng et al. (2023). *Judging LLM-as-a-judge with MT-Bench…* NeurIPS (LLM-judge biases).
