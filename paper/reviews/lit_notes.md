# Literature benchmark notes (for the critical reviews)

Pulled from the cited papers to benchmark whether our measurement performance is typical.

## Validation is done against HUMANS, with typical numbers
- **Gilardi, Alizadeh & Kubli 2023 (PNAS; arXiv:2303.15056).** Trained human annotators are the gold
  standard. ChatGPT zero-shot accuracy vs that human gold ≈ 0.59–0.83 across relevance tasks (e.g.
  0.70, 0.81, 0.83, 0.59); ChatGPT beats MTurk by ~25 pp. *Self-consistency* (intercoder) agreement:
  MTurk ~56%, trained annotators ~79%, ChatGPT(t=1) ~91%, ChatGPT(t=0.2) ~97%. Takeaway: the field
  reports **LLM-vs-human accuracy**; typical LLM accuracy vs human labels is ~0.6–0.85, not perfect.
- **Zheng et al. 2023 (LLM-as-a-judge; arXiv:2306.05685).** GPT-4 judge agrees with human preferences
  **>80%, ≈ the human–human agreement level**. Documented biases: position, verbosity, and
  **self-enhancement / self-preference** (models favor outputs from models like themselves).
- **Calderon, Reichart & Dror 2025 (alt-test; arXiv:2501.10970).** A formal test for replacing human
  annotators with an LLM **fundamentally requires human-annotated data** (compare the LLM to multiple
  human annotators via a winning-rate/epsilon criterion). Closed-source LLMs (GPT-4o) sometimes pass;
  open-source often fail; prompt sensitivity matters.
- **Egami, Hinck, Stewart & Wei 2023 (DSL; arXiv:2306.04746).** Even at 80–90% surrogate accuracy,
  naive use of surrogate labels gives **substantial bias and invalid CIs**; DSL fixes this by combining
  surrogates with **high-quality gold-standard labels sampled by a known design**. Gold = trusted
  ground truth (in their applications, human labels).
- **Wadden et al. 2020 (SciFact; arXiv:2004.14974).** Scientific claim verification = SUPPORTS/REFUTES/
  NOINFO over claim–abstract pairs; strong systems use **fine-tuning + rationale selection**, not
  zero-shot title+abstract NLI. It is a hard, benchmarked task (label-F1 well below 1).

## How OUR numbers compare (the problem)
1. **We report NO LLM-vs-human agreement.** Every validation paper above anchors on humans; we anchor
   on Claude and never check Claude against a human. By the field's standard our "gold" is unvalidated.
2. **The 3× PPI correction (0.21 → 0.71) is atypical.** PPI/DSL corrections are usually small because
   surrogates are ~80–90% accurate. A 3× swing implies the NLI surrogate is catastrophically
   mis-applied for this task (or the judge over-calls support) — not a clean "NLI under-detects."
3. **Our NLI is a weak baseline.** SciFact-grade claim verification uses fine-tuning + rationales;
   zero-shot entailment over a title+abstract vs a press-release claim is known to default to
   "neutral." So "NLI under-detects scientific support" overgeneralizes from a strawman.
4. **Self-preference / circularity (Zheng).** Claude judges a pipeline whose claims and retrieved
   references were produced by LLMs, and Claude also wrote the paper — a self-enhancement-bias risk
   that inflates apparent support and is never measured.
5. **Gold n=120 from one model.** CIs reflect sampling of Claude's labels only; they do not capture
   the gold's own (unmeasured) error vs humans, so they understate true uncertainty.
