#!/usr/bin/env python3
"""Generate articles from the Google Sheet queue.

Usage:
    python generate.py                         # Generate all pending articles
    python generate.py --limit 5               # Generate first 5 pending
    python generate.py --tech python,vue-js,ruby-on-rails  # Exact slug match
    python generate.py --tech python --no-cache           # Regenerate even if already done
    python generate.py --dry-run               # Show data without calling API
    python generate.py --validate-clearscope   # Validate articles in Clearscope after

Google Sheets is the default data source — no flag needed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import markdown as md_lib

from src.config import (
    ARTICLE_OUTPUT_DIR,
    SHEETS_SPREADSHEET_ID,
)
from src.loaders import (
    extract_tech_from_url,
    load_sc_queries,
    pull_sc_queries,
    load_clearscope_terms,
    get_case_studies,
)
from src.pipeline import generate_article
from src.validation import validate_article, format_validation_report


# ── HTML helpers ──────────────────────────────────────────────────────────


def ensure_html(article: str) -> str:
    """If the article already looks like HTML keep it, otherwise convert from markdown."""
    html_indicators = ["<h2>", "<h2 ", "<p>", "<p ", '<a href=']
    if any(indicator in article for indicator in html_indicators):
        return article.strip()

    return md_lib.markdown(article, extensions=["extra", "sane_lists", "smarty"])


def html_to_text_for_validation(html: str) -> str:
    """Convert HTML back to markdown-style text for the validation module."""
    text = html
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1', text)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', text)
    text = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1', text)
    text = re.sub(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text)
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text)
    text = re.sub(r'<em>(.*?)</em>', r'*\1*', text)
    text = re.sub(r'<li>(.*?)</li>', r'- \1', text)
    text = re.sub(r'</?(?:ul|ol|p|br|div|span|section|article)[^>]*>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Sheets helpers ────────────────────────────────────────────────────────


def apply_sheet_settings(settings: dict):
    """Override config.py values with settings from Google Sheet."""
    import src.config as config

    mapping = {
        "model": ("CLAUDE_MODEL", str),
        "selector_model": ("SELECTOR_MODEL", str),
        "researcher_model": ("RESEARCHER_MODEL", str),
        "temperature": ("CLAUDE_TEMPERATURE", float),
        "max_tokens": ("CLAUDE_MAX_TOKENS", int),
        "word_count_target": ("TARGET_WORD_COUNT", int),
        "web_search_enabled": ("WEB_SEARCH_ENABLED", lambda v: v.upper() == "TRUE"),
        "web_search_max_uses": ("WEB_SEARCH_MAX_USES", int),
    }

    for key, (attr, converter) in mapping.items():
        if key in settings and settings[key]:
            try:
                setattr(config, attr, converter(settings[key]))
                print(f"  Sheet override: {attr} = {getattr(config, attr)}")
            except (ValueError, TypeError):
                print(f"  Warning: invalid value for {key}: {settings[key]}")


def load_pages_from_sheets(sheets_client) -> list[dict]:
    """Load pending pages from Google Sheet queue."""
    queue = sheets_client.read_queue()
    pages = []
    for item in queue:
        url = item["url"]
        tech = extract_tech_from_url(url)
        pages.append({
            "url": url,
            "tech": tech,
            "clearscope_url": item.get("clearscope_url", ""),
            "row_index": item.get("row_index"),
        })
    return pages


# ── Core processing ──────────────────────────────────────────────────────


def process_page(
    page: dict,
    sheets_client,
    dry_run: bool = False,
    system_prompt_override: str | None = None,
) -> dict:
    """Process a single page: gather data, generate article, validate."""
    tech = page["tech"]
    url = page["url"]
    slug = url.rstrip("/").split("/")[-1]

    print(f"\n{'='*60}")
    print(f"Processing: {tech} ({url})")
    print(f"{'='*60}")

    # 1. Load templates from Google Sheet
    print("  Loading templates from Sheet...")
    keywords = sheets_client.read_keywords(tech)
    headers = sheets_client.read_headers(tech)
    questions = sheets_client.read_questions(tech)
    print(f"  → {len(keywords)} keywords, {len(headers)} headers, {len(questions)} questions")

    # 2. Load Search Console data (pull from API if not cached)
    print("  Loading Search Console data...")
    sc_queries = load_sc_queries(url)
    if not sc_queries:
        try:
            sc_queries = pull_sc_queries(url)
        except Exception as e:
            print(f"  SC pull failed ({e}), continuing without SC data")
            sc_queries = []
    print(f"  → {len(sc_queries)} SC queries loaded")

    # 3. Load Clearscope terms
    print("  Loading Clearscope terms...")
    clearscope_terms = load_clearscope_terms(slug)
    print(f"  → {len(clearscope_terms)} Clearscope terms loaded")

    # 4. Load case studies
    print("  Loading case studies...")
    case_studies = get_case_studies()
    print(f"  → {len(case_studies.get('case_studies', []))} case studies, {len(case_studies.get('testimonials', []))} testimonials")

    # 5. Generate article
    if dry_run:
        print("\n  [DRY RUN] Would generate article with:")
        print(f"    Keywords: {keywords[:5]}...")
        print(f"    Headers: {headers[:3]}...")
        print(f"    SC queries: {[q['query'] for q in sc_queries[:3]]}...")
        print(f"    Clearscope terms: {[t['term'] for t in clearscope_terms[:5]]}...")
        if system_prompt_override:
            print(f"    Using custom system prompt ({len(system_prompt_override)} chars)")
        return {"tech": tech, "url": url, "dry_run": True}

    article_raw, selected_h2_headers = generate_article(
        tech=tech,
        page_url=url,
        keywords=keywords,
        headers=headers,
        questions=questions,
        sc_queries=sc_queries,
        clearscope_terms=clearscope_terms,
        case_studies=case_studies,
        system_prompt_override=system_prompt_override,
    )

    # 6. Ensure HTML output
    article_html = ensure_html(article_raw)
    article_for_validation = html_to_text_for_validation(article_html)

    # 7. Save article
    os.makedirs(ARTICLE_OUTPUT_DIR, exist_ok=True)
    article_path = os.path.join(ARTICLE_OUTPUT_DIR, f"{slug}.html")
    with open(article_path, "w") as f:
        f.write(article_html)
    print(f"  Saved to {article_path}")

    # 8. Validate
    print("  Validating...")
    validation = validate_article(
        article=article_for_validation,
        tech=tech,
        clearscope_terms=clearscope_terms,
        keywords=keywords,
        headers_required=selected_h2_headers,
    )
    report = format_validation_report(validation, tech)
    print(f"\n{report}")

    report_path = os.path.join(ARTICLE_OUTPUT_DIR, f"{slug}_validation.json")
    with open(report_path, "w") as f:
        clean = json.loads(json.dumps(validation, default=str))
        json.dump(clean, f, indent=2)

    return {
        "tech": tech,
        "url": url,
        "article_path": article_path,
        "word_count": validation["word_count"]["count"],
        "grade": validation["grade"],
        "issues": validation["issues"],
        "warnings": validation.get("warnings", []),
        "clearscope_pct": validation.get("clearscope_coverage", {}).get("coverage_pct", ""),
    }


# ── Clearscope validation ────────────────────────────────────────────────


def validate_in_clearscope(results: list[dict], clearscope, pages: list[dict]):
    """Paste generated articles into Clearscope and read grades."""
    url_to_cs = {p["url"]: p.get("clearscope_url", "") for p in pages}

    for result in results:
        if result.get("dry_run"):
            continue
        cs_url = url_to_cs.get(result["url"], "")
        if not cs_url:
            continue

        article_path = result.get("article_path", "")
        if not article_path or not os.path.exists(article_path):
            continue

        with open(article_path, "r") as f:
            article_html = f.read()

        print(f"\n  Validating {result['tech']} in Clearscope...")
        grade = clearscope.paste_and_grade(cs_url, article_html)
        result["clearscope_grade"] = grade


# ── Main ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Generate Lemon.io hiring guide articles")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of articles to generate")
    parser.add_argument("--tech", type=str, default="",
                        help="Filter to these hire/ slugs only (exact match). e.g. --tech python,vue-js,ruby-on-rails")
    parser.add_argument("--no-cache", action="store_true",
                        help="Regenerate articles even if already done")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show data without calling Claude API")
    parser.add_argument("--validate-clearscope", action="store_true",
                        help="Validate articles in Clearscope after generation")
    args = parser.parse_args()

    # ── Connect to Google Sheet ───────────────────────────────────────
    if not SHEETS_SPREADSHEET_ID:
        print("Error: SHEETS_SPREADSHEET_ID not set in .env")
        print("Run: python selenium_pipeline.py --setup-sheets")
        sys.exit(1)

    from src.sheets import SheetsClient
    sheets_client = SheetsClient(SHEETS_SPREADSHEET_ID)

    # ── Load settings & prompt from Sheet ─────────────────────────────
    print("Loading settings from Google Sheet...")
    settings = sheets_client.read_settings()
    apply_sheet_settings(settings)

    print("Loading system prompt from Google Sheet...")
    system_prompt_override = sheets_client.read_system_prompt()
    if system_prompt_override:
        print(f"  Using custom prompt from sheet ({len(system_prompt_override)} chars)")
    else:
        print("  Prompt cell empty — using built-in default")

    # ── Load pages from queue ─────────────────────────────────────────
    pages = load_pages_from_sheets(sheets_client)
    print(f"Loaded {len(pages)} pending pages from Sheet queue")

    if args.tech:
        from src.loaders.templates import extract_slug_base
        slug_bases = {t.strip().lower() for t in args.tech.split(",") if t.strip()}
        pages = [
            p for p in pages
            if extract_slug_base(p["url"]) in slug_bases
        ]
        print(f"Filtered to {len(pages)} pages matching: {args.tech}")
        if not pages:
            full_queue = sheets_client.read_full_queue()
            already_done = [
                t for t in slug_bases
                if any(
                    extract_slug_base(q["url"]) == t and q["status"] != "pending"
                    for q in full_queue
                )
            ]
            if already_done:
                techs = ", ".join(already_done)
                msg = f"{techs} article was generated." if len(already_done) == 1 else f"{techs} articles were generated."
                print(f"{msg} Use --no-cache to regenerate.")
                if not args.no_cache:
                    sys.exit(0)
                done_items = [
                    q for q in full_queue
                    if extract_slug_base(q["url"]) in slug_bases and q["status"] != "pending"
                ]
                pages = [
                    {
                        "url": q["url"],
                        "tech": extract_tech_from_url(q["url"]),
                        "clearscope_url": q.get("clearscope_url", ""),
                        "row_index": q.get("row_index"),
                    }
                    for q in done_items
                ]
                print(f"Regenerating {len(pages)} article(s) (--no-cache)")
            else:
                print("No pages match the filter. Exiting.")
                sys.exit(0)

    if args.limit > 0:
        pages = pages[:args.limit]
        print(f"Limited to {len(pages)} pages")

    if not pages:
        print("No pending pages to process!")
        sys.exit(0)

    # ── Clearscope validation setup ───────────────────────────────────
    clearscope = None
    if args.validate_clearscope:
        from src.selenium_ops.clearscope_ops import ClearscopeAutomation
        clearscope = ClearscopeAutomation()
        clearscope.start()

    # ── Process ───────────────────────────────────────────────────────
    results = []
    try:
        for i, page in enumerate(pages, 1):
            print(f"\n[{i}/{len(pages)}]", end="")

            if page.get("row_index"):
                sheets_client.update_queue_status(page["row_index"], "processing")

            result = process_page(
                page, sheets_client,
                dry_run=args.dry_run,
                system_prompt_override=system_prompt_override,
            )
            results.append(result)

            if page.get("row_index"):
                status = "done"
                sheets_client.update_queue_status(page["row_index"], status)

            if not result.get("dry_run"):
                sheets_client.append_result({
                    "tech": result.get("tech", ""),
                    "url": result.get("url", ""),
                    "word_count": result.get("word_count", ""),
                    "grade": result.get("grade", ""),
                    "clearscope_pct": result.get("clearscope_pct", ""),
                    "issues": result.get("issues", []),
                    "warnings": result.get("warnings", []),
                    "output_file": result.get("article_path", ""),
                })

        # ── Clearscope validation ─────────────────────────────────────
        if args.validate_clearscope and clearscope:
            validate_in_clearscope(results, clearscope, pages)

    finally:
        if clearscope:
            clearscope.close()

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        if r.get("dry_run"):
            print(f"  {r['tech']}: [dry run]")
        else:
            status = "ok" if not r.get("issues") else f"{len(r['issues'])} issues"
            cs_grade = f", CS: {r['clearscope_grade']}" if r.get("clearscope_grade") else ""
            print(f"  {r['tech']}: {r.get('word_count', '?')} words, grade {r.get('grade', '?')} {status}{cs_grade}")

    summary_path = os.path.join(ARTICLE_OUTPUT_DIR, "_summary.json")
    os.makedirs(ARTICLE_OUTPUT_DIR, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
