"""A `Finding` is a value: comparable, frozen, and it survives a JSON round trip."""

from __future__ import annotations

import dataclasses

import pytest

from invoice_extractor.domain.findings import Finding, Severity


def test_finding_round_trips_through_dict() -> None:
    finding = Finding(
        severity=Severity.ERROR,
        code="totals_reconcile",
        message="490.00 + 98.00 = 588.00 but total_amount is 589.00",
        field="total_amount",
    )
    assert Finding.from_dict(finding.to_dict()) == finding


def test_finding_without_a_field_round_trips_as_null() -> None:
    finding = Finding(Severity.WARNING, "line_items_header_not_found", "no header row found")
    assert finding.to_dict()["field"] is None
    assert Finding.from_dict(finding.to_dict()) == finding


def test_to_dict_names_the_severity() -> None:
    assert Finding(Severity.INFO, "code", "message").to_dict()["severity"] == "INFO"


def test_finding_is_frozen() -> None:
    finding = Finding(Severity.INFO, "code", "message")
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.code = "other"  # type: ignore[misc]  # the point of the test is that this fails
