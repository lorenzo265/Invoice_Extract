"""The human-readable report, rendered from a result built in memory."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from invoice_extractor.document.model import BBox
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import (
    Evidence,
    FieldResult,
    InvoiceResult,
    LineItem,
    Strategy,
)
from invoice_extractor.extraction.specs import FIELD_ORDER
from invoice_extractor.output.text_report import render

BOX = BBox(400.0, 609.25, 472.83, 622.99)
VALUES: dict[str, object] = {
    "invoice_number": "INV-2024-0042",
    "invoice_date": None,
    "due_date": None,
    "supplier_vat_id": "GB123456789",
    "customer_vat_id": "DE123456789",
    "currency": "GBP",
    "vat_rate": Decimal("20.00"),
    "subtotal": Decimal("490.00"),
    "vat_amount": Decimal("98.00"),
    "total_amount": Decimal("588.00"),
}
ITEMS = (
    LineItem("ACM-1001", "Hex bolt", Decimal("500"), Decimal("0.12"), Decimal("60.00")),
    LineItem("ACM-2210", "Bearing", Decimal("40"), Decimal("3.85"), Decimal("430.00")),
)


def field(name: str, value: object) -> FieldResult:
    if value is None:
        return FieldResult(name, None, None, None, valid=False)
    label = name.replace("_", " ").title()
    evidence = Evidence(1, BOX, label, Strategy.LABEL_RIGHT, f"{label}: {value}")
    return FieldResult(name, value, f"{label}: {value}", evidence, valid=True, confidence=1.0)  # type: ignore[arg-type]  # VALUE_TYPES names the type each key holds


def result(findings: tuple[Finding, ...] = ()) -> InvoiceResult:
    return InvoiceResult(
        fields={name: field(name, VALUES.get(name)) for name in FIELD_ORDER},
        line_items=ITEMS,
        findings=findings,
        profile_id="acme",
        document_type="invoice",
        source_path="samples/acme_invoice.pdf",
    )


def report_lines(findings: tuple[Finding, ...] = ()) -> list[str]:
    return render(result(findings)).splitlines()


def line_starting(lines: list[str], prefix: str) -> str:
    return next(line for line in lines if line.startswith(prefix))


def test_report_marks_ok_when_no_finding() -> None:
    marked = line_starting(report_lines(), "[ok]  totals_reconcile")
    assert marked.endswith("490.00 + 98.00 = 588.00")


def test_report_renders_the_arithmetic_of_every_invariant_that_held() -> None:
    lines = report_lines()
    assert line_starting(lines, "[ok]  line_items_sum").endswith("60.00 + 430.00 = 490.00")
    assert line_starting(lines, "[ok]  vat_rate_consistent").endswith("20.00% x 490.00 = 98.00")


def test_report_marks_error_finding() -> None:
    error = Finding(
        Severity.ERROR, "totals_reconcile", "490.00 + 98.00 = 588.00 but x", "total_amount"
    )
    marked = line_starting(report_lines((error,)), "[!!]  totals_reconcile")
    assert marked.endswith("490.00 + 98.00 = 588.00 but x")


def test_report_marks_warning_finding() -> None:
    warning = Finding(
        Severity.WARNING, "line_items_sum", "line_items_sum skipped: subtotal not found"
    )
    assert line_starting(report_lines((warning,)), "[??]  line_items_sum")


def test_report_shows_dash_for_missing_field() -> None:
    row = line_starting(report_lines(), "due_date")
    assert row.split() == ["due_date", "-", "0.00", "-"]


def test_report_counts_findings_by_severity() -> None:
    findings = (
        Finding(Severity.ERROR, "totals_reconcile", "no"),
        Finding(Severity.WARNING, "line_items_sum", "skipped"),
        Finding(Severity.INFO, "note", "noted"),
    )
    assert line_starting(report_lines(findings), "1 error") == "1 error, 1 warning, 1 info findings"


def test_report_opens_and_closes_with_a_rule() -> None:
    lines = report_lines()
    assert lines[0] == "Invoice Extraction Report"
    assert lines[1] == "=" * 80
    assert lines[-1] == "=" * 80


def test_report_names_its_source_and_profile() -> None:
    lines = report_lines()
    assert lines[2] == "source   samples/acme_invoice.pdf"
    assert lines[3] == "profile  acme"
    assert lines[4] == "kind     invoice"


def test_report_shows_a_dash_for_the_kind_of_a_document_no_profile_matched() -> None:
    unread = dataclasses.replace(result(), profile_id=None, document_type=None)
    assert render(unread).splitlines()[4] == "kind     -"


def test_report_counts_the_line_items_it_lists() -> None:
    assert line_starting(report_lines(), "Line items") == "Line items (2)"


def test_report_shows_a_dash_when_a_candidate_matched_no_label() -> None:
    anchored = dataclasses.replace(
        field("currency", "GBP"),
        evidence=Evidence(1, BOX, None, Strategy.LABEL_PATTERN, "GBP"),
    )
    scoped = dataclasses.replace(result(), fields={"currency": anchored})
    row = line_starting(render(scoped).splitlines(), "currency")
    assert row.endswith("p1  LABEL_PATTERN  -")
