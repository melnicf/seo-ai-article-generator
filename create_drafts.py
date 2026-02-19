#!/usr/bin/env python3
"""Create Clearscope drafts for techs in the Google Sheet queue.

Uses the "Create Multiple Drafts" batch form: submits all keywords and
hire URLs at once, then updates the Sheet with draft URLs.

Usage:
    python create_drafts.py               # Create drafts for all techs without one
    python create_drafts.py --limit 5     # Process first 5 only
    python create_drafts.py --no-cache    # Recreate even if draft URL exists
    python create_drafts.py --tech python # Only hire/python-developers/
    python create_drafts.py --tech python,react,vue-js  # Exact slug match (use vue-js, ruby-on-rails)
"""

from __future__ import annotations

import argparse
import sys

from src.config import SHEETS_SPREADSHEET_ID


def main():
    parser = argparse.ArgumentParser(
        description="Create Clearscope drafts for techs in the Sheet queue"
    )
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of drafts to create")
    parser.add_argument("--no-cache", action="store_true",
                        help="Recreate drafts even if URL already exists")
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
        has_draft = bool(item.get("clearscope_url"))
        if args.no_cache or not has_draft:
            to_process.append(item)

    if not to_process:
        print("All techs already have Clearscope drafts (use --no-cache to recreate)")
        return

    print(f"Creating Clearscope drafts for {len(to_process)} techs (batch)...\n")

    keywords = []
    urls = []
    for item in to_process:
        tech = extract_tech_from_url(item["url"])
        keywords.append(f"hire {tech.lower()} developers")
        urls.append(item["url"].rstrip("/"))

    clearscope = ClearscopeAutomation()
    clearscope.start()

    updated = 0
    newly_created = 0
    try:
        if not clearscope.is_alive:
            print("Browser window was closed. Stopping.")
        else:
            try:
                draft_urls, newly_created = clearscope.create_drafts_batch(keywords, content_urls=urls)
                for item, draft_url in zip(to_process, draft_urls):
                    if draft_url and item.get("row_index"):
                        sheets_client.update_clearscope_url(item["row_index"], draft_url)
                        updated += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                raise
    finally:
        clearscope.close()

    print(f"\nDone. Created {newly_created} new, updated {updated}/{len(to_process)} rows with draft URLs.")
    print(f"Next: python extract_terms.py")


if __name__ == "__main__":
    main()
