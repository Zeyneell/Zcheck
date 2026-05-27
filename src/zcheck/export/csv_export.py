"""Dump a ScanResult to CSV (one row per site)."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from ..core.models import ScanResult

_FIELDS = [
    "site", "domain", "category", "existence",
    "recovery_email", "recovery_phone", "elapsed_ms", "note", "error",
]


def dumps(scan: ScanResult) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for r in scan.results:
        row = r.model_dump()
        row["existence"] = r.existence.value
        writer.writerow(row)
    return buf.getvalue()


def dump(scan: ScanResult, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps(scan), encoding="utf-8", newline="")
    return p
