## AI Mentions Extraction from Legislative Press Releases (v3)

This project analyzes press releases scraped from Democratic and Republican Senates and Assemblies.
It identifies Artificial Intelligence (AI) mentions, extracts AI-related sentences ("AI statements"),
produces exploratory data analysis (EDA), and organizes AI-containing documents for downstream work.

### Data layout

- `data/press_releases/Democratic/` — Democratic sources (scraped text files)
- `data/press_releases/Republican/` — Republican sources (scraped text files)
- `data/Dem_AI/` — created by the v3 script: Democratic documents that contain AI statements
- `data/Rep_AI/` — created by the v3 script: Republican documents that contain AI statements

### Scripts

- `analyze_press_releases_v3.py`
  - Parses documents for AI keywords and extracts AI statements (any sentence containing AI terms).
  - Generates EDA comparing Democratic vs Republican sources.
  - Copies AI-containing files to `data/Dem_AI` and `data/Rep_AI`.
  - Exports consolidated CSVs and optional charts.

- `llm_claims.py` (LLM-first, replaces rule-based claim export)
  - Extracts claims per press release using OpenAI Responses API (`gpt-4o-mini`) with a strict JSON schema.
  - Supports chunking for long docs, caching/resume, and per-doc outputs under `outputs/claims/llm/<party>/<file>.json`.
  - Aggregates compact claims to `outputs/claims/{dem,rep}_claims.json` with fields: `press_release`, `claim_number`, `claim_text`, `claim_desc`.

- `build_claim_lists.py` (legacy)
  - Previously exported compact JSON claims from CSVs under `data/structured_claims/`. Retained for reference.

- `gpt_references.py`
  - Uses the OpenAI Responses API (GPT-5 or compatible) with web search and a JSON schema to fetch structured scientific references for each claim.
  - Enforces de-duplication (by DOI, else title+year), incremental writes, and robust JSON extraction from model output.
  - Adds per-claim metadata (model, timestamps, raw preview, parse errors) for auditing.
  - Output: `outputs/structured_refs/dem_claim_references.json` and `outputs/structured_refs/rep_claim_references.json`.

- `prepare_pilot_annotations.py`
  - Prepares pilot doc/claim/pair CSVs for annotation. Now supports `--claims-source llm` to read claims from `outputs/claims/{dem,rep}_claims.json`.

- `summarize_structured_references.py`
  - Flattens references and creates tables in `outputs/viz_data/references/` and figures in `outputs/figures/references/`.

- `evaluate_ai_statements.py` (optional)
  - Reads `outputs/v3/ai_statements_v3.csv` and can surface candidate references from Crossref/arXiv.
  - CLI flags:
    - `--skip-fetch`: do not call external APIs (faster);
    - `--fill-missing`: merge existing JSON and guarantee one entry per AI statement;
    - `--limit`: limit number of statements processed (`-1` = all);
    - `--rows-per-source`: number of candidates fetched per source when fetching.
  - Use `--skip-fetch --fill-missing` to quickly regenerate outputs without network calls.
  - This aids evaluation but does not perform verification.

- `summarize_ai_reference_counts.py` (optional)
  - Summarizes counts of scientific references per AI statement from the existing JSON
    (no API calls). Writes CSV/JSON with totals.

### Running v3

Requirements: Python 3.9+ (standard library only).

```bash
python analyze_press_releases_v3.py
```

Optional evidence retrieval (after running v3):

```bash
python evaluate_ai_statements.py
```

Examples:

```bash
# Ensure one row per AI statement (no API calls; fast)
python evaluate_ai_statements.py --skip-fetch --fill-missing --limit -1

# Summarize reference counts from existing JSON
python summarize_ai_reference_counts.py
```

### LLM-first workflow (pilot)

Requirements:
- Python 3.9+
- Install dependencies:

```bash
pip install -r requirements.txt
```

Environment:
- Set an OpenAI API key in your shell before running:
- PowerShell (Windows):

```bash
$env:OPENAI_API_KEY="sk-..."
```

- bash/zsh (macOS/Linux):

```bash
export OPENAI_API_KEY="sk-..."
```

Steps (pilot):

```bash
# 0) Prepare pilot doc lists (Dem/Rep × AI/non-AI), optionally tighten filters
python prepare_pilot_annotations.py --docs-per-cell 25 --tighten-docs --tighten-claims --tighten-pairs

# 1) Extract claims from pilot docs with LLM (reads doc lists from outputs/pilot)
python llm_claims.py --from-pilot outputs/pilot --model gpt-4o-mini --parallel 4 --resume

# 2) Collect references for claims (dem/rep combined outputs)
python gpt_references.py --model gpt-4o-mini --resume --per-claim 25

# 3) Summarize references (tables + figures)
python summarize_structured_references.py

# 4) Build pilot annotation CSVs using LLM claims
python prepare_pilot_annotations.py --claims-source llm --tighten-docs --tighten-claims --tighten-pairs
```

Outputs:
- Per-doc claims: `outputs/claims/llm/<party>/<file>.json`
- Aggregated compact claims: `outputs/claims/{dem,rep}_claims.json`
- Structured references: `outputs/structured_refs/{dem,rep}_claim_references.json`
- Viz: `outputs/viz_data/references/*`, `outputs/figures/references/*`

### Reference retrieval (GPT-5 + web search, legacy CSV claims path also supported)

Requirements:
- Python 3.9+
- Install dependencies:

```bash

pip install -r requirements.txt
```

Environment:
- Set an OpenAI API key in your shell before running:
  - PowerShell (Windows):

```bash
$env:OPENAI_API_KEY="sk-..."
```

  - bash/zsh (macOS/Linux):

```bash
export OPENAI_API_KEY="sk-..."
```

Optional environment variables:
- `OPENAI_MODEL` (default: `gpt-5`)
- `LOG_LEVEL` (e.g., `DEBUG`, `INFO`)

Option A — Build compact claims JSONs from CSVs (legacy source):

```bash
python build_claim_lists.py --limit -1
```

This writes:
- `outputs/claims/dem_claims.json`
- `outputs/claims/rep_claims.json`

Each entry contains: `press_release`, `claim_number`, `claim_text`, and `claim_desc` when present.

Then generate structured references:

```bash
python gpt_references.py --limit -1 --per-claim 25 --model ${OPENAI_MODEL:-gpt-5}
```

What this does:
- Calls the OpenAI Responses API with a concise system+user prompt per claim.
- Enables the `web_search` tool and requests a strict JSON payload via JSON schema.
- Falls back gracefully (with/without schema/tool) and forces a second attempt if no references are returned.
- Extracts valid JSON from any text, then de-duplicates by DOI or title+year.
- Writes incrementally after each claim to allow resuming.

Outputs written to `outputs/structured_refs/`:
- `dem_claim_references.json`
- `rep_claim_references.json`

Each entry includes:
- `press_release`, `claim_number`, `claim_text`, `query` (the exact prompt), `references` (objects with `provider`, `id`, `doi`, `title`, `abstract`, `year`, `venue`, `authors`, `url`, `is_open_access`), `num_references`, and `search_metadata` (`provider`, `model`, `attempted_at`, `error`, `raw_preview`, `raw_text`, `parse_error`).

Notes:
- DOIs may be `null` if unavailable; a reputable URL (publisher or arXiv) is included.
- Internet access is required; the script throttles internally and logs concise previews of raw outputs for debugging.

### Outputs

Outputs are written to `outputs/v3/`:
- `ai_statements_v3.csv` — one row per AI statement (sentence)
- `ai_documents_v3.csv` — per-document AI presence summary
- `ai_eda_summary_v3.csv` and `ai_eda_summary_v3.md` — party-level EDA
- `ai_top_terms_v3.csv` — top AI terms per source
- `ai_time_series_v3.csv` — monthly counts when dates are available
- `figures/` — optional bar charts if `matplotlib` is available

Evaluation outputs (if you run the helper):
- `outputs/v3_eval/ai_statement_candidate_evidence.json`
- `outputs/v3_eval/ai_statement_candidate_evidence.csv`
- `outputs/v3_eval/ai_statement_reference_counts.json`
- `outputs/v3_eval/ai_statement_reference_counts.csv`

### What is detected (v3)

- **AI statements**: any sentence that contains AI-related keywords (e.g., "artificial intelligence", "machine learning",
  "LLM", "ChatGPT", "foundation model", "computer vision", "facial recognition", governance terms like
  "algorithmic transparency").
- **Contextual references captured**: URLs, DOIs, and arXiv IDs appearing in AI statements (for context only; no scoring).

### Legacy (deprecated)

- `structured_references.py` implemented a Semantic Scholar/OpenAlex-based pipeline with aggressive query compaction and rate limiting. It is no longer part of the primary workflow and is retained only for reference.

### File structure (example)

```
press_releases_proj/
  analyze_press_releases_v3.py
  evaluate_ai_statements.py
  data/
    press_releases/
      Democratic/
      Republican/
    Dem_AI/           # created by v3
    Rep_AI/           # created by v3
  outputs/
    v3/
      ai_statements_v3.csv
      ai_documents_v3.csv
      ai_eda_summary_v3.csv
      ai_eda_summary_v3.md
      ai_top_terms_v3.csv
      ai_time_series_v3.csv
      figures/
    v3_eval/
      ai_statement_candidate_evidence.json
      ai_statement_candidate_evidence.csv
```

### Maintenance

- To extend AI term coverage, edit `AI_KEYWORDS` in `analyze_press_releases_v3.py`.
- The sentence splitter is rule-based and robust to bullets and line breaks.
- Encoding fallback supports UTF-8/16, Latin-1, and CP1252.


