from zcheck.core import registry, runner
from zcheck.core.models import Existence
from zcheck.core.registry import SiteChecker

CONTROL = "known-account"


def _register(name, fn, control=None):
    registry.register(
        SiteChecker(name=name, domain=f"{name}.test", category="test",
                    mode="username", nsfw=False, run=fn, kind="username_def", control=control)
    )


def _make(found_for):
    async def fn(client, target, result):
        result.existence = Existence.FOUND if target in found_for else Existence.NOT_FOUND
    return fn


async def _always_found(client, target, result):
    result.existence = Existence.FOUND


def test_verdict_logic_unit():
    from zcheck.core.models import SiteResult

    def sr(e):
        return SiteResult(site="s", domain="s.test", category="t", existence=e)

    # canary found => degraded (false positive), no matter the control
    assert runner._verdict(sr(Existence.FOUND), sr(Existence.FOUND), True) == "degraded"
    # healthy: control found, canary clean
    assert runner._verdict(sr(Existence.FOUND), sr(Existence.NOT_FOUND), True) == "healthy"
    # control undetected (stale known / rate limit) is NOT a false-positive risk
    # => inconclusive, never degraded
    assert runner._verdict(sr(Existence.NOT_FOUND), sr(Existence.NOT_FOUND), True) == "inconclusive"
    # no control + clean canary => inconclusive (can't confirm positives)
    assert runner._verdict(sr(Existence.UNKNOWN), sr(Existence.NOT_FOUND), False) == "inconclusive"


async def test_doctor_flags_healthy_and_degraded():
    _register("good", _make({CONTROL}), control=CONTROL)  # finds control, not canary
    _register("liar", _always_found, control=CONTROL)  # finds everything incl canary

    rows = await runner.doctor(mode="username", concurrency=5)
    verdicts = {c.site: v for c, _k, v in rows}
    assert verdicts["good"] == "healthy"
    assert verdicts["liar"] == "degraded"
