## Press Releases Science Mentions Extraction

This project extracts scientific mentions, claims, and references from press releases contained in two zip archives:

- `OneDrive_2025-08-19.zip` — Democratic Assembly
- `OneDrive_2025-08-19 (1).zip` — Republican Assembly

The script unzips `.txt` documents, parses them for Artificial Intelligence (AI) and science-related terms, identifies claim-like language, and extracts references (URLs, DOIs, arXiv IDs, journal-like mentions). Results are exported to JSON, CSV, and Markdown.

### Files

- `analyze_press_releases.py`: Main analysis script (v1).
- `analyze_press_releases_v2.py`: Enhanced analysis (v2) with stricter AI detection, context-aware claims, verifiability scoring, comparative stats, and optional charts.
- `data/press_releases/`: Extracted `.txt` files organized by party.
- `outputs/`: Generated outputs:
  - `press_release_science_mentions.json` — structured results per document and sentence.
  - `press_release_science_mentions.csv` — one row per sentence mention.
  - `press_release_document_summary.csv` — per-document aggregates.
  - `press_release_science_mentions.md` — human-readable summary by source.
  - v2 additions (from `analyze_press_releases_v2.py`):
    - `press_release_science_mentions_v2.json` — includes context windows, `is_ai_claim`, and verifiability.
    - `press_release_science_mentions_v2.csv` — per-mention CSV including `verifiability_score`/`level`.
    - `press_release_document_summary_v2.csv` — per-document aggregates with AI-claim counts and average verifiability.
    - `press_release_party_comparison_v2.csv` — Democratic vs Republican comparative statistics.
    - `press_release_top_terms_v2.csv` — top AI/science term frequencies per source.
    - `press_release_science_mentions_v2.md` — comprehensive markdown summary with exemplars.
    - `outputs/figures/` — optional bar charts if matplotlib is available.

### Running

Requirements: Python 3.9+ (standard library only; no external dependencies).

Place the two zip files either:
- in this folder `press_releases_proj/`, or
- one level up (the parent directory).

Run v1:

```bash
python analyze_press_releases.py
```

Run v2 (recommended):

```bash
python analyze_press_releases_v2.py
```

The scripts will:
- Extract `.txt` files to `data/press_releases/Democratic` and `data/press_releases/Republican`.
- Analyze sentences for AI and science mentions, claim-like phrasing, and references.
- Write outputs into `outputs/`.
  - v2 additionally computes context-aware AI-related claims and verifiability scores, and writes party comparisons and optional figures.

### What the scripts detect

- AI keywords: e.g., "artificial intelligence", "machine learning", "LLM", "ChatGPT", "algorithmic transparency".
- Science terms: e.g., "peer-reviewed", "evidence", "study", "randomized", "DOI", "arXiv", metrics like "accuracy".
- Claim-like patterns: e.g., "research shows", "according to", "results indicate".
- References: URLs, DOIs, arXiv IDs, bracketed citations `[12]` or `[Author, 2020]`, journal-like strings.

v2 improvements:
- Uses boundary-aware regexes to avoid false positives from substrings (e.g., not matching "jail" for `ai`). Also normalizes variants like `A.I.` → `AI`.
- Flags `is_ai_claim` only when claim-like phrasing co-occurs with AI/science terms in the sentence or its immediate neighbors.
- Assigns a `verifiability_score` and `verifiability_level` to each mention based on presence/quality of references and quantitative metrics.

### Outputs schema

- JSON fields per document: `source`, `filename`, `document_date`, `num_sentences`, unique references, and `mentions`.
- Each `mention` (sentence) includes flags for AI/science/claim-like, matched terms, references, and the sentence text.

v2 mention fields add: `is_ai_claim`, `number_metrics`, `verifiability_score`, `verifiability_level`, `context_before`, `context_after`.

### Notes

- The sentence splitter is rule-based and robust to bullets and line breaks.
- Encoding fallback supports UTF-8/16, Latin-1, and CP1252.
- Datetime in Markdown is timezone-aware (UTC).
- Visualizations are optional; if `matplotlib` is not installed, v2 will skip plotting silently.

### Summary statistics and comparisons (v2)

Key CSVs in `outputs/`:
- `press_release_party_comparison_v2.csv`: per-source counts for AI mentions, science mentions, claim-like sentences, AI-related claims, and average verifiability scores.
- `press_release_top_terms_v2.csv`: top AI and science terms by source.
- `press_release_document_summary_v2.csv`: per-document aggregates including `num_ai_claims` and average verifiability.

If matplotlib is available, `outputs/figures/` will include:
- `ai_mentions_by_source.png`
- `science_mentions_by_source.png`
- `ai_claims_by_source.png`

These enable quick visual comparison of whether the Democratic vs Republican assemblies used more AI-related or scientific terminology, and whether their AI-related claims appear more verifiable (higher average scores).

### Maintenance

- To extend AI or science term coverage, edit `AI_KEYWORDS` and `SCIENCE_TERMS` in the script.
- To adjust "claim-like" detection, edit `CLAIM_PATTERNS`.


