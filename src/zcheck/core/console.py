"""Rich rendering for the CLI — same visual language as the Zloc toolkit."""

from __future__ import annotations

import sys

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from .models import Existence, ScanResult, SiteResult

# Windows defaults to cp1252 — switch stdio to UTF-8 so the banner/box glyphs
# render without crashing Rich (same guard Zloc uses).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

ZCHECK_THEME = Theme(
    {
        "brand": "bold magenta",
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
        "muted": "grey50",
        "label": "bold cyan",
        "value": "white",
        "kbd": "bold on grey15",
    }
)

console = Console(theme=ZCHECK_THEME, highlight=False)
err_console = Console(theme=ZCHECK_THEME, stderr=True, highlight=False)

ASCII = r"""
   ____      _               _
  |_  /__ __| |_  ___ __ __ | |__
   / / _/ _| ' \/ -_) _| / /| / /
  /___\__\__|_||_\___\__|_\_\|_\_\   OSINT
"""


def render_banner() -> None:
    from .. import __version__

    text = Text(ASCII, style="brand")
    sub = Text.assemble(
        ("Zcheck ", "brand"),
        (f"v{__version__}", "muted"),
        ("  ·  ", "muted"),
        ("email → accounts, holehe-style", "label"),
    )
    console.print(
        Panel(
            Align.center(Text.assemble(text, "\n", sub)),
            border_style="brand",
            padding=(0, 2),
        )
    )


def section(title: str) -> None:
    console.rule(f"[brand]{title}[/]", style="muted")


def found_table(scan: ScanResult) -> Table:
    title = Text.assemble(
        ("ACCOUNTS", "brand"),
        (" · ", "muted"),
        (scan.email, "value"),
        ("  ", ""),
        (f"{len(scan.found)} found", "ok"),
    )
    table = Table(title=title, title_justify="left", border_style="muted")
    table.add_column("Site", style="label", no_wrap=True)
    table.add_column("Category", style="muted")
    table.add_column("Domain / profile", style="value", overflow="fold")
    table.add_column("Leaked recovery", style="warn")
    for r in scan.found:
        target = r.extra.get("profile_url") or r.domain
        recovery = " ".join(x for x in (r.recovery_email, r.recovery_phone) if x)
        table.add_row(r.site, r.category, str(target), recovery)
    return table


def _count_line(scan: ScanResult) -> Text:
    c = scan.counts()
    t = Text("  ")
    t.append(f"{c[Existence.FOUND.value]} found", style="ok")
    t.append(f"  ·  {c[Existence.NOT_FOUND.value]} not found", style="muted")
    t.append(f"  ·  {c[Existence.UNKNOWN.value]} unknown", style="warn")
    t.append(f"  ·  {c[Existence.RATE_LIMITED.value]} rate-limited", style="brand")
    t.append(f"  ·  {c[Existence.ERROR.value]} errors", style="err")
    if scan.elapsed_ms is not None:
        t.append(f"   ({scan.elapsed_ms} ms)", style="muted")
    return t


def render_scan(scan: ScanResult) -> None:
    if scan.found:
        console.print(found_table(scan))
    else:
        console.print(
            Panel("No accounts confirmed.", style="warn", title=scan.email, border_style="muted")
        )
    downgraded = [r for r in scan.results if r.note and "downgraded" in r.note]
    if downgraded:
        console.print(
            f"  [muted]canary suppressed {len(downgraded)} likely false positive(s).[/]"
        )
    console.print(_count_line(scan))


def render_doctor(rows: list[tuple[SiteResult, SiteResult, str]]) -> None:
    """rows: (control_result, canary_result, verdict)."""
    table = Table(title="[brand]zcheck doctor[/] · checker health", title_justify="left",
                  border_style="muted")
    table.add_column("Site", style="label")
    table.add_column("Category", style="muted")
    table.add_column("Control", style="value")
    table.add_column("Canary", style="value")
    table.add_column("Verdict")
    style = {"healthy": "ok", "degraded": "err", "inconclusive": "warn"}
    for control, canary, verdict in rows:
        table.add_row(
            control.site,
            control.category,
            control.existence.value,
            canary.existence.value,
            Text(verdict, style=style.get(verdict, "value")),
        )
    console.print(table)
