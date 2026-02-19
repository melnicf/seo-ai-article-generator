#!/usr/bin/env python3
"""Create the Google Sheet control panel (first-time setup).

Usage:
    python setup_sheets.py              # Create new sheet
    python setup_sheets.py --format     # Fix black text on existing sheet (Queue, Run History)
"""

import argparse
import os

from dotenv import load_dotenv
load_dotenv()

from src.sheets.setup import apply_formatting, create_sheet


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Sheet control panel setup")
    parser.add_argument("--format", action="store_true",
                        help="Apply black text formatting to existing sheet (use SHEETS_SPREADSHEET_ID from .env)")
    args = parser.parse_args()
    if args.format:
        sheet_id = os.getenv("SHEETS_SPREADSHEET_ID", "")
        if not sheet_id:
            print("Error: SHEETS_SPREADSHEET_ID not set in .env")
            exit(1)
        apply_formatting(sheet_id)
    else:
        create_sheet()
