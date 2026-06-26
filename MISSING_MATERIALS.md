# Materials status — mostly recovered

Most of what was flagged as missing in the first pass was **recovered** from the original
project repo (`SaiDileepKoneru/AI-Policy-Project`), which Bruce provided and which is now
consolidated here.

## ✅ Recovered (now in this repo)
- **Pipeline code** — `scripts/core/` (v3 AI detection, `llm_claims.py`, `gpt_references.py`,
  `summarize_structured_references.py`) and `scripts/pilot/` (annotation prep, evaluation,
  classifier, triage).
- **Claims** — `outputs/claims/` (7,139 claims; per-doc LLM JSON under `outputs/claims/llm/`).
- **GPT-5 reference results** — `outputs/structured_refs/{dem,rep}_claim_references.json`
  (the data behind the talk's references-per-claim / venues / reference-years figures).
- **AI-related press-release text** — `data/Dem_AI/`, `data/Rep_AI/`, and full corpora under
  `data/press_releases/`.
- **Annotation framework** — `outputs/pilot/` (guidelines + Sai/Zack assignment sheets) and the
  design in `local_only/validation-ideas.md`.

## ◑ Still open / to confirm
1. **Completed human labels.** The `outputs/pilot/{sai,zack}/` files look like *assignments*;
   finished stance/relevance **labels** were not located. Did Sai/Zack complete any, and where?
2. **APSA 2026 decision** — accepted? Session/panel? Who presents?
3. **Xinyu Wang's role** on this strand (Wang co-authors the adjacent anti-vax paper; not on the
   Notre Dame talk).
4. **"Sai's comparison policy"** — the Dec 22 email trailed off ("the comparison policy that Sai
   has been working on…"). The repo shows a **transportation** extension
   (`outputs/pilot_transport/`) — is transportation the intended comparison domain?
5. **NSF program / deadline** targeted for the revised proposal.
6. **Original APSA draft** (`APSA 2026 Proposal Submission.docx`, Nakka's 2026-01-12 version) —
   only the *submitted* edit is in the repo; the original is in email only.

If you can point me to completed annotation labels (item 1), I can wire up the stance benchmark
immediately.
