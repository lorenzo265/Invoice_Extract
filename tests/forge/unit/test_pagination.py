"""Where the pages break, worked out from measured heights before anything is drawn."""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise

import pytest

from invoice_forge.model import LineItem
from invoice_forge.render.pagination import PageBudget, PlannedPage, plan_pages
from invoice_forge.render.table import CARRY_HEIGHT, MeasuredRow

ROW_HEIGHT = 20.0
TOTALS_HEIGHT = 100.0
# Room for exactly ten rows on the first page and twenty on the ones after it.
BUDGET = PageBudget(
    first_top=100.0,
    later_top=50.0,
    bottom=700.0,
    header_height=0.0,
    totals_height=TOTALS_HEIGHT,
    carry_forward=True,
)


def row(pos: int, height: float = ROW_HEIGHT) -> MeasuredRow:
    item = LineItem(
        pos=pos,
        sku=f"SKU-{pos}",
        description="A thing",
        quantity=Decimal("1"),
        unit="ea",
        unit_price=Decimal("10.00"),
        vat_rate=Decimal("19"),
    )
    return MeasuredRow(item=item, lines=("A thing",), parts=(), height=height)


def rows(count: int, height: float = ROW_HEIGHT) -> tuple[MeasuredRow, ...]:
    return tuple(row(pos, height) for pos in range(1, count + 1))


def placed(pages: tuple[PlannedPage, ...]) -> list[int]:
    return [item.item.pos for page in pages for item in page.rows]


def test_a_document_that_fits_is_one_page() -> None:
    pages = plan_pages(rows(5), BUDGET)
    assert len(pages) == 1
    assert pages[0].carried_in is None
    assert pages[0].carried_out is None


def test_every_row_is_placed_exactly_once_however_many_pages_it_takes() -> None:
    for count in (1, 12, 25, 40, 100):
        pages = plan_pages(rows(count), BUDGET)
        assert placed(pages) == list(range(1, count + 1)), count


def test_pages_are_numbered_from_one_without_a_gap() -> None:
    pages = plan_pages(rows(60), BUDGET)
    assert [page.number for page in pages] == list(range(1, len(pages) + 1))


def test_the_last_page_keeps_room_for_the_totals() -> None:
    pages = plan_pages(rows(40), BUDGET)
    last = pages[-1]
    used = sum(item.height for item in last.rows)
    room = BUDGET.bottom - BUDGET.later_top - CARRY_HEIGHT
    assert used + TOTALS_HEIGHT <= room


def test_a_break_carries_the_subtotal_out_and_the_same_amount_back_in() -> None:
    pages = plan_pages(rows(60), BUDGET)
    assert len(pages) > 1
    for leaving, arriving in pairwise(pages):
        assert leaving.carried_out == arriving.carried_in


def test_what_is_carried_is_what_the_pages_before_it_add_up_to() -> None:
    pages = plan_pages(rows(60), BUDGET)
    running = Decimal(0)
    for page in pages:
        running += sum((item.item.net_amount for item in page.rows), Decimal(0))
        if page.carried_out is not None:
            assert page.carried_out == running


def test_only_the_last_page_carries_nothing_out() -> None:
    pages = plan_pages(rows(60), BUDGET)
    assert [page.carried_out is None for page in pages] == [False] * (len(pages) - 1) + [True]


def test_the_first_page_carries_nothing_in() -> None:
    assert plan_pages(rows(60), BUDGET)[0].carried_in is None


def test_a_family_without_carry_forward_carries_nothing() -> None:
    budget = PageBudget(**{**vars_of(BUDGET), "carry_forward": False})
    pages = plan_pages(rows(60), budget)
    assert len(pages) > 1
    assert all(page.carried_in is None and page.carried_out is None for page in pages)


def test_the_totals_take_a_page_of_their_own_when_the_rows_leave_no_room() -> None:
    """Five rows fit the page; the totals block does not fit beside them, so it moves on."""
    tall = PageBudget(**{**vars_of(BUDGET), "totals_height": 590.0})
    pages = plan_pages(rows(5), tall)
    assert len(pages) == 2
    assert len(pages[0].rows) == 5
    assert pages[1].rows == ()
    assert pages[0].carried_out == pages[1].carried_in


def test_a_page_always_makes_progress_even_on_a_row_taller_than_the_page() -> None:
    pages = plan_pages(rows(3, height=10_000.0), BUDGET)
    assert [len(page.rows) for page in pages] == [1, 1, 1, 0]


def test_a_document_with_no_rows_is_still_one_page() -> None:
    pages = plan_pages((), BUDGET)
    assert len(pages) == 1
    assert pages[0].rows == ()


def test_a_taller_row_fits_fewer_to_the_page() -> None:
    short = plan_pages(rows(40, height=10.0), BUDGET)
    tall = plan_pages(rows(40, height=40.0), BUDGET)
    assert len(short) < len(tall)


def vars_of(budget: PageBudget) -> dict[str, object]:
    return {name: getattr(budget, name) for name in PageBudget.__slots__}


@pytest.mark.parametrize("count", [1, 2, 3, 10, 11, 30, 31, 99])
def test_no_page_is_ever_overfilled(count: int) -> None:
    pages = plan_pages(rows(count), BUDGET)
    for page in pages:
        top = BUDGET.later_top if page.number > 1 else BUDGET.first_top
        room = BUDGET.bottom - top - (CARRY_HEIGHT if page.number > 1 else 0.0)
        reserved = TOTALS_HEIGHT if page.carried_out is None else CARRY_HEIGHT
        assert sum(item.height for item in page.rows) <= room - reserved or len(page.rows) == 1
