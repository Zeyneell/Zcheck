"""Locate, load, and refresh the site datasets.

Resolution order for any dataset is: **user cache** (written by ``zcheck
update``) first, then the **bundled snapshot** shipped in the package. That is
the whole self-updating story — when a site changes and the dataset is fixed
upstream, ``update`` drops a fresh copy in the cache and every scan picks it up
without touching the installed code.
"""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any

import httpx

# Username dataset: the community-maintained WhatsMyName project (CC-licensed,
# attributed in DATA_SOURCES.md). This is the source of the 400+ coverage.
USERNAME_DATA_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
# Our own email-oracle defs. Override with ZCHECK_EMAIL_DATA_URL (e.g. a gist)
# if the project repo is private and raw fetch needs auth.
EMAIL_DATA_URL = os.environ.get(
    "ZCHECK_EMAIL_DATA_URL",
    "https://raw.githubusercontent.com/Zeyneell/Zcheck/main/src/zcheck/data/email_sites.json",
)

EMAIL_FILE = "email_sites.json"
USERNAME_FILE = "username_sites.json"


def cache_dir() -> Path:
    base = os.environ.get("ZCHECK_CACHE_DIR")
    if base:
        return Path(base)
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "zcheck"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "zcheck"


def _bundled(name: str) -> Path:
    return Path(str(resources.files("zcheck") / "data" / name))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve(name: str) -> Path:
    cached = cache_dir() / name
    return cached if cached.exists() else _bundled(name)


def load_email_sites() -> list[dict]:
    try:
        data = _read_json(_resolve(EMAIL_FILE))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return data.get("sites", data) if isinstance(data, dict) else data


def load_username_sites() -> list[dict]:
    try:
        data = _read_json(_resolve(USERNAME_FILE))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    # WhatsMyName wraps entries under "sites"; our normalized snapshot may too.
    return data.get("sites", data) if isinstance(data, dict) else data


def update(*, check_only: bool = False, timeout: float = 30.0) -> dict[str, str]:
    """Refresh datasets into the cache. Returns a per-source status map."""
    cache_dir().mkdir(parents=True, exist_ok=True)
    report: dict[str, str] = {}
    sources = {USERNAME_FILE: USERNAME_DATA_URL, EMAIL_FILE: EMAIL_DATA_URL}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for fname, url in sources.items():
            try:
                resp = client.get(url)
                resp.raise_for_status()
                payload = resp.json()
                sites = payload.get("sites", payload) if isinstance(payload, dict) else payload
                n = len(sites)
                if check_only:
                    report[fname] = f"available: {n} sites"
                    continue
                (cache_dir() / fname).write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
                report[fname] = f"updated: {n} sites -> {cache_dir() / fname}"
            except Exception as exc:  # network/parse failure is non-fatal
                report[fname] = f"skipped: {type(exc).__name__}: {exc}"
    return report
