"""Grading and human-readable report formatting for validation results."""

from src.config import EXTERNAL_LINKS_MAX


def compute_grade(issues: list, warnings: list) -> str:
    """Compute article grade from issues and warnings.

    A+ = no issues, no warnings
    A  = no issues, some warnings
    A- = 1 issue
    B+ = 2 issues
    B  = 3 issues
    C  = 4-5 issues
    D  = 6+ issues
    """
    if len(issues) == 0 and len(warnings) == 0:
        return "A+"
    if len(issues) == 0:
        return "A"
    if len(issues) <= 1:
        return "A-"
    if len(issues) <= 2:
        return "B+"
    if len(issues) <= 3:
        return "B"
    if len(issues) <= 5:
        return "C"
    return "D"


def format_validation_report(results: dict, tech: str) -> str:
    """Format validation results as a readable CLI report."""

    def _status(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    wc = results["word_count"]
    h2 = results["h2_count"]
    il = results["internal_links"]
    el = results["external_links"]
    hdr = results.get("header_coverage", {})
    cs = results.get("clearscope_coverage", {})
    kw = results.get("keyword_coverage", {})

    lines = [
        f"{'='*60}",
        f"VALIDATION REPORT: {tech}",
        f"{'='*60}",
        f"Grade: {results['grade']}",
        "",
        f"  [{_status(wc['pass'])}] Word count:       {wc['count']}  (target: 2800-3200)",
        f"  [{_status(h2['pass'])}] H2 headers:       {h2['count']}  (target: 7-9)",
        f"  [{_status(il['pass'])}] Internal links:   {il['count']}  (need: 2-3)",
        f"  [{_status(el['pass'])}] External links:   {el['count']}  (need: 2-3, max: {EXTERNAL_LINKS_MAX})",
    ]

    # Header templates
    if hdr and hdr.get("total", 0) > 0:
        hdr_found = hdr.get("found", 0)
        hdr_ok = hdr_found >= 7
        lines.append(
            f"  [{_status(hdr_ok)}] Headers from templates: {hdr_found} used out of {hdr.get('total', 0)} available"
        )

    # Keywords
    if kw and kw.get("total", 0) > 0:
        kw_found = kw.get("found", 0)
        kw_ok = kw_found >= 5
        lines.append(
            f"  [{_status(kw_ok)}] Keywords used:    {kw_found} exact matches  (need: 5-10)"
        )

    # Clearscope coverage
    if cs and cs.get("total_terms", 0) > 0:
        cs_pct = cs.get("coverage_pct", 0)
        cs_ok = cs_pct >= 90
        lines.append(
            f"  [{_status(cs_ok)}] Clearscope terms: {cs.get('found', '?')}/{cs.get('total_terms', '?')} = {cs_pct:.0f}%  (target: 90%+)"
        )
        if cs.get("missing_high_importance"):
            terms = ", ".join(
                t.get("term", str(t)) for t in cs["missing_high_importance"][:10]
            )
            lines.append(f"    Missing HIGH importance: {terms}")

    lm = results.get("lemon_mentions", {})
    lines.append(
        f"  [{_status(lm.get('pass', False))}] Lemon.io mentions: {lm.get('count', 0)}  (need: 3+)"
    )

    tech_m = results.get("tech_mentioned", {})
    if tech_m:
        lines.append(
            f"  [{_status(tech_m.get('pass', False))}] Tech '{tech_m.get('tech', '?')}' mentions: {tech_m.get('count', 0)}"
        )

    # Issues
    if results["issues"]:
        lines.append(f"\nISSUES ({len(results['issues'])}):")
        for issue in results["issues"]:
            lines.append(f"  - {issue}")

    # Warnings
    if results.get("warnings"):
        lines.append(f"\nWARNINGS ({len(results['warnings'])}):")
        for warning in results["warnings"]:
            lines.append(f"  ~ {warning}")

    if not results["issues"] and not results.get("warnings"):
        lines.append("\nAll checks passed!")

    lines.append(f"{'='*60}")
    return "\n".join(lines)
