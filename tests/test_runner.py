"""End-to-end runner tests with fake checkers — no network.

These are the false-positive guarantees the whole tool hinges on.
"""

from zcheck.core import registry, runner
from zcheck.core.models import Existence
from zcheck.core.registry import SiteChecker

REAL = "victim@example.com"


def _register(name, fn, mode="email", nsfw=False, control=None):
    registry.register(
        SiteChecker(name=name, domain=f"{name}.test", category="test",
                    mode=mode, nsfw=nsfw, run=fn, kind="plugin", control=control)
    )


async def _always_found(client, target, result):
    result.existence = Existence.FOUND


async def _real_only(client, target, result):
    result.existence = Existence.FOUND if target == REAL else Existence.NOT_FOUND


async def _boom(client, target, result):
    raise ValueError("checker blew up")


async def test_canary_downgrades_a_false_positive_oracle():
    _register("alwaysfound", _always_found)  # claims FOUND for anything (incl. canary)
    _register("realonly", _real_only)  # only the real address

    scan = await runner.scan(REAL, mode="email", concurrency=5, use_canary=True)

    found = {r.site for r in scan.found}
    assert found == {"realonly"}  # the over-matching oracle is suppressed

    bad = next(r for r in scan.results if r.site == "alwaysfound")
    assert bad.existence is Existence.UNKNOWN
    assert bad.note and "downgraded" in bad.note


async def test_without_canary_false_positive_survives():
    _register("alwaysfound", _always_found)
    scan = await runner.scan(REAL, mode="email", concurrency=5, use_canary=False)
    assert {r.site for r in scan.found} == {"alwaysfound"}


async def test_misbehaving_checker_is_isolated_as_error():
    _register("boom", _boom)
    _register("realonly", _real_only)
    scan = await runner.scan(REAL, mode="email", concurrency=5, use_canary=True)
    boom = next(r for r in scan.results if r.site == "boom")
    assert boom.existence is Existence.ERROR
    assert "ValueError" in (boom.error or "")
    # the good checker still ran
    assert {r.site for r in scan.found} == {"realonly"}


async def test_results_sorted_found_first():
    _register("realonly", _real_only)
    _register("nope", lambda c, t, r: _set_nf(r))
    scan = await runner.scan(REAL, mode="email", concurrency=5, use_canary=False)
    assert scan.results[0].existence is Existence.FOUND


async def _set_nf(result):
    result.existence = Existence.NOT_FOUND


def test_derive_username():
    assert runner.derive_username("john.doe+spam@gmail.com") == "john.doe"
    assert runner.derive_username("alice@x.com") == "alice"
