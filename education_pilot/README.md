# Education-policy pilot (William T. Grant Foundation spinoff)

This is the **K-12 education** adaptation of the science-use pipeline, built for the W.T. Grant
Foundation letter of inquiry *"AI-Assisted Evidence Linking: A Strategy to Improve Research Use
in Polarized K-12 Education Policymaking"* (Desmarais, Rajtmajer, Harden, Boehmke). It is
self-contained and uses only the corpus analysis (no LLM/API calls).

> The W.T. Grant LOI (App MG-208172) was **declined at the LOI stage** (Mar 2026); the agreed
> path forward is a revised **NSF** proposal. The two LOI documents are in
> [`../docs/source_materials/`](../docs/source_materials/). This pilot corpus is also the basis
> of the **submitted APSA 2026 abstract** (`../docs/02_apsa_2026_submission.md`).

## Contents

| Path | What |
|---|---|
| `analyze_press_releases.py` | The corpus / education-keyword analysis (self-contained, repo-runnable; seaborn optional). |
| `analyze_press_releases.cloud_original.py` | Verbatim original from the Dec 2025 cloud session (paths `/mnt/user-data/`, `/home/claude/`). |
| `data/raw/Dem_assembly_press_09012025.csv` | 4,279 Democratic CA Assembly press releases (index, name, district, title, link, date, party). |
| `data/raw/Rep_asm_press_09052025.csv` | 852 Republican CA Assembly press releases (Name, district, party, title, link, date). |
| `figures/fig1–4*.png` | Corpus overview, polarized topics, temporal trends, normalized topics. |

## Run

```bash
cd education_pilot
python3 analyze_press_releases.py   # pandas, numpy, matplotlib required; seaborn optional
```

Reads `data/raw/`, regenerates `figures/`, writes `data/processed/analyzed_press_releases.csv`,
and prints the corpus summary.

## Verified results (reproduce exactly)

- **5,131** total press releases (4,279 D / 852 R; ~5:1 reflects ~75% Democratic membership).
- **611** education-related (11.9%): **13.1%** of D vs **5.9%** of R output.
- Polarized topics (D vs R): SEL/mental health **80 vs 1**; school safety **38 vs 4**;
  reading/curriculum **26 vs 7**.

Note: these CSVs hold press-release **titles + links + dates**, not body text. The full text of
the AI-policy corpus (bodies) lives in the main repo under [`../data/press_releases/`](../data/press_releases/).
