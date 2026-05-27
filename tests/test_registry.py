from zcheck.core import registry
from zcheck.core.registry import SiteChecker, load_email_defs, load_username_defs, select


async def _noop(client, target, result):
    return None


def _checker(name, mode="email", nsfw=False, category="test", kind="plugin"):
    return SiteChecker(name=name, domain=f"{name}.test", category=category,
                       mode=mode, nsfw=nsfw, run=_noop, kind=kind)


EMAIL_DEF = {
    "name": "spotify",
    "domain": "spotify.com",
    "category": "music",
    "request": {"method": "GET", "url": "https://x/{email_enc}"},
    "rules": {"found": [{"status_code": 200}]},
}

USERNAME_DEF = {
    "name": "GitHub",
    "uri_check": "https://github.com/{account}",
    "e_code": 200,
    "e_string": "",
    "cat": "coding",
    "known": ["torvalds"],
}


def test_load_counts():
    assert load_email_defs([EMAIL_DEF]) == 1
    assert load_username_defs([USERNAME_DEF]) == 1
    assert len(registry.all_checkers()) == 2


def test_plugin_wins_over_def_regardless_of_order():
    load_email_defs([EMAIL_DEF])  # data def first
    registry.register(_checker("spotify", mode="email", kind="plugin"))
    chk = next(c for c in registry.all_checkers() if c.name == "spotify")
    assert chk.kind == "plugin"

    # And the reverse order: plugin already present, def must not clobber it.
    load_email_defs([EMAIL_DEF])
    chk = next(c for c in registry.all_checkers() if c.name == "spotify")
    assert chk.kind == "plugin"


def test_username_def_picks_up_control_from_known():
    load_username_defs([USERNAME_DEF])
    chk = next(c for c in registry.all_checkers() if c.name == "GitHub")
    assert chk.control == "torvalds"


def test_select_filters():
    registry.register(_checker("a", mode="email"))
    registry.register(_checker("b", mode="username"))
    registry.register(_checker("x", mode="username", nsfw=True, category="adult"))

    assert {c.name for c in select(mode="email")} == {"a"}
    assert {c.name for c in select(mode="username")} == {"b"}  # nsfw excluded by default
    assert {c.name for c in select(mode="username", nsfw=True)} == {"b", "x"}
    assert {c.name for c in select(mode="both", nsfw=True)} == {"a", "b", "x"}
    assert {c.name for c in select(only=["a"])} == {"a"}
    assert {c.name for c in select(categories=["adult"], nsfw=True)} == {"x"}
