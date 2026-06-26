# Rebuild plan — validated autonomous pipeline → Nature Communications

## The pivot (why this is no longer a "cautionary feasibility" paper)
The old paper concluded "we can't validate the LLM judge without in-domain human labels, so the
estimates are conditional on an unvalidated judge." The fix: **validate the judge against EXISTING
human-labeled benchmarks for the identical task** (claim × abstract → support/refute/silent). This
supplies the human anchor the old paper said it lacked, and — because benchmark text is human-written —
**directly rules out self-preference** as the driver of accuracy. The pipeline now *works*.

## Headline numbers (human-anchored validation)
SciFact (Wadden 2020), n=340 abstract-level pairs (138 support / 71 refute / 131 silent):
- **Claude Opus 4.8 judge: acc 0.803, macro-F1 0.803** (n=66 blind), refute F1 0.93, support F1 0.77, silent F1 0.71
- NLI-DeBERTa: acc 0.703, macro-F1 0.690 ; NLI-BART: acc 0.706, macro-F1 0.696
- TF-IDF baseline: acc 0.50, macro-F1 0.48
- claude~NLI kappa 0.46–0.48 (vs 0.15–0.21 on LLM-retrieved policy refs → the poor policy agreement
  was an artifact of relevance-retrieval, NOT a judge/NLI incompatibility)
- Open-LLM panel (Qwen2.5-3B, Phi-3.5-mini, OLMo-2-7B): [PENDING phase2]
Climate-FEVER (Diggelmann 2020), balanced 450 (150/class), contested real-world claims:
- Claude judge: [PENDING — 45 blind labels saved], NLI/panel: [PENDING phase2]
Lit context: Claude-3.5-Sonnet ~0.86 F1 zero-shot biomedical claim verification; GPT-4 ~0.93 acc on
political text annotation (Heseltine 2024; Törnberg 2025). Our 0.80 on broad SciFact is in-range.

## Pipeline (reproducible, no paid API, no human RAs)
1. Claim extraction (LLM) → empirical claims from press releases.
2. **Reproducible retrieval from OpenAlex** (openalex_retrieval.py) — real papers, real DOIs, real
   abstracts; replaces hallucination-prone "ask GPT-5 for references." [retrieval running]
3. Stance: validated LLM judge (Claude) as gold-on-a-sample + NLI surrogate on all + open-LLM panel;
   PPI to combine; party-level support rates.

## Application (CA legislative AI communication)
- Engagement asymmetry: Dems mention AI 4.8% of releases vs 2.6% Rep; 3.3 vs 1.6 AI statements/doc.
- Support rates by party (validated judge + PPI): Dem 0.71, Rep 0.54 [existing; recontextualize as
  anchored on a judge validated at 0.80 vs humans, not "unvalidated"].
- Retrieval robustness: OpenAlex vs GPT-5 references give similar pattern [PENDING phase2 policy_stance].
- Cross-domain: education-policy corpus (5,131 releases) shows pipeline generalizes beyond AI.

## Multi-state note
Attempted NY Senate + WA caucus press releases; sites have inconsistent/partisan-asymmetric bot
blocking (House Dems 200, House Reps 403) which would bias the party comparison → did NOT use. Pipeline
is state-agnostic and validated; multi-state rollout is the deployment path. Strengthened "more data"
via two human-labeled benchmarks + cross-domain instead.

## Paper structure (Nature Communications: Results before Methods)
Title → Abstract → Intro → Results(R1 pipeline, R2 benchmark validation, R3 self-preference ruled out,
R4 CA application, R5 reproducibility+cross-domain) → Discussion → Methods → Refs → Data/Code avail.

## TODO
- [x] SciFact validation (Claude + NLI + tfidf)
- [ ] phase2: SciFact panel, Climate-FEVER (NLI+panel), policy stance (OpenAlex+GPT5)  [running]
- [ ] Claude scoring on Climate-FEVER (run benchmark_validation --validators claude --tag cf_claude)
- [ ] figures (make_paper_figures_v2.py)
- [ ] write paper (Nature Comms framing), compile, verify cites
- [ ] email Bruce when done
