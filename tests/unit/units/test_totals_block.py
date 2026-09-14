"""Where the totals block is, and which of its rows names what."""

from __future__ import annotations

from conftest import Entry, make_block_profile, make_component, make_document, make_profile
from invoice_extractor.document.rows import cell_rows_of
from invoice_extractor.extraction.units.totals_block import (
    amounts,
    at,
    component_of,
    find_block,
)
from invoice_extractor.profile.schema import ComponentKind

COMPONENTS = {
    "subtotal": make_component(("Subtotal",)),
    "vat_amount": make_component(("Total VAT", "VAT")),
    "total_amount": make_component(("Total",)),
    "shipping": make_component(("Delivery",), ComponentKind.CHARGE, "SHIPPING"),
}


def block(rows: list[tuple[str, str, float]], page: int = 1) -> list[Entry]:
    """A totals block: a label at x=400 and its amount at x=500, one row per entry."""
    drawn: list[Entry] = []
    for label, amount, top in rows:
        drawn.append((page, label, 400.0, top, 460.0, top + 10.0))
        if amount:
            drawn.append((page, amount, 500.0, top, 550.0, top + 10.0))
    return drawn


def profile_with_block() -> object:
    return make_profile(totals=make_block_profile(COMPONENTS))


def test_the_block_is_the_run_of_rows_that_names_the_most_components() -> None:
    """A table heading says `VAT` too, and loses to the block that names three."""
    document = make_document(
        [
            (1, "VAT", 50.0, 300.0, 80.0, 310.0),
            *block([("Subtotal", "100.00", 600.0), ("VAT", "20.00", 612.0)]),
            *block([("Total", "120.00", 624.0)]),
        ]
    )
    found = find_block(document, profile_with_block())
    assert [row.cells[0].text for row in found.rows] == ["Subtotal", "VAT", "Total"]
    assert found.edge == 400.0


def test_a_document_with_no_component_row_has_no_block() -> None:
    document = make_document([(1, "Thank you for your custom", 50.0, 700.0, 200.0, 710.0)])
    found = find_block(document, profile_with_block())
    assert found.rows == ()
    assert found.edge == 0.0


def test_the_longest_label_a_row_starts_with_names_it() -> None:
    """`Total VAT` is the tax, however much of `Total` it begins with."""
    rows = cell_rows_of(make_document(block([("Total VAT", "20.00", 600.0)])).pages[0].lines)
    named = component_of(rows[0], COMPONENTS)
    assert named is not None
    assert named.name == "vat_amount"


def test_a_row_names_nothing_when_no_label_starts_it() -> None:
    rows = cell_rows_of(make_document(block([("Amount due", "20.00", 600.0)])).pages[0].lines)
    assert component_of(rows[0], COMPONENTS) is None


def test_only_the_cell_in_the_blocks_own_column_names_a_row() -> None:
    """The VAT summary beside the block says `VAT` at the same height as the block's net."""
    document = make_document(
        [
            (1, "VAT", 50.0, 600.0, 80.0, 610.0),
            *block([("Subtotal", "100.00", 600.0)]),
        ]
    )
    rows = cell_rows_of(document.pages[0].lines)
    named = component_of(rows[0], COMPONENTS, edge=400.0)
    assert named is not None
    assert named.name == "subtotal"


def test_a_row_far_below_the_block_is_not_part_of_it() -> None:
    """`cluster_gap` is what ends a block: what is drawn much lower is another block."""
    document = make_document(
        [
            *block([("Subtotal", "100.00", 300.0), ("VAT", "20.00", 312.0)]),
            *block([("Total", "120.00", 700.0)]),
        ]
    )
    found = find_block(document, profile_with_block())
    assert [row.cells[0].text for row in found.rows] == ["Subtotal", "VAT"]


def test_the_lower_of_two_blocks_naming_as_much_wins() -> None:
    """A page that says the same words twice is adding up in the one further down."""
    rows = [("Subtotal", "100.00", 300.0), ("Total", "120.00", 312.0)]
    lower = [("Subtotal", "100.00", 600.0), ("Total", "120.00", 612.0)]
    document = make_document([*block(rows), *block(lower)])
    found = find_block(document, profile_with_block())
    assert [row.top for row in found.rows] == [600.0, 612.0]


def test_amounts_are_what_is_printed_beside_the_label() -> None:
    rows = cell_rows_of(make_document(block([("Subtotal", "100.00", 600.0)])).pages[0].lines)
    named = component_of(rows[0], COMPONENTS)
    assert named is not None
    assert [cell.text for cell in amounts(rows[0], named)] == ["100.00"]


def test_a_cell_is_at_an_edge_within_the_column_tolerance() -> None:
    rows = cell_rows_of(make_document(block([("Subtotal", "", 600.0)])).pages[0].lines)
    cell = rows[0].cells[0]
    assert at(cell, 400.0)
    assert at(cell, 401.5)
    assert not at(cell, 420.0)
