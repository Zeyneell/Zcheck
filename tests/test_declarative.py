import httpx
import pytest
import respx

from zcheck.core.http import RateLimited
from zcheck.core.models import Existence, SiteResult
from zcheck.engine.declarative import EmailSiteDef, run_email_def

URL = "https://api.demo.test/check"

DEF = EmailSiteDef.from_dict(
    {
        "name": "demo",
        "domain": "demo.test",
        "category": "test",
        "request": {"method": "GET", "url": URL + "?email={email_enc}"},
        "rules": {
            "found": [{"json": "status", "equals": 20}],
            "not_found": [{"json": "status", "equals": 1}],
            "rate_limited": [{"status_code": 429}],
        },
        "recovery_email": {"json": "hint"},
    }
)


def _result():
    return SiteResult(site=DEF.name, domain=DEF.domain, category=DEF.category)


@respx.mock
async def test_found_with_recovery():
    respx.get(url__regex=r"https://api\.demo\.test/check.*").mock(
        return_value=httpx.Response(200, json={"status": 20, "hint": "j***@x.com"})
    )
    res = _result()
    async with httpx.AsyncClient() as client:
        await run_email_def(client, "a@b.com", DEF, res)
    assert res.existence is Existence.FOUND
    assert res.recovery_email == "j***@x.com"


@respx.mock
async def test_not_found():
    respx.get(url__regex=r"https://api\.demo\.test/check.*").mock(
        return_value=httpx.Response(200, json={"status": 1})
    )
    res = _result()
    async with httpx.AsyncClient() as client:
        await run_email_def(client, "a@b.com", DEF, res)
    assert res.existence is Existence.NOT_FOUND


@respx.mock
async def test_explicit_rate_limit_raises():
    respx.get(url__regex=r"https://api\.demo\.test/check.*").mock(
        return_value=httpx.Response(429, json={})
    )
    res = _result()
    with pytest.raises(RateLimited):
        async with httpx.AsyncClient() as client:
            await run_email_def(client, "a@b.com", DEF, res)


@respx.mock
async def test_unknown_when_no_rule_matches():
    respx.get(url__regex=r"https://api\.demo\.test/check.*").mock(
        return_value=httpx.Response(200, json={"status": 999})
    )
    res = _result()
    async with httpx.AsyncClient() as client:
        await run_email_def(client, "a@b.com", DEF, res)
    assert res.existence is Existence.UNKNOWN
    assert res.note


@respx.mock
async def test_error_on_transport_failure():
    respx.get(url__regex=r"https://api\.demo\.test/check.*").mock(
        side_effect=httpx.ConnectError("down")
    )
    res = _result()
    async with httpx.AsyncClient() as client:
        await run_email_def(client, "a@b.com", DEF, res)
    assert res.existence is Existence.ERROR


def test_email_is_url_encoded_in_request():
    # The '+' and '@' in a plus-addressed email must be percent-encoded.
    from urllib.parse import quote

    assert quote("a+tag@b.com", safe="") == "a%2Btag%40b.com"
