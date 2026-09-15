"""What a printed row under a table's header is, and what it is not."""

from __future__ import annotations

from conftest import make_table_profile
from invoice_extractor.document.model import BBox, TextPart
from invoice_extractor.document.rows import CellRow
from invoice_extractor.extraction.units.columns import find_header, place
from invoice_extractor.extraction.units.rowkind import Bounds, Previous, RowKind, classify

HEIGHT = 10.0
PRINTED = ("part_number", "description", "quantity", "unit_price", "net_amount")
REQUIRED = ("description", "net_amount")


def cell(text: str, x0: float, x1: float, y: float) -> TextPart:
    return TextPart(text, BBox(x0, y, x1, y + HEIGHT))


def row(y: float, *cells: TextPart) -> CellRow:
    return CellRow(page=1, cells=cells)


def header() -> object:
    profile = make_table_profile(columns={column: (column,) for column in PRINTED})
    found = find_header(
        [
            row(
                100.0,
                cell("part_number", 50, 100, 100.0),
                cell("description", 150, 250, 100.0),
                cell("quantity", 380, 420, 100.0),
                cell("unit_price", 440, 480, 100.0),
                cell("net_amount", 500, 545, 100.0),
            )
        ],
        profile,
    )
    assert found is not None
    return found


def bounds(stop: tuple[str, ...] = (), carry: tuple[str, ...] = ()) -> Bounds:
    return Bounds(
        stop_labels=stop, carry_forward_labels=carry, sub_item_indent=8.0, required_columns=REQUIRED
    )


# What a row is read against when nothing has been read yet.
NOTHING_YET = Previous()


def kind(printed: CellRow, previous: Previous = NOTHING_YET, **rules: tuple[str, ...]) -> RowKind:
    found = header()
    return classify(printed, place(printed, found), found, bounds(**rules), previous)


def item_row(y: float = 120.0) -> CellRow:
    return row(
        y,
        cell("ACM-1", 50, 100, y),
        cell("A bolt", 150, 250, y),
        cell("2", 380, 420, y),
        cell("3.50", 440, 480, y),
        cell("7.00", 500, 545, y),
    )


def test_a_row_that_fills_the_columns_a_table_cannot_do_without_is_a_row() -> None:
    assert kind(item_row()) is RowKind.ROW


def test_a_description_close_under_a_row_is_the_rest_of_that_row() -> None:
    rest = row(131.0, cell("with a washer", 150, 250, 131.0))
    assert kind(rest, Previous(bottom=130.0, read=True)) is RowKind.CONTINUATION


def test_a_description_after_a_gap_is_a_block_of_its_own() -> None:
    """A section heading is set off from the row above it; a wrapped line is not."""
    heading = row(150.0, cell("Software licences", 150, 250, 150.0))
    assert kind(heading, Previous(bottom=130.0, read=True)) is RowKind.OTHER


def test_the_first_description_under_a_header_continues_nothing() -> None:
    loose = row(120.0, cell("a note", 150, 250, 120.0))
    assert kind(loose, Previous()) is RowKind.OTHER


def test_a_description_indented_past_the_profiles_measure_is_a_component() -> None:
    part = row(131.0, cell("On-site installation", 160, 250, 131.0))
    assert kind(part, Previous(bottom=130.0, read=True)) is RowKind.SUB_ITEM


def test_a_stop_label_outside_the_description_column_ends_the_table() -> None:
    totals = row(200.0, cell("Subtotal", 380, 430, 200.0), cell("7.00", 500, 545, 200.0))
    assert kind(totals, stop=("Subtotal",)) is RowKind.STOP


def test_a_stop_label_printed_clear_of_the_table_belongs_to_another_block() -> None:
    """A vendor that sets its VAT summary on the left and its totals on the right prints
    `Subtotal` beside a summary line and no part of the way across it. That word ends the
    totals block; the summary runs on, because the two share a band and share no column.
    """
    alongside = row(200.0, cell("Subtotal", 600, 680, 200.0), cell("7.00", 700, 745, 200.0))
    assert kind(alongside, stop=("Subtotal",)) is RowKind.OTHER


def test_a_stop_label_inside_the_description_column_is_a_section_subtotal() -> None:
    """A table runs past its own sections' totals; only the totals block ends it."""
    section = row(200.0, cell("Subtotal Licences", 150, 250, 200.0), cell("7.00", 500, 545, 200.0))
    assert kind(section, stop=("Subtotal",)) is RowKind.SUBTOTAL


def test_a_carry_forward_label_is_what_a_page_break_carried() -> None:
    carried = row(200.0, cell("Carried forward", 150, 260, 200.0), cell("7.00", 500, 545, 200.0))
    assert kind(carried, carry=("Carried forward",), stop=("Subtotal",)) is RowKind.CARRY


def test_a_carry_forward_label_that_starts_with_a_stop_word_is_still_a_carry() -> None:
    """`Subtotal carried forward` says both; what it is is the more particular of the two."""
    carried = row(200.0, cell("Subtotal carried forward", 150, 280, 200.0))
    assert kind(carried, carry=("Subtotal carried forward",), stop=("Subtotal",)) is RowKind.CARRY
