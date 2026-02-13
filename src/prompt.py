"""Build the master prompt for Claude article generation."""

import json
import random
from src.config import LEMON_INTERNAL_LINKS


def build_system_prompt() -> str:
    """Return the system-level instructions for Claude."""
    return """You are an expert SEO content writer specializing in technology hiring content for Lemon.io, a marketplace of vetted developers from Europe and Latin America.

You write long-form articles (~3000 words) that are:
- Technically accurate and up-to-date
- Optimized for search engines using provided SEO terms
- Written for a business audience: startup founders, CTOs, solopreneurs, and SMB decision-makers
- Authoritative yet accessible — no jargon without context
- Structured for both continuous reading and header-based skimming

You ALWAYS follow these structural rules:
1. NO "Introduction" header. Start with a single paragraph (3-5 sentences) that immediately delivers value — a stat, a trend, a concrete insight. Then the first H2 header follows.
2. Use ## for major sections (H2) and ### for subsections (H3). Use #### (H4) only when absolutely necessary.
3. Headers NEVER repeat each other. Each header must be unique and specific.
4. The first H2 is never immediately followed by an H3 — there must be body text between them.
5. NO "Conclusion" header. End with a single paragraph that naturally wraps up and mentions Lemon.io's service.
6. Use bullet points and lists sparingly — only when the content genuinely calls for it (e.g., listing specific skills or tools). Don't stack bullets just to include keywords.
7. Target 5-10 H2 headers per article.

You ALWAYS follow these Lemon.io guidelines:
- When discussing hiring, vetting, onboarding developers: write from Lemon.io's perspective
- Lemon.io is a marketplace of vetted, experienced developers from Europe and Latin America
- Target audience: startups, solopreneurs, founders, CTOs, SMB businesses
- Key advantages: rigorous vetting process, matching speed (under 24 hours), full developer database access, hand-picked candidate matching
- Lemon.io offers part-time and full-time developers
- Compare Lemon.io favorably to: in-house hiring, HR agency services, development shops, general freelance platforms
- Call Lemon.io developers: dedicated, remote, part-time/full-time developers, engineers, programmers, coders, or experts
- NEVER call Lemon.io developers "freelancers" — use that word only when discussing other platforms or general market context

You ALWAYS follow these link rules:
- Include 2-3 external links to trusted sources (official documentation, recognized research, industry reports). NEVER link to Lemon.io competitors (Toptal, Upwork, Fiverr, Arc, Turing, etc.)
- Include 2-3 internal Lemon.io links with short, natural anchors (e.g., "Python developers", "back-end engineers", "full-stack developers")
- Format links as standard markdown: [anchor text](URL)

You ALWAYS include relevant statistics, trends, and technical updates. When referencing data, cite the source inline.

Output format: Markdown with proper heading hierarchy (##, ###). No frontmatter, no meta tags — just the article content starting with the opening paragraph."""


def build_user_prompt(
    tech: str,
    page_url: str,
    keywords: list[str],
    headers: list[str],
    questions: list[str],
    sc_queries: list[dict],
    clearscope_terms: list[dict],
    case_studies: dict,
) -> str:
    """Build the complete user prompt with all data sources."""

    # ── Select relevant internal links (exclude self) ──────────────────────
    internal_links = {
        anchor: url
        for anchor, url in LEMON_INTERNAL_LINKS.items()
        if url != page_url
    }
    # Pick 3 most relevant (prefer related tech, always include lemon.io)
    selected_links = {}
    if "Lemon.io" in internal_links:
        selected_links["Lemon.io"] = internal_links["Lemon.io"]
    remaining = {k: v for k, v in internal_links.items() if k != "Lemon.io"}
    for anchor, url in list(remaining.items())[:3]:
        selected_links[anchor] = url

    # ── Format SC queries ──────────────────────────────────────────────────
    sc_section = ""
    if sc_queries:
        top_queries = sc_queries[:50]
        query_lines = [f"  - \"{q['query']}\" (impressions: {q['impressions']}, position: {q['position']})" for q in top_queries]
        sc_section = f"""
## SEARCH CONSOLE DATA
These are real queries people use to find this page. Weave the most relevant ones naturally into the article:
{chr(10).join(query_lines)}
"""

    # ── Format Clearscope terms ────────────────────────────────────────────
    cs_section = ""
    if clearscope_terms:
        # Group by importance (importance is a number string: "10", "9", etc.)
        def _imp(t):
            try:
                return int(t["importance"])
            except (ValueError, TypeError):
                return 0

        high = [t for t in clearscope_terms if _imp(t) >= 8]
        medium = [t for t in clearscope_terms if 5 <= _imp(t) < 8]
        low = [t for t in clearscope_terms if _imp(t) < 5]

        def _fmt_term(t):
            parts = [t["term"]]
            variants = t.get("variants", [])
            if variants:
                parts.append(f"(also: {', '.join(variants[:3])})")
            uses_min = t.get("typical_uses_min", 1)
            uses_max = t.get("typical_uses_max", 2)
            parts.append(f"[use {uses_min}-{uses_max}x]")
            return " ".join(parts)

        high_lines = "\n".join(f"  - {_fmt_term(t)}" for t in high)
        medium_lines = "\n".join(f"  - {_fmt_term(t)}" for t in medium)
        low_lines = "\n".join(f"  - {_fmt_term(t)}" for t in low[:30])

        cs_section = f"""
## CLEARSCOPE SEO TERMS (CRITICAL — aim for 90%+ coverage)
You MUST naturally incorporate these terms into the article. Use the primary term OR any of its listed variants. The [use Nx] indicates how many times each term should ideally appear.

HIGH IMPORTANCE (must include ALL):
{high_lines}

MEDIUM IMPORTANCE (include MOST):
{medium_lines}

LOWER IMPORTANCE (include where natural):
{low_lines}
"""

    # ── Format case studies ────────────────────────────────────────────────
    cs_data = case_studies if isinstance(case_studies, dict) else {}
    studies = cs_data.get("case_studies", [])
    testimonials = cs_data.get("testimonials", [])

    # Pick 2-3 relevant case studies to reference
    selected_studies = random.sample(studies, min(3, len(studies))) if studies else []
    study_lines = []
    for s in selected_studies:
        stats_str = "; ".join(s["stats"])
        study_lines.append(f"  - {s['industry']}: {s['headline']} ({stats_str})")
        if s.get("quote"):
            study_lines.append(f"    Quote: \"{s['quote']}\" — {s['quote_author']}")

    testimonial_lines = []
    for t in testimonials[:2]:
        testimonial_lines.append(f"  - \"{t['quote']}\" — {t['author']}")

    case_section = f"""
## LEMON.IO CASE STUDIES & TESTIMONIALS
Reference 1-2 of these naturally in the article to support claims about Lemon.io:

Case studies:
{chr(10).join(study_lines)}

Testimonials:
{chr(10).join(testimonial_lines)}
"""

    # ── Format keywords ────────────────────────────────────────────────────
    kw_section = f"""
## TARGET KEYWORDS
Naturally include 5-10 of these keyword variations throughout the article:
{chr(10).join(f"  - {k}" for k in keywords)}
"""

    # ── Format headers ─────────────────────────────────────────────────────
    header_section = f"""
## HEADER TEMPLATES
Use 5-10 of these as H2 (##) section headers. You may slightly rephrase them for better flow, but keep the core topic:
{chr(10).join(f"  - {h}" for h in headers)}
"""

    # ── Format questions ───────────────────────────────────────────────────
    # Deduplicate questions
    unique_questions = list(dict.fromkeys(questions))
    question_section = f"""
## QUESTIONS TO ADDRESS
Answer 8-12 of these within the article body (NOT as a FAQ section — integrate answers naturally into relevant sections):
{chr(10).join(f"  - {q}" for q in unique_questions)}
"""

    # ── Format internal links ──────────────────────────────────────────────
    link_section = f"""
## INTERNAL LINKS
Include 2-3 of these Lemon.io links with short anchors:
{chr(10).join(f"  - [{anchor}]({url})" for anchor, url in selected_links.items())}
"""

    # ── Build the final prompt ─────────────────────────────────────────────
    prompt = f"""Write a ~3000-word article about hiring {tech} developers for the page: {page_url}

The article is the "Hiring Guide" content section of this landing page on Lemon.io. It should help founders, CTOs, and startup leaders understand why they need {tech} developers, what to look for, how much it costs, and how to hire them through Lemon.io.

{sc_section}
{cs_section}
{kw_section}
{header_section}
{question_section}
{case_section}
{link_section}

## ADDITIONAL REQUIREMENTS
- Article must be approximately 3000 words (2800-3200 range)
- Start with a compelling paragraph — use a recent statistic or industry trend about {tech}
- End with a single paragraph (no "Conclusion" header) mentioning Lemon.io
- Include 2-3 external links to official {tech} documentation, trusted industry sources, or recent research
- DO NOT link to any developer hiring platforms that compete with Lemon.io
- Write in a professional but approachable tone
- Every claim about the technology should be accurate and current

Write the article now."""

    return prompt
