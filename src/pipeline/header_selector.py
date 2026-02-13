"""AI-powered header selection step.

Uses a fast, cheap model to dynamically pick the best H2 headers for a
given technology from the full template list, ensuring a logical article
structure and SEO relevance.
"""

from __future__ import annotations

import json
from typing import Optional

import anthropic

from src.config import SELECTOR_MODEL


def select_headers(
    client: anthropic.Anthropic,
    tech: str,
    all_headers: list[str],
    num_h2: int = 8,
    clearscope_terms: Optional[list[dict]] = None,
) -> tuple[list[str], list[str]]:
    """Select the best H2 headers for this technology using AI.

    Args:
        client: Anthropic API client.
        tech: Human-readable technology name (e.g. "Python").
        all_headers: Full list of header templates from CSV.
        num_h2: Exact number of H2 headers to select.
        clearscope_terms: Optional Clearscope terms for SEO context.

    Returns:
        (h2_headers, []) — selected H2s. H3 subheaders are not from templates;
        the article model creates its own where appropriate.
    """
    cs_context = ""
    if clearscope_terms:
        top_terms = [t["term"] for t in clearscope_terms[:20]]
        cs_context = f"\nTop SEO terms for this article: {', '.join(top_terms)}"

    numbered = "\n".join(f"  {i+1}. {h}" for i, h in enumerate(all_headers))

    prompt = f"""You are selecting the article structure for a ~3000-word hiring guide about {tech} developers on Lemon.io.

Below are {len(all_headers)} header templates. Pick EXACTLY {num_h2} that make the best H2 sections for an article about hiring {tech} developers. Choose headers that:
- Cover the most important topics for someone hiring {tech} talent
- Are specifically relevant to {tech} (not just generic)
- Form a logical article flow when read in sequence
- Include at least one Lemon.io-specific header (about hiring process, benefits, speed)
- Include at least one cost/pricing header
{cs_context}

Available headers:
{numbered}

Respond with ONLY a JSON array of the {num_h2} selected header numbers (1-indexed), in the order they should appear in the article. Example: [5, 2, 6, 14, 1, 7, 3, 11]

JSON array:"""

    message = client.messages.create(
        model=SELECTOR_MODEL,
        max_tokens=200,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Parse the JSON array from response
    try:
        if "```" in response_text:
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        selected_indices = json.loads(response_text.strip())
    except (json.JSONDecodeError, IndexError):
        print(f"  Warning: Header selection failed to parse, using first {num_h2} headers")
        selected_indices = list(range(1, num_h2 + 1))

    # Convert 1-indexed to 0-indexed and extract headers
    h2_headers = []
    used_indices = set()
    for idx in selected_indices:
        i = idx - 1
        if 0 <= i < len(all_headers):
            h2_headers.append(all_headers[i])
            used_indices.add(i)

    # Safety: ensure we have at least num_h2 headers
    for i, h in enumerate(all_headers):
        if len(h2_headers) >= num_h2:
            break
        if i not in used_indices:
            h2_headers.append(h)
            used_indices.add(i)

    # H3 subheaders are not taken from templates; the article model creates its own.
    return h2_headers, []
