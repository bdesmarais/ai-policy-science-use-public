# Autonomous validation report (open-source models)

- Pairs judged: **621**  |  Validators: **claude_judge, nli_deberta, nli_bart**
- Models: `claude_judge`=Claude Opus 4.8 (claude-opus-4-8), `nli_deberta`=MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli, `nli_bart`=facebook/bart-large-mnli
- Unanimous (high-confidence) pairs: **507** (81.6%)

## Cross-validator agreement (autonomous inter-annotator reliability)
- `claude_judge~nli_deberta`: 45.3% agree, κ=0.24 (n=64)
- `claude_judge~nli_bart`: 42.2% agree, κ=0.196 (n=64)
- `nli_deberta~nli_bart`: 86.3% agree, κ=0.654 (n=621)

## Consensus stance distribution

- silent: 474 (76.3%)
- support: 101 (16.3%)
- refute: 44 (7.1%)
- mixed: 2 (0.3%)

## Support rate by party (PPI-debiased; gold anchor = Claude Opus 4.8 gold labels (n where judged))

- **dem**: 0.642 (95% CI [0.4589, 0.8256]; naive 0.209; anchor n=30/292)
- **rep**: 0.609 (95% CI [0.438, 0.7808]; naive 0.109; anchor n=34/329)