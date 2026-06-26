# Autonomous validation report

- Pairs judged: **621**  |  Validators: **tfidf, lexical**
- Unanimous (high-confidence) pairs: **569** (91.6%)

## Cross-validator agreement (autonomous inter-annotator reliability)
- `tfidf~lexical`: 91.6% agree, κ = 0.811

## Consensus stance distribution

- silent: 446 (71.8%)
- support: 169 (27.2%)
- refute: 6 (1.0%)

## Support rate by party (PPI-debiased)

- **dem**: 0.284  (95% CI [0.2325, 0.336]; naive 0.284; anchor n=269/292)
- **rep**: 0.261  (95% CI [0.2139, 0.3089]; naive 0.261; anchor n=300/329)

_Baseline validators used in this run; install `transformers`+`torch` and set `OPENAI_API_KEY` to activate the NLI + LLM-judge production validators._