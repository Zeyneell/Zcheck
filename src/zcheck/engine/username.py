"""Run a WhatsMyName-compatible username probe.

We deliberately mirror the WhatsMyName ``wmn-data.json`` contract (``uri_check``,
``e_code``, ``e_string``, ``m_string``, ``post_body``) so the dataset can be
ingested as-is by ``zcheck update`` and stay community-maintained.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..core.http import RateLimited, request_with_retry
from ..core.models import Existence, SiteResult


@dataclass(frozen=True)
class UsernameSiteDef:
    name: str
    uri_check: str
    e_code: int
    e_string: str
    category: str = "other"
    m_string: str | None = None
    m_code: int | None = None
    post_body: str | None = None
    headers: dict[str, str] | None = None
    nsfw: bool = False
    known: tuple[str, ...] = ()

    @property
    def domain(self) -> str:
        # Best-effort host for display, derived from the check URL template.
        rest = self.uri_check.split("://", 1)[-1]
        return rest.split("/", 1)[0].replace("{account}", "").strip(".")

    @classmethod
    def from_wmn(cls, d: dict[str, Any]) -> "UsernameSiteDef":
        cat = d.get("cat", "other")
        return cls(
            name=d["name"],
            uri_check=d["uri_check"],
            e_code=int(d["e_code"]),
            e_string=d.get("e_string", ""),
            category=cat,
            m_string=d.get("m_string"),
            m_code=int(d["m_code"]) if "m_code" in d else None,
            post_body=d.get("post_body"),
            headers=d.get("headers"),
            nsfw="nsfw" in cat.lower() or bool(d.get("nsfw")),
            known=tuple(d.get("known", [])),
        )


async def run_username_def(
    client: httpx.AsyncClient, username: str, site: UsernameSiteDef, result: SiteResult
) -> None:
    """Execute one username probe, mutating ``result`` in place."""
    url = site.uri_check.replace("{account}", username)
    method = "POST" if site.post_body else "GET"

    kwargs: dict[str, Any] = {}
    if site.headers:
        kwargs["headers"] = site.headers
    if site.post_body:
        kwargs["content"] = site.post_body.replace("{account}", username)

    # Do NOT follow redirects: a 301/302 to a generic landing page would
    # otherwise surface as a 200 and be mistaken for an existing account.
    resp = await request_with_retry(client, method, url, follow_redirects=False, **kwargs)
    if resp is None:
        result.existence = Existence.ERROR
        result.error = "no response (timeout / transport error)"
        return

    if resp.status_code == 429:
        raise RateLimited(f"{site.name} returned 429")

    body = resp.text
    positive = resp.status_code == site.e_code and (site.e_string == "" or site.e_string in body)
    negative_marker = bool(site.m_string and site.m_string in body)

    if positive and not negative_marker:
        result.existence = Existence.FOUND
        result.extra["profile_url"] = url
    else:
        result.existence = Existence.NOT_FOUND
