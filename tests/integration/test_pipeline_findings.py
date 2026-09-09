"""Invariants and confidence, end to end on a real PDF."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from make_samples import SAMPLES, draw

from invoice_extractor import extract, load_layout
from invoice_extractor.domain.findings import Severity

SAMPLES_DIR = Path("samples")
BUNDLED = ("acme", "nordic")

MUTATED_TOTALS = (
    (620, "Subtotal: 490.00"),
    (638, "VAT Rate: 20.00%"),
    (656, "VAT Amount: 98.00"),
    (674, "Total Due: 589.00"),
)


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_clean_samples_have_no_findings_and_full_confidence(layout_id: str) -> None:
    result = extract(SAMPLES_DIR / f"{layout_id}_invoice.pdf", load_layout(layout_id))
    assert result.findings == ()
    assert [field.confidence for field in result.fields.values()] == [1.0] * len(result.fields)


def test_mutated_total_yields_error_finding(tmp_path: Path) -> None:
    mutated = dataclasses.replace(SAMPLES["acme"], totals_lines=MUTATED_TOTALS)
    pdf_path = tmp_path / "acme_invoice.pdf"
    draw(mutated, pdf_path)

    result = extract(pdf_path, load_layout("acme"))

    errors = [finding for finding in result.findings if finding.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].code == "totals_reconcile"
    assert errors[0].field == "total_amount"
    assert result.fields["total_amount"].confidence < 1.0
    assert result.fields["subtotal"].confidence == 1.0
