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


