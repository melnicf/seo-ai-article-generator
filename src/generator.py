"""Generate articles using the Anthropic Claude API."""

import os
import time
import anthropic
from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_TEMPERATURE
from src.prompt import build_system_prompt, build_user_prompt


def generate_article(
    tech: str,
    page_url: str,
    keywords: list[str],
    headers: list[str],
    questions: list[str],
    sc_queries: list[dict],
    clearscope_terms: list[dict],
    case_studies: dict,
) -> str:
    """Generate a single article by calling Claude API.

    Returns the markdown article content as a string.
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        tech=tech,
        page_url=page_url,
        keywords=keywords,
        headers=headers,
        questions=questions,
        sc_queries=sc_queries,
        clearscope_terms=clearscope_terms,
        case_studies=case_studies,
    )

    print(f"  → Calling Claude ({CLAUDE_MODEL})...")
    start = time.time()

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        temperature=CLAUDE_TEMPERATURE,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )

    elapsed = time.time() - start
    article = message.content[0].text
    word_count = len(article.split())
    print(f"  ✓ Generated {word_count} words in {elapsed:.1f}s")

    return article
