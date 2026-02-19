#!/usr/bin/env python3
"""Scrape all tech pages from lemon.io/hire/ and populate Google Sheet queue.

Usage:
    python scrape_techs.py                # Scrape all techs
    python scrape_techs.py --limit 10     # Scrape and add first 10 only
"""

from __future__ import annotations

import argparse
import sys

from src.config import SHEETS_SPREADSHEET_ID


def main():
    parser = argparse.ArgumentParser(
        description="Scrape tech pages from lemon.io/hire/ and populate Google Sheet"
    )
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of techs to add")
    args = parser.parse_args()

    if not SHEETS_SPREADSHEET_ID:
        print("Error: SHEETS_SPREADSHEET_ID not set in .env")
        print("Run: python scrape_techs.py --setup-sheets")
        sys.exit(1)

    from src.sheets import SheetsClient
    from src.selenium_ops.hire_scraper import scrape_hire_techs

    sheets_client = SheetsClient(SHEETS_SPREADSHEET_ID)
    techs = scrape_hire_techs()

    if args.limit > 0:
        techs = techs[:args.limit]
        print(f"  Limited to {args.limit} techs")

    added = sheets_client.populate_queue(techs)
    total = len(techs)
    print(f"  Added {added} new techs to Sheet queue ({total - added} already existed)")
    print(f"\nNext: python create_drafts.py")


if __name__ == "__main__":
    main()
