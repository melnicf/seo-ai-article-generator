"""Pull Search Console query data for a specific URL."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.config import SC_CACHE_DIR as SC_DIR, GOOGLE_CREDENTIALS_PATH, SC_SITE_URL


def pull_sc_queries(page_url: str, days: int = 30, force: bool = False) -> list[dict]:
    """Pull Search Console queries for a specific page URL.

    Returns list of dicts with: query, clicks, impressions, ctr, position.
    Results are cached to data/search_console/<slug>.json.
    """
    slug = page_url.rstrip("/").split("/")[-1]
    cache_file = SC_DIR / f"{slug}.json"

    if cache_file.exists() and not force:
        return json.loads(cache_file.read_text())

    # Lazy import — only needed when actually calling the API
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("Google API libraries not installed. Run: pip install -r requirements.txt")
        return []

    SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
    token_path = Path("token.json")
    creds = None

    # Load existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(GOOGLE_CREDENTIALS_PATH).exists():
                print(f"Missing credentials file: {GOOGLE_CREDENTIALS_PATH}")
                print("Download OAuth credentials from Google Cloud Console.")
                return []
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    service = build("searchconsole", "v1", credentials=creds)

    end_date = datetime.now() - timedelta(days=3)  # SC data has ~3 day lag
    start_date = end_date - timedelta(days=days)

    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["query"],
        "dimensionFilterGroups": [
            {
                "filters": [
                    {
                        "dimension": "page",
                        "operator": "equals",
                        "expression": page_url,
                    }
                ]
            }
        ],
        "rowLimit": 1000,
    }

    response = (
        service.searchanalytics()
        .query(siteUrl=SC_SITE_URL, body=request_body)
        .execute()
    )

    rows = []
    for row in response.get("rows", []):
        rows.append(
            {
                "query": row["keys"][0],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": round(row["ctr"], 4),
                "position": round(row["position"], 1),
            }
        )

    # Sort by impressions descending
    rows.sort(key=lambda x: x["impressions"], reverse=True)

    SC_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(rows, indent=2))
    print(f"  Pulled {len(rows)} SC queries for {slug}")
    return rows


def load_sc_queries(page_url: str) -> list[dict]:
    """Load cached SC queries, returning empty list if not available."""
    slug = page_url.rstrip("/").split("/")[-1]
    cache_file = SC_DIR / f"{slug}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    return []
