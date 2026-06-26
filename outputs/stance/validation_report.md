# Autonomous validation report (open-source models)

- Pairs judged: **621**  |  Validators: **claude_judge, nli_deberta, nli_bart**
- Models: `claude_judge`=Claude Opus 4.8 (claude-opus-4-8), `nli_deberta`=MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli, `nli_bart`=facebook/bart-large-mnli
- Unanimous (high-confidence) pairs: **474** (76.3%)

## Cross-validator agreement (autonomous inter-annotator reliability)
- `claude_judge~nli_deberta`: 41.9% agree, κ=0.202 (n=124)
- `claude_judge~nli_bart`: 37.9% agree, κ=0.143 (n=124)
- `nli_deberta~nli_bart`: 86.3% agree, κ=0.654 (n=621)

## Consensus stance distribution

- silent: 472 (76.0%)
- support: 105 (16.9%)
- refute: 42 (6.8%)
- mixed: 2 (0.3%)

## Support rate by party (PPI-debiased; gold anchor = Claude Opus 4.8 gold labels (n where judged))

- **dem**: 0.709 (95% CI [0.5741, 0.8437]; naive 0.209; anchor n=60/292)
- **rep**: 0.578 (95% CI [0.4513, 0.705]; naive 0.109; anchor n=64/329)