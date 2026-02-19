#!/usr/bin/env python3
"""Extract SEO terms from Clearscope drafts and cache them locally.

Opens a browser, logs in to Clearscope, navigates to each draft URL
from the Sheet, and scrapes the terms panel.

Usage:
    python extract_terms.py               # Extract terms for all drafts
    python extract_terms.py --limit 5     # Process first 5 only
    python extract_terms.py --no-cache    # Re-extract even if cached
    python extract_terms.py --tech python # Only hire/python-developers/
    python extract_terms.py --tech python,vue-js,ruby-on-rails  # Exact slug match
"""

from __future__ import annotations

import argparse
import sys
import time

from src.config import SHEETS_SPREADSHEET_ID


def main():
    parser = argparse.ArgumentParser(
        description="Extract SEO terms from Clearscope drafts"
    )
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of drafts to process")
    parser.add_argument("--no-cache", action="store_true",
                        help="Re-extract even if terms are already cached")
    parser.add_argument("--tech", type=str, default="",
                        help="Filter to these hire/ slugs only (exact match). e.g. --tech python,vue-js,ruby-on-rails")
    args = parser.parse_args()

    if not SHEETS_SPREADSHEET_ID:
        print("Error: SHEETS_SPREADSHEET_ID not set in .env")
        sys.exit(1)

    from src.sheets import SheetsClient
    from src.selenium_ops.clearscope_ops import ClearscopeAutomation
    from src.loaders.templates import extract_tech_from_url, extract_slug_base

    sheets_client = SheetsClient(SHEETS_SPREADSHEET_ID)
    queue = sheets_client.read_full_queue()

    if args.tech:
        slug_bases = {t.strip().lower() for t in args.tech.split(",") if t.strip()}
        queue = [
            item for item in queue
            if extract_slug_base(item["url"]) in slug_bases
        ]
        print(f"  Filtered to {len(queue)} techs matching: {args.tech}")
        if not queue:
            print("No techs match the filter. Exiting.")
            return

    if args.limit > 0:
        queue = queue[:args.limit]

    to_process = []
    for item in queue:
        if not item.get("clearscope_url"):
            continue
        slug = item["url"].rstrip("/").split("/")[-1]
        if args.no_cache or not ClearscopeAutomation.terms_cached(slug):
            to_process.append(item)

    if not to_process:
        print("All drafts already have cached terms (use --no-cache to re-extract)")
        return

    print(f"Extracting terms for {len(to_process)} drafts...\n")

    clearscope = ClearscopeAutomation()
    clearscope.start()

    extracted = 0
    try:
        for i, item in enumerate(to_process, 1):
            slug = item["url"].rstrip("/").split("/")[-1]
            tech = extract_tech_from_url(item["url"])
            print(f"\n[{i}/{len(to_process)}] {tech}")

            if not clearscope.is_alive:
                print("Browser window was closed. Stopping.")
                break

            try:
                terms = clearscope.scrape_terms(item["clearscope_url"])
                if terms:
                    clearscope.save_terms(slug, terms)
                    extracted += 1
            except Exception as e:
                print(f"  ERROR: {e}")

            time.sleep(2)

    finally:
        clearscope.close()

    print(f"\nDone. Extracted terms for {extracted}/{len(to_process)} drafts.")
    print(f"Next: python generate.py")


if __name__ == "__main__":
    main()
