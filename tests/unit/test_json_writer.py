"""The machine-readable output, and the round trip it promises."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from invoice_extractor.document.model import BBox
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import (
    Evidence,
    FieldResult,
    InvoiceResult,
    LineItem,
    Strategy,
)
from invoice_extractor.output.json_writer import to_json, write_json


def result() -> InvoiceResult:
    evidence = Evidence(
        1, BBox(400.0, 609.25, 472.83, 622.99), "Subtotal", Strategy.LABEL_RIGHT, "Subtotal: 490.00"
    )
    subtotal = FieldResult(
        name="subtotal",
        value=Decimal("490.00"),
        raw_text="Subtotal: 490.00",
        evidence=evidence,
        valid=True,
        confidence=1.0,
        confidence_breakdown={"validator_passed": 0.3},
    )
    absent = FieldResult("due_date", None, None, None, valid=False)
    return InvoiceResult(
        fields={"subtotal": subtotal, "due_date": absent},
        line_items=(
            LineItem(
                "FJ-771",
                "Kabelkanal 40x60, 2 m",
                Decimal("30"),
                Decimal("89.00"),
                Decimal("2670.00"),
            ),
        ),
        findings=(Finding(Severity.WARNING, "line_items_sum", "skipped", "subtotal"),),
        profile_id="nordic",
        source_path="samples/nordic_invoice.pdf",
    )


def test_to_json_ends_with_newline_and_is_stable() -> None:
    rendered = to_json(result())
    assert rendered.endswith("\n")
    assert rendered == to_json(result())


def test_json_round_trips_through_from_dict() -> None:
    original = result()
    assert InvoiceResult.from_dict(json.loads(to_json(original))) == original


def test_to_json_keeps_decimals_as_strings() -> None:
    data = json.loads(to_json(result()))
    assert data["fields"]["subtotal"]["value"] == "490.00"
    assert data["line_items"][0]["net_amount"] == "2670.00"


def test_to_json_keeps_non_ascii_unescaped() -> None:
    assert "Kabelkanal 40x60, 2 m" in to_json(result())


def test_write_json_writes_exactly_what_to_json_returns(tmp_path: Path) -> None:
    path = tmp_path / "out.json"
    write_json(result(), path)
    assert path.read_text(encoding="utf-8") == to_json(result())
