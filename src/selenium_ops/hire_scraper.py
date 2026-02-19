"""Scrape all technology/role pages from lemon.io/hire/."""

from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

from src.loaders.templates import extract_tech_from_url

HIRE_BASE = "https://lemon.io/hire/"


def scrape_hire_techs() -> list[dict]:
    """Fetch lemon.io/hire/ and extract all unique /hire/<slug>/ URLs.

    Returns deduplicated list of dicts: {url, slug, tech}
    sorted alphabetically by tech name.
    """
    print("Scraping lemon.io/hire/ for all tech pages...")

    resp = requests.get(HIRE_BASE, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    seen_slugs: set[str] = set()
    techs: list[dict] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]

        # Normalize relative / absolute URLs
        if href.startswith("/hire/") and href != "/hire/":
            full_url = "https://lemon.io" + href
        elif href.startswith("https://lemon.io/hire/") and href != HIRE_BASE:
            full_url = href
        else:
            continue

        # Ensure trailing slash
        if not full_url.endswith("/"):
            full_url += "/"

        slug = full_url.rstrip("/").split("/")[-1]

        # Skip the base /hire/ page itself
        if not slug or slug == "hire":
            continue

        # Deduplicate
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        tech = extract_tech_from_url(full_url)
        techs.append({
            "url": full_url,
            "slug": slug,
            "tech": tech,
        })

    techs.sort(key=lambda t: t["tech"].lower())

    print(f"  Found {len(techs)} unique tech pages")
    return techs
