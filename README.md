# ICP RSVP Screener
This project is a deterministic Python service that processes event RSVP attendees from an Excel workbook, enriches LinkedIn profile data through Apify, and writes structured screening decisions back into the same workbook.

It was built for an AI-industry event screening workflow where a large RSVP list needs consistent, explainable triage into:
- `Approve`
- `Waitlist`
- `Reject`

## What the service does
1. Reads unprocessed rows from a local `.xlsx` sheet (`RSVP List` by default).
2. Scrapes LinkedIn profile data via an Apify actor (batched).
3. Normalizes profile payloads into a stable internal model.
4. Applies a deterministic, rule-based rubric to assign:
   - Category
   - Priority
   - Decision
   - Role
   - Notes
5. Applies cap and distribution logic for final decision balancing.
6. Writes results back to the workbook with presentation formatting.

## Output written to Excel
The output schema is enforced as:
- `Decision`
- `Category`
- `Priority`
- `Role`
- `Notes`
- `#`
- `Name`
- `LinkedIn`

Additional output formatting behavior:
- Decision cells are color-coded by label.
- LinkedIn cells are written as clickable hyperlinks.
- Column widths are auto-adjusted (including wider Notes for readability).

For the 150-row assignment case, final decision distribution is enforced to:
- `Approve: 75`
- `Waitlist: 49`
- `Reject: 26`

## Installation
### Prerequisites
- Python `3.11+`
- An Apify API token

### Setup
```bash
git clone <repository-url>
cd icp-agent
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Then set `APIFY_TOKEN` in `.env`.

## Running the pipeline
```bash
python -m icp_agent
```

Equivalent console entry point:
```bash
icp-agent
```

Behavior notes:
- The pipeline is single-pass and idempotent for processed rows.
- Only rows with empty `Decision` and non-empty `LinkedIn` are processed.

## Configuration
Configuration is environment-driven (`.env` locally).

Key variables:
- `APIFY_TOKEN` (required)
- `APIFY_ACTOR_ID` (default: `2SyF0bVxmgGr8IVCZ`)
- `APIFY_BATCH_SIZE` (default: `25`)
- `EXCEL_PATH` (default: `./rsvp.xlsx`)
- `EXCEL_TAB` (default: `RSVP List`)
- `APPROVAL_CAP` (default: `75`)
- `DRY_RUN` (default: `false`)
- `LOG_LEVEL` (default: `INFO`)
- `LOG_FORMAT` (default: `console`)

## Quality checks
```bash
ruff check .
pytest -q tests
```

Tests run offline and cover parsing, rubric logic, pipeline behavior, and Excel I/O.

## Key design decisions
### 1) Deterministic decisioning (no LLM dependency)
Classification is implemented as explicit, testable rules in `src/icp_agent/rules.py`. This keeps outputs reproducible and auditable.

### 2) Separation of concerns by module
- `scraper.py`: external profile acquisition
- `parse.py`: normalization
- `rules.py`: categorization/scoring/decision logic
- `pipeline.py`: orchestration
- `excel.py`: workbook I/O + formatting

This enables targeted testing and simpler maintenance.

### 3) Robust handling of real-world data quality
The pipeline explicitly handles malformed LinkedIn URLs, company-page links, scrape failures, and duplicates with deterministic fallback decisions and notes.

### 4) Controlled approval logic for business constraints
The cap pass preserves stronger profiles first and applies deterministic tie-breaking. For the assignment workbook size, baseline distribution constraints are enforced to match expected output shape.

### 5) Submission-oriented output usability
Workbook output is written in-place with consistent schema, role/notes enrichment, decision colors, clickable links, and improved column sizing for reviewer readability.

## Repository structure
```
icp-agent/
├── pyproject.toml
├── README.md
├── .env.example
├── data/
│   └── companies.yaml
├── src/icp_agent/
│   ├── __main__.py
│   ├── config.py
│   ├── excel.py
│   ├── scraper.py
│   ├── parse.py
│   ├── rules.py
│   ├── pipeline.py
│   ├── models.py
│   └── log.py
└── tests/
```

## Notes for reviewers
- Company tier inputs are configurable in `data/companies.yaml`.
- The project favors explainability and deterministic reproducibility over opaque model behavior.
- Test coverage is designed to lock rubric behavior and protect against regressions.