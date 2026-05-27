from zcheck.core.models import Existence, ScanResult, SiteResult


def _r(name, existence, category="test"):
    return SiteResult(site=name, domain=f"{name}.test", category=category, existence=existence)


def test_counts_and_found():
    scan = ScanResult(
        email="x@y.com",
        results=[
            _r("a", Existence.FOUND),
            _r("b", Existence.NOT_FOUND),
            _r("c", Existence.FOUND),
            _r("d", Existence.ERROR),
            _r("e", Existence.RATE_LIMITED),
        ],
    )
    c = scan.counts()
    assert c["found"] == 2
    assert c["not_found"] == 1
    assert c["error"] == 1
    assert c["rate_limited"] == 1
    assert {r.site for r in scan.found} == {"a", "c"}


def test_done_sets_finish_and_sorts_found_first():
    scan = ScanResult(
        email="x@y.com",
        results=[_r("b", Existence.NOT_FOUND), _r("a", Existence.FOUND)],
    )
    scan.done()
    assert scan.finished_at is not None
    assert scan.elapsed_ms is not None
    assert scan.results[0].existence is Existence.FOUND


def test_siteresult_helpers():
    assert _r("a", Existence.FOUND).found is True
    assert _r("a", Existence.FOUND).conclusive is True
    assert _r("a", Existence.UNKNOWN).conclusive is False
