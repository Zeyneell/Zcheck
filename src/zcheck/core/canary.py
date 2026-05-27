"""Canary identifiers: the self-correcting layer.

For every scan we also probe a *guaranteed non-existent* email / username. If a
checker reports FOUND for that canary, its oracle is over-matching (the site
changed, added a captcha wall, or always answers "exists"). We then downgrade
the real result to UNKNOWN instead of reporting a false positive. This is what
keeps results trustworthy as sites drift, with no code change required.
"""

from __future__ import annotations

import secrets

from .models import Existence, SiteResult


def canary_email() -> str:
    """A syntactically valid address that should belong to nobody."""
    token = secrets.token_hex(12)
    return f"zcheck.canary.{token}@gmail.com"


def canary_username() -> str:
    return f"zcheck_canary_{secrets.token_hex(8)}"


def unreliable_checks(canary_results: list[SiteResult]) -> set[str]:
    """Names of checkers that 'found' the canary → cannot be trusted this run."""
    return {r.site for r in canary_results if r.existence is Existence.FOUND}


def apply_canary(results: list[SiteResult], unreliable: set[str]) -> None:
    """Downgrade real FOUND results from checkers the canary proved unreliable."""
    for r in results:
        if r.site in unreliable and r.existence is Existence.FOUND:
            r.existence = Existence.UNKNOWN
            r.note = "downgraded: checker also matched a non-existent canary identifier"
