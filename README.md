# Assessing Science Use in AI Policymaking — An AI Evidence-Linking Pipeline

> **Consolidated June 2026 to revive a dormant project.** This repository merges the original
> pipeline codebase (from [`SaiDileepKoneru/AI-Policy-Project`](https://github.com/SaiDileepKoneru/AI-Policy-Project),
> whose git history is preserved here) with the project's talks, proposals, the submitted APSA
> 2026 paper, the education-policy pilot, and a background + revival plan. Start with the
> [revival plan](docs/03_status_and_revival_plan.md).

> **★ Status (June 2026) — read the [paper](paper/main.pdf) for the honest scope.** The repo measures
> whether the topically-nearest scientific literature *corroborates* legislators' empirical claims (not
> observed "evidence use"). Design principle: **one frontier model (Claude Opus 4.8) does the language
> steps — claim extraction, retrieval guidance, and stance judging — and everything around it is free and
> open** (OpenAlex, NLI surrogate, open panel, the estimator). The constraint is *not* "no proprietary
> model" but **"no *second* paid service."** What the paper establishes, with scope stated plainly:
> - **Judging is validated against human benchmarks** (SciFact, Climate-FEVER); the judge approaches human
>   inter-annotator agreement (κ 0.71 vs 0.75 on SciFact). And it need not be proprietary: a **combined
>   open stack** (majority vote + a stacker trained only on public benchmark gold, no in-domain labels)
>   **reaches the judge** on SciFact (0.83 vs 0.80) and narrows the Climate-FEVER gap to within noise.
> - **Retrieval no longer needs a paid web-search service.** The same model guiding the free **OpenAlex**
>   index surfaces a genuinely relevant reference for **97% of empirical claims (vs 40% for naive keyword
>   search)**, **abstains on 20/20 non-scientific claims** a keyword search blindly answers, and grounds
>   **~90% of references in a DOI (vs 27–35% for the old GPT-5 path)** — reproducible and fabrication-free.
>   See `scripts/core/claude_retrieval.py` and [`docs/06_retrieval.md`](docs/06_retrieval.md).
> - **Refreshed through June 2026.** The corpus is kept current: both caucus archives (asmdc.org,
>   asmrc.org) are re-scraped from their sitemaps for the last 12 months (`fetch_refresh_releases.py`),
>   yielding 26 fresh Democratic AI releases (and ~0 Republican — a real asymmetry) → 44 fresh AI claims.
>   Re-running the pipeline on them with **no proprietary retrieval and no second paid service**
>   (model-guided queries → free index → validated judge; the single frontier model still does the
>   language steps) gives an end-to-end corroboration of **0.57** [0.42,0.70] (0.68 is only a *ceiling*
>   under perfect retrieval, not a co-equal estimate), near the historical rate, on current claims. The
>   refresh adds recency/scale/index-portability, **not validity**. Retrieval is **index-agnostic** —
>   OpenAlex *or* **Crossref** (the free DOI registry) as a drop-in fallback (`crossref_retrieval.py`).
> - **Extraction is now validated too (no human coders).** The extractor matches human check-worthiness
>   labels (ClaimBuster) at the published SOTA (F1 **0.74**, κ 0.53); **95%** of extracted claims are
>   entailed by their source release (faithfulness — rarely fabricates); yield is party-balanced (7.1 vs
>   7.3 claims/release). See `benchmark_extraction_validation.py`, `faithfulness_validation.py`.
> - **Judge validated on application-like pairs too.** On **AVeriTeC** (real-world claims + web-*retrieved*
>   evidence — the noisy pairing the application produces), the judge agrees with human verdicts at **κ=0.75,
>   above** AVeriTeC's own human inter-annotator κ=0.62. Across SciFact→Climate-FEVER→AVeriTeC (curated→
>   retrieved) the judge is within/above the human-agreement band (`averitec_validation.py`, `make_band_figure.py`).
> - **On the human audit:** we mount a principled defense (paper §Discussion) that a fresh in-domain human
>   audit is a **complementary** check on the joint pipeline, not the decisive gate — human coders agree
>   weakly on contested claims (Climate-FEVER α=0.33), the judge never sees party (structural party-cue
>   rebuttal), and committed labels are reproducible where human coding is not.
>
> Retrieval code: `scripts/core/claude_retrieval.py`, `score_retrieval_arms.py`,
> `retrieval_experiment_report.py`; validation: `benchmark_validation.py`, `open_ensemble.py`. The whole
> pipeline reproduces from committed inputs with **only** the one frontier model (the GPT-5 path is
> retained solely as the superseded baseline).

## What this project is

An **AI pipeline that measures how policymakers use scientific evidence**. It ingests
policymaking communications (state legislators' press releases), extracts the empirical
**claims** that ought to be backed by research, retrieves **relevant peer-reviewed science**,
and assesses whether that science **supports, refutes, or is silent on** each claim. Goals are
both *descriptive* (how does evidence enter policy debate; how does it vary by party /
polarization?) and *interventional* (can AI-synthesized "Evidence Reports" improve research use
by legislators?).

Two policy domains share the one pipeline:
1. **AI policy** — the original case (this codebase): claims in **AI-related press releases by
   California state legislators**. Presented as *"Assessing Science Use in AI Policymaking: An AI
   Pipeline,"* RISE AI Conference, Notre Dame, Oct 7 2025.
2. **K-12 education policy** — a pilot extension built for a William T. Grant Foundation letter
   of inquiry (see [`education_pilot/`](education_pilot/)).

## The pipeline (Policy → Science)

```
scrape PRs ─► AI-statement detection (v3) ─► LLM claim extraction ─► model-guided OpenAlex ─► real refs
            scripts/core/                    scripts/core/           retrieval (free index)    (title, DOI,
            analyze_press_releases_v3.py     llm_claims.py           scripts/core/             venue, year,
                                                                     claude_retrieval.py        abstract)
                                                          │
                                                          ▼
                       benchmark-validated stance judge  (support / refute / silent)
                       scripts/core/benchmark_validation.py + open_ensemble.py
                       → judging validated vs SciFact/Climate-FEVER; open stack reaches the judge
```
> The legacy GPT-5 + web_search retrieval (`scripts/core/gpt_references.py`) is retained only as the
> superseded baseline; the current pipeline uses `claude_retrieval.py` over the free OpenAlex index.

Full usage and script-by-script docs: **[docs/PIPELINE.md](docs/PIPELINE.md)** (the original
project README). Workflow diagram: [`workflow-schematic.png`](workflow-schematic.png).

## Status of the pipeline (from the team's own notes)

Per [`local_only/PI_update.md`](local_only/PI_update.md):
- **AI statements** extracted and summarized (`outputs/v3/`, `outputs/viz_data/statements/`,
  `outputs/figures/statements/`) — complete.
- **Claims** extracted — reported as **7,139 total (5,249 D / 1,890 R)** in
  `outputs/claims/`.
- **Scientific references** retrieved for all claims via GPT-5 + web search —
  `outputs/structured_refs/{dem,rep}_claim_references.json` — complete, summarized into
  `outputs/viz_data/references/` + `outputs/figures/references/`.
- **Human validation / stance annotation** — *designed and partially set up* but not finished.
  The 4-checkpoint annotation scheme is in [`local_only/validation-ideas.md`](local_only/validation-ideas.md);
  annotator assignment sheets for **Sai** and **Zack** are under `outputs/pilot/{sai,zack}/`
  (plus a transportation-domain extension in `outputs/pilot_transport/`).

**The open problem** (where the project paused, per Bruce, Mar 2026): the LLM retrieves
*relevant* science well; the unsolved, paper-blocking step is reliably judging whether the
science **supports** the claim — i.e., the **stance (support / refute / silent) classification**
and its human-coded validation. This is checkpoint #4 in `validation-ideas.md` and the core
deliverable promised in the APSA abstract.

## Repository map

| Path | Contents |
|---|---|
| [`docs/PIPELINE.md`](docs/PIPELINE.md) | Original project README — how to run every stage |
| [`scripts/core/`](scripts/core/) | The pipeline: v3 AI detection, LLM claim extraction, GPT-5 reference retrieval, reference summarization |
| [`scripts/core/autonomous_validation.py`](scripts/core/autonomous_validation.py) | **Autonomous** validation: LLM-judge + NLI/classifier validators, cross-validator agreement, PPI/DSL-debiased estimates (no human RAs) |
| [`docs/04_autonomous_validation.md`](docs/04_autonomous_validation.md) | Design + recent literature for running the validation fully autonomously |
| [`scripts/pilot/`](scripts/pilot/) | Annotation prep, evaluation, doc classifier, false-positive triage |
| [`data/`](data/) | Scraped press-release text (`press_releases/{Democratic,Republican}/`) + AI-only docs (`Dem_AI/`, `Rep_AI/`) |
| [`outputs/`](outputs/) | claims, structured_refs, v3 stats, viz_data, figures, and the `pilot/` annotation sets |
| [`docs/01_project_background.md`](docs/01_project_background.md) | Full background: motivation, pipeline, both domains, findings, literature |
| [`docs/02_apsa_2026_submission.md`](docs/02_apsa_2026_submission.md) | The APSA 2026 story + **full submitted abstract** |
| [`docs/03_status_and_revival_plan.md`](docs/03_status_and_revival_plan.md) | Why it stalled, what's recovered, and the concrete plan to restart |
| [`docs/timeline.md`](docs/timeline.md) | Dated project timeline |
| [`docs/source_materials/`](docs/source_materials/) | Notre Dame talk, both W.T. Grant LOIs, the **submitted** APSA proposal |
| [`education_pilot/`](education_pilot/) | The K-12 education spinoff (W.T. Grant LOI): corpus, reproducible analysis, figures |
| [`local_only/`](local_only/) | The team's PI update + validation-ideas notes (kept — high value) |
| [`archive/`](archive/) | Earlier script versions + an outputs snapshot |
| [`MISSING_MATERIALS.md`](MISSING_MATERIALS.md) | What (little) is still to track down |

## Team

| Role | People |
|---|---|
| PI | **Bruce A. Desmarais** (Penn State) |
| Faculty | **Sarah Rajtmajer** (PSU, IST), **Jeffrey J. Harden** (Notre Dame), **Frederick Boehmke** (Iowa) |
| Lead student / APSA author | **Nitheesha Nakka** (PhD PSU Dec 2025 → Princeton) |
| Pipeline / annotation | **Sai (Dileep) Koneru**, **Zack**, Saksham Ranjan, Olivia Kuester, Emily Anderson (Koneru & Zack have since left) |
| Possible / adjacent | **Xinyu Wang** (PSU) — co-author on the related anti-vax-statements paper; role here to confirm |

NSF support acknowledged on the Notre Dame talk: **NSF 2318460, 2148215**.

## Quick starts

```bash
# AI-policy pipeline (needs OPENAI_API_KEY for the LLM stages) — see docs/PIPELINE.md
pip install -r requirements.txt

# Education pilot corpus analysis (no API key; pandas/numpy/matplotlib)
cd education_pilot && python3 analyze_press_releases.py
```

## The headline answer (APSA)

**Version submitted at APSA 2026:** [`docs/source_materials/APSA_2026_Proposal_SUBMITTED_bd_edits.docx`](docs/source_materials/APSA_2026_Proposal_SUBMITTED_bd_edits.docx)
— Bruce's Jan 13 2026 edit of Nitheesha Nakka's draft, focused on the CA education pilot data,
submitted by Nakka under the **Information Technology & Politics** division (Political
Methodology 2nd). Full text + story: [docs/02_apsa_2026_submission.md](docs/02_apsa_2026_submission.md).

---
*Pipeline code and outputs originate from [SaiDileepKoneru/AI-Policy-Project](https://github.com/SaiDileepKoneru/AI-Policy-Project)
(history preserved). Consolidated and documented for project revival, June 2026.*
