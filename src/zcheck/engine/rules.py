"""Condition evaluation for declarative checkers.

A *condition* is a dict; every key in it must hold (logical AND). A *rule* is a
list of conditions; the rule matches if any condition matches (logical OR). This
is what lets us describe a site's "account exists" oracle purely as JSON, so a
site changing its response only means editing data — never code.

Supported condition keys:
    status_code:      int | [int, ...]            HTTP status equals / is in set
    body_contains:    str | [str, ...]            substring present in body (any)
    body_not_contains:str | [str, ...]            substring absent from body (all)
    body_regex:       str                         regex search over body
    json:             "dot.path"                  combined with one comparator below
        equals:       Any                         json value == x
        in:           [Any, ...]                  json value in set
        exists:       bool                        path resolves / does not
    final_url_contains: str                       substring in the final (post-redirect) URL
    header:           {"name": str, "contains": str}   response header contains value
"""

from __future__ import annotations

import re
from typing import Any

import httpx


def _json_path(data: Any, path: str) -> tuple[bool, Any]:
    """Resolve a dotted path. Returns (found, value)."""
    cur = data
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
                continue
            except (ValueError, IndexError):
                return False, None
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def _parsed_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def evaluate_condition(resp: httpx.Response, cond: dict[str, Any]) -> bool:
    """True only if every key in the condition holds for the response."""
    body = resp.text

    if "status_code" in cond:
        if resp.status_code not in _as_list(cond["status_code"]):
            return False

    if "body_contains" in cond:
        if not any(s in body for s in _as_list(cond["body_contains"])):
            return False

    if "body_not_contains" in cond:
        if any(s in body for s in _as_list(cond["body_not_contains"])):
            return False

    if "body_regex" in cond:
        if re.search(cond["body_regex"], body) is None:
            return False

    if "final_url_contains" in cond:
        if cond["final_url_contains"] not in str(resp.url):
            return False

    if "header" in cond:
        spec = cond["header"]
        value = resp.headers.get(spec.get("name", ""), "")
        if spec.get("contains", "") not in value:
            return False

    if "json" in cond:
        found, value = _json_path(_parsed_json(resp), cond["json"])
        if "exists" in cond:
            if found is not bool(cond["exists"]):
                return False
        if "equals" in cond:
            if not found or value != cond["equals"]:
                return False
        if "in" in cond:
            if not found or value not in cond["in"]:
                return False
        if not any(k in cond for k in ("exists", "equals", "in")):
            # Bare `json` path: treat as an existence/truthiness test.
            if not found or value in (None, False, "", [], {}):
                return False

    return True


def match_rule(resp: httpx.Response, conditions: list[dict[str, Any]] | None) -> bool:
    """True if any condition in the rule matches (OR)."""
    if not conditions:
        return False
    return any(evaluate_condition(resp, c) for c in conditions)


def extract(resp: httpx.Response, spec: dict[str, Any] | None) -> Any | None:
    """Pull a single value (e.g. a leaked recovery email) from the response."""
    if not spec:
        return None
    if "json" in spec:
        found, value = _json_path(_parsed_json(resp), spec["json"])
        return value if found else None
    if "body_regex" in spec:
        m = re.search(spec["body_regex"], resp.text)
        if m:
            return m.group(spec.get("group", 0) if m.groups() else 0)
    return None
