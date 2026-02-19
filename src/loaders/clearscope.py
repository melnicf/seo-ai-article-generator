"""Load Clearscope term recommendations and check article coverage."""

import csv
import re
from pathlib import Path

from src.config import CLEARSCOPE_DIR


def load_clearscope_terms(tech_slug: str) -> list[dict]:
    """Load Clearscope recommended terms from CSV export or Selenium JSON cache.

    Checks for JSON first (scraped by Selenium), then falls back to CSV.

    Files should be placed in data/clearscope/<tech_slug>.csv or .json.

    Returns list of dicts: {term, variants, importance, typical_uses_min,
                            typical_uses_max, current_uses}
    """
    import json as _json

    # Prefer JSON cache (from Selenium scraper)
    json_path = CLEARSCOPE_DIR / f"{tech_slug}.json"
    if json_path.exists():
        terms = _json.loads(json_path.read_text())
        terms.sort(key=lambda t: int(str(t.get("importance", "0")).split("/")[0] or 0), reverse=True)
        print(f"  Loaded {len(terms)} Clearscope terms for {tech_slug} (from Selenium cache)")
        return terms

    csv_path = CLEARSCOPE_DIR / f"{tech_slug}.csv"

    if not csv_path.exists():
        print(f"  No Clearscope data found for {tech_slug}")
        print(f"  Run with --scrape-clearscope or export CSV to {csv_path}")
        return []

    terms = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            term = (
                row.get("Primary Variant", "")
                or row.get("term", "")
                or row.get("Term", "")
                or ""
            ).strip()

            if not term:
                continue

            variants_raw = (
                row.get("Secondary Variants", "")
                or row.get("variants", "")
                or ""
            ).strip()
            variants = [v.strip() for v in variants_raw.split(";") if v.strip()]

            importance = (
                row.get("Importance", "")
                or row.get("importance", "")
                or "5"
            )

            uses_min = row.get("Typical Uses Min", "1")
            uses_max = row.get("Typical Uses Max", "2")

            current_uses = row.get("Uses", "0")

            terms.append({
                "term": term,
                "variants": variants,
                "importance": str(importance).strip(),
                "typical_uses_min": int(uses_min) if uses_min else 1,
                "typical_uses_max": int(uses_max) if uses_max else 2,
                "current_uses": int(current_uses) if current_uses else 0,
            })

    def importance_sort_key(t):
        try:
            return int(t["importance"].split("/")[0])
        except (ValueError, IndexError):
            return 0

    terms.sort(key=importance_sort_key, reverse=True)
    print(f"  Loaded {len(terms)} Clearscope terms for {tech_slug}")
    return terms


def check_term_coverage(article_text: str, terms: list[dict]) -> dict:
    """Check what percentage of Clearscope terms appear in the article.

    Checks the primary term AND all secondary variants — a term counts as
    found if any variant appears in the text.

    Returns dict with: total_terms, found, missing, coverage_pct,
                       missing_terms, missing_list
    """
    if not terms:
        return {
            "total_terms": 0,
            "found": 0,
            "missing": 0,
            "coverage_pct": 100.0,
            "missing_terms": [],
            "missing_list": [],
        }

    text_lower = article_text.lower()
    found = []
    missing = []

    for t in terms:
        all_variants = [t["term"].lower()]
        for v in t.get("variants", []):
            if v.strip():
                all_variants.append(v.strip().lower())

        term_found = False
        for variant in all_variants:
            if variant in text_lower:
                term_found = True
                break
            singular = variant.rstrip("s")
            if singular and len(singular) > 2 and singular in text_lower:
                term_found = True
                break

        if term_found:
            found.append(t["term"])
        else:
            missing.append(t)

    coverage = len(found) / len(terms) if terms else 1.0

    return {
        "total_terms": len(terms),
        "found": len(found),
        "missing": len(missing),
        "coverage_pct": round(coverage * 100, 1),
        "missing_terms": missing[:30],
        "missing_list": [m["term"] for m in missing[:30]],
    }
