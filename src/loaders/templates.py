"""Load and hydrate CSV templates with a specific technology name."""

import csv
from pathlib import Path
from src.config import KEYWORDS_CSV, HEADERS_CSV, QUESTIONS_CSV


def _load_csv_column(path: Path, skip_header: bool = True) -> list[str]:
    """Read the first column of a CSV, stripping whitespace."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        if skip_header:
            next(reader, None)
        for row in reader:
            if row and row[0].strip():
                rows.append(row[0].strip())
    return rows


def load_keywords(tech: str) -> list[str]:
    """Return keyword list with {TECH} replaced."""
    raw = _load_csv_column(KEYWORDS_CSV)
    return [k.replace("{TECH}", tech) for k in raw]


def load_headers(tech: str) -> list[str]:
    """Return header templates with {TECH} replaced."""
    raw = _load_csv_column(HEADERS_CSV)
    return [h.replace("{TECH}", tech) for h in raw]


def load_questions(tech: str) -> list[str]:
    """Return question templates with {TECH} replaced."""
    raw = _load_csv_column(QUESTIONS_CSV)
    return [q.replace("{TECH}", tech) for q in raw]


def extract_slug_base(url: str) -> str:
    """Extract slug base from hire URL for exact matching.

    Example: '.../java-developers/' -> 'java', '.../vue-js-developers/' -> 'vue-js'
    Use for --tech filtering so 'java' matches only java, not javascript.
    """
    slug = url.rstrip("/").split("/")[-1]
    for suffix in ("-developers", "-developer", "-engineers", "-engineer",
                   "-analysts", "-analyst", "-scientists", "-scientist"):
        slug = slug.replace(suffix, "")
    return slug.lower()


def extract_tech_from_url(url: str) -> str:
    """Extract a human-readable tech name from a lemon.io hire URL.

    Example: 'https://lemon.io/hire/python-developers/' -> 'Python'
             'https://lemon.io/hire/ruby-on-rails-developers/' -> 'Ruby on Rails'
    """
    slug = url.rstrip("/").split("/")[-1]
    for suffix in ("-developers", "-developer", "-engineers", "-engineer",
                    "-analysts", "-analyst", "-scientists", "-scientist"):
        slug = slug.replace(suffix, "")

    KNOWN_CASING = {
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "php": "PHP",
        "html": "HTML",
        "css": "CSS",
        "ios": "iOS",
        "asp-net": "ASP.NET",
        "net": ".NET",
        "node-js": "Node.js",
        "react-native": "React Native",
        "vue-js": "Vue.js",
        "next-js": "Next.js",
        "three-js": "Three.js",
        "ruby-on-rails": "Ruby on Rails",
    }
    if slug in KNOWN_CASING:
        return KNOWN_CASING[slug]
    return slug.replace("-", " ").title()
