"""Populate the registry from every source: plugins + datasets.

``load()`` is idempotent and cheap to call; the CLI calls it once at startup.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys

from ..core import datafiles
from ..core.registry import load_email_defs, load_username_defs

_loaded = False


def _import_plugins() -> int:
    from . import plugins  # noqa: WPS433 (local import keeps import graph lazy)

    count = 0
    for mod in pkgutil.iter_modules(plugins.__path__, plugins.__name__ + "."):
        # Reload if already imported so the @email_site decorators re-run after a
        # registry.clear() (e.g. on `update` reload or in tests). A plain
        # import_module would return the cached module without re-registering.
        if mod.name in sys.modules:
            importlib.reload(sys.modules[mod.name])
        else:
            importlib.import_module(mod.name)
        count += 1
    return count


def load(*, force: bool = False) -> dict[str, int]:
    """Register all checkers. Returns counts per source."""
    global _loaded
    if _loaded and not force:
        return {}
    plugins = _import_plugins()
    email = load_email_defs(datafiles.load_email_sites())
    username = load_username_defs(datafiles.load_username_sites())
    _loaded = True
    return {"plugins": plugins, "email_defs": email, "username_defs": username}
