"""What the totals block says: its amounts, its charges, and the total said again."""

from __future__ import annotations

from decimal import Decimal

from conftest import Entry, make_block_profile, make_component, make_document, make_profile
from invoice_extractor.domain.evidence import Strategy
from invoice_extractor.extraction.block import read_block, read_totals
from invoice_extractor.extraction.spec import BlockSpec
from invoice_extractor.profile.schema import ComponentKind, Profile

TOTALS = BlockSpec(name="totals", fields=("vat_rate", "subtotal", "vat_amount", "total_amount"))
COMPONENTS = {
    "subtotal": make_component(("Subtotal",)),
    "vat_rate": make_component(("VAT rate",), ComponentKind.RATE),
    "vat_amount": make_component(("Total VAT", "VAT")),
    "total_amount": make_component(("Total",)),
    "shipping": make_component(("Delivery",), ComponentKind.CHARGE, "SHIPPING"),
    "surcharge": make_component(("Surcharge",), ComponentKind.CHARGE, "SURCHARGE"),
}


def block(rows: list[tuple[str, ...]], top: float = 600.0) -> list[Entry]:
    """A totals block: a label at x=400, then one amount column every 100 points."""
    drawn: list[Entry] = []
    for index, row in enumerate(rows):
        height = top + index * 12.0
        label, *printed = row
        drawn.append((1, label, 400.0, height, 460.0, height + 10.0))
        for column, amount in enumerate(printed):
            left = 500.0 + column * 100.0
            drawn.append((1, amount, left, height, left + 50.0, height + 10.0))
    return drawn


def profile_with_block(**kwargs: object) -> Profile:
    return make_profile(totals=make_block_profile(COMPONENTS), **kwargs)  # type: ignore[arg-type]


def test_a_block_publishes_its_components_as_fields() -> None:
    document = make_document(block([("Subtotal", "100.00"), ("VAT", "20.00"), ("Total", "120.00")]))
    totals = read_totals(TOTALS, document, profile_with_block())
    read = {name: found.field.value for name, found in totals.extractions.items()}
    assert read == {
        "vat_rate": None,
        "subtotal": Decimal("100.00"),
        "vat_amount": Decimal("20.00"),
        "total_amount": Decimal("120.00"),
    }


def test_a_published_amount_points_at_the_row_it_was_read_from() -> None:
    document = make_document(block([("Subtotal", "100.00")]))
    found = read_totals(TOTALS, document, profile_with_block()).extractions["subtotal"]
    evidence = found.field.evidence
    assert evidence is not None
    assert evidence.strategy is Strategy.BLOCK_ROW
    assert evidence.matched_label == "Subtotal"
    assert evidence.raw_text == "100.00"
    assert found.zone is not None


def test_a_component_the_block_does_not_print_is_published_as_absent() -> None:
    document = make_document(block([("Subtotal", "100.00")]))
    found = read_totals(TOTALS, document, profile_with_block()).extractions["total_amount"]
    assert found.field.value is None
    assert not found.field.valid
    assert found.zone is None


def test_a_document_with_no_block_reads_nothing() -> None:
    document = make_document([(1, "Thank you", 50.0, 700.0, 100.0, 710.0)])
    assert read_block(document, profile_with_block()).components == {}


def test_a_rate_is_read_without_its_sign() -> None:
    document = make_document(block([("Subtotal", "100.00"), ("VAT rate", "20 %")]))
    read = read_block(document, profile_with_block())
    assert read.components["vat_rate"].value == Decimal("20")


def test_an_amount_set_under_its_label_is_the_number_at_the_labels_own_x() -> None:
    """A stacked block prints the label on one row and the amount under it, not beside."""
    document = make_document(
        [
            (1, "Subtotal", 400.0, 600.0, 460.0, 610.0),
            (1, "9 999.00", 250.0, 612.0, 300.0, 622.0),
            (1, "100.00", 400.0, 612.0, 450.0, 622.0),
        ]
    )
    read = read_block(document, profile_with_block())
    assert read.components["subtotal"].value == Decimal("100.00")


def test_a_label_with_nothing_under_it_reads_nothing() -> None:
    document = make_document(
        [
            (1, "Subtotal", 400.0, 600.0, 460.0, 610.0),
            (1, "Total", 400.0, 612.0, 460.0, 622.0),
        ]
    )
    assert read_block(document, profile_with_block()).components == {}


def test_a_label_on_the_last_row_with_no_amount_reads_nothing() -> None:
    document = make_document([(1, "Subtotal", 400.0, 600.0, 460.0, 610.0)])
    assert read_block(document, profile_with_block()).components == {}


def test_every_charge_row_is_a_charge_of_its_own() -> None:
    """A block may charge twice for the same thing, and each row is one of them."""
    document = make_document(
        block(
            [
                ("Subtotal", "100.00"),
                ("Delivery", "5.00"),
                ("Surcharge", "5.00"),
                ("Total", "110.00"),
            ]
        )
    )
    read = read_block(document, profile_with_block())
    assert [(charge.type, charge.amount) for charge in read.charges] == [
        ("SHIPPING", Decimal("5.00")),
        ("SURCHARGE", Decimal("5.00")),
    ]
    assert all(charge.declared for charge in read.charges)


def test_the_column_that_closes_the_identity_is_the_one_read() -> None:
    """Two columns of amounts, and the invoice is the one where the arithmetic works."""
    document = make_document(
        block(
            [
                ("Subtotal", "100.00", "83.00"),
                ("VAT", "20.00", "16.60"),
                ("Total", "500.00", "99.60"),
            ]
        )
    )
    read = read_block(document, profile_with_block())
    assert read.columns == 2
    assert read.components["total_amount"].value == Decimal("99.60")


def test_the_first_column_is_read_when_neither_closes() -> None:
    document = make_document(
        block([("Subtotal", "100.00", "83.00"), ("Total", "500.00", "400.00")])
    )
    read = read_block(document, profile_with_block())
    assert read.components["total_amount"].value == Decimal("500.00")


def test_a_block_with_no_net_closes_nothing() -> None:
    document = make_document(block([("VAT", "20.00"), ("Total", "120.00")]))
    read = read_block(document, profile_with_block())
    assert read.components["total_amount"].value == Decimal("120.00")


def test_the_total_said_again_in_another_currency_is_read_with_its_rate() -> None:
    """A row of the block that names no component of it, and says two numbers and a code."""
    document = make_document(
        [
            *block([("Subtotal", "100.00"), ("Total", "120.00")]),
            (1, "Equivalent EUR 140.40 at 1.1700", 400.0, 624.0, 520.0, 634.0),
        ]
    )
    read = read_block(document, profile_with_block(currencies=("GBP", "EUR")))
    assert read.secondary is not None
    assert read.secondary.currency == "EUR"
    assert read.secondary.total_amount == Decimal("140.40")
    assert read.secondary.exchange_rate == Decimal("1.1700")
    assert read.secondary.evidence is not None


def test_a_line_naming_another_currency_with_one_number_is_not_an_echo() -> None:
    document = make_document(
        [
            *block([("Subtotal", "100.00"), ("Total", "120.00")]),
            (1, "Paid in EUR 140.40", 400.0, 624.0, 520.0, 634.0),
        ]
    )
    read = read_block(document, profile_with_block(currencies=("GBP", "EUR")))
    assert read.secondary is None


def test_a_block_in_one_currency_echoes_nothing() -> None:
    document = make_document(
        [
            *block([("Subtotal", "100.00"), ("Total", "120.00")]),
            (1, "Payable within 30 days", 400.0, 624.0, 520.0, 634.0),
        ]
    )
    assert read_block(document, profile_with_block()).secondary is None


def test_a_block_set_flush_right_beside_a_summary_is_read_whole() -> None:
    """The labels end together and start apart, and the VAT summary on the left of the
    page shares their rows — the shape a vendor's ERP prints, and every row must be read."""
    document = make_document(
        [
            (1, "VAT Summary", 20.0, 588.0, 80.0, 598.0),
            (1, "EUR", 155.0, 600.0, 172.0, 610.0),
            (1, "EUR", 226.0, 600.0, 242.0, 610.0),
            (1, "Subtotal", 430.0, 600.0, 460.0, 610.0),
            (1, "1,201.96", 500.0, 600.0, 550.0, 610.0),
            (1, "VAT", 20.0, 612.0, 36.0, 622.0),
            (1, "Delivery", 432.0, 612.0, 460.0, 622.0),
            (1, "0.00", 500.0, 612.0, 550.0, 622.0),
            (1, "Type", 20.0, 624.0, 40.0, 634.0),
            (1, "VAT", 448.0, 624.0, 460.0, 634.0),
            (1, "240.39", 500.0, 624.0, 550.0, 634.0),
            (1, "SR", 20.0, 636.0, 32.0, 646.0),
            (1, "20", 92.0, 636.0, 102.0, 646.0),
            (1, "1,201.96", 141.0, 636.0, 172.0, 646.0),
            (1, "240.39", 218.0, 636.0, 242.0, 646.0),
            (1, "Total", 442.0, 636.0, 460.0, 646.0),
            (1, "1,442.35", 500.0, 636.0, 550.0, 646.0),
        ]
    )
    read = read_block(document, profile_with_block())
    assert {name: found.value for name, found in read.components.items()} == {
        "subtotal": Decimal("1201.96"),
        "shipping": Decimal("0.00"),
        "vat_amount": Decimal("240.39"),
        "total_amount": Decimal("1442.35"),
    }
    assert [(charge.type, charge.amount) for charge in read.charges] == [
        ("SHIPPING", Decimal("0.00"))
    ]


def test_a_row_whose_amount_is_not_a_number_reads_nothing() -> None:
    document = make_document(block([("Subtotal", "on account"), ("Total", "120.00")]))
    read = read_block(document, profile_with_block())
    assert "subtotal" not in read.components
