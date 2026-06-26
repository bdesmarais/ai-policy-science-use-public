# Status & Revival Plan

## Where things stand (June 2026)

The project went **dormant** after ~March 2026, but the **full pipeline and outputs have now
been recovered** (this repo, consolidated from the original `SaiDileepKoneru/AI-Policy-Project`).

Proximate causes of the original stall:
- **People dispersed.** Nitheesha Nakka graduated (Dec 2025) → **Princeton**. Pipeline/annotation
  students **Sai Koneru** and **Zack** left the group (Rajtmajer, Mar 13 2026: *"Sai and Zach
  are gone, but I can bring other students to move the pilot work forward"*).
- **Near-term funding failed.** The **W.T. Grant** LOI (App **MG-208172**) was **not invited to
  a full proposal** (Mar 12 2026): *"the strategy … relies primarily on passive methods of
  sharing evidence."* Agreed path forward: advance the pilot and prepare an **NSF** proposal.
- **Attention shifted** to the adjacent anti-vaccination-statements paper (BDS / SSRN).

## What is already done (recovered assets)

From [`local_only/PI_update.md`](../local_only/PI_update.md) and the `outputs/` tree:
- ✅ **Scraped corpus** of CA legislative press releases (text bodies) — `data/press_releases/`.
- ✅ **AI-statement detection (v3)** — `outputs/v3/`, summarized to `outputs/viz_data/statements/`
  + `outputs/figures/statements/`.
- ✅ **Claim extraction (LLM)** — **7,139 claims (5,249 D / 1,890 R)** — `outputs/claims/`.
- ✅ **Scientific-reference retrieval (GPT-5 + web search)** for all claims —
  `outputs/structured_refs/{dem,rep}_claim_references.json`, summarized to
  `outputs/viz_data/references/` + `outputs/figures/references/`.
- ◑ **Validation / annotation framework** — *designed, partially set up, not finished.* The
  4-checkpoint scheme is in [`local_only/validation-ideas.md`](../local_only/validation-ideas.md);
  guidelines + per-annotator assignment sheets for **Sai** and **Zack** are under
  `outputs/pilot/{sai,zack}/` (plus a transportation-domain extension in `outputs/pilot_transport/`).

## The open problem

LLMs **retrieve** relevant science well; the unsolved step is judging whether the science
**supports** the claim. In the team's annotation design this is **checkpoint #4 — stance
classification** (support / refute / mixed / unclear), gated on checkpoint #3 (evidence
relevance). This is exactly the validation the **APSA abstract** promises ("validate the AI
pipeline by comparing automated claim-evidence assessments to human expert coding").

## Revival plan

### Phase 0 — Finish the validation study (makes the APSA paper real)
1. **Recruit 1–2 annotators** to replace Sai & Zack.
2. **Resume the existing annotation framework** (`outputs/pilot/`, `validation-ideas.md`,
   `outputs/pilot/guidelines.md`): doc AI-relevance → claim quality → pair relevance → **stance**.
   Use the existing assignment sheets; double-annotate ~15% and report Cohen's κ.
3. **Build the human-coded gold set** for stance (support/refute/silent), stratified by party ×
   topic (the design suggests ≈241 claims → ≈1,200 pairs to start; the APSA/LOI target is ≥1,000).
4. **Benchmark LLM stance judgments** (GPT-5 + ≥1 alternative) against the gold set; report
   precision/recall, confusion matrices, and systematic (party/topic) error. **This is the APSA
   contribution.** A new `scripts/` stage for stance scoring is the main code to add.

### Phase 1 — Scale & describe
5. Extend scraping beyond CA Assembly to more states; re-run the pipeline (LOI target ≈25,000
   releases, 2020–2025).
6. Produce the descriptive "evidence use by party / domain" results for both the AI and
   education domains (the education corpus + analysis are ready now in `education_pilot/`).

### Phase 2 — Reframe & resubmit funding
7. **Answer the W.T. Grant critique**: replace "passive" evidence-sharing with an **active**
   intervention (interactive Evidence Reports / a chatbot), and foreground the **RCT**.
8. Prepare the **NSF** proposal (agreed path); the 3-phase LOI design is a ready skeleton.

### Quick wins available now
- Education corpus analysis is fully reproducible today (`education_pilot/`).
- The references dataset (`outputs/viz_data/references/`) supports immediate descriptive
  write-up of evidence recency/venue/volume by party.
- A short methods note framing the **stance** problem + a small benchmark would de-risk Phase 0.

## Open questions for Bruce
- APSA 2026 — accepted? Who presents?
- Confirm **Xinyu Wang's** role on this strand (vs. the anti-vax paper).
- Target **NSF** program / deadline for the revised proposal?
- Were any of the `outputs/pilot/{sai,zack}/` assignments actually **completed** (labels), or
  only assigned? (The sheets present look like assignments; finished labels weren't located.)
