"""Load Clearscope term recommendations from manual CSV exports."""

import csv
import re
from pathlib import Path

from src.config import CLEARSCOPE_DIR


def load_clearscope_terms(tech_slug: str) -> list[dict]:
    """Load Clearscope recommended terms from a CSV export.

    Actual Clearscope CSV format:
      Primary Variant, Secondary Variants, Importance, Typical Uses Min,
      Typical Uses Max, Uses, Semantic Group

    Files should be placed in data/clearscope/<tech_slug>.csv
    e.g., data/clearscope/python-developers.csv

    Returns list of dicts: {term, variants, importance, typical_uses_min,
                            typical_uses_max, current_uses}
    """
    csv_path = CLEARSCOPE_DIR / f"{tech_slug}.csv"

    if not csv_path.exists():
        print(f"  No Clearscope data found at {csv_path}")
        print(f"  Export terms from Clearscope for this keyword and save as {csv_path}")
        return []

    terms = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Primary term
            term = (
                row.get("Primary Variant", "")
                or row.get("term", "")
                or row.get("Term", "")
                or ""
            ).strip()

            if not term:
                continue

            # Secondary variants (semicolon-separated)
            variants_raw = (
                row.get("Secondary Variants", "")
                or row.get("variants", "")
                or ""
            ).strip()
            variants = [v.strip() for v in variants_raw.split(";") if v.strip()]

            # Importance score
            importance = (
                row.get("Importance", "")
                or row.get("importance", "")
                or "5"
            )

            # Typical uses range
            uses_min = row.get("Typical Uses Min", "1")
            uses_max = row.get("Typical Uses Max", "2")
            typical_uses = f"{uses_min}-{uses_max}"

            # Current uses in existing content
            current_uses = row.get("Uses", "0")

            terms.append({
                "term": term,
                "variants": variants,
                "importance": str(importance).strip(),
                "typical_uses": typical_uses,
                "typical_uses_min": int(uses_min) if uses_min else 1,
                "typical_uses_max": int(uses_max) if uses_max else 2,
                "current_uses": int(current_uses) if current_uses else 0,
            })

    # Sort by importance descending
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
        # Build list of all variants to check
        all_variants = [t["term"].lower()]
        for v in t.get("variants", []):
            if v.strip():
                all_variants.append(v.strip().lower())

        # A term is "found" if any variant (primary or secondary) appears
        term_found = False
        for variant in all_variants:
            if variant in text_lower:
                term_found = True
                break
            # Also try without trailing 's' for simple plurals
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
