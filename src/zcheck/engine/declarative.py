"""Run a JSON-defined email oracle (the holehe-style core, but data-driven)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from ..core.http import RateLimited, random_ua, request_with_retry
from ..core.models import Existence, SiteResult
from . import rules


@dataclass(frozen=True)
class EmailSiteDef:
    name: str
    domain: str
    category: str
    request: dict[str, Any]
    rules: dict[str, list[dict[str, Any]]]
    nsfw: bool = False
    recovery_email: dict[str, Any] | None = None
    recovery_phone: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EmailSiteDef":
        return cls(
            name=d["name"],
            domain=d["domain"],
            category=d.get("category", "other"),
            request=d["request"],
            rules=d.get("rules", {}),
            nsfw=d.get("nsfw", False),
            recovery_email=d.get("recovery_email"),
            recovery_phone=d.get("recovery_phone"),
        )


def _interpolate(value: Any, mapping: dict[str, str]) -> Any:
    """Substitute {placeholders} in strings, recursing into dicts/lists."""
    if isinstance(value, str):
        out = value
        for key, repl in mapping.items():
            out = out.replace("{" + key + "}", repl)
        return out
    if isinstance(value, dict):
        return {k: _interpolate(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v, mapping) for v in value]
    return value


async def run_email_def(
    client: httpx.AsyncClient, email: str, site: EmailSiteDef, result: SiteResult
) -> None:
    """Execute one declarative email checker, mutating ``result`` in place."""
    mapping = {"email": email, "email_enc": quote(email, safe=""), "ua": random_ua()}
    req = site.request
    method = req.get("method", "GET").upper()
    url = _interpolate(req["url"], mapping)

    kwargs: dict[str, Any] = {}
    if "headers" in req:
        kwargs["headers"] = _interpolate(req["headers"], mapping)
    if "json" in req:
        kwargs["json"] = _interpolate(req["json"], mapping)
    if "data" in req:
        kwargs["data"] = _interpolate(req["data"], mapping)
    if "params" in req:
        kwargs["params"] = _interpolate(req["params"], mapping)

    resp = await request_with_retry(client, method, url, **kwargs)
    if resp is None:
        result.existence = Existence.ERROR
        result.error = "no response (timeout / transport error)"
        return

    # Explicit rate-limit rule wins; otherwise a bare 429 is treated as throttling.
    if rules.match_rule(resp, site.rules.get("rate_limited")) or resp.status_code == 429:
        raise RateLimited(f"{site.name} returned {resp.status_code}")

    if rules.match_rule(resp, site.rules.get("found")):
        result.existence = Existence.FOUND
        result.recovery_email = rules.extract(resp, site.recovery_email)
        result.recovery_phone = rules.extract(resp, site.recovery_phone)
    elif rules.match_rule(resp, site.rules.get("not_found")):
        result.existence = Existence.NOT_FOUND
    else:
        result.existence = Existence.UNKNOWN
        result.note = f"no rule matched (status {resp.status_code})"
