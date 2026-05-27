# Contributing to Zcheck

Most of Zcheck is **data, not code**. Adding a site usually means adding one JSON object.

## Adding an email oracle (`src/zcheck/data/email_sites.json`)

An email oracle hits a site's "is this email already registered?" endpoint and maps the response
to `found` / `not_found`. Add an object to the `sites` array:

```json
{
  "name": "spotify",
  "domain": "spotify.com",
  "category": "music",
  "nsfw": false,
  "request": {
    "method": "GET",
    "url": "https://.../check?email={email_enc}",
    "headers": { "User-Agent": "{ua}" },
    "json": { "email": "{email}" }
  },
  "rules": {
    "found":        [{ "json": "status", "equals": 20 }],
    "not_found":    [{ "json": "status", "equals": 1 }],
    "rate_limited": [{ "status_code": 429 }]
  },
  "recovery_email": { "json": "obfuscated_email" }
}
```

Placeholders: `{email}`, `{email_enc}` (percent-encoded), `{ua}` (random User-Agent).

A **rule** is a list of **conditions**; the rule matches if *any* condition matches (OR). Within a
condition, *every* key must hold (AND). Supported condition keys:

| key | meaning |
|---|---|
| `status_code` | int or list of ints |
| `body_contains` / `body_not_contains` | substring(s) present / absent |
| `body_regex` | regex search over the body |
| `final_url_contains` | substring in the post-redirect URL |
| `header` | `{ "name": ..., "contains": ... }` |
| `json` | dotted path, with `equals` / `in` / `exists`, or bare for truthiness |

`recovery_email` / `recovery_phone` use `{ "json": "path" }` or `{ "body_regex": "..." }`.

Evaluation order is `rate_limited` → `found` → `not_found`, else `unknown`. A bare `429` is always
treated as rate-limited. **Every positive is still re-validated against a canary at runtime**, so a
slightly loose `found` rule won't produce a false positive — but tighten it anyway.

## Adding a username site

The username sweep consumes the **WhatsMyName** `wmn-data.json` format directly, so the best way to
add username sites is to contribute upstream to
[WhatsMyName](https://github.com/WebBreacher/WhatsMyName) and run `zcheck update`. A minimal entry:

```json
{
  "name": "GitHub",
  "uri_check": "https://github.com/{account}",
  "e_code": 200,
  "e_string": "data-hovercard-type=\"user\"",
  "m_string": "Not Found",
  "cat": "coding",
  "known": ["torvalds"]
}
```

`known` accounts double as `doctor`'s positive controls.

## Adding a Python plugin (complex sites)

For sites needing a CSRF token, signing, or several steps, drop a module in
`src/zcheck/sites/plugins/` — it's auto-discovered:

```python
from ...core.http import request_with_retry
from ...core.models import Existence, SiteResult
from ...core.registry import email_site

@email_site("example", "example.com", "social", control="known-account")
async def check(client, email, result: SiteResult) -> None:
    resp = await request_with_retry(client, "GET", f"https://example.com/check?e={email}")
    if resp is None:
        result.existence = Existence.ERROR; result.error = "no response"; return
    result.existence = Existence.FOUND if resp.status_code == 200 else Existence.NOT_FOUND
```

## Before opening a PR

```powershell
ruff check src tests
pytest -q
zcheck doctor --only <your-site>   # should not be "degraded"
```
