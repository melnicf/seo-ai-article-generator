"""Web research step: gather current statistics, trends, and salary data.

Uses a fast model with the Anthropic web search tool to collect real-time
data for the article. Results are returned as structured text that gets
injected into the article generation prompt.
"""

import time
from datetime import datetime

import anthropic

from src.config import (
    RESEARCHER_MODEL,
    WEB_SEARCH_MAX_USES,
)

CURRENT_YEAR = datetime.now().year


def _build_research_prompt(tech: str) -> str:
    """Build the prompt that tells the researcher what to look for."""
    year = CURRENT_YEAR
    prev_year = year - 1

    return f"""You are a research assistant gathering current data about {tech} developers and the {tech} technology market.

Search the web and compile the following information. For EVERY data point, include the exact source URL.

## REQUIRED RESEARCH

1. **Market statistics** — Search for {year} (or latest available) data on:
   - Number of {tech} developers worldwide
   - {tech} popularity ranking among programming languages/frameworks (Stack Overflow Survey, TIOBE, GitHub Octoverse, etc.)
   - {tech} job market growth or demand trends
   - Any recent notable adoption statistics

2. **Salary data** — Search for {year} or {prev_year} {tech} developer salary ranges:
   - Average {tech} developer salary in the US (and/or globally)
   - Senior vs junior salary ranges if available
   - Remote {tech} developer rates if available
   - Source: Stack Overflow Survey, Glassdoor, Indeed, PayScale, or similar

3. **Technology trends** — Search for what's current in the {tech} ecosystem:
   - Major recent releases, updates, or milestones
   - Trending frameworks, libraries, or tools in the {tech} ecosystem
   - How {tech} is being used with AI/ML (if applicable)
   - Any notable companies or projects using {tech}

4. **Hiring market context** — Search for:
   - {tech} developer shortage or supply/demand data
   - Time-to-hire statistics for {tech} roles
   - Remote hiring trends for {tech} developers

## OUTPUT FORMAT

Return your findings as a structured brief. For each data point:
- State the fact clearly
- Include the year of the data
- Include the source name AND full URL in markdown link format

Example:
- According to the [Stack Overflow 2026 Developer Survey](https://survey.stackoverflow.co/2026/), Python is used by 51% of professional developers worldwide.

Do NOT make up statistics. If you cannot find current data for something, say so explicitly — do not fabricate numbers. Only include data you found via web search with real source URLs.

Compile all findings into a single research brief."""


def _extract_research_text(message: anthropic.types.Message) -> str:
    """Extract text content from a response that may include search blocks."""
    text_parts: list[str] = []
    for block in message.content:
        if block.type == "text":
            text_parts.append(block.text)
    return "".join(text_parts)


def _extract_search_stats(message: anthropic.types.Message) -> dict:
    """Pull web search usage stats from the response."""
    usage = message.usage
    server_tool_use = getattr(usage, "server_tool_use", None)
    search_requests = 0
    if server_tool_use:
        search_requests = getattr(server_tool_use, "web_search_requests", 0)
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "web_search_requests": search_requests,
    }


def research_tech(
    client: anthropic.Anthropic,
    tech: str,
) -> str:
    """Run web research for a technology and return a structured brief.

    Args:
        client: Anthropic API client.
        tech: Human-readable technology name (e.g., "Python", "React").

    Returns:
        Research brief as a string with sourced data points.
    """
    prompt = _build_research_prompt(tech)

    print(f"  -> Researching {tech} ({RESEARCHER_MODEL} + web search)...")
    start = time.time()

    message = client.messages.create(
        model=RESEARCHER_MODEL,
        max_tokens=4096,
        temperature=0.0,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": WEB_SEARCH_MAX_USES,
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    # Handle pause_turn: Claude may pause long-running turns with web search
    while message.stop_reason == "pause_turn":
        print("  .. research paused (searching), continuing...")
        message = client.messages.create(
            model=RESEARCHER_MODEL,
            max_tokens=4096,
            temperature=0.0,
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": WEB_SEARCH_MAX_USES,
                }
            ],
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": message.content},
            ],
        )

    elapsed = time.time() - start
    research = _extract_research_text(message)
    stats = _extract_search_stats(message)

    print(
        f"  OK Research complete in {elapsed:.1f}s "
        f"({stats['web_search_requests']} searches, "
        f"{stats['input_tokens']} in / {stats['output_tokens']} out)"
    )

    return research
