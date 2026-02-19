"""Google Sheets client for reading config and writing results."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from googleapiclient.errors import HttpError

from src.config import GOOGLE_CREDENTIALS_PATH

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TOKEN_PATH = Path("sheets_token.json")


class SheetsClient:
    """Read settings, prompts, queue and write run history to a Google Sheet."""

    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self.service = self._authenticate()

    # ── Auth ──────────────────────────────────────────────────────────────

    def _authenticate(self):
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(GOOGLE_CREDENTIALS_PATH).exists():
                    raise FileNotFoundError(
                        f"Missing credentials file: {GOOGLE_CREDENTIALS_PATH}\n"
                        "Download OAuth credentials from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    GOOGLE_CREDENTIALS_PATH, SCOPES
                )
                creds = flow.run_local_server(port=0)
            TOKEN_PATH.write_text(creds.to_json())

        return build("sheets", "v4", credentials=creds)

    # ── Read helpers ──────────────────────────────────────────────────────

    def _get_values(self, range_name: str) -> list[list[str]]:
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )
            return result.get("values", [])
        except HttpError as e:
            if e.resp.status == 404:
                sys.exit(
                    "Spreadsheet not found (404). Verify SHEETS_SPREADSHEET_ID in .env\n"
                    "and that you have access. Run: python setup_sheets.py to create a new one."
                )
            raise

    # ── Template tabs (Keywords / Headers / Questions) ─────────────────────

    def _read_template_column(self, tab: str, tech: str) -> list[str]:
        """Read a single-column template tab, replacing {TECH} with the tech name.
        Falls back to CSV if the tab does not exist (e.g. older spreadsheet)."""
        try:
            rows = self._get_values(f"{tab}!A2:A")
            return [
                row[0].strip().replace("{TECH}", tech)
                for row in rows
                if row and row[0].strip()
            ]
        except HttpError as e:
            if e.resp.status == 400 and "Unable to parse range" in str(e):
                return self._fallback_template(tab, tech)
            raise

    def _fallback_template(self, tab: str, tech: str) -> list[str]:
        """Fall back to CSV when sheet tab does not exist."""
        from src.loaders.templates import load_keywords, load_headers, load_questions
        loaders = {"Keywords": load_keywords, "Headers": load_headers, "Questions": load_questions}
        return loaders[tab](tech)

    def read_keywords(self, tech: str) -> list[str]:
        return self._read_template_column("Keywords", tech)

    def read_headers(self, tech: str) -> list[str]:
        return self._read_template_column("Headers", tech)

    def read_questions(self, tech: str) -> list[str]:
        return self._read_template_column("Questions", tech)

    # ── Settings tab ──────────────────────────────────────────────────────

    def read_settings(self) -> dict:
        """Read Settings tab as key-value pairs (column A = name, B = value)."""
        rows = self._get_values("Settings!A2:B")
        settings = {}
        for row in rows:
            if len(row) >= 2 and row[0].strip():
                settings[row[0].strip()] = row[1].strip()
        return settings

    # ── Prompts tab ───────────────────────────────────────────────────────

    def read_system_prompt(self) -> str | None:
        """Read the full system prompt from the Prompts tab (cell A2).

        Returns the custom prompt text, or None if the cell is empty
        (meaning: use the built-in default).
        """
        rows = self._get_values("Prompts!A2")
        if rows and rows[0] and rows[0][0].strip():
            return rows[0][0].strip()
        return None

    # ── Queue tab ─────────────────────────────────────────────────────────

    def read_queue(self) -> list[dict]:
        """Read Queue tab. Columns: URL, Clearscope Draft URL, Status."""
        rows = self._get_values("Queue!A2:C")
        queue = []
        for i, row in enumerate(rows):
            url = row[0].strip() if len(row) > 0 else ""
            cs_url = row[1].strip() if len(row) > 1 else ""
            status = row[2].strip().lower() if len(row) > 2 else "pending"
            if url and status == "pending":
                queue.append({
                    "url": url,
                    "clearscope_url": cs_url,
                    "status": status,
                    "row_index": i + 2,  # 1-indexed, skip header
                })
        return queue

    def update_queue_status(self, row_index: int, status: str):
        """Update the Status column (C) for a specific row."""
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f"Queue!C{row_index}",
            valueInputOption="RAW",
            body={"values": [[status]]},
        ).execute()

    def read_full_queue(self) -> list[dict]:
        """Read ALL rows in Queue tab regardless of status."""
        rows = self._get_values("Queue!A2:C")
        queue = []
        for i, row in enumerate(rows):
            url = row[0].strip() if len(row) > 0 else ""
            cs_url = row[1].strip() if len(row) > 1 else ""
            status = row[2].strip().lower() if len(row) > 2 else "pending"
            if url:
                queue.append({
                    "url": url,
                    "clearscope_url": cs_url,
                    "status": status,
                    "row_index": i + 2,
                })
        return queue

    def populate_queue(self, techs: list[dict]) -> int:
        """Add tech URLs to Queue tab, skipping duplicates.

        Args:
            techs: List of dicts with 'url' key (and optionally 'slug', 'tech').

        Returns:
            Number of new rows added.
        """
        existing = self.read_full_queue()
        existing_urls = {item["url"].rstrip("/") for item in existing}

        new_rows = []
        for tech in techs:
            url = tech["url"].rstrip("/") + "/"
            if url.rstrip("/") not in existing_urls:
                new_rows.append([url, "", "pending"])

        if not new_rows:
            return 0

        response = self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range="Queue!A:C",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": new_rows},
        ).execute()
        self._format_appended_row_black_text(response, "Queue", 3)

        return len(new_rows)

    def update_clearscope_url(self, row_index: int, clearscope_url: str):
        """Set the Clearscope Draft URL (column B) for a specific row."""
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f"Queue!B{row_index}",
            valueInputOption="RAW",
            body={"values": [[clearscope_url]]},
        ).execute()

    # ── Run History tab ───────────────────────────────────────────────────

    def append_result(self, result: dict):
        """Append a result row to the Run History tab."""
        output_file = result.get("output_file", "")
        output_cell = self._output_file_to_link(output_file)
        issues = result.get("issues", [])
        warnings = result.get("warnings", [])

        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            result.get("tech", ""),
            result.get("url", ""),
            str(result.get("word_count", "")),
            result.get("grade", ""),
            str(result.get("clearscope_pct", "")),
            str(len(issues)),
            str(len(warnings)),
            output_cell,
        ]
        response = self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range="Run History!A:I",
            valueInputOption="USER_ENTERED",  # Required for HYPERLINK formula
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        self._format_appended_row_black_text(response, "Run History", 9)
        if issues or warnings:
            self._add_notes_to_result_row(response, issues, warnings)

    def _output_file_to_link(self, path: str) -> str:
        """Convert output file path to HYPERLINK formula that opens the folder."""
        if not path or not path.strip():
            return ""
        p = Path(path)
        try:
            folder = p.parent.resolve()
            folder_uri = folder.as_uri()
            display = p.name
            # Escape quotes in display text for formula safety
            display = display.replace('"', '""')
            return f'=HYPERLINK("{folder_uri}", "{display}")'
        except (OSError, RuntimeError):
            return path

    def _format_appended_row_black_text(
        self, append_response: dict, tab_name: str, col_count: int
    ) -> None:
        """Apply black text to newly appended rows (avoids white text from theme default)."""
        updates = append_response.get("updates", {})
        updated_range = updates.get("updatedRange", "")
        if not updated_range:
            return
        nums = re.findall(r"\d+", updated_range)
        if len(nums) < 1:
            return
        start_row_1based = int(nums[0])
        end_row_1based = int(nums[-1]) if len(nums) > 1 else start_row_1based
        start_row_0based = start_row_1based - 1
        end_row_0based = end_row_1based  # endRowIndex is exclusive

        meta = (
            self.service.spreadsheets()
            .get(
                spreadsheetId=self.spreadsheet_id,
                fields="sheets(properties(sheetId,title))",
            )
            .execute()
        )
        sheet_id = None
        for sheet in meta.get("sheets", []):
            if sheet.get("properties", {}).get("title") == tab_name:
                sheet_id = sheet["properties"]["sheetId"]
                break
        if sheet_id is None:
            return

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={
                "requests": [{
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": start_row_0based,
                            "endRowIndex": end_row_0based,
                            "startColumnIndex": 0,
                            "endColumnIndex": col_count,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {
                                    "foregroundColor": {"red": 0, "green": 0, "blue": 0, "alpha": 1},
                                }
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.foregroundColor",
                    }
                }]
            },
        ).execute()

    def _add_notes_to_result_row(
        self, append_response: dict, issues: list, warnings: list
    ) -> None:
        """Add issues and warnings as cell notes on the newly appended row."""
        updates = append_response.get("updates", {})
        updated_range = updates.get("updatedRange", "")
        if not updated_range:
            return

        match = re.search(r"[A-Z](\d+)", updated_range)
        if not match:
            return
        row_1based = int(match.group(1))
        row_0based = row_1based - 1

        # Get Run History sheet ID
        meta = (
            self.service.spreadsheets()
            .get(
                spreadsheetId=self.spreadsheet_id,
                fields="sheets(properties(sheetId,title))",
            )
            .execute()
        )
        sheet_id = None
        for sheet in meta.get("sheets", []):
            if sheet.get("properties", {}).get("title") == "Run History":
                sheet_id = sheet["properties"]["sheetId"]
                break
        if sheet_id is None:
            return

        requests = []
        # Column G (index 6) = Issues, Column H (index 7) = Warnings
        if issues:
            note_text = "\n".join(f"• {str(i)}" for i in issues)
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_0based,
                        "endRowIndex": row_0based + 1,
                        "startColumnIndex": 6,
                        "endColumnIndex": 7,
                    },
                    "cell": {"note": note_text},
                    "fields": "note",
                }
            })
        if warnings:
            note_text = "\n".join(f"• {str(w)}" for w in warnings)
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_0based,
                        "endRowIndex": row_0based + 1,
                        "startColumnIndex": 7,
                        "endColumnIndex": 8,
                    },
                    "cell": {"note": note_text},
                    "fields": "note",
                }
            })

        if requests:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests},
            ).execute()
