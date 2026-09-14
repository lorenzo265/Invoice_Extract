"""The result types and the JSON shape docs/SAMPLES_SPEC.md fixes for them."""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from invoice_extractor.document.model import BBox
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import (
    VALUE_TYPES,
    Evidence,
    FieldResult,
    InvoiceResult,
    LineItem,
    Strategy,
)

FIELD_ORDER = tuple(VALUE_TYPES)
BOX = BBox(400.0, 65.25, 543.39, 78.99)

VALUES: dict[str, Any] = {
    "invoice_number": "INV-2024-0042",
    "invoice_date": date(2024, 3, 15),
    "due_date": date(2024, 4, 14),
    "supplier_vat_id": "GB123456789",
    "customer_vat_id": "DE123456789",
    "currency": "GBP",
    "vat_rate": Decimal("20.00"),
    "subtotal": Decimal("490.00"),
    "vat_amount": Decimal("98.00"),
    "total_amount": Decimal("588.00"),
}


def found(name: str, value: Any, raw_text: str) -> FieldResult:
    return FieldResult(
        name=name,
        value=value,
        raw_text=raw_text,
        evidence=Evidence(1, BOX, name.replace("_", " ").title(), Strategy.LABEL_RIGHT, raw_text),
        valid=True,
        confidence=1.0,
        confidence_breakdown={"validator_passed": 1.0},
    )


def populated() -> InvoiceResult:
    return InvoiceResult(
        fields={name: found(name, value, f"{name}: {value}") for name, value in VALUES.items()},
        line_items=(
            LineItem(
                "ACM-1001",
                "Hex bolt M8 x 40, zinc",
                Decimal("500"),
                Decimal("0.12"),
                Decimal("60.00"),
            ),
        ),
        findings=(Finding(Severity.WARNING, "line_items_sum", "skipped", "subtotal"),),
        profile_id="acme",
        source_path="samples/acme_invoice.pdf",
    )


def serialized() -> dict[str, Any]:
    return populated().to_dict()


def test_invoice_result_round_trips_through_dict() -> None:
    result = populated()
    assert InvoiceResult.from_dict(result.to_dict()) == result


def test_to_dict_serializes_decimal_as_string_and_date_as_iso() -> None:
    fields = serialized()["fields"]
    assert fields["subtotal"]["value"] == "490.00"
    assert fields["invoice_date"]["value"] == "2024-03-15"


def test_to_dict_serializes_line_item_numbers_as_strings() -> None:
    item = serialized()["line_items"][0]
    assert item["quantity"] == "500"
    assert item["net_amount"] == "60.00"


def test_to_dict_names_the_strategy_and_spells_out_the_bbox() -> None:
    evidence = serialized()["fields"]["invoice_number"]["evidence"]
    assert evidence["strategy"] == "LABEL_RIGHT"
    assert evidence["bbox"] == {"x0": 400.0, "y0": 65.25, "x1": 543.39, "y1": 78.99}


def test_from_dict_restores_value_types_by_field_name() -> None:
    restored = InvoiceResult.from_dict(serialized())
    assert restored.fields["invoice_date"].value == date(2024, 3, 15)
    assert restored.fields["subtotal"].value == Decimal("490.00")
    assert restored.fields["invoice_number"].value == "INV-2024-0042"


def test_to_dict_keeps_field_order() -> None:
    assert tuple(serialized()["fields"]) == FIELD_ORDER


def test_missing_field_serializes_every_key_as_null() -> None:
    absent = FieldResult(name="due_date", value=None, raw_text=None, evidence=None, valid=False)
    result = dataclasses.replace(populated(), fields={"due_date": absent})
    entry = result.to_dict()["fields"]["due_date"]
    assert entry["value"] is None
    assert entry["raw_text"] is None
    assert entry["evidence"] is None
    assert entry["valid"] is False
    assert InvoiceResult.from_dict(result.to_dict()) == result


@pytest.mark.parametrize(
    ("instance", "attribute"),
    [
        (BOX, "x0"),
        (LineItem("s", "d", Decimal(1), Decimal(1), Decimal(1)), "part_number"),
        (FieldResult("n", None, None, None, valid=False), "value"),
        (Evidence(1, BOX, None, Strategy.LABEL_RIGHT, "raw"), "raw_text"),
        (InvoiceResult({}, (), (), "acme", "samples/acme_invoice.pdf"), "profile_id"),
    ],
)
def test_models_are_frozen(instance: object, attribute: str) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, attribute, "tampered")
