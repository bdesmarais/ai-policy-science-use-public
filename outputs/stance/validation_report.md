# Autonomous validation report (open-source models)

- Pairs judged: **614**  |  Validators: **claude_judge, nli_deberta, nli_bart**
- Models: `claude_judge`=Claude Opus 4.8 (claude-opus-4-8), `nli_deberta`=MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli, `nli_bart`=facebook/bart-large-mnli
- Unanimous (high-confidence) pairs: **472** (76.9%)

## Cross-validator agreement (autonomous inter-annotator reliability)
- `claude_judge~nli_deberta`: 43.3% agree, κ=0.214 (n=120)
- `claude_judge~nli_bart`: 39.2% agree, κ=0.151 (n=120)
- `nli_deberta~nli_bart`: 86.5% agree, κ=0.658 (n=614)

## Consensus stance distribution

- silent: 468 (76.2%)
- support: 103 (16.8%)
- refute: 41 (6.7%)
- mixed: 2 (0.3%)

## Support rate by party (PPI-debiased; gold anchor = Claude Opus 4.8 gold labels (n where judged))

- **dem**: 0.708 (95% CI [0.5727, 0.8425]; naive 0.208; anchor n=60/289)
- **rep**: 0.544 (95% CI [0.4142, 0.6741]; naive 0.111; anchor n=60/325)