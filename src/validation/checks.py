"""Individual validation checks and the main validate_article orchestrator."""

import re
from datetime import datetime

from src.loaders.clearscope import check_term_coverage
from src.validation.report import compute_grade

CURRENT_YEAR = datetime.now().year


# ── Competitor domains ────────────────────────────────────────────────────

COMPETITORS = [
    "toptal.com", "upwork.com", "fiverr.com", "arc.dev", "turing.com",
    "gun.io", "hired.com", "andela.com", "x-team.com", "codementor.io",
    "freelancer.com", "peopleperhour.com", "guru.com",
]


# ── Main validation entry point ──────────────────────────────────────────


def validate_article(
    article: str,
    tech: str,
    clearscope_terms: list[dict],
    keywords: list[str],
    headers_required: list[str],
) -> dict:
    """Run all validation checks on a generated article.

    Returns a dict with per-check results, issues, warnings, grade, and
    overall pass/fail.
    """
    results = {
        "word_count": check_word_count(article),
        "h2_count": check_h2_count(article),
        "structure": check_structure(article),
        "lemon_mentions": check_lemon_mentions(article),
        "internal_links": check_internal_links(article),
        "external_links": check_external_links(article),
        "no_competitor_links": check_no_competitor_links(article),
        "no_freelancer_for_lemon": check_no_freelancer_lemon(article),
        "tech_mentioned": check_tech_mentioned(article, tech),
        "header_coverage": check_header_coverage(article, headers_required),
        "clearscope_coverage": {},
        "keyword_coverage": check_keyword_coverage(article, keywords),
        "cited_statistics": check_cited_statistics(article),
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

    # Aggregate issues and warnings
    issues, warnings = _collect_issues(results, tech)
    results["issues"] = issues
    results["warnings"] = warnings
    results["pass"] = len(issues) == 0
    results["grade"] = compute_grade(issues, warnings)

    return results


# ── Issue aggregation ─────────────────────────────────────────────────────


def _collect_issues(results: dict, tech: str) -> tuple[list[str], list[str]]:
    """Walk through all check results and collect issues/warnings."""
    issues = []
    warnings = []

    wc = results["word_count"]
    if wc["count"] < 2800:
        issues.append(f"Too short: {wc['count']} words (need 2800+)")
    elif wc["count"] < 2500:
        issues.append(f"Way too short: {wc['count']} words (need 2800+)")
    if wc["count"] > 3200:
        warnings.append(f"Slightly long: {wc['count']} words (target 3200 max)")
    if wc["count"] > 3500:
        issues.append(f"Too long: {wc['count']} words (target 3200 max)")

    h2 = results["h2_count"]
    if h2["count"] < 7:
        issues.append(f"Too few H2s: {h2['count']} (need 7-9)")
    if h2["count"] > 10:
        issues.append(f"Too many H2s: {h2['count']} (target 7-9)")

    if not results["structure"]["starts_with_paragraph"]:
        issues.append("Article doesn't start with a paragraph before first H2")
    if results["structure"]["has_introduction_header"]:
        issues.append("Article has an 'Introduction' header (not allowed)")
    if results["structure"]["has_conclusion_header"]:
        issues.append("Article has a 'Conclusion' header (not allowed)")
    if results["structure"]["h2_immediately_followed_by_h3"]:
        warnings.append("An H2 is immediately followed by H3 without body text")

    if results["lemon_mentions"]["count"] < 3:
        issues.append("Too few Lemon.io mentions (need 3+)")

    if results["internal_links"]["count"] < 2:
        issues.append(f"Only {results['internal_links']['count']} internal links (need 2-3)")
    if results["internal_links"]["count"] > 4:
        warnings.append(f"Too many internal links: {results['internal_links']['count']} (target 2-3)")

    if results["external_links"]["count"] < 2:
        issues.append(f"Only {results['external_links']['count']} external links (need 2-3)")
    if results["external_links"]["count"] > 4:
        warnings.append(f"Too many external links: {results['external_links']['count']} (target 2-3)")

    if not results["no_competitor_links"]["pass"]:
        issues.append(f"Contains competitor links: {results['no_competitor_links']['found']}")

    if not results["tech_mentioned"]["pass"]:
        issues.append(f"Tech '{tech}' only mentioned {results['tech_mentioned']['count']} times (need 5+)")

    hdr_cov = results["header_coverage"]
    if hdr_cov["total"] > 0 and hdr_cov["coverage_pct"] < 25:
        issues.append(f"Low header template coverage: {hdr_cov['coverage_pct']:.0f}% ({hdr_cov['found']}/{hdr_cov['total']})")
    elif hdr_cov["total"] > 0 and hdr_cov["coverage_pct"] < 40:
        warnings.append(f"Header template coverage could be better: {hdr_cov['coverage_pct']:.0f}% ({hdr_cov['found']}/{hdr_cov['total']})")

    cs_cov = results.get("clearscope_coverage", {})
    if cs_cov.get("coverage_pct", 100) < 85:
        issues.append(f"Low Clearscope coverage: {cs_cov['coverage_pct']:.0f}% (target 90%+)")
    elif cs_cov.get("coverage_pct", 100) < 90:
        warnings.append(f"Clearscope coverage below target: {cs_cov['coverage_pct']:.0f}% (target 90%+)")

    kw_cov = results.get("keyword_coverage", {})
    kw_found = kw_cov.get("found", 0)
    if kw_cov.get("total", 0) > 0 and kw_found < 5:
        issues.append(f"Too few keywords used: {kw_found}/{kw_cov.get('total', 0)} (need 5-10 exact phrases)")
    elif kw_cov.get("total", 0) > 0 and kw_found < 7:
        warnings.append(f"Keyword usage on low end: {kw_found}/{kw_cov.get('total', 0)} (target 5-10 exact phrases)")

    cited = results.get("cited_statistics", {})
    if cited.get("uncited_count", 0) > 3:
        issues.append(f"{cited['uncited_count']} statistics without source links (max 3 allowed)")
    elif cited.get("uncited_count", 0) > 0:
        warnings.append(f"{cited['uncited_count']} statistics appear to lack source links")
    if cited.get("outdated_count", 0) > 0:
        warnings.append(f"{cited['outdated_count']} references to outdated data (pre-{CURRENT_YEAR - 1})")

    return issues, warnings


# ── Individual check functions ────────────────────────────────────────────


def count_prose_words(article: str) -> int:
    """Count words the way Clearscope does — visible prose only.

    Strips: markdown headers (##), link URLs, image syntax, bold/italic
    markers, bullet markers, and other markdown formatting.
    """
    text = article
    # Remove markdown images: ![alt](url)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # Replace markdown links [anchor](url) with just the anchor text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove header markers (##, ###, etc.)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}", "", text)
    text = re.sub(r"_{1,3}", "", text)
    # Remove bullet/list markers at line start
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
    # Remove inline code backticks
    text = re.sub(r"`", "", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    return len(text.split())


def check_word_count(article: str) -> dict:
    count = count_prose_words(article)
    return {"count": count, "pass": 2800 <= count <= 3200}


def check_h2_count(article: str) -> dict:
    h2s = re.findall(r"^## .+", article, re.MULTILINE)
    return {"count": len(h2s), "headers": h2s, "pass": 5 <= len(h2s) <= 10}


def check_structure(article: str) -> dict:
    lines = article.strip().split("\n")
    first_non_empty = ""
    for line in lines:
        if line.strip():
            first_non_empty = line.strip()
            break

    starts_with_paragraph = not first_non_empty.startswith("#")
    has_intro_header = bool(
        re.search(r"^#{1,4}\s+introduction", article, re.MULTILINE | re.IGNORECASE)
    )
    has_conclusion_header = bool(
        re.search(r"^#{1,4}\s+conclusion", article, re.MULTILINE | re.IGNORECASE)
    )
    h2_then_h3 = bool(re.search(r"^## .+\n+### ", article, re.MULTILINE))

    return {
        "starts_with_paragraph": starts_with_paragraph,
        "has_introduction_header": has_intro_header,
        "has_conclusion_header": has_conclusion_header,
        "h2_immediately_followed_by_h3": h2_then_h3,
    }


def check_lemon_mentions(article: str) -> dict:
    mentions = re.findall(r"lemon\.io", article, re.IGNORECASE)
    return {"count": len(mentions), "pass": len(mentions) >= 3}


def check_internal_links(article: str) -> dict:
    links = re.findall(r"\[([^\]]+)\]\((https?://lemon\.io[^\)]*)\)", article)
    return {"count": len(links), "links": links, "pass": len(links) >= 2}


def check_external_links(article: str) -> dict:
    all_links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", article)
    external = [(anchor, url) for anchor, url in all_links if "lemon.io" not in url]
    return {"count": len(external), "links": external, "pass": len(external) >= 2}


def check_no_competitor_links(article: str) -> dict:
    all_links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", article)
    found = [
        (anchor, url) for anchor, url in all_links
        if any(comp in url for comp in COMPETITORS)
    ]
    return {"pass": len(found) == 0, "found": found}


def check_no_freelancer_lemon(article: str) -> dict:
    """Check that 'freelancer' is not used to describe Lemon.io devs."""
    pattern = r"(?:lemon\.io|lemon)\s+(?:\w+\s+){0,5}freelancer"
    found = re.findall(pattern, article, re.IGNORECASE)
    return {"pass": len(found) == 0, "found": found}


def check_tech_mentioned(article: str, tech: str) -> dict:
    """Check that the core technology name appears prominently."""
    count = len(re.findall(re.escape(tech), article, re.IGNORECASE))
    return {"tech": tech, "count": count, "pass": count >= 5}


def check_header_coverage(article: str, headers_required: list[str]) -> dict:
    """Check how many of the required template headers appear in the article.

    Uses a two-tier matching approach:
    1. Exact substring containment (strict)
    2. Key-word overlap: if 60%+ of the significant words in the template
       appear in an article header, count it as a match (fuzzy)
    """
    if not headers_required:
        return {"total": 0, "found": 0, "coverage_pct": 100.0, "missing": []}

    article_headers = re.findall(r"^#{2,3}\s+(.+)", article, re.MULTILINE)
    article_headers_lower = [h.strip().lower() for h in article_headers]

    stop_words = {
        "a", "an", "the", "to", "for", "of", "in", "on", "with",
        "and", "or", "is", "are", "do", "does", "how", "what",
        "when", "where", "why", "i", "you", "your", "my", "it",
        "can", "should", "must", "that", "this", "from",
    }

    def _significant_words(text: str) -> set:
        words = set(re.findall(r"[a-z]+", text.lower()))
        return words - stop_words

    found = []
    missing = []
    for req in headers_required:
        req_lower = req.strip().lower()

        # Tier 1: exact substring containment
        if any(req_lower in ah or ah in req_lower for ah in article_headers_lower):
            found.append(req)
            continue

        # Tier 2: keyword overlap (60%+ of significant words match)
        req_words = _significant_words(req_lower)
        if req_words and any(
            len(req_words & _significant_words(ah)) / len(req_words) >= 0.6
            for ah in article_headers_lower
        ):
            found.append(req)
            continue

        missing.append(req)

    coverage = len(found) / len(headers_required) * 100
    return {
        "total": len(headers_required),
        "found": len(found),
        "coverage_pct": round(coverage, 1),
        "missing": missing[:15],
    }


def check_keyword_coverage(article: str, keywords: list[str]) -> dict:
    lower_article = article.lower()
    found = [kw for kw in keywords if kw.lower() in lower_article]
    return {
        "total": len(keywords),
        "found": len(found),
        "coverage_pct": (len(found) / len(keywords) * 100) if keywords else 100,
        "missing": [kw for kw in keywords if kw.lower() not in lower_article],
    }


def check_cited_statistics(article: str) -> dict:
    """Check that numeric statistics have source links and are recent.

    Looks for patterns like percentages, dollar amounts, and large numbers
    that indicate a statistic, then checks whether a markdown link appears
    nearby (within the same sentence or adjacent text).
    """
    stat_pattern = re.compile(
        r"(?:"
        r"\d+(?:\.\d+)?%"           # percentages: 42%, 3.5%
        r"|\$\d[\d,]*(?:\.\d+)?"    # dollar amounts: $150,000, $45.5
        r"|\d{1,3}(?:,\d{3})+"      # large numbers with commas: 1,200,000
        r"|\d+(?:\.\d+)?\s*(?:million|billion|trillion)"  # "8.2 million"
        r")",
        re.IGNORECASE,
    )

    link_pattern = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)")

    lines = article.split("\n")
    total_stats = 0
    uncited_stats = 0
    uncited_examples: list[str] = []

    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            continue
        matches = stat_pattern.findall(line)
        if not matches:
            continue
        total_stats += len(matches)
        context = "\n".join(lines[max(0, i - 1) : i + 2])
        if not link_pattern.search(context):
            uncited_stats += len(matches)
            for m in matches[:2]:
                uncited_examples.append(f"{m} (line {i + 1})")

    outdated_years = re.findall(
        r"\b(201\d|202[0-3])\b", article
    )

    return {
        "total_stats": total_stats,
        "uncited_count": uncited_stats,
        "uncited_examples": uncited_examples[:10],
        "outdated_count": len(outdated_years),
        "outdated_years": list(set(outdated_years)),
        "pass": uncited_stats <= 3 and len(outdated_years) == 0,
    }
