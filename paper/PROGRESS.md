# Paper build — living progress tracker

**Goal (Bruce, June 2026):** write the full paper to *submission-ready*, working serially (no agent
swarms), don't stop per-step to email; email only when done. Work continuously across turns.

**Working title:** *Does the Science Support the Claim? Autonomously Measuring Scientific-Evidence
Use in State Legislative Communication with LLM Judges and Prediction-Powered Inference.*

**Target venue:** a political-methodology / computational-social-science outlet (e.g., Political
Analysis, PSRM, or APSR-methods); also fulfills the APSA 2026 paper.

## Section status
- [x] scaffold (main.tex, references.bib, sections/)
- [x] Methods (sections/methods.tex)
- [x] Related work (sections/related.tex)
- [x] Introduction (sections/intro.tex)
- [x] Data (sections/data.tex)
- [x] Results (sections/results.tex) — 4 figures + 2 tables
- [ ] Discussion (sections/discussion.tex)
- [ ] Limitations + Conclusion (sections/conclusion.tex)
- [ ] Abstract (in main.tex)
- [ ] compile to PDF (pdflatex/latexmk) + fix errors
- [ ] proofread pass
- [ ] final commit + ONE email to Bruce with the finished PDF info

## Data / analysis tasks
- [x] SCALE Claude gold judgments: now 120 pairs (60 D / 60 R) in claude_judge_labels.json.
      (Could scale further to tighten CIs more; 120 gives usable CIs.)
- [x] Generate paper figures into paper/figures/ (corpus, agreement, support-rate w/ CIs,
      NLI-vs-Claude bias, education asymmetries).
- [ ] Final validation run; lock numbers into results.tex.

## Key numbers locked in (authoritative, from outputs/)
- Corpus (v3): 7,139 CA Assembly press releases (Dem 5,249 / Rep 1,890), 2010s–2025.
- AI-related: 303 docs (Dem 254 / Rep 49); 910 AI statements (Dem 832 / Rep 78).
  Doc-with-AI ratio Dem 0.048 vs Rep 0.026; avg AI stmts/AI-doc Dem 3.28 vs Rep 1.59.
- Reference retrieval: 621 claim–reference pairs validated; OA rate Dem 0.83 / Rep 0.90 / overall 0.87
  (785 refs w/ OA info); top venue arXiv; reference years concentrate post-2015, spike to 2024.
- Education pilot (separate corpus): 5,131 releases (4,279 D / 852 R); 611 education-related (11.9%);
  SEL 80 vs 1; school safety 38 vs 4.
- Autonomous validation (120-pair Claude gold + 2 NLI surrogates on 621 pairs):
  - Claude~NLI agreement κ≈0.14–0.20 (low, n=124); NLI~NLI κ=0.654 (high, n=621).
  - Consensus: silent 76.0% / support 16.9% / refute 6.8%.
  - Support rate naive-NLI: Dem 0.21 / Rep 0.11.
    PPI-debiased (Claude gold): Dem 0.709 [0.574, 0.844] / Rep 0.578 [0.451, 0.705]; anchor n=60/64.
  - Claude gold support_rate: Dem 0.70 / Rep 0.567 (raw, 120 pairs).

## Env notes
- pdflatex/xelatex/latexmk available. torch+transformers installed; MPS works; NO API key (use
  open models + Claude-in-session as judge).
- Each work-turn: quick `agentmail check` for a NEW Bruce reply (honor a "stop"/redirect); else keep working. Do NOT email per-step.
