"""Orchestrate the full article generation pipeline.

Three-step process:
1. Header selection (fast model) — picks the best H2 headers for the tech
2. Web research (mid model + web search) — gathers current stats/trends
3. Article generation (main model) — writes the article using all inputs
"""

from __future__ import annotations

import time
import anthropic

from src.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    CLAUDE_TEMPERATURE,
    SELECTOR_MODEL,
    WEB_SEARCH_ENABLED,
)
from src.pipeline.anthropic_retry import messages_create_with_retry
from src.pipeline.header_selector import select_headers
from src.pipeline.researcher import research_tech
from src.pipeline.prompts import build_system_prompt, build_user_prompt


def generate_article(
    tech: str,
    page_url: str,
    keywords: list[str],
    headers: list[str],
    questions: list[str],
    sc_queries: list[dict],
    clearscope_terms: list[dict],
    case_studies: dict,
    system_prompt_override: str | None = None,
) -> tuple[str, list[str]]:
    """Generate a single article by calling Claude API.

    Args:
        tech: Human-readable technology name.
        page_url: Target URL on lemon.io.
        keywords: Templated keyword phrases.
        headers: Full list of header templates from CSV.
        questions: Questions to address in the article body.
        sc_queries: Search Console query data.
        clearscope_terms: Clearscope SEO terms.
        case_studies: Dict with 'case_studies' and 'testimonials' keys.
        system_prompt_override: Optional full system prompt from Google Sheets.
                               If provided, replaces the built-in prompt entirely.

    Returns:
        (article_html, selected_h2_headers) — article content and the H2
        headers that were prescribed (for validation). H3s are created by the model.
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # ── Step 1: Select headers with fast model ────────────────────────────
    print(f"  -> Selecting headers for {tech} ({SELECTOR_MODEL})...")
    h2_headers, h3_headers = select_headers(
        client=client,
        tech=tech,
        all_headers=headers,
        num_h2=8,
        clearscope_terms=clearscope_terms,
    )
    print(f"  OK Selected {len(h2_headers)} H2 headers, {len(h3_headers)} available for H3")

    # ── Step 2: Web research (separate call, cheaper model) ───────────────
    research_brief = ""
    if WEB_SEARCH_ENABLED:
        research_brief = research_tech(client=client, tech=tech)

    # ── Step 3: Generate article with main model (no tools) ───────────────
    system_prompt = build_system_prompt(full_override=system_prompt_override)
    user_prompt = build_user_prompt(
        tech=tech,
        page_url=page_url,
        keywords=keywords,
        h2_headers=h2_headers,
        h3_headers=h3_headers,
        questions=questions,
        sc_queries=sc_queries,
        clearscope_terms=clearscope_terms,
        case_studies=case_studies,
        research_brief=research_brief,
    )

    print(f"  -> Generating article ({CLAUDE_MODEL})...")
    start = time.time()

    message = messages_create_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        temperature=CLAUDE_TEMPERATURE,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    elapsed = time.time() - start
    article = message.content[0].text
    word_count = len(article.split())
    usage = message.usage
    print(
        f"  OK Generated {word_count} words in {elapsed:.1f}s "
        f"({usage.input_tokens} in / {usage.output_tokens} out)"
    )

    return article, h2_headers
