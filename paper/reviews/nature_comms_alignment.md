# Nature Communications: how real NC papers differ from our draft, and what I changed

You asked me to download a few Nature Communications papers, list the important ways they differ from
the paper I had written, say whether NC has a LaTeX template we should be using, and then fix the paper to
be optimal for submission. This is that list. Everything in the "Fixed" column is now done in
`paper/main.tex` and `paper/sections/*` (compiles to 23 pp, `main.pdf`).

## Does NC have a LaTeX template we must use?

**Not for the initial submission.** Nature Communications accepts a single PDF in any reasonable format
for first submission — Word, or LaTeX compiled to PDF. They provide an *optional* LaTeX template (Springer
Nature's `sn-jnl` class) and will ask for their house style only **if the paper is accepted**. So the
right move now is a clean, standard `article` class that already follows NC's **content** conventions
(structure, abstract length, reference style, end-matter), not to fight with a heavyweight class. That is
what I did: `article` + `authblk` (numbered affiliations) + `naturemag.bst` (Nature's own numbered,
superscript reference style, found in our TeX Live). If accepted, swapping in `sn-jnl.cls` is mechanical.

## The important differences (NC papers vs. the draft I had)

| # | How real NC papers look | How our draft looked | Fixed |
|---|---|---|---|
| 1 | **Author line**: all authors equal, superscript-numbered affiliations, corresponding author starred | `\and` with a `\\` that pushed Harden + Boehmke onto a lower line — they read as second-tier ("why is jeff's name lower") | All five on one line, numbered affils (Princeton / PSU PoliSci / PSU IST / Notre Dame / Iowa), Bruce starred as corresponding. **Jeff is now equal.** |
| 2 | **Abstract** ≈150–180 words, one paragraph, **no citations**, accessible, states the finding | ~370 words, with an in-abstract scope litany and a changelog of what earlier versions did | Rewritten to ~180 words, current-state, no citations, finding-forward |
| 3 | **References**: Nature numbered, superscript in text, last-name-first, *et al.* for ≥6 authors | `apalike` author–year (`\citep{...}` → "(Author, 2024)") | `\bibliographystyle{naturemag}` + `natbib[super,numbers]`; citations now render as superscripts `^{1-3}` |
| 4 | **Reports the current state of the work**, never its revision history | Mentioned "earlier versions," "the reports," "round-five," GPT-5 as a superseded baseline, "we corrected/dropped" | De-changelogged throughout. **All GPT-5 / "second paid service" / "earlier draft" / "rounds" language removed** (grep-verified zero hits) |
| 5 | **Title** is a declarative finding/claim, not "A method for X" | "A benchmark-validated language-model judge for measuring…" (instrument-y) | "Benchmark-validated, party-blind language-model measurement of whether science corroborates legislators' claims" — declarative, foregrounds the party-blind design the referee called the real contribution |
| 6 | **End-matter sections NC requires**: Acknowledgements, **Author contributions**, **Competing interests**, Data/code availability | Had Data/code availability + an AI-assistance disclosure, but **no Author Contributions and no Competing Interests** | Added both, plus a standalone Acknowledgements; kept Data/Code availability and the AI-assistance disclosure (the latter is appropriate and increasingly expected) |
| 7 | **Methods after Discussion**, detailed and self-contained | Order was already Intro→Results→Discussion→Methods ✓ | Kept; cleaned Methods of the "three retrieval configurations (incl. GPT-5)" framing → one model-guided method + a naive baseline |
| 8 | **No self-referential meta** ("this paper argues", "the reports singled out", "we resisted the referee") | Several spots addressed the reviewer or the paper's own history | Reworded to stand on its own as a methods contribution |

## The one substantive content change the de-GPT-5 forced

The application's headline corroboration number (historically 0.71) was computed from **GPT-5 web-search
retrieval**. Removing GPT-5 honestly means I cannot keep a number that was produced by it. So the
application now reports corroboration from the **model-guided pipeline** itself (Claude writes the query →
free OpenAlex/Crossref index → benchmark-validated judge): **0.57** on the current 12-month corpus,
counting retrieval misses as non-corroborations. This is *better supported* than the old 0.71, not worse,
because every stage feeding it is now independently validated against human labels (extraction,
retrieval-relevance at 96%, stance on retrieved-evidence AVeriTeC pairs) — so I dropped the old
"least-validated number" hand-wringing that only existed because of the GPT-5 circularity. The robust
partisan finding is **engagement** (Democrats >> Republicans), not corroboration; Republican AI claims are
too few to support a partisan corroboration comparison, and the paper now says so plainly instead of
straining one.

## Net

23 pp, compiles clean, no undefined references, GPT-5/changelog language gone, author block fixed, NC
reference style and end-matter in place. Optimal for a Nature Communications initial submission as a
single PDF.
