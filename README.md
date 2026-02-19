# Lemon.io Article Generator

AI-powered pipeline that generates SEO-optimized hiring guide articles (~3000 words each) for Lemon.io `/hire/` landing pages. Output is **WordPress-ready HTML**.

## What It Does

Each `/hire/` page on Lemon.io (e.g., `/hire/python-developers/`, `/hire/node-js-developers/`) has a content section with a long-form hiring guide. This tool generates those articles by combining multiple data sources into a single prompt, then feeding it to Claude (Anthropic) to produce a high-quality, SEO-optimized article.

**Target scale:** 500 articles. **Test run:** 5 articles.

---

## Architecture

Four scripts, run in order:

| Script | What it does |
|--------|-------------|
| `setup_sheets.py` | Create the Google Sheet control panel (first-time setup) |
| `scrape_techs.py` | Scrape all tech pages from lemon.io/hire/ → populate Google Sheet queue |
| `create_drafts.py` | Create Clearscope drafts for each tech (Selenium, slow) |
| `extract_terms.py` | Extract SEO terms from existing Clearscope drafts |
| `generate.py` | Generate articles from the Sheet queue |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy .env.example to .env and fill in API keys
cp .env.example .env

# 3. Create the Google Sheet control panel
python3 setup_sheets.py

# 4. Add the sheet ID to .env
echo "SHEETS_SPREADSHEET_ID=your_id" >> .env

# 5. Scrape techs from /hire/ page
python3 scrape_techs.py --limit 3

# 6. Create Clearscope drafts (opens browser, needs login)
python3 create_drafts.py --limit 3

# 7. Extract SEO terms from drafts
python3 extract_terms.py --limit 3

# 8. Generate articles
python3 generate.py --limit 3
```

---

## Scripts

### `setup_sheets.py`

Creates the Google Sheet control panel (first run) or applies black text formatting to an existing sheet.

```bash
python3 setup_sheets.py              # Create new sheet
python3 setup_sheets.py --format     # Fix Queue/Run History text visibility on existing sheet
```

### `scrape_techs.py`

Scrapes lemon.io/hire/ for all tech/role page URLs, deduplicates, and adds them to the Google Sheet Queue tab.

```bash
python3 scrape_techs.py                # All techs
python3 scrape_techs.py --limit 10     # First 10 only
```

### `create_drafts.py`

Opens a browser, logs in to Clearscope, and creates a draft for each tech that doesn't have a Clearscope URL yet. Updates the Sheet with draft URLs.

```bash
python3 create_drafts.py               # All techs without drafts
python3 create_drafts.py --limit 5     # First 5 only
python3 create_drafts.py --no-cache    # Recreate even if URL exists
python3 create_drafts.py --tech python # Only hire/python-developers/
python3 create_drafts.py --tech python,vue-js,ruby-on-rails  # Exact slug match
```

### `extract_terms.py`

Opens a browser, logs in to Clearscope, navigates to each draft URL, and scrapes the terms panel. Caches to `data/clearscope/{slug}.json`.

> **Important:** After creating drafts with `create_drafts.py`, wait for Clearscope to finish generating its term analysis before running `extract_terms.py`. This can take a few minutes per draft. If you run it too early, the terms panel will be empty and extraction will fail.

```bash
python3 extract_terms.py               # All drafts without cached terms
python3 extract_terms.py --limit 5     # First 5 only
python3 extract_terms.py --no-cache   # Re-extract even if cached
python3 extract_terms.py --tech python # Only hire/python-developers/
python3 extract_terms.py --tech python,vue-js,ruby-on-rails  # Exact slug match
```

### `generate.py`

Reads the Google Sheet queue, generates articles for all pending items. Google Sheets is the default — no flag needed.

```bash
python3 generate.py                         # All pending articles
python3 generate.py --limit 5               # First 5 pending
python3 generate.py --tech python,vue-js,ruby-on-rails # Exact slug match
python3 generate.py --tech python --no-cache            # Regenerate even if already done
python3 generate.py --dry-run               # Show data without calling API
python3 generate.py --validate-clearscope   # Validate in Clearscope after
```

---

## Google Sheet Tabs

### Settings

Key-value pairs that override `config.py` at runtime:

| Setting | Default |
|---------|---------|
| model | claude-opus-4-6 |
| temperature | 0.7 |
| word_count_target | 3000 |
| web_search_enabled | TRUE |
| web_search_max_uses | 3 |

### Prompts

Cell A2 contains the entire system prompt. Edit it to change tone, structure rules, Lemon.io messaging, link rules, anything. Clear the cell to use the built-in default.

Keywords, headers, SC queries, Clearscope terms, and case studies are injected into the user prompt — they are **not** affected by system prompt changes.

### Queue

| Column | Content |
|--------|---------|
| A: URL | e.g., `https://lemon.io/hire/python-developers/` |
| B: Clearscope Draft URL | Auto-populated by `create_drafts.py` |
| C: Status | `pending` → `processing` → `done` (managed by `generate.py`) |

`scrape_techs.py` populates column A. `create_drafts.py` populates column B. `generate.py` reads pending rows and updates status.

### Run History

Auto-populated after each generation run: timestamp, tech, word count, grade, clearscope coverage, issues, output file path.

---

## Pipeline Flow

```
scrape_techs.py         create_drafts.py       extract_terms.py       generate.py
───────────────         ────────────────       ────────────────       ───────────
Scrape /hire/           Selenium login         Selenium login         Read Sheet queue
→ extract tech URLs     Create draft per       Scrape terms per       Load templates
→ populate Sheet        tech in queue          draft URL              Load SC data
                        → save URLs to Sheet   → cache to JSON        Load Clearscope terms
                                                                      AI pipeline (3 steps)
                                                                      Save HTML + update Sheet
```

### Three-Step AI Pipeline

| Step | Model | Purpose | Cost/article |
|------|-------|---------|-------------|
| **Header selection** | Haiku 4.5 | Pick best 8 H2 headers from templates | ~$0.01 |
| **Web research** | Sonnet 4.5 + web search | Gather current-year stats, salary data, trends with source URLs | ~$0.08 |
| **Article writing** | Opus 4.6 (no tools) | Write the article using all data + research brief | ~$0.40 |

---

## Project Structure

```
ai-article-generator/
├── setup_sheets.py                  # First-time: create Google Sheet
├── scrape_techs.py                  # Step 1: scrape /hire/ → populate Sheet
├── create_drafts.py                 # Step 2: create Clearscope drafts
├── extract_terms.py                 # Step 3: extract SEO terms
├── generate.py                      # Step 4: generate articles
├── requirements.txt
├── .env / .env.example
├── credentials.json                 # Google OAuth credentials (not committed)
│
├── src/
│   ├── config.py                    # Paths, API keys, model settings
│   │
│   ├── selenium_ops/
│   │   ├── hire_scraper.py          # Scrapes lemon.io/hire/ for tech pages
│   │   └── clearscope_ops.py       # Clearscope draft creation + term extraction
│   │
│   ├── loaders/
│   │   ├── templates.py             # Loads keywords/headers/questions CSVs
│   │   ├── search_console.py        # Google SC API integration + caching
│   │   ├── clearscope.py            # Parses Clearscope CSV/JSON cache
│   │   └── case_studies.py          # Scrapes lemon.io case studies
│   │
│   ├── pipeline/
│   │   ├── generator.py             # Orchestrates 3-step AI pipeline
│   │   ├── header_selector.py       # AI header selection (Haiku)
│   │   ├── researcher.py            # Web research step (Sonnet + web search)
│   │   └── prompts.py               # System + user prompt construction
│   │
│   ├── sheets/
│   │   ├── client.py                # Google Sheets read/write operations
│   │   └── setup.py                 # Create sheet with default tabs
│   │
│   └── validation/
│       ├── checks.py                # Individual validation checks
│       └── report.py                # Grading and report formatting
│
├── data/
│   ├── templates/                   # CSV templates with {TECH} placeholders
│   ├── search_console/              # Cached SC query JSONs
│   ├── clearscope/                  # Clearscope terms (.json or .csv)
│   └── case_studies/                # Cached case study data
│
└── output/
    └── articles/                    # Generated .html + validation .json
```

---

## Setup Details

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_CREDENTIALS_PATH=credentials.json
SC_SITE_URL=sc-domain:lemon.io
SHEETS_SPREADSHEET_ID=                  # From --setup-sheets
CLEARSCOPE_WORKSPACE=lemon-io           # Your Clearscope workspace name
```

**Important:** Web search must be enabled in your [Anthropic Console](https://console.anthropic.com/) under Privacy settings.

### 3. Google authentication

The same Google OAuth credentials are used for both Search Console and Sheets:

- Create a project in [Google Cloud Console](https://console.cloud.google.com/)
- Enable the **Search Console API** and **[Google Sheets API](https://console.developers.google.com/apis/api/sheets.googleapis.com/overview)** (click the link → select your project → Enable)
- Create OAuth 2.0 credentials (Desktop app type)
- Download the JSON as `credentials.json`
- Add your Google account as a test user in the OAuth consent screen

Two token files are generated automatically:
- `token.json` — Search Console access
- `sheets_token.json` — Google Sheets access

---

## Validation Checks

Each article is automatically validated for:

| Check | Criteria |
|-------|----------|
| Word count | 2800–3200 words |
| H2 headers | 5–10 per article |
| Structure | Starts with paragraph, no "Introduction"/"Conclusion" headers |
| Lemon.io mentions | At least 3 |
| Internal links | 2–3 links to other lemon.io/hire/ pages |
| External links | 2–3 links to trusted external sources (max 6) |
| No competitor links | No links to Toptal, Upwork, Fiverr, etc. |
| Clearscope coverage | 90%+ of recommended terms included |
| Keyword coverage | Templated keywords present in article |
| Cited statistics | Statistics have source links, no unattributed numbers |

Results are graded: **A+** (0 issues), **A** (warnings only), **B** (1-3 issues), **C** (4-5), **D** (6+).

---

## Cost Estimate

| Step | Model | Per article | 500 articles |
|------|-------|------------|-------------|
| Header selection | Haiku 4.5 | ~$0.01 | ~$5 |
| Web research | Sonnet 4.5 + search | ~$0.08 | ~$40 |
| Article writing | Opus 4.6 | ~$0.40 | ~$200 |
| **Total** | | **~$0.50** | **~$250** |

---

## Troubleshooting

**"SHEETS_SPREADSHEET_ID not set"**
→ Run `python3 setup_sheets.py` first, then add the ID to `.env`.

**"Google Sheets API has not been used in project ... or it is disabled"**
→ Enable the Sheets API in your Google Cloud project: go to [Google Sheets API](https://console.developers.google.com/apis/api/sheets.googleapis.com/overview), select your project, click **Enable**. Wait a minute, then retry.

**"ANTHROPIC_API_KEY not set"**
→ Create a `.env` file with your key. See `.env.example`.

**"Google API libraries not installed"**
→ Run `pip install -r requirements.txt`

**"Error 403: access_denied" during Google OAuth**
→ Add your Google account as a test user in Google Cloud Console → APIs & Services → OAuth consent screen → Test users.

**Clearscope Selenium not finding elements**
→ Clearscope may have updated their UI. Check `src/selenium_ops/clearscope_ops.py` and adjust CSS selectors. Run with browser visible (not headless) to debug.

**"No Clearscope data found"**
→ Either export CSV manually to `data/clearscope/{slug}.csv`, or run `python3 extract_terms.py`.

**Web search not working**
→ Ensure web search is enabled in your [Anthropic Console](https://console.anthropic.com/) Privacy settings.
