"""Scrape and cache Lemon.io case studies from the public page and detail pages."""

import json
import re
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.config import CASE_STUDIES_CACHE as CASE_STUDIES_DIR

CASE_STUDIES_INDEX_URL = "https://lemon.io/case-studies/"
CACHE_FILE = CASE_STUDIES_DIR / "case_studies.json"

# All known case study detail page URLs
CASE_STUDY_URLS = [
    "https://lemon.io/case-studies/lemonio-meets-skyfi/",
    "https://lemon.io/case-studies/lemoneyeo-meets-tvscientific/",
    "https://lemon.io/case-studies/lemonyeo-meets-fathom/",
    "https://lemon.io/case-studies/lemonyeo-meets-peptalkr/",
    "https://lemon.io/case-studies/lemonio-meets-savr/",
    "https://lemon.io/case-studies/lemonyeo-meets-velvettech/",
    "https://lemon.io/case-studies/currents/",
    "https://lemon.io/case-studies/scrumbly/",
    "https://lemon.io/case-studies/lemonio-meets-myndy/",
    "https://lemon.io/case-studies/lemonio-meets-adherium/",
    "https://lemon.io/case-studies/lemonio-meets-little-spoon/",
    "https://lemon.io/case-studies/lemonio-meets-realestateapi/",
]


# ── Text cleaning helpers ─────────────────────────────────────────────────


def _clean_text(text: str) -> str:
    """Normalize whitespace and strip."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


NAVIGATION_NOISE = {
    "start hiring", "find jobs", "login", "for developers", "for companies",
    "rate calculator", "how we vet developers", "faq for companies",
    "case studies", "testimonials", "about us", "view all services",
    "home", "hire with confidence", "hire talent", "get started",
    "get a dev", "job description", "start hiring", "place request",
    "looking for other role?", "looking for other skill?",
    "read more about our screening", "hire a miraculous dev",
    "get supreme devs", "get impressive engineers",
    "get passionate qualified devs", "hire best-fit devs",
    "hire trusted talent",
}

NAV_PREFIXES = ("hire ", "looking for", "view all", "get started", "place ")


def _is_navigation_text(text: str) -> bool:
    """Check if text is likely a navigation item, not actual content."""
    lower = text.lower().strip()
    if lower in NAVIGATION_NOISE:
        return True
    if any(lower.startswith(p) for p in NAV_PREFIXES):
        return True
    return False


# ── Extraction helpers ────────────────────────────────────────────────────


def _extract_technologies(soup: BeautifulSoup) -> list:
    """Extract technology names from case study page."""
    technologies = []

    for el in soup.find_all(string=re.compile(r"technolog", re.IGNORECASE)):
        parent = el.parent
        if parent is None:
            continue
        container = parent.parent if parent.parent else parent
        for sibling in container.find_all(["span", "li", "a", "p", "div"]):
            text = _clean_text(sibling.get_text())
            if "technolog" in text.lower():
                continue
            if 2 < len(text) < 25 and not _is_navigation_text(text):
                if text not in technologies:
                    technologies.append(text)

    for el in soup.select("[class*='tech'], [class*='stack'], [class*='badge']"):
        text = _clean_text(el.get_text())
        if 2 < len(text) < 25 and not _is_navigation_text(text):
            if text not in technologies:
                technologies.append(text)

    tech_indicators = {
        "js", "css", "html", "api", "sdk", "ui", "ux", "ai", "ml", "db",
        "sql", "net", "ios", "devops", "react", "node", "vue", "angular",
        "python", "java", "swift", "flutter", "typescript", "javascript",
        "docker", "aws", "gcp", "azure", "linux", "git", "ci", "cd",
        "front-end", "back-end", "full-stack", "data", "cloud", "mobile",
    }
    filtered = []
    for t in technologies:
        lower = t.lower()
        words = t.split()
        if len(words) == 2 and all(w[0].isupper() for w in words):
            if not any(ind in lower for ind in tech_indicators):
                continue
        filtered.append(t)

    technologies = filtered

    combined = [t for t in technologies if " " in t and len(t.split()) >= 3]
    if combined:
        individual = [t for t in technologies if t not in combined]
        if individual:
            technologies = individual

    return technologies[:15]


def _extract_customer_quotes(soup: BeautifulSoup, full_text: str) -> list:
    """Extract customer quotes from case study page using multiple strategies."""
    quotes = []
    seen = set()

    def _add_quote(text):
        text = _clean_text(text)
        if len(text) > 30 and text not in seen and not _is_navigation_text(text):
            seen.add(text)
            quotes.append(text)

    for bq in soup.find_all("blockquote"):
        _add_quote(bq.get_text())

    for el in soup.select(
        "[class*='quote'], [class*='testimonial'], [class*='review']"
    ):
        _add_quote(el.get_text())

    for el in soup.find_all(["em", "i"]):
        text = el.get_text()
        if len(text) > 40:
            _add_quote(text)

    quote_patterns = [
        re.compile(r'\u201c(.{30,}?)\u201d', re.DOTALL),
        re.compile(r'\u2018(.{30,}?)\u2019', re.DOTALL),
        re.compile(r'"([^"]{30,}?)"'),
    ]
    for pattern in quote_patterns:
        for match in pattern.finditer(full_text):
            _add_quote(match.group(1))

    return quotes


# ── Page scraping ─────────────────────────────────────────────────────────


def _scrape_detail_page(url: str):
    """Scrape a single case study detail page for rich content."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Warning: Could not fetch {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup.find_all(["nav", "header", "footer"]):
        tag.decompose()

    full_text = soup.get_text(separator="\n", strip=True)

    h1 = soup.find("h1")
    title = _clean_text(h1.get_text()) if h1 else ""

    h2_headings = [_clean_text(h.get_text()) for h in soup.find_all("h2")]
    h2_headings = [h for h in h2_headings if not _is_navigation_text(h)]

    paragraphs = []
    for p in soup.find_all("p"):
        text = _clean_text(p.get_text())
        if len(text) > 40 and not _is_navigation_text(text):
            paragraphs.append(text)

    body_text = "\n\n".join(paragraphs)
    customer_quotes = _extract_customer_quotes(soup, full_text)
    technologies = _extract_technologies(soup)

    return {
        "url": url,
        "title": title,
        "h2_headings": h2_headings,
        "body_text": body_text,
        "customer_quotes": customer_quotes,
        "technologies": technologies,
        "full_text_length": len(full_text),
    }


# Fallback when data/case_studies/case_studies.json does not exist (e.g. first run).
# Only URLs are needed; card data and testimonials are then empty until the cache is populated.
CASE_STUDY_CARDS: list[dict] = []
TESTIMONIALS: list[dict] = []


# ── Main scraper ──────────────────────────────────────────────────────────


def _load_seed_from_cache() -> Optional[dict]:
    """Load existing case studies + testimonials from cache file, if it exists."""
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def scrape_case_studies(force: bool = False) -> dict:
    """Scrape all case study data from Lemon.io.

    Uses data/case_studies/case_studies.json as the source for URLs, card data
    (company, industry, headline, stats), and testimonials. When the cache
    exists, only detail pages are re-scraped and merged back. When the cache
    does not exist, falls back to hardcoded URLs and card/testimonial data.

    Returns dict with keys: case_studies, testimonials
    """
    if CACHE_FILE.exists() and not force:
        return json.loads(CACHE_FILE.read_text())

    seed = _load_seed_from_cache()
    if seed:
        urls = [s["url"] for s in seed["case_studies"] if s.get("url")]
        cards_by_index = {i: s for i, s in enumerate(seed["case_studies"])}
        testimonials = seed.get("testimonials", [])
    else:
        urls = CASE_STUDY_URLS
        cards_by_index = {i: (CASE_STUDY_CARDS[i] if i < len(CASE_STUDY_CARDS) else {}) for i in range(len(urls))}
        testimonials = TESTIMONIALS

    if not urls:
        raise FileNotFoundError(
            f"No case study URLs found. Ensure {CACHE_FILE} exists with case_studies[].url or use hardcoded fallback."
        )

    print("Scraping Lemon.io case studies (index + detail pages)...")

    studies = []
    for i, url in enumerate(urls):
        print(f"  [{i+1}/{len(urls)}] Scraping {url}")
        detail = _scrape_detail_page(url)
        card = cards_by_index.get(i, {})

        entry = {
            "company": card.get("company", ""),
            "industry": card.get("industry", ""),
            "headline": card.get("headline", ""),
            "stats": card.get("stats", []),
        }

        if detail:
            entry["url"] = detail["url"]
            entry["title"] = detail["title"]
            entry["body_text"] = detail["body_text"]
            entry["customer_quotes"] = detail["customer_quotes"]
            entry["technologies"] = detail["technologies"]
            entry["h2_headings"] = detail["h2_headings"]
        else:
            entry["url"] = url
            entry["title"] = card.get("headline", "")
            entry["body_text"] = ""
            entry["customer_quotes"] = []
            entry["technologies"] = []
            entry["h2_headings"] = []

        studies.append(entry)

    result = {
        "case_studies": studies,
        "testimonials": testimonials,
    }

    CASE_STUDIES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"  Saved {len(studies)} case studies + {len(testimonials)} testimonials to {CACHE_FILE}")
    return result


def get_case_studies() -> dict:
    """Load case studies, scraping if not cached."""
    return scrape_case_studies(force=False)
