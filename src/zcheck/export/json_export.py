"""Dump a ScanResult to JSON."""

from __future__ import annotations

from pathlib import Path

from ..core.models import ScanResult


def dumps(scan: ScanResult) -> str:
    return scan.model_dump_json(indent=2)


def dump(scan: ScanResult, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps(scan), encoding="utf-8")
    return p
