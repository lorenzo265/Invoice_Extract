"""The rows of the two tables and the party blocks, and the JSON they round-trip through."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from invoice_extractor.document.model import BBox
from invoice_extractor.domain.evidence import Evidence, Strategy
from invoice_extractor.domain.parties import Party
from invoice_extractor.domain.rows import LineItem, SubItem, VatSummaryRow

BOX = BBox(150.0, 327.86, 354.02, 337.9)


def evidence(text: str = "A bolt") -> Evidence:
    return Evidence(1, BOX, None, Strategy.TABLE_CELL, text)


def item() -> LineItem:
    return LineItem(
        pos=1,
        part_number="ACM-1001",
        description="Hex bolt M8 x 40, zinc",
        quantity=Decimal("500"),
        unit="ea",
        unit_price=Decimal("0.12"),
        discount_pct=Decimal("5"),
        vat_rate=Decimal("20"),
        net_amount=Decimal("60.00"),
        sub_items=(SubItem("Fitting kit", Decimal(1), Decimal("2.50")),),
        cells={"description": evidence()},
    )


def test_a_row_round_trips_through_its_own_dict() -> None:
    assert LineItem.from_dict(item().to_dict()) == item()


def test_a_rows_numbers_are_written_as_their_own_digits() -> None:
    written = item().to_dict()
    assert written["quantity"] == "500"
    assert written["unit_price"] == "0.12"
    assert written["pos"] == 1


def test_a_column_the_vendor_does_not_print_is_null_and_comes_back_null() -> None:
    bare = LineItem(description="A bolt", net_amount=Decimal("7.00"))
    written = bare.to_dict()
    assert written["part_number"] is None
    assert written["quantity"] is None
    assert LineItem.from_dict(written) == bare


def test_a_rows_cells_carry_the_box_each_value_was_read_from() -> None:
    restored = LineItem.from_dict(item().to_dict())
    assert restored.cells["description"].bbox == BOX
    assert restored.cells["description"].strategy is Strategy.TABLE_CELL


def test_a_component_round_trips_with_the_prices_it_carries() -> None:
    sub = SubItem("Fitting kit", Decimal(1), Decimal("2.50"))
    assert SubItem.from_dict(sub.to_dict()) == sub
    assert SubItem.from_dict(SubItem("Bare").to_dict()) == SubItem("Bare")


def test_a_vat_line_round_trips_through_its_own_dict() -> None:
    row = VatSummaryRow(
        code="S",
        rate=Decimal("20"),
        base=Decimal("19.25"),
        vat=Decimal("3.85"),
        cells={"vat": evidence("3.85")},
    )
    assert VatSummaryRow.from_dict(row.to_dict()) == row


def test_a_party_round_trips_through_its_own_dict() -> None:
    party = Party(
        name="Acme Systems Ltd",
        lines=("1 Elm Close", "Leeds"),
        vat_id="GB123456789",
        evidence=(evidence("Acme Systems Ltd"),),
    )
    assert Party.from_dict(party.to_dict()) == party


def test_a_party_that_defers_says_so_and_names_no_address() -> None:
    deferred = Party(name="Acme Systems Ltd", placeholder=True)
    written = deferred.to_dict()
    assert written["placeholder"] is True
    assert written["lines"] == []
    assert Party.from_dict(written) == deferred


@pytest.mark.parametrize(
    ("instance", "attribute"),
    [
        (item(), "description"),
        (SubItem("Fitting kit"), "description"),
        (VatSummaryRow(code="S"), "code"),
        (Party(name="Acme"), "name"),
    ],
)
def test_the_records_are_frozen(instance: object, attribute: str) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, attribute, "tampered")
