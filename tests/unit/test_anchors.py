"""The four anchors, on pages built in memory.

Every rule `document/anchors.py` states is about drawing, so every test here draws: a
letterhead is a block with a gap under it, a table is rows that share their columns, and
a totals block is the narrow rows that follow one.
"""

from __future__ import annotations

from conftest import PAGE_HEIGHT, line
from invoice_extractor.document.anchors import anchors_of, table_runs
from invoice_extractor.document.model import Anchors, TextLine
from invoice_extractor.document.rows import rows_of

COLUMNS = (56.0, 200.0, 360.0, 470.0)
LEADING = 14.0


def table(top: float, rows: int, prefix: str = "row") -> list[TextLine]:
    """A header row and `rows - 1` rows under it, all at the same column positions."""
    drawn = []
    for index in range(rows):
        y = top + index * LEADING
        for column, x in enumerate(COLUMNS):
            drawn.append(line(f"{prefix}{index}c{column}", x, y))
    return drawn


def totals(top: float, count: int = 3) -> list[TextLine]:
    """Narrow rows: a label at one tab stop and an amount at another."""
    return [
        entry
        for index in range(count)
        for entry in (
            line("Subtotal", 360.0, top + index * LEADING),
            line(f"{index + 1}00.00", 470.0, top + index * LEADING),
        )
    ]


def test_a_table_is_a_run_of_rows_that_share_their_columns() -> None:
    (run,) = table_runs(rows_of(table(300.0, 4)))
    assert len(run) == 4


def test_two_tables_separated_by_something_else_are_two_runs() -> None:
    drawn = [*table(300.0, 3), line("Nettosumme 100,00", 56.0, 360.0), *table(400.0, 3, "vat")]
    assert len(table_runs(rows_of(drawn))) == 2


def test_a_single_row_is_not_a_table() -> None:
    assert table_runs(rows_of(table(300.0, 1))) == ()


def test_the_header_band_is_the_first_row_of_the_first_table() -> None:
    found = anchors_of(table(300.0, 4), PAGE_HEIGHT)
    assert found.table_header_band is not None
    top, bottom = found.table_header_band
    assert top < bottom <= 300.0 + LEADING


def test_a_page_with_no_table_has_no_header_band() -> None:
    assert anchors_of([line("Rechnung", 56.0, 60.0)], PAGE_HEIGHT).table_header_band is None


def test_the_totals_top_is_the_first_narrow_row_carrying_a_number_after_the_table() -> None:
    block = totals(420.0)
    found = anchors_of([*table(300.0, 4), *block], PAGE_HEIGHT)
    assert found.totals_top == min(entry.bbox.y0 for entry in block[:2])


def test_a_narrow_row_without_a_number_is_not_the_totals_block() -> None:
    wording = [line("Es gelten unsere Allgemeinen Geschäftsbedingungen.", 56.0, 420.0)]
    assert anchors_of([*table(300.0, 4), *wording], PAGE_HEIGHT).totals_top is None


def test_a_second_table_is_where_the_vat_summary_starts() -> None:
    drawn = [*table(300.0, 3), line("Nettosumme 100,00", 56.0, 360.0), *table(400.0, 3, "vat")]
    found = anchors_of(drawn, PAGE_HEIGHT)
    assert found.vat_summary_top is not None
    assert found.table_header_band is not None
    assert found.vat_summary_top > found.table_header_band[1]


def test_a_page_with_one_table_has_no_vat_summary() -> None:
    assert anchors_of(table(300.0, 4), PAGE_HEIGHT).vat_summary_top is None


def test_the_letterhead_ends_at_the_first_real_gap_near_the_top() -> None:
    drawn = [line("Nordlicht GmbH", 56.0, 60.0), line("Am Hafen 60", 56.0, 74.0)]
    drawn.append(line("RECHNUNG", 56.0, 200.0))
    found = anchors_of(drawn, PAGE_HEIGHT)
    assert found.logo_bottom == max(entry.bbox.y1 for entry in drawn[:2])


def test_a_page_whose_first_gap_is_too_far_down_has_no_letterhead() -> None:
    """A continuation page opens with a table, not with a vendor's name."""
    drawn = [line(f"row {index}", 56.0, 60.0 + index * LEADING) for index in range(30)]
    assert anchors_of(drawn, PAGE_HEIGHT).logo_bottom is None


def test_a_page_with_nothing_on_it_carries_no_anchors() -> None:
    assert anchors_of([], PAGE_HEIGHT) == Anchors(None, None, None, None)


def test_a_row_reads_back_as_its_cells_left_to_right() -> None:
    drawn = rows_of([line("Subtotal", 360.0, 420.0), line("100.00", 470.0, 420.0)])
    assert [row.text for row in drawn] == ["Subtotal 100.00"]
