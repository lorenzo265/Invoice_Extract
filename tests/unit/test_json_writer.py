"""The machine-readable output, and the round trip it promises."""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal
from pathlib import Path

from invoice_extractor.document.model import BBox
from invoice_extractor.domain.checks import Check
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import (
    Evidence,
    FieldResult,
    InvoiceResult,
    LineItem,
    Strategy,
)
from invoice_extractor.output.json_writer import (
    emit,
    findings_path,
    to_findings_json,
    to_json,
    write_json,
)


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
                part_number="FJ-771",
                description="Kabelkanal 40x60, 2 m",
                quantity=Decimal("30"),
                unit_price=Decimal("89.00"),
                net_amount=Decimal("2670.00"),
            ),
        ),
        findings=(Finding(Severity.WARNING, "line_items_sum", "skipped", "subtotal"),),
        profile_id="nordic",
        document_type="invoice",
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


def checked() -> InvoiceResult:
    """The same result, with something to say about itself and a record of what was asked."""
    return dataclasses.replace(
        result(),
        findings=(Finding(Severity.WARNING, "dates_in_order", "due before invoice", "due_date"),),
        checks=(Check("dates_in_order", False, ("due_date",), "due before invoice"),),
    )


def test_the_findings_mirror_carries_what_was_found_and_what_was_asked() -> None:
    mirror = json.loads(to_findings_json(checked()))
    assert mirror["findings"] == [finding.to_dict() for finding in checked().findings]
    assert mirror["checks"] == [check.to_dict() for check in checked().checks]
    assert mirror["valid"] is True, "a warning is not what makes a document invalid"
    assert mirror["source_path"] == checked().source_path
    assert mirror["profile_id"] == checked().profile_id


def test_the_mirror_is_named_after_the_result_it_mirrors(tmp_path: Path) -> None:
    assert findings_path(tmp_path / "acme.json").name == "acme.findings.json"


def test_emit_writes_the_result_and_its_findings_together(tmp_path: Path) -> None:
    written, mirror = emit(checked(), tmp_path / "acme.json")
    assert written.read_text(encoding="utf-8") == to_json(checked())
    assert mirror.read_text(encoding="utf-8") == to_findings_json(checked())
    assert {path.name for path in tmp_path.iterdir()} == {"acme.json", "acme.findings.json"}
