"""Retry Anthropic API calls on overload (529) and rate limit (429).

The article step uses claude-opus-4-6 with large prompts and often hits
OverloadedError. This helper retries with exponential backoff so runs
succeed without manual re-runs.
"""

import time

import anthropic
from anthropic._exceptions import OverloadedError, RateLimitError

# OverloadedError is not re-exported from anthropic in some SDK versions
RETRYABLE = (OverloadedError, RateLimitError)

# Retry up to 5 times: wait 8s, 16s, 32s, 64s, then give up
MAX_RETRIES = 5
BASE_DELAY = 4  # seconds; 4, 8, 16, 32, 64
MAX_DELAY = 120  # cap wait at 2 minutes


def messages_create_with_retry(client: anthropic.Anthropic, **kwargs):
    """Call client.messages.create(**kwargs) with retries on overload/rate-limit."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return client.messages.create(**kwargs)
        except RETRYABLE as e:
            last_error = e
            if attempt == MAX_RETRIES - 1:
                raise
            delay = min(BASE_DELAY * (2**attempt), MAX_DELAY)
            kind = type(e).__name__
            print(f"  .. API {kind}, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})...")
            time.sleep(delay)
    if last_error:
        raise last_error
    raise RuntimeError("retry loop exited without return or raise")
