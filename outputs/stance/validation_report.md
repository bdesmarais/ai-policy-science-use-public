# Autonomous validation report (open-source models)

- Pairs judged: **621**  |  Validators: **nli_deberta, nli_bart**
- Models: `nli_deberta`=MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli, `nli_bart`=facebook/bart-large-mnli
- Unanimous (high-confidence) pairs: **536** (86.3%)

## Cross-validator agreement (autonomous inter-annotator reliability)
- `nli_deberta~nli_bart`: 86.3% agree, κ=0.654 (n=621)

## Consensus stance distribution

- silent: 479 (77.1%)
- support: 97 (15.6%)
- refute: 45 (7.2%)

## Support rate by party (PPI-debiased)

- **dem**: 0.209 (95% CI [0.1623, 0.2555]; naive 0.209; anchor n=242/292)
- **rep**: 0.109 (95% CI [0.0757, 0.1432]; naive 0.109; anchor n=294/329)