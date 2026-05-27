"""Async HTTP client used by every checker.

Borrows the rotation/retry shape from the Zloc toolkit but adds POST support and
explicit rate-limit signalling, which the holehe-style oracles depend on.
"""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class RateLimited(Exception):
    """Raised by a checker when the site throttled us; the result is inconclusive."""


def random_ua() -> str:
    return random.choice(USER_AGENTS)


@asynccontextmanager
async def make_client(
    *,
    timeout: httpx.Timeout | float | None = None,
    follow_redirects: bool = True,
    http2: bool = True,
    limits: httpx.Limits | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    headers = {**DEFAULT_HEADERS, "User-Agent": random_ua()}
    async with httpx.AsyncClient(
        timeout=timeout or DEFAULT_TIMEOUT,
        follow_redirects=follow_redirects,
        http2=http2,
        headers=headers,
        limits=limits or httpx.Limits(max_connections=100, max_keepalive_connections=20),
    ) as client:
        yield client


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retries: int = 1,
    backoff: float = 0.4,
    **kwargs: Any,
) -> httpx.Response | None:
    """Issue a request with simple exponential backoff.

    Returns None on definitive transport failure. A 5xx is retried; a 429 is
    returned as-is so the caller can map it to a rate-limited result.
    """
    last_status: int | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code >= 500:
                last_status = resp.status_code
                raise httpx.HTTPStatusError("server error", request=resp.request, response=resp)
            return resp
        except (httpx.TimeoutException, httpx.HTTPError):
            if attempt < retries:
                await asyncio.sleep(backoff * (2**attempt))
    if last_status is not None:
        # We exhausted retries on a 5xx; surface nothing rather than guess.
        return None
    return None
