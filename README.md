# Assessing Science Use in AI Policymaking — An AI Evidence-Linking Pipeline

> **Consolidated June 2026 to revive a dormant project.** This repository merges the original
> pipeline codebase (from [`SaiDileepKoneru/AI-Policy-Project`](https://github.com/SaiDileepKoneru/AI-Policy-Project),
> whose git history is preserved here) with the project's talks, proposals, the submitted APSA
> 2026 paper, the education-policy pilot, and a background + revival plan. Start with the
> [revival plan](docs/03_status_and_revival_plan.md).

> **★ Status (June 2026) — read the [paper](paper/main.pdf) for the honest scope; this is not a
> solved, fully-open pipeline.** The repo measures whether the topically-nearest scientific literature
> *corroborates* legislators' empirical claims (not observed "evidence use"). The hard step — judging
> support/refute/silent — is done by an LLM judge **validated against human-labeled benchmarks**
> (SciFact, Climate-FEVER), and that judge approaches human inter-annotator agreement (κ 0.71 vs 0.75
> on SciFact). But the scope matters and the paper is explicit about it:
> - The best judge (**Claude Opus 4.8**) is a **proprietary** model — *not* open, local, or free. Only
>   the surrogate layer (NLI + the open panel + OpenAlex) is open; among the open models, only **NLI
>   matches the judge, and only on clean SciFact pairs**; the panel trails, and all open models
>   underperform on the harder Climate-FEVER claims.
> - The **headline corroboration rates (0.71 / 0.54) depend on a proprietary GPT-5 generative-retrieval
>   step** (only ~30% of whose references carry a DOI); the reproducible **OpenAlex** path surfaces
>   little claim-specific evidence and drives nearly everything to "silent."
> - **Only the judging step is validated, on curated benchmark pairs** — not the pipeline as applied; an
>   in-domain human audit is the decisive missing test.
>
> New code: `scripts/core/benchmark_validation.py`, `openalex_retrieval.py`, `policy_stance.py`,
> `review_response_analysis.py`. **Some scripts under [`docs/PIPELINE.md`](docs/PIPELINE.md) require a
> paid OpenAI/GPT-5 key** (the original pipeline); the benchmark-validation and open components do not.

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
scrape PRs ─► AI-statement detection (v3) ─► LLM claim extraction ─► GPT-5 + web_search ─► structured
            scripts/core/                    scripts/core/           reference retrieval    references
            analyze_press_releases_v3.py     llm_claims.py           scripts/core/          (JSON: title,
                                                                     gpt_references.py       DOI, venue,
                                                                                             year, authors…)
                                                          │
                                                          ▼
                          human validation / stance annotation (scripts/pilot/, outputs/pilot/)
                          → the OPEN problem: does the science *support* the claim?
```

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
