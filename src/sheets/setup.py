"""Create the Google Sheet with all required tabs and default content."""

from __future__ import annotations

from src.sheets.client import SheetsClient

# Stable sheet IDs for referencing tabs in formatting requests
_SHEET_IDS = {
    "settings": 0,
    "prompts": 1,
    "queue": 2,
    "history": 3,
    "keywords": 4,
    "headers": 5,
    "questions": 6,
}

SETTINGS_DEFAULTS = [
    ["Setting", "Value"],
    ["model", "claude-opus-4-6"],
    ["selector_model", "claude-haiku-4-5-20251001"],
    ["researcher_model", "claude-sonnet-4-5-20250929"],
    ["temperature", "0.7"],
    ["max_tokens", "16000"],
    ["word_count_target", "3000"],
    ["web_search_enabled", "TRUE"],
    ["web_search_max_uses", "3"],
]

def _get_default_prompt_text() -> str:
    """Get the full default system prompt for the sheet."""
    from src.pipeline.prompts import build_system_prompt
    return build_system_prompt()

QUEUE_HEADER = [
    ["URL", "Clearscope Draft URL (optional)", "Status"],
]

HISTORY_HEADER = [
    ["Timestamp", "Tech", "URL", "Word Count", "Grade",
     "Clearscope %", "Issues", "Warnings", "Output File"],
]


def _load_csv_defaults() -> dict[str, list[list[str]]]:
    """Load default template data from CSV files for sheet pre-population."""
    import csv
    from src.config import KEYWORDS_CSV, HEADERS_CSV, QUESTIONS_CSV

    def _read_col(path) -> list[list[str]]:
        rows = []
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    rows.append(header[:1])
                for row in reader:
                    if row and row[0].strip():
                        rows.append([row[0].strip()])
        except FileNotFoundError:
            pass
        return rows

    return {
        "keywords": _read_col(KEYWORDS_CSV) or [["Templated Keywords"]],
        "headers": _read_col(HEADERS_CSV) or [["Header Templates"]],
        "questions": _read_col(QUESTIONS_CSV) or [["Predefined Questions"]],
    }

# ── Colour palette ────────────────────────────────────────────────────────

_HEADER_BG = {"red": 0.20, "green": 0.24, "blue": 0.35, "alpha": 1}
_HEADER_FG = {"red": 1, "green": 1, "blue": 1, "alpha": 1}
_ALT_ROW_BG = {"red": 0.95, "green": 0.96, "blue": 0.98, "alpha": 1}
_DATA_TEXT = {"red": 0.15, "green": 0.15, "blue": 0.15, "alpha": 1}  # Dark gray for data cells
_PROMPT_LABEL_BG = {"red": 0.93, "green": 0.87, "blue": 0.51, "alpha": 1}
_PROMPT_LABEL_FG = {"red": 0.20, "green": 0.20, "blue": 0.20, "alpha": 1}

# ── Column width specs (pixels) per tab ───────────────────────────────────

_COL_WIDTHS = {
    "settings": [260, 360],
    "prompts": [900],
    "queue": [400, 400, 130],
    "history": [160, 140, 400, 110, 80, 110, 80, 90, 340],
    "keywords": [420],
    "headers": [520],
    "questions": [520],
}


# ── Formatting helpers ────────────────────────────────────────────────────


def _col_width_requests(sheet_id: int, widths: list[int]) -> list[dict]:
    """Generate updateDimensionProperties requests for column widths."""
    return [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": i,
                    "endIndex": i + 1,
                },
                "properties": {"pixelSize": w},
                "fields": "pixelSize",
            }
        }
        for i, w in enumerate(widths)
    ]


def _header_format_request(sheet_id: int, col_count: int, *, bg=None, fg=None) -> dict:
    """Format header row: bold, coloured background, centred, frozen."""
    bg = bg or _HEADER_BG
    fg = fg or _HEADER_FG
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 0,
                "endColumnIndex": col_count,
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": bg,
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": fg},
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP",
                    "padding": {"top": 6, "bottom": 6, "left": 8, "right": 8},
                }
            },
            "fields": (
                "userEnteredFormat.backgroundColor,"
                "userEnteredFormat.textFormat,"
                "userEnteredFormat.horizontalAlignment,"
                "userEnteredFormat.verticalAlignment,"
                "userEnteredFormat.wrapStrategy,"
                "userEnteredFormat.padding"
            ),
        }
    }


def _freeze_rows(sheet_id: int, rows: int = 1) -> dict:
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": rows},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    }


def _header_row_height(sheet_id: int, px: int = 40) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": 0,
                "endIndex": 1,
            },
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


def _wrap_all_cells(sheet_id: int, col_count: int, row_count: int = 1000) -> dict:
    """Enable text wrapping on all data cells below the header."""
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": row_count,
                "startColumnIndex": 0,
                "endColumnIndex": col_count,
            },
            "cell": {
                "userEnteredFormat": {
                    "wrapStrategy": "WRAP",
                    "verticalAlignment": "TOP",
                    "padding": {"top": 4, "bottom": 4, "left": 6, "right": 6},
                }
            },
            "fields": (
                "userEnteredFormat.wrapStrategy,"
                "userEnteredFormat.verticalAlignment,"
                "userEnteredFormat.padding"
            ),
        }
    }


def _data_cells_black_text(sheet_id: int, col_count: int, row_count: int = 1000) -> dict:
    """Set black text on data cells (must run after banding to override theme defaults)."""
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": row_count,
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
    }


def _alternating_colors(sheet_id: int, col_count: int) -> dict:
    return {
        "addBanding": {
            "bandedRange": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "startColumnIndex": 0,
                    "endColumnIndex": col_count,
                },
                "rowProperties": {
                    "headerColor": _HEADER_BG,
                    "firstBandColor": {"red": 1, "green": 1, "blue": 1, "alpha": 1},
                    "secondBandColor": _ALT_ROW_BG,
                },
            }
        }
    }


def _merge_cells(sheet_id: int, row: int, start_col: int, end_col: int) -> dict:
    return {
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row,
                "endRowIndex": row + 1,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "mergeType": "MERGE_ALL",
        }
    }


def _build_format_requests() -> list[dict]:
    """Build all batchUpdate requests for formatting every tab."""
    requests: list[dict] = []
    sid = _SHEET_IDS

    # ── Settings ──────────────────────────────────────────────────────
    s_cols = len(SETTINGS_DEFAULTS[0])
    requests += _col_width_requests(sid["settings"], _COL_WIDTHS["settings"])
    requests.append(_header_format_request(sid["settings"], s_cols))
    requests.append(_freeze_rows(sid["settings"]))
    requests.append(_header_row_height(sid["settings"], 40))
    requests.append(_wrap_all_cells(sid["settings"], s_cols))
    requests.append(_alternating_colors(sid["settings"], s_cols))

    # Left-align Setting column values
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sid["settings"],
                "startRowIndex": 1,
                "endRowIndex": len(SETTINGS_DEFAULTS),
                "startColumnIndex": 0,
                "endColumnIndex": 1,
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"bold": True, "fontSize": 10},
                }
            },
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # ── Prompts ───────────────────────────────────────────────────────
    requests += _col_width_requests(sid["prompts"], _COL_WIDTHS["prompts"])

    # Label row: merged across 3 cols, styled prominently
    requests.append(_merge_cells(sid["prompts"], 0, 0, 3))
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sid["prompts"],
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 0,
                "endColumnIndex": 3,
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _PROMPT_LABEL_BG,
                    "textFormat": {
                        "bold": True,
                        "fontSize": 12,
                        "foregroundColor": _PROMPT_LABEL_FG,
                    },
                    "horizontalAlignment": "LEFT",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP",
                    "padding": {"top": 8, "bottom": 8, "left": 12, "right": 12},
                }
            },
            "fields": (
                "userEnteredFormat.backgroundColor,"
                "userEnteredFormat.textFormat,"
                "userEnteredFormat.horizontalAlignment,"
                "userEnteredFormat.verticalAlignment,"
                "userEnteredFormat.wrapStrategy,"
                "userEnteredFormat.padding"
            ),
        }
    })
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": sid["prompts"],
                "dimension": "ROWS",
                "startIndex": 0,
                "endIndex": 1,
            },
            "properties": {"pixelSize": 44},
            "fields": "pixelSize",
        }
    })

    # Prompt body cell: wrap text, top-aligned, comfortable padding
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sid["prompts"],
                "startRowIndex": 1,
                "endRowIndex": 2,
                "startColumnIndex": 0,
                "endColumnIndex": 1,
            },
            "cell": {
                "userEnteredFormat": {
                    "wrapStrategy": "WRAP",
                    "verticalAlignment": "TOP",
                    "textFormat": {"fontSize": 10},
                    "padding": {"top": 10, "bottom": 10, "left": 12, "right": 12},
                }
            },
            "fields": (
                "userEnteredFormat.wrapStrategy,"
                "userEnteredFormat.verticalAlignment,"
                "userEnteredFormat.textFormat,"
                "userEnteredFormat.padding"
            ),
        }
    })

    # ── Queue ─────────────────────────────────────────────────────────
    q_cols = len(QUEUE_HEADER[0])
    requests += _col_width_requests(sid["queue"], _COL_WIDTHS["queue"])
    requests.append(_header_format_request(sid["queue"], q_cols))
    requests.append(_freeze_rows(sid["queue"]))
    requests.append(_header_row_height(sid["queue"], 40))
    requests.append(_wrap_all_cells(sid["queue"], q_cols))
    requests.append(_alternating_colors(sid["queue"], q_cols))

    # ── Run History ───────────────────────────────────────────────────
    h_cols = len(HISTORY_HEADER[0])
    requests += _col_width_requests(sid["history"], _COL_WIDTHS["history"])
    requests.append(_header_format_request(sid["history"], h_cols))
    requests.append(_freeze_rows(sid["history"]))
    requests.append(_header_row_height(sid["history"], 40))
    requests.append(_wrap_all_cells(sid["history"], h_cols))
    requests.append(_alternating_colors(sid["history"], h_cols))

    # ── Keywords / Headers / Questions ──────────────────────────────
    for tab in ("keywords", "headers", "questions"):
        requests += _col_width_requests(sid[tab], _COL_WIDTHS[tab])
        requests.append(_header_format_request(sid[tab], 1))
        requests.append(_freeze_rows(sid[tab]))
        requests.append(_header_row_height(sid[tab], 40))
        requests.append(_wrap_all_cells(sid[tab], 1))
        requests.append(_alternating_colors(sid[tab], 1))

    return requests


# ── Public entry point ────────────────────────────────────────────────────


def create_sheet(title: str = "Article Generator Control Panel") -> str:
    """Create a new Google Sheet with all required tabs, fully formatted.

    Returns the spreadsheet ID.
    """
    from src.sheets.client import SCOPES, TOKEN_PATH
    from pathlib import Path
    from src.config import GOOGLE_CREDENTIALS_PATH

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
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    service = build("sheets", "v4", credentials=creds)

    templates = _load_csv_defaults()

    # Create spreadsheet with explicit sheet IDs for reliable formatting
    spreadsheet = service.spreadsheets().create(
        body={
            "properties": {"title": title},
            "sheets": [
                {"properties": {"sheetId": _SHEET_IDS["settings"], "title": "Settings"}},
                {"properties": {"sheetId": _SHEET_IDS["prompts"], "title": "Prompts"}},
                {"properties": {"sheetId": _SHEET_IDS["queue"], "title": "Queue"}},
                {"properties": {"sheetId": _SHEET_IDS["history"], "title": "Run History"}},
                {"properties": {"sheetId": _SHEET_IDS["keywords"], "title": "Keywords"}},
                {"properties": {"sheetId": _SHEET_IDS["headers"], "title": "Headers"}},
                {"properties": {"sheetId": _SHEET_IDS["questions"], "title": "Questions"}},
            ],
        }
    ).execute()

    spreadsheet_id = spreadsheet["spreadsheetId"]

    # Populate tabs with data
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "RAW",
            "data": [
                {"range": "Settings!A1", "values": SETTINGS_DEFAULTS},
                {"range": "Prompts!A1", "values": [
                    ["System Prompt (edit below — or clear cell to use built-in default)"],
                    [_get_default_prompt_text()],
                ]},
                {"range": "Queue!A1", "values": QUEUE_HEADER},
                {"range": "Run History!A1", "values": HISTORY_HEADER},
                {"range": "Keywords!A1", "values": templates["keywords"]},
                {"range": "Headers!A1", "values": templates["headers"]},
                {"range": "Questions!A1", "values": templates["questions"]},
            ],
        },
    ).execute()

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": _build_format_requests()},
    ).execute()

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    print(f"\nSheet created: {url}")
    print(f"\nAdd this to your .env file:")
    print(f"  SHEETS_SPREADSHEET_ID={spreadsheet_id}")
    print(f"\nTabs created: Settings, Prompts, Queue, Run History, Keywords, Headers, Questions")
    print(f"  - Settings: model, temperature, word count, etc.")
    print(f"  - Prompts: edit any section (leave DEFAULT for built-in)")
    print(f"  - Queue: add URLs to generate articles for")
    print(f"  - Run History: auto-populated after each run")
    print(f"  - Keywords: templated keywords (use {{TECH}} placeholder)")
    print(f"  - Headers: H2 header templates (use {{TECH}} placeholder)")
    print(f"  - Questions: FAQ question templates (use {{TECH}} placeholder)")

    return spreadsheet_id


def apply_formatting(spreadsheet_id: str) -> None:
    """Apply black text formatting to Queue and Run History tabs on an existing spreadsheet."""
    from src.sheets.client import SCOPES, TOKEN_PATH
    from pathlib import Path
    from src.config import GOOGLE_CREDENTIALS_PATH

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
            flow = InstalledAppFlow.from_client_secrets_file(
                Path(GOOGLE_CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    service = build("sheets", "v4", credentials=creds)
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))")
        .execute()
    )
    title_to_id = {
        s["properties"]["title"]: s["properties"]["sheetId"]
        for s in meta.get("sheets", [])
    }
    requests = []
    if "Queue" in title_to_id:
        sid = title_to_id["Queue"]
        requests.append(_data_cells_black_text(sid, 3))
    if "Run History" in title_to_id:
        sid = title_to_id["Run History"]
        requests.append(_data_cells_black_text(sid, len(HISTORY_HEADER[0])))
    if not requests:
        print("No Queue or Run History tabs found.")
        return
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()
    print("Applied black text formatting to Queue and Run History.")
