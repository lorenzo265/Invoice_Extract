"""The machine-readable result: `InvoiceResult.to_dict`, as JSON.

`Decimal` leaves as a string and `date` as ISO-8601 because `to_dict` already made them
so — a JSON number would round-trip through IEEE-754 and undo ADR-0003.
"""

from __future__ import annotations

import json
from pathlib import Path

from invoice_extractor.domain.models import InvoiceResult

INDENT = 2


def to_json(result: InvoiceResult) -> str:
    return json.dumps(result.to_dict(), indent=INDENT, ensure_ascii=False) + "\n"


def write_json(result: InvoiceResult, path: Path) -> None:
    path.write_text(to_json(result), encoding="utf-8")
