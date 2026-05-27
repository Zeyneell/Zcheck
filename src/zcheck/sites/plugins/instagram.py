"""Instagram — needs a CSRF token grabbed from the login page first.

This is the canonical example of why plugins exist: the oracle is a two-step
flow (GET to seed the ``csrftoken`` cookie, then POST the recovery endpoint with
that token). Instagram rate-limits and captcha-walls aggressively, so most of
the branches here resolve to RATE_LIMITED / UNKNOWN rather than guessing.
"""

from __future__ import annotations

import httpx

from ...core.http import RateLimited, request_with_retry
from ...core.models import Existence, SiteResult
from ...core.registry import email_site

LOGIN = "https://www.instagram.com/accounts/login/"
RECOVERY = "https://www.instagram.com/api/v1/web/accounts/account_recovery_send_ajax/"


@email_site("instagram", "instagram.com", "social")
async def check(client: httpx.AsyncClient, email: str, result: SiteResult) -> None:
    seed = await request_with_retry(client, "GET", LOGIN)
    if seed is None:
        result.existence = Existence.ERROR
        result.error = "could not load login page for CSRF token"
        return

    token = seed.cookies.get("csrftoken") or client.cookies.get("csrftoken")
    if not token:
        result.existence = Existence.UNKNOWN
        result.note = "no csrftoken issued (likely geo/bot wall)"
        return

    headers = {
        "X-CSRFToken": token,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": LOGIN,
    }
    resp = await request_with_retry(
        client, "POST", RECOVERY,
        headers=headers,
        data={"email_or_username": email, "recaptcha_challenge_field": ""},
    )
    if resp is None:
        result.existence = Existence.ERROR
        result.error = "no response from recovery endpoint"
        return
    if resp.status_code == 429:
        raise RateLimited("instagram throttled the recovery endpoint")

    try:
        body = resp.json()
    except Exception:
        result.existence = Existence.UNKNOWN
        result.note = f"non-JSON response (status {resp.status_code})"
        return

    # A successful recovery send => the address is attached to an account.
    if body.get("status") == "ok" and body.get("message"):
        result.existence = Existence.FOUND
        result.extra["message"] = body.get("message")
    elif "no users found" in str(body).lower():
        result.existence = Existence.NOT_FOUND
    elif body.get("message") == "checkpoint_required" or "spam" in str(body).lower():
        raise RateLimited("instagram checkpoint / spam wall")
    else:
        result.existence = Existence.UNKNOWN
        result.note = f"ambiguous recovery response (status {resp.status_code})"
