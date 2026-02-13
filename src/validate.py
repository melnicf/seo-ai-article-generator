"""Validate generated articles against quality requirements."""

import re
from src.clearscope import check_term_coverage


def validate_article(
    article: str,
    tech: str,
    clearscope_terms: list[dict],
    keywords: list[str],
    headers_required: list[str],
) -> dict:
    """Run all validation checks on a generated article.

    Returns a dict with validation results and an overall pass/fail.
    """
    results = {
        "word_count": _check_word_count(article),
        "h2_count": _check_h2_count(article),
        "structure": _check_structure(article),
        "lemon_mentions": _check_lemon_mentions(article),
        "internal_links": _check_internal_links(article),
        "external_links": _check_external_links(article),
        "no_competitor_links": _check_no_competitor_links(article),
        "no_freelancer_for_lemon": _check_no_freelancer_lemon(article),
        "tech_mentioned": _check_tech_mentioned(article, tech),
        "header_coverage": _check_header_coverage(article, headers_required),
        "clearscope_coverage": {},
        "keyword_coverage": _check_keyword_coverage(article, keywords),
    }

    # Clearscope term coverage
    if clearscope_terms:
        coverage = check_term_coverage(article, clearscope_terms)
        results["clearscope_coverage"] = {
            "total_terms": coverage["total_terms"],
            "found": coverage["found"],
            "missing": coverage["missing"],
            "coverage_pct": coverage["coverage_pct"],
            "missing_high_importance": [
                t for t in coverage.get("missing_terms", [])
                if t.get("importance", "").startswith(("10", "9", "8"))
            ],
        }

    # Overall assessment
    issues = []
    wc = results["word_count"]
    if wc["count"] < 2500:
        issues.append(f"Too short: {wc['count']} words (need 2800+)")
    if wc["count"] > 3500:
        issues.append(f"Too long: {wc['count']} words (target 3200 max)")

    h2 = results["h2_count"]
    if h2["count"] < 4:
        issues.append(f"Too few H2s: {h2['count']} (need 5-10)")
    if h2["count"] > 12:
        issues.append(f"Too many H2s: {h2['count']} (target 5-10)")

    if not results["structure"]["starts_with_paragraph"]:
        issues.append("Article doesn't start with a paragraph before first H2")
    if results["structure"]["has_introduction_header"]:
        issues.append("Article has an 'Introduction' header (not allowed)")
    if results["structure"]["has_conclusion_header"]:
        issues.append("Article has a 'Conclusion' header (not allowed)")

    if results["lemon_mentions"]["count"] < 3:
        issues.append("Too few Lemon.io mentions")

    if results["internal_links"]["count"] < 2:
        issues.append(f"Only {results['internal_links']['count']} internal links (need 2-3)")

    if results["external_links"]["count"] < 1:
        issues.append(f"Only {results['external_links']['count']} external links (need 2-3)")

    if not results["no_competitor_links"]["pass"]:
        issues.append(f"Contains competitor links: {results['no_competitor_links']['found']}")

    if not results["tech_mentioned"]["pass"]:
        issues.append(f"Tech '{tech}' only mentioned {results['tech_mentioned']['count']} times (need 5+)")

    hdr_cov = results["header_coverage"]
    if hdr_cov["total"] > 0 and hdr_cov["coverage_pct"] < 30:
        issues.append(f"Low header template coverage: {hdr_cov['coverage_pct']:.0f}% ({hdr_cov['found']}/{hdr_cov['total']})")

    cs_cov = results.get("clearscope_coverage", {})
    if cs_cov.get("coverage_pct", 100) < 80:
        issues.append(f"Low Clearscope coverage: {cs_cov['coverage_pct']:.0f}% (target 90%+)")

    results["issues"] = issues
    results["pass"] = len(issues) == 0
    results["grade"] = "A+" if len(issues) == 0 else ("A" if len(issues) <= 2 else ("B" if len(issues) <= 4 else "C"))

    return results


def _check_word_count(article: str) -> dict:
    words = article.split()
    return {"count": len(words), "pass": 2800 <= len(words) <= 3200}


def _check_h2_count(article: str) -> dict:
    h2s = re.findall(r"^## .+", article, re.MULTILINE)
    return {"count": len(h2s), "headers": h2s, "pass": 5 <= len(h2s) <= 10}


def _check_structure(article: str) -> dict:
    lines = article.strip().split("\n")
    first_non_empty = ""
    for line in lines:
        if line.strip():
            first_non_empty = line.strip()
            break

    starts_with_paragraph = not first_non_empty.startswith("#")
    has_intro_header = bool(re.search(r"^#{1,4}\s+introduction", article, re.MULTILINE | re.IGNORECASE))
    has_conclusion_header = bool(re.search(r"^#{1,4}\s+conclusion", article, re.MULTILINE | re.IGNORECASE))

    # Check for H2 immediately followed by H3 (no body text)
    h2_then_h3 = bool(re.search(r"^## .+\n+### ", article, re.MULTILINE))

    return {
        "starts_with_paragraph": starts_with_paragraph,
        "has_introduction_header": has_intro_header,
        "has_conclusion_header": has_conclusion_header,
        "h2_immediately_followed_by_h3": h2_then_h3,
    }


def _check_lemon_mentions(article: str) -> dict:
    mentions = re.findall(r"lemon\.io", article, re.IGNORECASE)
    return {"count": len(mentions), "pass": len(mentions) >= 3}


def _check_internal_links(article: str) -> dict:
    links = re.findall(r"\[([^\]]+)\]\((https?://lemon\.io[^\)]*)\)", article)
    return {"count": len(links), "links": links, "pass": len(links) >= 2}


def _check_external_links(article: str) -> dict:
    all_links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", article)
    external = [(anchor, url) for anchor, url in all_links if "lemon.io" not in url]
    return {"count": len(external), "links": external, "pass": len(external) >= 2}


COMPETITORS = [
    "toptal.com", "upwork.com", "fiverr.com", "arc.dev", "turing.com",
    "gun.io", "hired.com", "andela.com", "x-team.com", "codementor.io",
    "freelancer.com", "peopleperhour.com", "guru.com",
]


def _check_no_competitor_links(article: str) -> dict:
    all_links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", article)
    found = [(anchor, url) for anchor, url in all_links
             if any(comp in url for comp in COMPETITORS)]
    return {"pass": len(found) == 0, "found": found}


def _check_no_freelancer_lemon(article: str) -> dict:
    """Check that 'freelancer' is not used to describe Lemon.io devs."""
    # Simple heuristic: look for "Lemon" near "freelancer"
    pattern = r"(?:lemon\.io|lemon)\s+(?:\w+\s+){0,5}freelancer"
    found = re.findall(pattern, article, re.IGNORECASE)
    return {"pass": len(found) == 0, "found": found}


def _check_tech_mentioned(article: str, tech: str) -> dict:
    """Check that the core technology name appears prominently."""
    count = len(re.findall(re.escape(tech), article, re.IGNORECASE))
    return {"tech": tech, "count": count, "pass": count >= 5}


def _check_header_coverage(article: str, headers_required: list[str]) -> dict:
    """Check how many of the required template headers appear in the article."""
    if not headers_required:
        return {"total": 0, "found": 0, "coverage_pct": 100.0, "missing": []}

    article_headers = re.findall(r"^#{2,3}\s+(.+)", article, re.MULTILINE)
    article_headers_lower = [h.strip().lower() for h in article_headers]

    found = []
    missing = []
    for req in headers_required:
        req_lower = req.strip().lower()
        # fuzzy: check if the required header text is contained in any article header
        if any(req_lower in ah or ah in req_lower for ah in article_headers_lower):
            found.append(req)
        else:
            missing.append(req)

    coverage = len(found) / len(headers_required) * 100
    return {
        "total": len(headers_required),
        "found": len(found),
        "coverage_pct": round(coverage, 1),
        "missing": missing[:15],
    }


def _check_keyword_coverage(article: str, keywords: list[str]) -> dict:
    lower_article = article.lower()
    found = [kw for kw in keywords if kw.lower() in lower_article]
    return {
        "total": len(keywords),
        "found": len(found),
        "coverage_pct": (len(found) / len(keywords) * 100) if keywords else 100,
        "missing": [kw for kw in keywords if kw.lower() not in lower_article],
    }


def format_validation_report(results: dict, tech: str) -> str:
    """Format validation results as a readable report."""
    lines = [
        f"{'='*60}",
        f"VALIDATION REPORT: {tech}",
        f"{'='*60}",
        f"Grade: {results['grade']}",
        f"Word count: {results['word_count']['count']}",
        f"H2 headers: {results['h2_count']['count']}",
        f"Lemon.io mentions: {results['lemon_mentions']['count']}",
        f"Internal links: {results['internal_links']['count']}",
        f"External links: {results['external_links']['count']}",
    ]

    hdr = results.get("header_coverage", {})
    if hdr and hdr.get("total", 0) > 0:
        lines.append(f"Header template coverage: {hdr.get('coverage_pct', 0):.0f}% ({hdr.get('found', 0)}/{hdr.get('total', 0)})")

    tech_m = results.get("tech_mentioned", {})
    if tech_m:
        lines.append(f"Tech '{tech_m.get('tech', '?')}' mentions: {tech_m.get('count', 0)}")

    cs = results.get("clearscope_coverage", {})
    if cs:
        lines.append(f"Clearscope coverage: {cs.get('coverage_pct', 'N/A')}% ({cs.get('found', '?')}/{cs.get('total_terms', '?')})")
        if cs.get("missing_high_importance"):
            lines.append(f"  Missing HIGH importance: {', '.join(t.get('term', str(t)) for t in cs['missing_high_importance'][:10])}")

    kw = results.get("keyword_coverage", {})
    if kw:
        lines.append(f"Keyword coverage: {kw.get('coverage_pct', 0):.0f}% ({kw.get('found', 0)}/{kw.get('total', 0)})")

    if results["issues"]:
        lines.append(f"\nISSUES ({len(results['issues'])}):")
        for issue in results["issues"]:
            lines.append(f"  ⚠ {issue}")
    else:
        lines.append("\n✓ All checks passed!")

    lines.append(f"{'='*60}")
    return "\n".join(lines)
