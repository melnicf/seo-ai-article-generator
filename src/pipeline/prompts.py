"""Build the system and user prompts for Claude article generation."""

import random
from src.config import LEMON_INTERNAL_LINKS, TECH_OFFICIAL_LINKS


# ── System prompt ─────────────────────────────────────────────────────────


def build_system_prompt() -> str:
    """Return the system-level instructions for Claude."""
    return """You are an expert SEO content writer specializing in technology hiring content for Lemon.io, a marketplace of vetted developers from Europe and Latin America.

You write long-form articles (~3000 words) that are:
- Technically accurate and up-to-date
- Optimized for search engines using provided SEO terms
- Written for a business audience: startup founders, CTOs, solopreneurs, and SMB decision-makers
- Authoritative yet accessible — no jargon without context
- Structured for both continuous reading and header-based skimming

## STRUCTURAL RULES (STRICT — violations will fail review)

1. NO "Introduction" header. Start with a single paragraph (3-5 sentences) that immediately delivers value — a stat, a trend, a concrete insight. The first H2 follows right after.
2. The prompt provides an EXACT list of H2 headers. Use ONLY those H2s — do not add extra H2 sections. Each H2 section should be roughly 300-400 words.
3. You may add H3 (###) subsections within H2 sections for deeper structure. At least 2-3 H2 sections should have H3s.
4. Use #### (H4) only when absolutely necessary.
5. Headers NEVER repeat each other. Each header must be unique and specific.
6. The first H2 is never immediately followed by an H3 — there must be a paragraph of body text between them.
7. NO "Conclusion" header. End with a single closing paragraph that naturally wraps up and mentions Lemon.io's service.
8. Use bullet points and lists sparingly — only when the content genuinely calls for it. Don't stack bullets just to fill space.
9. Total article length: ~3000 words (2800-3200). Do NOT exceed 3200 words.

## KEYWORD RULES

The prompt provides TARGET KEYWORDS. These are exact phrases people search on Google. You MUST:
- Pick 5-10 of the provided keywords and include them VERBATIM (word-for-word, as written) in the article
- Distribute them across different sections — not clustered in one place
- Work them into natural sentences. Example: "When companies hire dedicated Python developers through Lemon.io, they get..."

## LEMON.IO GUIDELINES

- When discussing searching, vetting, hiring, onboarding developers: write from Lemon.io's perspective
- Lemon.io is a marketplace of vetted, experienced developers from Europe and Latin America
- It best serves startups, solopreneurs, founders, CTOs, SMB businesses looking for rapid scaling of their development capacity
- Key advantages: rigorous vetting process, matching speed (under 24 hours), full developer database access, hand-picked candidate matching
- Lemon.io offers part-time and full-time developers
- Compare Lemon.io favorably to: in-house hiring, HR agency services, development shops, general freelance platforms
- Call Lemon.io developers: dedicated, remote, part-time/full-time developers, engineers, programmers, coders, or experts
- NEVER call Lemon.io developers "freelancers" — use that word only when discussing other platforms or general market context
- Integrate Lemon.io case studies and testimonials as proof points — cite specific stats and quotes from real customers

## LINK RULES (MANDATORY — each is a hard requirement)

1. You MUST include exactly 2-3 EXTERNAL links. The user prompt provides suggested official URLs for this technology — use those. Every tech (Python, React, Node.js, etc.) has official sites and docs; when you mention the technology or a framework/library by name, add a link to its official site or documentation. Do not skip external links.
2. You MUST include exactly 2-3 INTERNAL Lemon.io links using short anchors (e.g., [back-end developers](URL), [AI engineers](URL)). Choose from the INTERNAL LINKS list provided.
3. NEVER link to Lemon.io competitors (Toptal, Upwork, Fiverr, Arc, Turing, etc.)
4. Format all links as standard markdown: [anchor text](URL)

## CLEARSCOPE SEO TERMS (MANDATORY — 90%+ IS A MUST)

- The user prompt includes a list of Clearscope terms. You MUST use 90%+ of these terms in the article — this is a hard requirement, not a suggestion. Include the primary term OR any of its variants naturally. HIGH importance terms are non-negotiable; add MEDIUM and LOWER until you reach 90%+ coverage. Articles below 90% fail validation and are rejected.

## CONTENT QUALITY

- Include recent statistics, trends, and technical updates. Cite sources inline.
- Every claim about the technology must be accurate and current.
- Professional but approachable tone — no corporate fluff.

Output format: Markdown with proper heading hierarchy (##, ###). No frontmatter, no meta tags — just the article content starting with the opening paragraph."""


# ── User prompt ───────────────────────────────────────────────────────────


def build_user_prompt(
    tech: str,
    page_url: str,
    keywords: list[str],
    h2_headers: list[str],
    h3_headers: list[str],
    questions: list[str],
    sc_queries: list[dict],
    clearscope_terms: list[dict],
    case_studies: dict,
) -> str:
    """Build the complete user prompt with all data sources.

    Args:
        tech: Human-readable technology name.
        page_url: Target URL on lemon.io.
        keywords: Templated keyword phrases.
        h2_headers: Pre-selected H2 section headers (chosen by AI selector).
        h3_headers: Remaining templates available for H3 subsections.
        questions: Questions to address in the article body.
        sc_queries: Search Console query data.
        clearscope_terms: Clearscope SEO terms.
        case_studies: Dict with 'case_studies' and 'testimonials' keys.
    """
    sections = [
        _build_intro(tech, page_url),
        _build_sc_section(sc_queries),
        _build_clearscope_section(clearscope_terms),
        _build_keyword_section(tech, keywords),
        _build_header_section(h2_headers, h3_headers),
        _build_question_section(questions),
        _build_case_study_section(case_studies),
        _build_internal_link_section(tech, page_url),
        _build_external_link_section(tech),
        _build_requirements(tech),
        _build_self_check(),
    ]

    return "\n".join(s for s in sections if s) + "\n\nWrite the article now."


# ── Section builders (private) ────────────────────────────────────────────


def _build_intro(tech: str, page_url: str) -> str:
    return f"""Write a ~3000-word article about hiring {tech} developers for the page: {page_url}

The article is the "Hiring Guide" content section of this landing page on Lemon.io. It should help founders, CTOs, and startup leaders understand why they need {tech} developers, what to look for when hiring, how much it costs, and how to hire them through Lemon.io."""


def _build_sc_section(sc_queries: list[dict]) -> str:
    if not sc_queries:
        return ""
    top_queries = sc_queries[:50]
    query_lines = [
        f'  - "{q["query"]}" (impressions: {q["impressions"]}, position: {q["position"]})'
        for q in top_queries
    ]
    return f"""
## SEARCH CONSOLE DATA
These are real queries people use to find this page. Weave the most relevant ones naturally into the article:
{chr(10).join(query_lines)}
"""


def _build_clearscope_section(clearscope_terms: list[dict]) -> str:
    if not clearscope_terms:
        return ""

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

    return f"""
## CLEARSCOPE SEO TERMS (MANDATORY — YOU MUST USE 90%+ OF THESE TERMS)
This is a hard requirement: at least 90% of the terms below must appear in your article (primary term OR any listed variant). Articles that do not reach 90% coverage fail validation. Use the [use Nx] guidance for how often each term should appear. Prioritize: include ALL HIGH, then as many MEDIUM and LOWER as needed to reach 90%+.

HIGH IMPORTANCE (you MUST include ALL of these):
{high_lines}

MEDIUM IMPORTANCE (include as many as needed to reach 90%+):
{medium_lines}

LOWER IMPORTANCE (include where natural — every term counts toward the 90% target):
{low_lines}
"""


def _build_keyword_section(tech: str, keywords: list[str]) -> str:
    kw_lines = [f'  {i+1}. "{k}"' for i, k in enumerate(keywords)]
    return f"""
## TARGET KEYWORDS (exact-match SEO phrases)
These are EXACT keyword phrases people type into Google. Pick 5-10 of the {len(keywords)} phrases below and include them VERBATIM (word-for-word, as written) in the article body. Distribute them across different sections — don't cluster them.

Work them into natural sentences.
Example: "When startups hire dedicated {tech} developers, they gain access to..."
Example: "The best way to find {tech} programmers is through a vetted marketplace like Lemon.io."

{chr(10).join(kw_lines)}
"""


def _build_header_section(h2_headers: list[str], h3_headers: list[str]) -> str:
    h2_lines = chr(10).join(f"  {i+1}. {h}" for i, h in enumerate(h2_headers))

    return f"""
## ARTICLE STRUCTURE (STRICT — do not add or remove H2 sections)
Your article MUST use EXACTLY these {len(h2_headers)} sections as H2 (##) headers, in this order. Use the wording as-is or with only minimal changes:

{h2_lines}

You may add H3 (###) subsections within any H2 section where they improve structure. Create your own subheader text — do not use a fixed list. At least 2-3 H2 sections should contain H3s.

CRITICAL: Do NOT create additional H2 sections beyond the {len(h2_headers)} listed above. Each H2 section should be roughly 300-400 words to hit the ~3000 word target.
"""


def _build_question_section(questions: list[str]) -> str:
    unique_questions = list(dict.fromkeys(questions))
    return f"""
## QUESTIONS TO ADDRESS
Answer 8-12 of these within the article body. Do NOT create a FAQ section — integrate answers naturally into relevant sections. The reader should get the answer while reading, not in a list:
{chr(10).join(f"  - {q}" for q in unique_questions)}
"""


def _build_case_study_section(case_studies: dict) -> str:
    cs_data = case_studies if isinstance(case_studies, dict) else {}
    studies = cs_data.get("case_studies", [])
    testimonials = cs_data.get("testimonials", [])

    selected_studies = random.sample(studies, min(3, len(studies))) if studies else []
    study_lines = []
    for s in selected_studies:
        stats_str = "; ".join(s["stats"])
        study_lines.append(f"  - {s['industry']}: {s['headline']} ({stats_str})")
        if s.get("quote"):
            study_lines.append(f'    Quote: "{s["quote"]}" — {s["quote_author"]}')

    testimonial_lines = [
        f'  - "{t["quote"]}" — {t["author"]}' for t in testimonials[:3]
    ]

    return f"""
## LEMON.IO CASE STUDIES & TESTIMONIALS (MUST USE)
You MUST weave at least 2 of these into the article body as proof points. Include specific stats AND at least one direct quote. Do NOT dump them all in one section — spread them across the article where they support the narrative (e.g., when discussing vetting quality, speed, cost savings, or industry applications).

Case studies:
{chr(10).join(study_lines)}

Testimonials:
{chr(10).join(testimonial_lines)}
"""


def _build_internal_link_section(tech: str, page_url: str) -> str:
    internal_links = {
        anchor: url
        for anchor, url in LEMON_INTERNAL_LINKS.items()
        if url != page_url
    }
    link_lines = [f"  - [{anchor}]({url})" for anchor, url in internal_links.items()]

    return f"""
## INTERNAL LINKS (MANDATORY — must include 2-3)
You MUST include exactly 2-3 internal Lemon.io links from the list below. Pick the ones most relevant to {tech} development. Use SHORT anchors (e.g., "back-end developers", "AI engineers", "full-stack developers"):

{chr(10).join(link_lines)}
"""


def _build_external_link_section(tech: str) -> str:
    """Build the external links section with suggested official URLs for this tech."""
    key = tech.lower().strip()
    links = TECH_OFFICIAL_LINKS.get(key)
    if not links:
        return f"""
## EXTERNAL LINKS (MANDATORY — must include 2-3)
You MUST include exactly 2-3 external links to trusted sources: official {tech} documentation, language/framework docs, or recognized research (e.g., Stack Overflow surveys, GitHub). When you mention the technology or a framework by name, link to its official site or docs. Do not skip external links.
"""
    link_lines = [f"  - [{label}]({url})" for label, url in links]
    return f"""
## EXTERNAL LINKS (MANDATORY — must include 2-3)
You MUST include exactly 2-3 external links. Use these suggested official/trusted URLs when relevant (e.g., when first mentioning the technology or a framework). You may use others as well, but at least 2-3 links must appear in the article:

{chr(10).join(link_lines)}

When you mention {tech}, a related framework, or a tool by name, add a link to its official site or documentation. Do not skip external links.
"""


def _build_requirements(tech: str) -> str:
    return f"""
## ADDITIONAL REQUIREMENTS
- Article must be approximately 3000 words (2800-3200 range)
- Start with a compelling opening paragraph — use a recent statistic or industry trend about {tech}. Do NOT use any header before this paragraph.
- End with a single closing paragraph (no "Conclusion" header) that mentions Lemon.io services with a link
- Include 2-3 external links using the suggested official URLs above (or equivalent). Every article must have external links; do not omit them.
- DO NOT link to any developer hiring platforms that compete with Lemon.io
- Write in a professional but approachable tone
- Every claim about the technology should be accurate and current
- You MUST use 90%+ of the Clearscope terms listed above — this is non-negotiable. Include all HIGH, then add MEDIUM and LOWER until coverage is 90%+."""


def _build_self_check() -> str:
    return """
## PRE-SUBMISSION SELF-CHECK
Before outputting the article, mentally verify:
1. ONLY the prescribed H2 headers are used — no extra H2 sections added
2. Total word count is between 2800-3200 (each H2 section ~300-400 words)
3. At least 2-3 H2 sections contain H3 subsections
4. At least 5 TARGET KEYWORDS appear verbatim in the text
5. At least 2 internal Lemon.io links are included (using short anchors)
6. At least 2 external links are included (use the suggested official URLs — do not skip)
7. At least 2 case studies or testimonials are woven into the body
8. 90%+ of Clearscope terms are used (MUST — count them: all HIGH, then MEDIUM/LOWER until 90%+)
9. The article starts with a paragraph (no header) and ends with a paragraph (no "Conclusion" header)
10. No Lemon.io developers are called "freelancers"

If any check fails, revise the article before outputting."""
