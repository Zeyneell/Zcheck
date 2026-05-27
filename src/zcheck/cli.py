"""Zcheck CLI — typer-based, with subcommands and a Zloc-style interactive menu."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.table import Table

from . import __version__, sites
from .core import datafiles, registry, runner
from .core.console import console, render_banner, render_doctor, render_scan, section
from .core.models import ScanResult
from .export import csv_export, json_export

app = typer.Typer(
    name="zcheck",
    help="Async email→accounts OSINT — holehe-style, data-driven, self-checking.",
    no_args_is_help=False,
    add_completion=False,
)

_VALID_MODES = ("email", "username", "both")


def _ensure_loaded() -> None:
    sites.load()


def _valid_email(email: str) -> bool:
    """Syntax-only validation (no DNS) so we don't scan garbage input."""
    try:
        from email_validator import EmailNotValidError, validate_email

        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False
    except Exception:
        return "@" in email and "." in email.split("@")[-1]


def _csv(opt: Optional[str]) -> Optional[set[str]]:
    if not opt:
        return None
    return {p.strip() for p in opt.split(",") if p.strip()}


def _save(scan: ScanResult, json_out: Optional[Path], csv_out: Optional[Path]) -> None:
    if json_out:
        p = json_export.dump(scan, json_out)
        console.print(f"  [ok]+[/] JSON saved → [value]{p}[/]")
    if csv_out:
        p = csv_export.dump(scan, csv_out)
        console.print(f"  [ok]+[/] CSV  saved → [value]{p}[/]")


def _run_scan(
    email: str,
    *,
    mode: str,
    username: Optional[str],
    only: Optional[set[str]],
    cats: Optional[set[str]],
    nsfw: bool,
    concurrency: int,
    timeout: float,
    canary: bool,
    json_out: Optional[Path] = None,
    csv_out: Optional[Path] = None,
) -> None:
    _ensure_loaded()
    if not _valid_email(email):
        console.print(f"  [err]![/] '{email}' is not a valid email address.")
        return
    selected = registry.select(mode=mode, only=only, categories=cats, nsfw=nsfw)  # type: ignore[arg-type]
    total = len(selected)
    if total == 0:
        console.print("  [warn]No checkers match that selection.[/]")
        return

    with Progress(
        TextColumn("[muted]{task.description}[/]"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"probing {total} sites", total=total)

        def _tick(_r) -> None:
            progress.advance(task)

        scan = asyncio.run(
            runner.scan(
                email,
                mode=mode,  # type: ignore[arg-type]
                username=username,
                only=only,
                categories=cats,
                nsfw=nsfw,
                concurrency=concurrency,
                timeout=timeout,
                use_canary=canary,
                on_result=_tick,
            )
        )
    render_scan(scan)
    _save(scan, json_out, csv_out)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="Print version and exit."),
) -> None:
    if version:
        console.print(f"zcheck {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        interactive()


@app.command()
def scan(
    email: str = typer.Argument(..., help="Email address to investigate."),
    mode: str = typer.Option("both", "--mode", "-m", help="email | username | both."),
    username: Optional[str] = typer.Option(
        None, "--username", "-u", help="Override the username guessed from the email."
    ),
    only: Optional[str] = typer.Option(None, "--only", help="Comma-separated site names."),
    cats: Optional[str] = typer.Option(None, "--cat", "-c", help="Comma-separated categories."),
    nsfw: bool = typer.Option(False, "--nsfw", help="Include adult sites (off by default)."),
    concurrency: int = typer.Option(50, "--concurrency", help="Parallel requests."),
    timeout: float = typer.Option(10.0, "--timeout", help="Per-request timeout (s)."),
    no_canary: bool = typer.Option(False, "--no-canary", help="Disable false-positive validation."),
    json_out: Optional[Path] = typer.Option(None, "--json", help="Write JSON report."),
    csv_out: Optional[Path] = typer.Option(None, "--csv", help="Write CSV report."),
) -> None:
    """Find which sites an email is registered on."""
    if mode not in _VALID_MODES:
        raise typer.BadParameter(f"mode must be one of {_VALID_MODES}")
    render_banner()
    section(f"scan · {email}")
    _run_scan(
        email, mode=mode, username=username, only=_csv(only), cats=_csv(cats), nsfw=nsfw,
        concurrency=concurrency, timeout=timeout, canary=not no_canary,
        json_out=json_out, csv_out=csv_out,
    )


@app.command(name="sites")
def sites_cmd(
    mode: str = typer.Option("both", "--mode", "-m", help="email | username | both."),
    cats: Optional[str] = typer.Option(None, "--cat", "-c", help="Filter by categories."),
    nsfw: bool = typer.Option(False, "--nsfw", help="Include adult sites."),
) -> None:
    """List the sites Zcheck can check."""
    _ensure_loaded()
    selected = registry.select(mode=mode, categories=_csv(cats), nsfw=nsfw)  # type: ignore[arg-type]
    by_cat: dict[str, int] = {}
    email_n = username_n = 0
    for c in selected:
        by_cat[c.category] = by_cat.get(c.category, 0) + 1
        email_n += c.mode == "email"
        username_n += c.mode == "username"

    table = Table(title=f"[brand]{len(selected)}[/] sites · {email_n} email · {username_n} username",
                  title_justify="left", border_style="muted")
    table.add_column("Category", style="label")
    table.add_column("Sites", style="value", justify="right")
    for cat, n in sorted(by_cat.items(), key=lambda kv: (-kv[1], kv[0])):
        table.add_row(cat, str(n))
    console.print(table)


@app.command()
def doctor(
    mode: str = typer.Option("both", "--mode", "-m", help="email | username | both."),
    only: Optional[str] = typer.Option(None, "--only", help="Comma-separated site names."),
    cats: Optional[str] = typer.Option(None, "--cat", "-c", help="Comma-separated categories."),
    nsfw: bool = typer.Option(False, "--nsfw", help="Include adult sites."),
    concurrency: int = typer.Option(50, "--concurrency", help="Parallel requests."),
    json_out: Optional[Path] = typer.Option(None, "--json", help="Write a JSON health report."),
) -> None:
    """Self-test checkers against a known control + a canary to catch drift."""
    _ensure_loaded()
    render_banner()
    section("doctor · checker health")
    rows = asyncio.run(
        runner.doctor(
            mode=mode, only=_csv(only), categories=_csv(cats), nsfw=nsfw,  # type: ignore[arg-type]
            concurrency=concurrency,
        )
    )
    render_doctor(rows)
    degraded = [r for r in rows if r[2] == "degraded"]
    console.print(
        f"  [ok]{sum(r[2]=='healthy' for r in rows)} healthy[/]  ·  "
        f"[err]{len(degraded)} degraded[/]  ·  "
        f"[warn]{sum(r[2]=='inconclusive' for r in rows)} inconclusive[/]"
    )
    if json_out:
        import json

        payload = [
            {"site": c.site, "mode_category": c.category, "control": c.existence.value,
             "canary": k.existence.value, "verdict": v}
            for c, k, v in rows
        ]
        Path(json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"  [ok]+[/] health report → [value]{json_out}[/]")
    if degraded:
        raise typer.Exit(code=1)  # non-zero so CI fails on drift


@app.command()
def update(
    check: bool = typer.Option(False, "--check", help="Report availability without writing."),
) -> None:
    """Refresh the site datasets into the user cache."""
    render_banner()
    section("update · datasets")
    report = datafiles.update(check_only=check)
    for fname, status in report.items():
        style = "ok" if status.startswith(("updated", "available")) else "warn"
        console.print(f"  [{style}]{fname}[/]: {status}")
    sites.load(force=True)


def _hint(*lines: str) -> None:
    for line in lines:
        console.print(f"  [muted]{line}[/]")


def interactive() -> None:
    _ensure_loaded()
    render_banner()
    while True:
        console.print()
        console.print("[label][1][/] Scan email      [muted]— find accounts tied to an email (email + username sweep)[/]")
        console.print("[label][2][/] List sites      [muted]— what Zcheck can check, by category[/]")
        console.print("[label][3][/] Doctor          [muted]— self-test checkers, catch false positives / drift[/]")
        console.print("[label][4][/] Update          [muted]— refresh the site datasets[/]")
        console.print("[label][0][/] Exit")
        choice = Prompt.ask("\n[brand]select[/]", choices=["0", "1", "2", "3", "4"], default="0")

        try:
            if choice == "0":
                break

            elif choice == "1":
                console.print()
                _hint(
                    "Type the full email address. Example: someone@example.com",
                    "Full scan, no questions: email oracles + username sweep across 730+ sites,",
                    "adult sites included. (For finer control use the command line: zcheck scan ...)",
                )
                email = Prompt.ask("[label]email[/]")
                section(f"scan · {email}")
                _run_scan(
                    email, mode="both", username=None, only=None, cats=None, nsfw=True,
                    concurrency=50, timeout=10.0, canary=True,
                )

            elif choice == "2":
                sites_cmd(mode="both", cats=None, nsfw=True)

            elif choice == "3":
                console.print()
                _hint(
                    "Doctor probes each checker with a known control + a throwaway canary.",
                    "Full run hits every site twice — scope it with a category if you like.",
                )
                cat = Prompt.ask("[muted]category (empty = all)[/]", default="")
                section("doctor · checker health")
                rows = asyncio.run(runner.doctor(categories=_csv(cat) if cat else None))
                render_doctor(rows)

            elif choice == "4":
                section("update · datasets")
                report = datafiles.update()
                for fname, status in report.items():
                    style = "ok" if status.startswith("updated") else "warn"
                    console.print(f"  [{style}]{fname}[/]: {status}")
                sites.load(force=True)

        except KeyboardInterrupt:
            console.print("\n[warn]interrupted[/]")
            continue
        except Exception as exc:  # noqa: BLE001
            console.print(f"[err]error:[/] {exc}")

    console.print("[muted]bye.[/]")


if __name__ == "__main__":
    app()
