"""Smoke-test the bundled datasets actually load and register."""

from zcheck import sites
from zcheck.core import registry


def test_bundled_datasets_load_400_plus():
    counts = sites.load(force=True)
    assert counts["plugins"] >= 2
    assert counts["username_defs"] > 400, "WhatsMyName snapshot should bring 400+ sites"

    checkers = registry.all_checkers()
    assert len(checkers) > 400
    for c in checkers:
        assert c.name
        assert c.mode in ("email", "username")
        assert c.run is not None


def test_email_defs_present():
    sites.load(force=True)
    email = [c for c in registry.all_checkers() if c.mode == "email"]
    names = {c.name for c in email}
    assert {"gravatar", "spotify"} <= names
