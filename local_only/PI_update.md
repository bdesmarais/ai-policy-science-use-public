## Project goal

Support/refute structured claims made in California legislative press releases by:
- Extracting AI-related statements (v3) from raw texts.
- Building compact structured claim lists (Democratic and Republican).
- Retrieving scientific references per claim using GPT‑5 (Responses API with web_search and JSON schema).
- Summarizing references across claims for analysis and visualization.

## Data processed and locations

- Raw press releases
  - `data/press_releases/Democratic/`, `data/press_releases/Republican/`

- AI statements (v3) outputs
  - `outputs/v3/ai_statements_v3.csv`: one row per AI sentence (source, filename, date, matched terms, URLs/DOIs/arXiv, sentence text)
  - `outputs/v3/ai_documents_v3.csv`: per-document counts (sentences, AI statement counts, unique URLs/DOIs/arXiv)
  - Auxiliary EDA files and optional figures under `outputs/v3/`

- Structured claims (for references)
  - `outputs/claims/dem_claims.json`, `outputs/claims/rep_claims.json`: `{press_release, claim_number, claim_text, claim_desc}` per claim

- References (final JSON)
  - `outputs/structured_refs/dem_claim_references.json`, `outputs/structured_refs/rep_claim_references.json`: per-claim results with `references` list and `search_metadata`

- Statements analysis deliverables (ready for Tableau)
  - Tables: `outputs/viz_data/statements/`
  - Figures: `outputs/figures/statements/`

- References analysis deliverables (ready for Tableau)
  - Tables: `outputs/viz_data/references/`
  - Figures: `outputs/figures/references/`

## AI statements analysis (v3)

What was generated from the v3 statements pipeline:

- Tables (CSV)
  - `statements_by_party.csv`: documents, documents_with_ai, documents_with_ai_ratio, total AI statements, average per doc, average per AI doc.
  - `top_terms_by_party.csv`: top AI terms (ranked) with counts per party.
  - `statements_per_doc.csv`: distribution of AI statements per document (party label; usable for box/violin plots).
  - `citations_in_text.csv`: totals and per-statement averages for URLs/DOIs/arXiv mentions in AI statements (by party).

- Figures (PNG)
  - `docs_with_ai_by_party.png`, `ai_statements_by_party.png`, `top_terms_by_party.png` (top 10 per party), `statements_per_doc_distribution.png`.

## References analysis (structured claims)

Flattened references dataset and summary tables derived from the GPT‑5 references:

- Flattened references (row = reference with claim context)
  - `references_flat.csv` columns: `party` (claim owner), `press_release`, `claim_number`, `claim_text`, `provider`, `id`, `doi`, `title`, `abstract`, `year`, `venue` (normalized), `authors` (joined), `url`, `is_open_access`.

- Summary tables (CSV)
  - `references_per_claim.csv`: number of references attached to each claim (interpreted as evidence we retrieved for the party’s claim).
  - `venues.csv`: distribution of normalized venues (journal/conference) by party.
  - `years.csv`: distribution of reference years by party.
  - `open_access_rate.csv`: OA rate for party and overall.
  - `references_by_press_release.csv`: references aggregated per press release by party.
  - `duplicates_report.csv`: duplicate keys by DOI or title+year with counts (quality check).
  - `provider_counts.csv`: provider frequencies (e.g., arXiv, publisher) by party.

- Figures (PNG)
  - `refs_per_claim_distribution.png`: references per claim (boxplot by party).
  - `top_venues.png`: top venues per party (horizontal bars).
  - `years_hist.png`: reference years (histogram by party).
  - `oa_rate_for_party.png`: open access rate for party (bar).
  - `refs_per_press_release_topk.png`: top press releases by total references.

## Methodology and safeguards (references)

- Retrieval
  - GPT‑5 Responses API with `web_search` and a strict JSON schema for `{references:[...]}`.
  - Two‑pass strategy (schema+tool → fallbacks) to maximize robust structured output.

- Prompt constraints
  - `provider` = discovery source (e.g., ‘arXiv’, ‘publisher’, ‘Crossref’, ‘OpenAlex’).
  - `venue` = true journal/conference; use ‘arXiv’ only if preprint‑only.
  - Include `claim_desc` when available for additional topical guidance.
  - Allow `doi = null` with a reputable URL; do not fabricate identifiers.

- Normalization
  - Venue names normalized to standard forms where applicable (e.g., NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV, AAAI, IJCAI, ACL, EMNLP, NAACL, KDD, The Web Conference, SIGIR, JMLR, PNAS).

- De‑duplication
  - Deduplicate first by DOI; else by title+year.

- Auditability
  - Per‑claim metadata retained in JSON outputs (model, timestamp, raw preview, parse status).

## How to interpret key metrics

- References per claim: quantity of evidence we retrieved for each party’s claim (not supplied by the party).
- OA rate for party: proportion of references for that party’s claims that are open access (our retrieval outcome).
- Venue distribution: where referenced works are published/presented; normalized for consistency.
- Year distribution: recency of evidence used in assessing claims.
- Press‑release variation: heterogeneity in reference counts across individual press releases.
- Provider counts: where references were discovered (arXiv vs publisher, etc.), distinct from publication venues.

## Current status

- AI statements deliverables are complete (tables and interim figures) in:
  - Tables: `outputs/viz_data/statements/`
  - Figures: `outputs/figures/statements/`

- References are fully collected (Dem + Rep) and summarized into analysis‑ready assets:
  - Tables: `outputs/viz_data/references/`
  - Figures: `outputs/figures/references/`

## Caveats and notes

- GPT‑5 outputs are strongly constrained but may omit DOIs when unavailable; reputable URLs are included.
- Venue normalization covers common venues; niche venues may appear verbatim.
- Title+year de‑duplication (fallback) can conflate identical titles; DOI presence mitigates this.
- “Party” labels denote claim ownership; references represent evidence we retrieved to support/refute those claims, independent of what the party cited in the press release.

## Paths to share

- Statements (tables): `outputs/viz_data/statements/`
- Statements (figures): `outputs/figures/statements/`
- References (tables): `outputs/viz_data/references/`
- References (figures): `outputs/figures/references/`

## Optional next steps

- Map venues to disciplines/fields to show disciplinary mix.
- Spot‑check a sample of references per claim for topical precision.
- Build a Tableau workbook with two dashboards (“AI Statements Overview” and “References Overview”) sourcing the CSVs above.


