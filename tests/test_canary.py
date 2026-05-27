from zcheck.core import canary
from zcheck.core.models import Existence, SiteResult


def _r(site, existence):
    return SiteResult(site=site, domain=f"{site}.test", category="x", existence=existence)


def test_canary_identifiers_are_unique_and_shaped():
    assert canary.canary_email() != canary.canary_email()
    assert "@" in canary.canary_email()
    assert canary.canary_username().startswith("zcheck_canary_")


def test_unreliable_checks_collects_canary_hits():
    canary_results = [
        _r("alpha", Existence.FOUND),  # found the canary -> unreliable
        _r("beta", Existence.NOT_FOUND),
        _r("gamma", Existence.ERROR),
    ]
    assert canary.unreliable_checks(canary_results) == {"alpha"}


def test_apply_canary_downgrades_only_unreliable_found():
    results = [
        _r("alpha", Existence.FOUND),  # unreliable -> downgrade
        _r("beta", Existence.FOUND),  # reliable -> keep
        _r("alpha2", Existence.NOT_FOUND),
    ]
    results[2].site = "alpha"  # an unreliable site that wasn't FOUND stays untouched
    canary.apply_canary(results, {"alpha"})
    assert results[0].existence is Existence.UNKNOWN
    assert results[0].note and "downgraded" in results[0].note
    assert results[1].existence is Existence.FOUND
    assert results[2].existence is Existence.NOT_FOUND
