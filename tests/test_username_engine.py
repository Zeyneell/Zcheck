import httpx
import pytest
import respx

from zcheck.core.http import RateLimited
from zcheck.core.models import Existence, SiteResult
from zcheck.engine.username import UsernameSiteDef, run_username_def

WMN = {
    "name": "DemoSite",
    "uri_check": "https://demo.test/u/{account}",
    "e_code": 200,
    "e_string": "profile",
    "m_string": "Not Found",
    "cat": "social",
    "known": ["alice", "bob"],
}


def _site(**over):
    d = {**WMN, **over}
    return UsernameSiteDef.from_wmn(d)


def _result(site):
    return SiteResult(site=site.name, domain=site.domain, category=site.category)


def test_from_wmn_parsing_and_known():
    s = _site()
    assert s.name == "DemoSite"
    assert s.e_code == 200
    assert s.known == ("alice", "bob")
    assert s.domain == "demo.test"
    assert s.nsfw is False


def test_nsfw_detected_from_category():
    assert _site(cat="xx NSFW xx").nsfw is True


@respx.mock
async def test_found_requires_code_and_string_and_no_marker():
    respx.get("https://demo.test/u/alice").mock(
        return_value=httpx.Response(200, text="<h1>profile of alice</h1>")
    )
    s = _site()
    res = _result(s)
    async with httpx.AsyncClient() as client:
        await run_username_def(client, "alice", s, res)
    assert res.existence is Existence.FOUND
    assert res.extra["profile_url"] == "https://demo.test/u/alice"


@respx.mock
async def test_not_found_on_wrong_status():
    respx.get("https://demo.test/u/ghost").mock(
        return_value=httpx.Response(404, text="profile")  # e_string present but wrong code
    )
    s = _site()
    res = _result(s)
    async with httpx.AsyncClient() as client:
        await run_username_def(client, "ghost", s, res)
    assert res.existence is Existence.NOT_FOUND


@respx.mock
async def test_negative_marker_overrides_positive_code():
    # 200 + e_string present, but the m_string ("Not Found") is also present:
    # this is the classic soft-404 false positive — must resolve NOT_FOUND.
    respx.get("https://demo.test/u/ghost").mock(
        return_value=httpx.Response(200, text="profile ... Not Found")
    )
    s = _site()
    res = _result(s)
    async with httpx.AsyncClient() as client:
        await run_username_def(client, "ghost", s, res)
    assert res.existence is Existence.NOT_FOUND


@respx.mock
async def test_rate_limited():
    respx.get("https://demo.test/u/x").mock(return_value=httpx.Response(429))
    s = _site()
    res = _result(s)
    with pytest.raises(RateLimited):
        async with httpx.AsyncClient() as client:
            await run_username_def(client, "x", s, res)


@respx.mock
async def test_post_body_uses_post():
    route = respx.post("https://demo.test/u/alice").mock(
        return_value=httpx.Response(200, text="profile")
    )
    s = _site(post_body='{"u":"{account}"}')
    res = _result(s)
    async with httpx.AsyncClient() as client:
        await run_username_def(client, "alice", s, res)
    assert route.called
    assert res.existence is Existence.FOUND
