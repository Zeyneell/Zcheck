"""Unified registry of site checkers.

Three sources feed one registry, all exposing the same ``run(client, target,
result)`` coroutine so the runner treats them identically:

* **email plugins** — hand-written Python for sites needing CSRF tokens or
  multi-step flows (decorated with :func:`email_site`);
* **declarative email defs** — JSON oracles interpreted by the engine;
* **username defs** — WhatsMyName-compatible entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, Literal

import httpx

from ..engine.declarative import EmailSiteDef, run_email_def
from ..engine.username import UsernameSiteDef, run_username_def
from .models import SiteResult

Mode = Literal["email", "username"]
RunFn = Callable[[httpx.AsyncClient, str, SiteResult], Awaitable[None]]


@dataclass(frozen=True)
class SiteChecker:
    name: str
    domain: str
    category: str
    mode: Mode
    nsfw: bool
    run: RunFn
    kind: str = "plugin"  # plugin | email_def | username_def
    # An identifier known to exist on this site, used by `zcheck doctor` as a
    # positive control. For username defs this is taken from WhatsMyName "known".
    control: str | None = None

    @property
    def key(self) -> str:
        return f"{self.mode}:{self.name.lower()}"


_REGISTRY: dict[str, SiteChecker] = {}


def register(checker: SiteChecker) -> None:
    # Hand-written plugins win over a declarative def of the same name/mode.
    existing = _REGISTRY.get(checker.key)
    if existing and existing.kind == "plugin" and checker.kind != "plugin":
        return
    _REGISTRY[checker.key] = checker


def email_site(
    name: str,
    domain: str,
    category: str = "other",
    *,
    nsfw: bool = False,
    control: str | None = None,
) -> Callable[[RunFn], RunFn]:
    """Decorator registering a hand-written email checker plugin."""

    def deco(fn: RunFn) -> RunFn:
        register(
            SiteChecker(
                name=name, domain=domain, category=category, mode="email",
                nsfw=nsfw, run=fn, kind="plugin", control=control,
            )
        )
        return fn

    return deco


def load_email_defs(defs: Iterable[dict]) -> int:
    count = 0
    for d in defs:
        site = EmailSiteDef.from_dict(d)

        async def run(client, email, result, _s=site):  # bind per-iteration
            await run_email_def(client, email, _s, result)

        register(
            SiteChecker(
                name=site.name, domain=site.domain, category=site.category,
                mode="email", nsfw=site.nsfw, run=run, kind="email_def",
            )
        )
        count += 1
    return count


def load_username_defs(defs: Iterable[dict]) -> int:
    count = 0
    for d in defs:
        site = UsernameSiteDef.from_wmn(d)

        async def run(client, username, result, _s=site):
            await run_username_def(client, username, _s, result)

        register(
            SiteChecker(
                name=site.name, domain=site.domain, category=site.category,
                mode="username", nsfw=site.nsfw, run=run, kind="username_def",
                control=site.known[0] if site.known else None,
            )
        )
        count += 1
    return count


def all_checkers() -> list[SiteChecker]:
    return list(_REGISTRY.values())


def clear() -> None:
    _REGISTRY.clear()


def select(
    *,
    mode: Mode | Literal["both"] = "both",
    only: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    nsfw: bool = False,
) -> list[SiteChecker]:
    """Filter the registry for a scan."""
    only_set = {s.lower() for s in only} if only else None
    cat_set = {c.lower() for c in categories} if categories else None
    out: list[SiteChecker] = []
    for c in _REGISTRY.values():
        if mode != "both" and c.mode != mode:
            continue
        if not nsfw and c.nsfw:
            continue
        if only_set is not None and c.name.lower() not in only_set:
            continue
        if cat_set is not None and c.category.lower() not in cat_set:
            continue
        out.append(c)
    return out


def categories() -> dict[str, int]:
    out: dict[str, int] = {}
    for c in _REGISTRY.values():
        out[c.category] = out.get(c.category, 0) + 1
    return dict(sorted(out.items()))
