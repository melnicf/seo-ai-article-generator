# Lemon.io Article Generator

AI-powered pipeline that generates SEO-optimized hiring guide articles (~3000 words each) for Lemon.io `/hire/` landing pages.

## What It Does

Each `/hire/` page on Lemon.io (e.g., `/hire/python-developers/`, `/hire/node-js-developers/`) has a content section with a long-form hiring guide. This tool generates those articles by combining multiple data sources into a single prompt, then feeding it to Claude (Anthropic) to produce a high-quality, SEO-optimized article.

**Target scale:** 500 articles. **Test run:** 5 articles.

---

## Pipeline Flow

```
hire_pages.csv          → list of URLs to process
       ↓
┌──────┴──────────────────────────────────────┐
│  For each URL:                              │
│                                             │
│  1. Templates        (keywords.csv,         │
│                       headers.csv,          │
│                       questions.csv)        │
│     → {TECH} replaced with tech name        │
│                                             │
│  2. Search Console   (Google SC API)        │
│     → top 50 queries by impressions         │
│     → cached to data/search_console/        │
│                                             │
│  3. Clearscope       (CSV export)           │
│     → SEO terms with importance & variants  │
│     → read from data/clearscope/            │
│                                             │
│  4. Case Studies     (scraped + cached)     │
│     → 12 case studies, 46 testimonials      │
│     → cached to data/case_studies/          │
│                                             │
│  5. Prompt Assembly  (src/prompt.py)        │
│     → system prompt: writing rules,         │
│       Lemon.io guidelines, link rules       │
│     → user prompt: all data combined        │
│                                             │
│  6. Claude API       (src/generator.py)     │
│     → generates ~3000 word markdown article │
│                                             │
│  7. Validation       (src/validate.py)      │
│     → word count, H2 count, structure,      │
│       links, Clearscope term coverage,      │
│       keyword coverage, Lemon.io mentions   │
│                                             │
│  8. Save             (output/articles/)     │
│     → {slug}.md + {slug}_validation.json    │
└─────────────────────────────────────────────┘
```

### Data Sources Per Article

| Source | What It Provides | How It Gets There |
|--------|-----------------|-------------------|
| **Templates** | 24 keyword variants, 27 header templates, 25 questions — all with `{TECH}` substitution | `data/templates/*.csv` (from spreadsheet) |
| **Search Console** | Real search queries people use to find each `/hire/` page (impressions, clicks, position) | Google SC API → cached JSON |
| **Clearscope** | SEO terms with importance (1-10), secondary variants, and suggested usage frequency | Manual CSV export from Clearscope → `data/clearscope/` |
| **Case Studies** | 12 detailed case studies + 46 client testimonials from lemon.io/case-studies | Scraped once, cached to JSON |

---

## Project Structure

```
ai-article-generator/
├── main.py                  # Entry point — runs the full pipeline
├── requirements.txt         # Python dependencies
├── .env                     # API keys (not committed)
├── .env.example             # Template for .env
├── credentials.json         # Google OAuth credentials (not committed)
├── token.json               # Google OAuth token (auto-generated, not committed)
│
├── src/
│   ├── config.py            # All paths, API keys, model settings
│   ├── templates.py         # Loads keywords/headers/questions CSVs
│   ├── search_console.py    # Google SC API integration + caching
│   ├── clearscope.py        # Parses Clearscope CSV exports
│   ├── case_studies.py      # Scrapes lemon.io case studies
│   ├── prompt.py            # Builds system + user prompts for Claude
│   ├── generator.py         # Calls Anthropic Claude API
│   └── validate.py          # Post-generation quality checks
│
├── data/
│   ├── templates/
│   │   ├── hire_pages.csv   # URLs to process (5 for test, 500 for prod)
│   │   ├── keywords.csv     # Templated keywords with {TECH}
│   │   ├── headers.csv      # Templated H2/H3 headers with {TECH}
│   │   └── questions.csv    # Templated questions with {TECH}
│   ├── search_console/      # Cached SC query JSONs (per page)
│   ├── clearscope/          # Clearscope Terms CSV exports (per page)
│   └── case_studies/        # Cached scraped case study data
│
└── output/
    └── articles/            # Generated articles (.md) + validation reports (.json)
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=sk-ant-...        # Your Anthropic API key
GOOGLE_CREDENTIALS_PATH=credentials.json
SC_SITE_URL=sc-domain:lemon.io      # Domain property format for Search Console
```

### 3. Google Search Console authentication

- Create a project in [Google Cloud Console](https://console.cloud.google.com/)
- Enable the **Search Console API**
- Create OAuth 2.0 credentials (Desktop app type)
- Download the JSON as `credentials.json` in the project root
- Add your Google account as a test user in the OAuth consent screen
- On first run, a browser window opens for OAuth — after auth, `token.json` is created and reused

### 4. Clearscope data

For each page you want to generate, export the **Terms** tab from Clearscope as CSV and save it to `data/clearscope/{slug}.csv`.

The slug matches the URL path segment: `python-developers`, `node-js-developers`, `java-developers`, etc.

The CSV must have these columns (Clearscope default export):
- `Primary Variant`
- `Secondary Variants`
- `Importance`
- `Typical Uses Min`
- `Typical Uses Max`
- `Uses`

---

## Usage

### Run the full pipeline (all pages in hire_pages.csv)

```bash
python3 main.py
```

### Run for the first N pages only

```bash
python3 main.py --limit 5
```

### Run for a specific technology

```bash
python3 main.py --page python
```

### Dry run (show data loaded, don't call Claude)

```bash
python3 main.py --dry-run
```

### Output

Articles are saved to `output/articles/`:
- `python-developers.md` — the generated article (markdown)
- `python-developers_validation.json` — validation report
- `_summary.json` — summary of all generated articles

---

## Validation Checks

Each article is automatically validated for:

| Check | Criteria |
|-------|----------|
| Word count | 2800–3200 words |
| H2 headers | 5–10 per article |
| Structure | Starts with paragraph (no header), no "Introduction"/"Conclusion" headers |
| Lemon.io mentions | At least 3 |
| Internal links | 2–3 links to other lemon.io/hire/ pages |
| External links | 2–3 links to trusted external sources |
| No competitor links | No links to Toptal, Upwork, Fiverr, etc. |
| No "freelancer" for Lemon.io devs | "Freelancer" only used for general market context |
| Tech mentions | Technology name appears 5+ times |
| Clearscope coverage | 90%+ of recommended terms included |
| Keyword coverage | Templated keywords present in article |
| Header coverage | Templated headers reflected in article structure |

Results are graded: **A+** (0 issues), **A** (1-2), **B** (3-4), **C** (5+).

---

## Current State (Test Run)

The pipeline is configured for a 5-article test run with these pages:

| Page | SC Data | Clearscope CSV | Templates |
|------|---------|----------------|-----------|
| `python-developers` | Cached | Ready | Ready |
| `react-developers` | Cached | Ready | Ready |
| `node-js-developers` | Cached | Ready | Ready |
| `java-developers` | Cached | Ready | Ready |
| `app-developers` | Cached | Ready | Ready |

Run `python3 main.py` to generate all 5.

---

## Production: Scaling to 500 Articles

To move from 5 test articles to the full 500, three things need to happen:

### 1. Get the full list of 500 /hire/ page URLs

The file `data/templates/hire_pages.csv` currently has 5 test URLs. For production, populate it with all 500 URLs. Possible sources:
- Lemon.io sitemap (`/sitemap.xml`)
- CMS export of all `/hire/` pages
- Manual list from the marketing/SEO team

Format — one column, header `URL`:
```csv
URL
https://lemon.io/hire/python-developers/
https://lemon.io/hire/react-developers/
...
```

### 2. Automate Clearscope CSV export with Selenium

Clearscope does not have an API. For 500 pages, manually exporting CSVs is not practical. Build a Selenium script that:

1. Logs into Clearscope (`clearscope.io`)
2. For each target keyword (e.g., "hire python developers"):
   - Navigates to the draft or creates a new report
   - Waits for the Terms tab to load
   - Clicks the CSV export button
   - Saves the file to `data/clearscope/{slug}.csv`
3. Handles rate limiting and session timeouts

**Implementation notes:**
- Clearscope uses client-side rendering — use explicit `WebDriverWait` for element visibility
- Store Clearscope credentials in `.env` (`CLEARSCOPE_EMAIL`, `CLEARSCOPE_PASSWORD`)
- Run in batches of 50-100 to avoid session issues
- The export filename from Clearscope may need renaming to match the `{slug}.csv` convention

Suggested file: `scripts/export_clearscope.py`

### 3. Automate Clearscope grade validation with Selenium

After articles are generated, validate them against Clearscope's grading by pasting each article into Clearscope's editor and reading back the grade:

1. Log into Clearscope
2. For each generated article:
   - Navigate to the corresponding draft
   - Clear the editor content
   - Paste the generated article text
   - Wait for the grade to recalculate
   - Read the grade (A, A+, B, etc.) from the UI
   - Save the grade alongside the validation report
3. Flag any articles that score below A

**Implementation notes:**
- Clearscope's editor is likely a rich text editor (e.g., ProseMirror/TipTap) — pasting via Selenium may require `ActionChains` with clipboard injection or direct JavaScript execution
- Grade recalculation can take a few seconds — poll until the grade element updates
- Store results in `output/articles/{slug}_clearscope_grade.json`

Suggested file: `scripts/validate_clearscope.py`

### Production run checklist

```
[ ] Populate hire_pages.csv with all 500 URLs
[ ] Run Selenium Clearscope export script for all 500 keywords
[ ] Verify all 500 CSVs exist in data/clearscope/
[ ] Ensure SC API token is valid (may need re-auth)
[ ] Run: python3 main.py (or in batches with --limit)
[ ] Run Selenium Clearscope grade validation
[ ] Review articles scoring below A
[ ] Re-generate articles that fail validation
[ ] Export final articles for CMS upload
```

### Cost estimate for 500 articles

| Model | Input cost | Output cost | Total estimate |
|-------|-----------|-------------|----------------|
| Claude Sonnet | ~$1.50 | ~$7.50 | **~$9** |
| Claude Opus | ~$7.50 | ~$37.50 | **~$45** |

(Based on ~4K input tokens and ~4K output tokens per article at current Anthropic pricing.)

---

## Configuration Reference

All settings live in `src/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Anthropic model to use |
| `CLAUDE_MAX_TOKENS` | `16000` | Max output tokens (~4000 words) |
| `CLAUDE_TEMPERATURE` | `0.7` | Creativity level (0=deterministic, 1=creative) |
| `TARGET_WORD_COUNT` | `3000` | Target article length |
| `MIN_CLEARSCOPE_COVERAGE` | `0.90` | Minimum Clearscope term coverage |
| `SC_SITE_URL` | `sc-domain:lemon.io` | Search Console property identifier |

---

## Troubleshooting

**"ANTHROPIC_API_KEY not set"**
→ Create a `.env` file with your key. See `.env.example`.

**"Google API libraries not installed"**
→ Run `pip install -r requirements.txt`

**"Error 403: access_denied" during Google OAuth**
→ Add your Google account as a test user in Google Cloud Console → APIs & Services → OAuth consent screen → Test users.

**"User does not have sufficient permission for site"**
→ Make sure `SC_SITE_URL` in `.env` matches your Search Console property. For domain properties use `sc-domain:lemon.io`, not `https://lemon.io/`.

**"No Clearscope data found"**
→ Ensure the CSV filename matches the URL slug: `python-developers.csv` for `https://lemon.io/hire/python-developers/`. The file must be in `data/clearscope/`.

**Clearscope CSV loads 0 terms**
→ The CSV may have a BOM character. The parser handles `utf-8-sig` encoding, but if the file was re-saved with a different encoding, check the raw bytes.
