#!/usr/bin/env python3
"""Main pipeline: generate articles for Lemon.io /hire/ landing pages.

Usage:
    python main.py                    # Process all pages in hire_pages.csv
    python main.py --limit 5          # Process first 5 pages (test run)
    python main.py --page python      # Process only python page
    python main.py --dry-run          # Show what would be generated, don't call API
"""

import argparse
import csv
import os
import json
import sys
from pathlib import Path

from src.config import HIRE_PAGES_CSV, ARTICLE_OUTPUT_DIR
from src.loaders import (
    load_keywords,
    load_headers,
    load_questions,
    extract_tech_from_url,
    load_sc_queries,
    load_clearscope_terms,
    get_case_studies,
)
from src.pipeline import generate_article
from src.validation import validate_article, format_validation_report


def load_pages(csv_path: str) -> list[dict]:
    """Load page URLs from CSV."""
    pages = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", row.get("URL", "")).strip()
            if url:
                tech = extract_tech_from_url(url)
                pages.append({"url": url, "tech": tech})
    return pages


def process_page(page: dict, dry_run: bool = False) -> dict:
    """Process a single page: gather data, generate article, validate."""
    tech = page["tech"]
    url = page["url"]
    # Derive slug from URL (e.g., "python-developers") for file lookups
    slug = url.rstrip("/").split("/")[-1]  # 'python-developers', 'node-js-developers', etc.

    print(f"\n{'='*60}")
    print(f"Processing: {tech} ({url})")
    print(f"{'='*60}")

    # ── 1. Load templates ──────────────────────────────────────────────
    print("  Loading templates...")
    keywords = load_keywords(tech)
    headers = load_headers(tech)
    questions = load_questions(tech)
    print(f"  → {len(keywords)} keywords, {len(headers)} headers, {len(questions)} questions")

    # ── 2. Load Search Console data ────────────────────────────────────
    print("  Loading Search Console data...")
    sc_queries = load_sc_queries(url)
    print(f"  → {len(sc_queries)} SC queries loaded")

    # ── 3. Load Clearscope terms ───────────────────────────────────────
    print("  Loading Clearscope terms...")
    clearscope_terms = load_clearscope_terms(slug)
    print(f"  → {len(clearscope_terms)} Clearscope terms loaded")

    # ── 4. Load case studies ───────────────────────────────────────────
    print("  Loading case studies...")
    case_studies = get_case_studies()
    print(f"  → {len(case_studies.get('case_studies', []))} case studies, {len(case_studies.get('testimonials', []))} testimonials")

    # ── 5. Generate article ────────────────────────────────────────────
    if dry_run:
        print("\n  [DRY RUN] Would generate article with:")
        print(f"    Keywords: {keywords[:5]}...")
        print(f"    Headers: {headers[:3]}...")
        print(f"    SC queries: {[q['query'] for q in sc_queries[:3]]}...")
        print(f"    Clearscope terms: {[t['term'] for t in clearscope_terms[:5]]}...")
        return {"tech": tech, "url": url, "dry_run": True}

    article, selected_h2_headers = generate_article(
        tech=tech,
        page_url=url,
        keywords=keywords,
        headers=headers,
        questions=questions,
        sc_queries=sc_queries,
        clearscope_terms=clearscope_terms,
        case_studies=case_studies,
    )

    # ── 6. Save article ───────────────────────────────────────────────
    os.makedirs(ARTICLE_OUTPUT_DIR, exist_ok=True)
    article_path = os.path.join(ARTICLE_OUTPUT_DIR, f"{slug}.md")
    with open(article_path, "w") as f:
        f.write(article)
    print(f"  ✓ Saved to {article_path}")

    # ── 7. Validate ───────────────────────────────────────────────────
    # Only require the selected H2 headers (H3s are created by the model, not from templates)
    print("  Validating...")
    validation = validate_article(
        article=article,
        tech=tech,
        clearscope_terms=clearscope_terms,
        keywords=keywords,
        headers_required=selected_h2_headers,
    )
    report = format_validation_report(validation, tech)
    print(f"\n{report}")

    # Save validation report
    report_path = os.path.join(ARTICLE_OUTPUT_DIR, f"{slug}_validation.json")
    with open(report_path, "w") as f:
        # Convert any non-serializable items
        clean = json.loads(json.dumps(validation, default=str))
        json.dump(clean, f, indent=2)

    return {
        "tech": tech,
        "url": url,
        "article_path": article_path,
        "word_count": validation["word_count"]["count"],
        "grade": validation["grade"],
        "issues": validation["issues"],
    }


def main():
    parser = argparse.ArgumentParser(description="Generate Lemon.io hiring guide articles")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of pages to process")
    parser.add_argument("--page", type=str, default="", help="Process only pages matching this string")
    parser.add_argument("--dry-run", action="store_true", help="Show data without calling Claude API")
    args = parser.parse_args()

    # Load pages
    pages = load_pages(HIRE_PAGES_CSV)
    print(f"Loaded {len(pages)} pages from {HIRE_PAGES_CSV}")

    # Filter
    if args.page:
        pages = [p for p in pages if args.page.lower() in p["tech"].lower()]
        print(f"Filtered to {len(pages)} pages matching '{args.page}'")

    if args.limit > 0:
        pages = pages[:args.limit]
        print(f"Limited to {len(pages)} pages")

    if not pages:
        print("No pages to process!")
        sys.exit(1)

    # Process
    results = []
    for i, page in enumerate(pages, 1):
        print(f"\n[{i}/{len(pages)}]", end="")
        result = process_page(page, dry_run=args.dry_run)
        results.append(result)

    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        if r.get("dry_run"):
            print(f"  {r['tech']}: [dry run]")
        else:
            status = "✓" if not r.get("issues") else f"⚠ {len(r['issues'])} issues"
            print(f"  {r['tech']}: {r.get('word_count', '?')} words, grade {r.get('grade', '?')} {status}")

    # Save summary
    summary_path = os.path.join(ARTICLE_OUTPUT_DIR, "_summary.json")
    os.makedirs(ARTICLE_OUTPUT_DIR, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
