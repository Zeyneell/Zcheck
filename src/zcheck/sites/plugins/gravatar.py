"""Gravatar — the most deterministic email oracle there is.

Every Gravatar profile is addressable by the MD5 of the lowercased, trimmed
email. A 200 on the JSON endpoint means a profile exists for that address; a
404 means it doesn't. No rate limits, no CSRF — ideal as a self-test control.
"""

from __future__ import annotations

import hashlib

import httpx

from ...core.http import request_with_retry
from ...core.models import Existence, SiteResult
from ...core.registry import email_site


@email_site("gravatar", "gravatar.com", "profile")
async def check(client: httpx.AsyncClient, email: str, result: SiteResult) -> None:
    digest = hashlib.md5(email.strip().lower().encode()).hexdigest()
    resp = await request_with_retry(client, "GET", f"https://en.gravatar.com/{digest}.json")
    if resp is None:
        result.existence = Existence.ERROR
        result.error = "no response"
        return
    if resp.status_code == 200:
        result.existence = Existence.FOUND
        try:
            entry = resp.json()["entry"][0]
            result.extra["profile_url"] = entry.get("profileUrl")
            result.extra["username"] = entry.get("preferredUsername")
        except Exception:
            pass
    elif resp.status_code == 404:
        result.existence = Existence.NOT_FOUND
    else:
        result.existence = Existence.UNKNOWN
        result.note = f"unexpected status {resp.status_code}"
