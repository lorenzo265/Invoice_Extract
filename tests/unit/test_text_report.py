"""The human-readable report, rendered from a result built in memory."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from invoice_extractor.document.model import BBox
from invoice_extractor.domain.checks import Check
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import (
    Charge,
    Evidence,
    FieldResult,
    InvoiceResult,
    LineItem,
    Party,
    SecondaryAmounts,
    Strategy,
    VatSummaryRow,
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
    LineItem(
        part_number="ACM-1001",
        description="Hex bolt",
        quantity=Decimal("500"),
        unit_price=Decimal("0.12"),
        net_amount=Decimal("60.00"),
    ),
    LineItem(
        part_number="ACM-2210",
        description="Bearing",
        quantity=Decimal("40"),
        unit_price=Decimal("3.85"),
        net_amount=Decimal("430.00"),
    ),
)


def field(name: str, value: object) -> FieldResult:
    if value is None:
        return FieldResult(name, None, None, None, valid=False)
    label = name.replace("_", " ").title()
    evidence = Evidence(1, BOX, label, Strategy.LABEL_RIGHT, f"{label}: {value}")
    return FieldResult(
        name,
        value,  # type: ignore[arg-type]  # VALUE_TYPES names the type each key holds
        f"{label}: {value}",
        evidence,
        valid=True,
        confidence=1.0,
    )


def result(findings: tuple[Finding, ...] = ()) -> InvoiceResult:
    return InvoiceResult(
        fields={name: field(name, VALUES.get(name)) for name in FIELD_ORDER},
        line_items=ITEMS,
        findings=findings,
        profile_id="acme",
        document_type="invoice",
        source_path="samples/acme_invoice.pdf",
    )


def report_lines(findings: tuple[Finding, ...] = (), checks: tuple[Check, ...] = ()) -> list[str]:
    return render(dataclasses.replace(result(findings), checks=checks)).splitlines()


def _held() -> Check:
    names = ("subtotal", "vat_amount", "total_amount")
    return Check("subtotal_plus_vat_equals_total", True, names, "490.00 + 98.00 = 588.00")


def line_starting(lines: list[str], prefix: str) -> str:
    return next(line for line in lines if line.startswith(prefix))


def test_a_check_that_held_is_marked_and_shows_what_it_came_to() -> None:
    lines = report_lines(checks=(_held(),))
    assert line_starting(lines, "[ok]  subtotal_plus_vat_equals_total").endswith(
        "490.00 + 98.00 = 588.00"
    )


def test_a_check_that_failed_is_marked_by_the_finding_that_says_so() -> None:
    failed = Check("subtotal_plus_vat_equals_total", False, ("total_amount",), "588.00 but 1.00")
    error = Finding(Severity.ERROR, failed.code, failed.detail, "total_amount")
    marked = line_starting(report_lines((error,), (failed,)), "[!!]  subtotal_plus_vat")
    assert marked.endswith("588.00 but 1.00")


def test_a_check_that_failed_as_a_warning_is_marked_as_one() -> None:
    failed = Check("document_type_matches_total_sign", False, ("total_amount",), "odd")
    warning = Finding(Severity.WARNING, failed.code, failed.detail, "total_amount")
    assert line_starting(report_lines((warning,), (failed,)), "[??]  document_type")


def test_a_check_that_failed_with_no_finding_beside_it_is_marked_as_an_error() -> None:
    failed = Check("dates_in_order", False, ("due_date",), "out of order")
    assert line_starting(report_lines(checks=(failed,)), "[!!]  dates_in_order")


def test_a_check_this_document_could_not_be_asked_is_marked_apart() -> None:
    skipped = Check("per_rate_vat_consistency", None, ("vat_summary",), "no summary")
    assert line_starting(report_lines(checks=(skipped,)), "[--]  per_rate_vat_consistency")


def test_a_document_no_rule_was_run_against_shows_no_checks() -> None:
    assert not [row for row in report_lines() if row.startswith("Checks")]


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


def test_report_names_the_parties_the_document_printed() -> None:
    parties = {
        "supplier": Party(name="Acme Ltd", lines=("1 Elm Close",), vat_id="GB123456789"),
        "ship_to": Party(name="Elsewhere Ltd", placeholder=True),
    }
    lines = render(dataclasses.replace(result(), parties=parties)).splitlines()
    block = lines[lines.index("Parties") + 1 :]
    assert block[0].endswith("Acme Ltd · 1 Elm Close · GB123456789")
    assert block[1].endswith("Elsewhere Ltd · (as billed)")


def test_report_lists_the_vat_summary_the_document_printed() -> None:
    summary = (
        VatSummaryRow(code="S", rate=Decimal(20), base=Decimal("490.00"), vat=Decimal("98.00")),
    )
    lines = render(dataclasses.replace(result(), vat_summary=summary)).splitlines()
    assert line_starting(lines, "VAT summary") == "VAT summary (1)"
    assert line_starting(lines, "S").split() == ["S", "20", "490.00", "98.00"]


def test_a_document_with_no_blocks_and_no_summary_prints_neither() -> None:
    printed = render(result())
    assert "Parties" not in printed
    assert "VAT summary" not in printed


CHARGES = (
    Charge(
        type="SHIPPING",
        amount=Decimal("12.50"),
        evidence=Evidence(1, BOX, "Delivery", Strategy.BLOCK_ROW, "12.50"),
    ),
    Charge(type="OTHER", amount=Decimal("5.00"), declared=False),
)
ECHO = SecondaryAmounts(
    currency="USD", total_amount=Decimal("658.56"), exchange_rate=Decimal("1.1200")
)


def test_a_report_prints_what_the_block_charged_and_where_each_charge_was_read() -> None:
    lines = render(dataclasses.replace(result(), charges=CHARGES)).splitlines()
    assert line_starting(lines, "Charges (2)")
    assert line_starting(lines, "SHIPPING").split() == [
        "SHIPPING",
        "12.50",
        "declared",
        "p1",
        "BLOCK_ROW",
        '"Delivery"',
    ]
    assert line_starting(lines, "OTHER").split() == ["OTHER", "5.00", "inferred", "-"]


def test_a_report_of_a_document_with_charges_prints_them_beside_its_checks() -> None:
    lines = render(dataclasses.replace(result(), charges=CHARGES, checks=(_held(),))).splitlines()
    assert line_starting(lines, "Charges (2)")
    assert line_starting(lines, "[ok]  subtotal_plus_vat_equals_total")


def test_a_report_prints_the_total_said_again_in_another_currency() -> None:
    lines = render(dataclasses.replace(result(), secondary_amounts=ECHO)).splitlines()
    assert line_starting(lines, "Second currency")
    assert line_starting(lines, "USD").split() == ["USD", "658.56", "at", "1.1200"]
