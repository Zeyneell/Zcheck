"""Concurrency, timing, and canary validation for a scan."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Callable, Iterable, Literal

import httpx

from . import canary as canary_mod
from .http import RateLimited, make_client
from .models import Existence, ScanResult, SiteResult
from .registry import SiteChecker, select

ResultCb = Callable[[SiteResult], None]


def derive_username(email: str) -> str:
    """Best-effort username candidate from an email local-part."""
    local = email.split("@", 1)[0]
    local = local.split("+", 1)[0]  # drop plus-addressing tag
    return local


def _target_for(checker: SiteChecker, email: str, username: str) -> str:
    return email if checker.mode == "email" else username


async def _run_checker(
    client: httpx.AsyncClient,
    target: str,
    checker: SiteChecker,
    sem: asyncio.Semaphore,
    on_result: ResultCb | None = None,
) -> SiteResult:
    res = SiteResult(
        site=checker.name, domain=checker.domain, category=checker.category
    )
    start = perf_counter()
    async with sem:
        try:
            await checker.run(client, target, res)
        except RateLimited as exc:
            res.existence = Existence.RATE_LIMITED
            res.note = str(exc)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            res.existence = Existence.ERROR
            res.error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:  # a misbehaving checker must not kill the scan
            res.existence = Existence.ERROR
            res.error = f"{type(exc).__name__}: {exc}"
    res.elapsed_ms = int((perf_counter() - start) * 1000)
    if on_result is not None:
        on_result(res)
    return res


async def scan(
    email: str,
    *,
    mode: Literal["email", "username", "both"] = "both",
    username: str | None = None,
    only: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    nsfw: bool = False,
    concurrency: int = 20,
    timeout: float = 10.0,
    use_canary: bool = True,
    on_result: ResultCb | None = None,
) -> ScanResult:
    checkers = select(mode=mode, only=only, categories=categories, nsfw=nsfw)
    username = username or derive_username(email)
    out = ScanResult(email=email)

    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with make_client(timeout=timeout, limits=limits) as client:
        sem = asyncio.Semaphore(concurrency)
        tasks = [
            _run_checker(client, _target_for(c, email, username), c, sem, on_result)
            for c in checkers
        ]
        results = await asyncio.gather(*tasks)

        # Canary validation: re-probe only the checkers that claimed a hit, using
        # throwaway identifiers. Any that "find" the canary are downgraded.
        if use_canary:
            c_email, c_user = canary_mod.canary_email(), canary_mod.canary_username()
            hot = [c for c, r in zip(checkers, results) if r.found]
            if hot:
                canary_tasks = [
                    _run_checker(client, _target_for(c, c_email, c_user), c, sem)
                    for c in hot
                ]
                canary_results = await asyncio.gather(*canary_tasks)
                canary_mod.apply_canary(results, canary_mod.unreliable_checks(canary_results))

    out.results = list(results)
    return out.done()


def _verdict(control: SiteResult, canary: SiteResult, has_control: bool) -> str:
    # "degraded" is reserved for the one unforgivable failure: the checker
    # "finds" a throwaway canary, i.e. it produces false positives. Everything
    # else we can't fully trust we call "inconclusive" rather than cry wolf —
    # a control that goes undetected is usually a stale known-account or a rate
    # limit, neither of which means the oracle reports phantom accounts.
    if canary.existence is Existence.FOUND:
        return "degraded"
    if has_control and control.existence is Existence.FOUND and canary.existence is Existence.NOT_FOUND:
        return "healthy"
    return "inconclusive"


async def doctor(
    *,
    mode: Literal["email", "username", "both"] = "both",
    only: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    nsfw: bool = False,
    concurrency: int = 20,
    timeout: float = 10.0,
) -> list[tuple[SiteResult, SiteResult, str]]:
    """Health-check every selected checker against a known control + a canary.

    Returns (control_result, canary_result, verdict) per checker. This is how
    breakage is detected automatically — wire it into CI to catch drift.
    """
    checkers = select(mode=mode, only=only, categories=categories, nsfw=nsfw)
    c_email, c_user = canary_mod.canary_email(), canary_mod.canary_username()

    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with make_client(timeout=timeout, limits=limits) as client:
        sem = asyncio.Semaphore(concurrency)
        canary_tasks = [
            _run_checker(client, _target_for(c, c_email, c_user), c, sem) for c in checkers
        ]
        control_at: dict[int, int] = {}
        control_tasks = []
        for i, c in enumerate(checkers):
            if c.control:
                control_at[i] = len(control_tasks)
                control_tasks.append(_run_checker(client, c.control, c, sem))
        canary_results = await asyncio.gather(*canary_tasks)
        control_results = await asyncio.gather(*control_tasks)

    rows: list[tuple[SiteResult, SiteResult, str]] = []
    for i, c in enumerate(checkers):
        canary = canary_results[i]
        if i in control_at:
            control = control_results[control_at[i]]
            has_control = True
        else:
            control = SiteResult(
                site=c.name, domain=c.domain, category=c.category, note="no control account"
            )
            has_control = False
        rows.append((control, canary, _verdict(control, canary, has_control)))
    return rows
