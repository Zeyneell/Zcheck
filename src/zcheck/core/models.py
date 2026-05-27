"""Typed result models for a Zcheck scan."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Existence(str, Enum):
    """Whether the target email is registered on a given site."""

    FOUND = "found"  # email has an account on this site
    NOT_FOUND = "not_found"  # site confirms no account
    UNKNOWN = "unknown"  # checker ran but couldn't decide
    RATE_LIMITED = "rate_limited"  # site throttled us; result is inconclusive
    ERROR = "error"  # network/parse failure


class SiteResult(BaseModel):
    """Outcome of probing one site for one email."""

    site: str
    domain: str
    category: str
    existence: Existence = Existence.UNKNOWN
    # Some sites leak a partially masked recovery email/phone on reset flows.
    recovery_email: str | None = None
    recovery_phone: str | None = None
    # Any other site-specific intel a checker wants to surface.
    extra: dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: int | None = None
    error: str | None = None
    # Human-readable annotation, e.g. why a result was downgraded by the canary.
    note: str | None = None

    @property
    def found(self) -> bool:
        return self.existence is Existence.FOUND

    @property
    def conclusive(self) -> bool:
        return self.existence in (Existence.FOUND, Existence.NOT_FOUND)


class ScanResult(BaseModel):
    """All site results for a single email lookup."""

    email: str
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    results: list[SiteResult] = Field(default_factory=list)

    @property
    def found(self) -> list[SiteResult]:
        return [r for r in self.results if r.existence is Existence.FOUND]

    @property
    def elapsed_ms(self) -> int | None:
        if self.finished_at is None:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)

    def counts(self) -> dict[str, int]:
        out = {e.value: 0 for e in Existence}
        for r in self.results:
            out[r.existence.value] += 1
        return out

    def done(self) -> "ScanResult":
        self.finished_at = _utcnow()
        # Stable, friendly ordering: found first, then by site name.
        self.results.sort(key=lambda r: (not r.found, r.category, r.site.lower()))
        return self
