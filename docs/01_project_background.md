# Project Background

## Motivation

Policymaking increasingly turns on technical questions — in AI governance, in education, in
public health — where the relevant evidence is voluminous, fast-moving, and contested.
Legislators and staff rarely have the time or training to locate and weigh the scientific
record behind the claims they make. At the same time, "what the research shows" has itself
become a partisan battleground: evidence is invoked selectively, and scientific authority is
contested.

This project asks two linked questions:

1. **Descriptive:** How do policymakers actually invoke scientific evidence in their public
   communications, and how does that vary by party, polarization, and policy domain?
2. **Interventional:** Can modern LLMs *measure* the evidentiary basis of policy claims at
   scale — and can delivering AI-synthesized, non-partisan "Evidence Reports" to legislators
   *improve* their use of research evidence?

## The AI evidence-linking pipeline

The core technical artifact is a pipeline that turns a policymaking document into a set of
**(claim → relevant science → support assessment)** records:

1. **Collect** policy communications (press releases, and eventually bill analyses and
   committee testimony) via web scraping.
2. **Extract claims** — use **NotebookLM** to pull up to 10 claims per document that "if you
   were writing a scientific paper, you would need to have references" for. Output is
   structured: press-release ID, claim number, claim text + description.
3. **Retrieve evidence** — use a web-connected LLM (**GPT-5**, via the OpenAI API) to return
   up to 10 candidate scientific references per claim, as JSON (title, DOI, authors, year,
   venue, URL). The design intent (per the W.T. Grant proposal) is parallel search across
   **Crossref, Semantic Scholar, and targeted web sources**.
4. **Assess support** — judge whether the retrieved science **supports, refutes, or is silent
   on** the claim. This is *scientific hypothesis evidencing* in the sense of Koneru, Wu &
   Rajtmajer (2024). **This step is the project's principal open problem** (see
   [03_status_and_revival_plan.md](03_status_and_revival_plan.md)).
5. **Report** — eventually, synthesize per-claim assessments into accessible "Evidence
   Reports" for time-constrained policymakers.

## Domain 1 — AI policy (the original case)

Presented at the **RISE AI Conference, Notre Dame, October 7 2025** as *"Assessing Science Use
in AI Policymaking: An AI Pipeline"* (slides: [`docs/source_materials/ND_AI_talk_bd.pdf`](source_materials/ND_AI_talk_bd.pdf)).

Why AI policy, and why California:
- State AI policymaking is exploding — NCSL counts of AI bills in state legislatures jumped
  from ~75 (2019) to ~480 (2024).
- California is the highest-activity, highest-profile state (with New York), and AI policy
  combines high salience with high technical uncertainty — an ideal stress test for an
  evidence-linking pipeline.

Pilot findings reported in the talk (CA legislators' **AI-related** press releases):
- Volume skews sharply Democratic: **254** AI-related releases from Democratic Assembly
  members vs **49** from Republicans.
- Fightin'-words analysis (Monroe et al. 2008) shows partisan vocabulary: Democrats emphasize
  *generative, health, data, use, legal, deepfakes*; Republicans emphasize *accountability,
  fairness, enforcement, safety, senate*.
- The pipeline retrieves a **substantial** body of relevant science (median ~20 references per
  claim for both parties), heavily skewed to **recent** years (reference counts rising steeply
  through 2024).
- Top venues: **arXiv, Science, PNAS, Nature, CVPR, NeurIPS, FAccT** (Dem) and **arXiv,
  Science, International Data Privacy Law, PNAS, Nature, USENIX** (Rep).
- Takeaway: there *is* a large recent scientific literature relevant to AI-policy debates, and
  Gen-AI tools can surface it — but **validation** of the support/refute judgment is the
  outstanding need.

## Domain 2 — K-12 education policy (the W.T. Grant pilot)

To pursue William T. Grant Foundation funding (whose focus area is *improving the use of
research evidence*), the team adapted the pipeline to **polarized K-12 education policy**:
SEL/mental health, school safety, reading/curriculum, school choice, ed-tech/AI.

The letter of inquiry — *"AI-Assisted Evidence Linking: A Strategy to Improve Research Use in
Polarized K-12 Education Policymaking"* (Desmarais, Rajtmajer, Harden, Boehmke) — proposed a
three-phase design:
- **Phase 1 (Baseline):** ~25,000 press releases across states (2020–2025); validate ≥1,000
  claim-evidence pairs with human coders.
- **Phase 2 (Tool + pilot):** build "Evidence Reports"; pilot with ≥50 legislative staff in 10
  states; pre/post surveys + interviews.
- **Phase 3 (RCT):** randomized trial with ≥2,000 legislators/staff; difference-in-differences
  on citation accuracy + research-use attitudes.

The pilot corpus (this repo's `data/`) demonstrates feasibility: **5,131** CA Assembly press
releases (4,279 D / 852 R; the ~5:1 imbalance reflects ~75% Democratic membership). Keyword
filtering finds **611** education-related releases (11.9%), with strong partisan asymmetries:
- Education share: **13.1%** (D) vs **5.9%** (R).
- SEL / student mental health: **80** (D) vs **1** (R).
- School safety: **38** (D) vs **4** (R).
- Reading / curriculum: **26** (D) vs **7** (R) — roughly balanced, and slightly *higher* for
  Republicans once normalized by total output.

These are reproduced exactly by [`code/analyze_press_releases.py`](../code/analyze_press_releases.py);
figures in [`figures/`](../figures/).

## Relationship to other group work (adjacent, not in this repo)

The same faculty core (Desmarais, Rajtmajer, Harden, Boehmke) runs several related lines:
- **Anti-vaccination statements paper** — *"Elected officials' online anti-vaccination
  statements respond to online engagement"* (Kim, Wang, Harden, Rajtmajer, Boehmke,
  Desmarais). Submitted to **Big Data & Society** (#BDS-26-0448, Apr 2026); on **SSRN**
  (abstract 6779038, May 2026). Same computational-social-science team; **distinct topic.**
- **Policy diffusion / SPID** (Boehmke) and a broader data-policy strand (the "Democratic
  Accountability Requires Democratic Data" commentary with Munger, Lin, Tai, Patni) provide
  intellectual and methodological context but are separate projects.

## Key citations used in the proposals

- Koneru, Wu & Rajtmajer (2024), *Can LLMs discern evidence for scientific hypotheses?* —
  the methodological backbone for the support/refute step.
- Grimmer (2013); Lipinski (2009) — legislative communication / press releases as data.
- Monroe, Colaresi & Quinn (2008) — Fightin' Words for partisan term comparison.
- Weiss (1979); Oliver et al. (2022); Bogenschneider et al. (2019); Langer et al. (2016) —
  the "research use" literature underpinning the theory of change.
- Full reference list in the W.T. Grant LOI (`docs/source_materials/AI_WTG_LOI.pdf`).
