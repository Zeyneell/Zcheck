import httpx

from zcheck.engine import rules


def _resp(status=200, *, json=None, text=None, headers=None, url="https://x.test/p"):
    kwargs = {"request": httpx.Request("GET", url)}
    if json is not None:
        kwargs["json"] = json
    if text is not None:
        kwargs["text"] = text
    if headers is not None:
        kwargs["headers"] = headers
    return httpx.Response(status, **kwargs)


def test_status_code_scalar_and_list():
    assert rules.evaluate_condition(_resp(200), {"status_code": 200})
    assert rules.evaluate_condition(_resp(404), {"status_code": [200, 404]})
    assert not rules.evaluate_condition(_resp(500), {"status_code": [200, 404]})


def test_body_contains_and_not_contains():
    r = _resp(text="email already taken")
    assert rules.evaluate_condition(r, {"body_contains": "already"})
    assert rules.evaluate_condition(r, {"body_contains": ["nope", "taken"]})
    assert not rules.evaluate_condition(r, {"body_not_contains": "already"})
    assert rules.evaluate_condition(r, {"body_not_contains": "absent-string"})


def test_body_regex():
    r = _resp(text="code=ABC123 done")
    assert rules.evaluate_condition(r, {"body_regex": r"code=[A-Z]+\d+"})
    assert not rules.evaluate_condition(r, {"body_regex": r"code=\d{9}"})


def test_json_equals_in_exists_and_bare():
    r = _resp(json={"status": 20, "taken": True, "nested": {"ok": 1}})
    assert rules.evaluate_condition(r, {"json": "status", "equals": 20})
    assert not rules.evaluate_condition(r, {"json": "status", "equals": 1})
    assert rules.evaluate_condition(r, {"json": "status", "in": [10, 20, 30]})
    assert rules.evaluate_condition(r, {"json": "nested.ok", "equals": 1})
    assert rules.evaluate_condition(r, {"json": "missing", "exists": False})
    assert not rules.evaluate_condition(r, {"json": "missing", "exists": True})
    assert rules.evaluate_condition(r, {"json": "taken"})  # bare truthiness


def test_condition_keys_are_anded():
    r = _resp(200, text="taken")
    assert rules.evaluate_condition(r, {"status_code": 200, "body_contains": "taken"})
    assert not rules.evaluate_condition(r, {"status_code": 200, "body_contains": "free"})


def test_match_rule_is_or():
    r = _resp(429)
    conds = [{"status_code": 429}, {"body_contains": "slow down"}]
    assert rules.match_rule(r, conds)
    assert not rules.match_rule(r, None)
    assert not rules.match_rule(r, [])


def test_extract_json_and_regex():
    r = _resp(json={"obfuscated_email": "j***@gmail.com"})
    assert rules.extract(r, {"json": "obfuscated_email"}) == "j***@gmail.com"
    r2 = _resp(text="recovery: +1 *** *** 1234")
    assert rules.extract(r2, {"body_regex": r"\+\d[\d *]+\d"})
    assert rules.extract(r, None) is None
