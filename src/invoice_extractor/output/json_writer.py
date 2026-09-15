"""Stage 8: the machine-readable result, and the mirror of what it found.

`Decimal` leaves as a string and `date` as ISO-8601 because `to_dict` already made them
so — a JSON number would round-trip through IEEE-754 and undo ADR-0003.

`emit` writes two files where one would do, because they are read by different people.
`result.json` is everything; `<result>.findings.json` is what a reviewer queues on — the
findings and the checks, and nothing to scroll past to reach them (ENGINE_SPEC §2,
stage 8). Both are written from the one result, so they cannot disagree (ADR-0010).
"""

from __future__ import annotations

import json
from pathlib import Path

from invoice_extractor.domain.models import InvoiceResult

INDENT = 2
FINDINGS_SUFFIX = "findings.json"


def to_json(result: InvoiceResult) -> str:
    return json.dumps(result.to_dict(), indent=INDENT, ensure_ascii=False) + "\n"


def to_findings_json(result: InvoiceResult) -> str:
    """What the document said about itself, and what was asked of it, on their own."""
    mirror = {
        "source_path": result.source_path,
        "profile_id": result.profile_id,
        "valid": result.valid,
        "findings": [finding.to_dict() for finding in result.findings],
        "checks": [check.to_dict() for check in result.checks],
    }
    return json.dumps(mirror, indent=INDENT, ensure_ascii=False) + "\n"


def write_json(result: InvoiceResult, path: Path) -> None:
    path.write_text(to_json(result), encoding="utf-8")


def findings_path(path: Path) -> Path:
    """Where the mirror goes: beside the result, named after it."""
    return path.with_suffix(f".{FINDINGS_SUFFIX}")


def emit(result: InvoiceResult, path: Path) -> tuple[Path, Path]:
    """The result and its findings, written together and named after each other."""
    mirror = findings_path(path)
    write_json(result, path)
    mirror.write_text(to_findings_json(result), encoding="utf-8")
    return path, mirror
