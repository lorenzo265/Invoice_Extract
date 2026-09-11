"""What each layout knob does to a family's declaration, with no PDF in sight.

A knob is the other value of its axis: `classic` declares one, `with_knobs` replaces it.
The renderer never sees a `Knob`, so these are the whole of what a layout knob does.
"""

from __future__ import annotations

import pytest

from invoice_forge.knobs import KNOB_NAMES, Knob
from invoice_forge.layout.classic import CLASSIC, DISCOUNT_COLUMNS, TRAPS
from invoice_forge.layout.spec import CustomerVat, PageLine
from invoice_forge.layout.variants import with_knobs

LAYOUT_KNOBS = (
    Knob.CARRY_FORWARD,
    Knob.PAGE_NUMBERING,
    Knob.DISCOUNT,
    Knob.PARTY_BLOCKS,
    Knob.TRAP_LABELS,
    Knob.CUSTOMER_VAT_POSITION,
    Knob.REPEAT_LETTERHEAD,
)


def test_no_knobs_leaves_the_family_exactly_as_declared() -> None:
    assert with_knobs(CLASSIC, ()) == CLASSIC


@pytest.mark.parametrize("knob", LAYOUT_KNOBS)
def test_a_layout_knob_changes_the_declaration(knob: Knob) -> None:
    assert with_knobs(CLASSIC, (knob,)) != CLASSIC


@pytest.mark.parametrize("name", KNOB_NAMES)
def test_applying_a_knob_never_raises_whatever_it_names(name: str) -> None:
    assert with_knobs(CLASSIC, (Knob(name),)) is not None


def test_carry_forward_is_the_break_that_carries_nothing() -> None:
    """`classic` carries a subtotal across a break; the knob is the other value of that axis."""
    assert CLASSIC.pagination.carry_forward is True
    assert with_knobs(CLASSIC, (Knob.CARRY_FORWARD,)).pagination.carry_forward is False


def test_repeat_letterhead_is_the_letterhead_that_does_not_repeat() -> None:
    assert CLASSIC.pagination.repeat_letterhead is True
    assert with_knobs(CLASSIC, (Knob.REPEAT_LETTERHEAD,)).pagination.repeat_letterhead is False


def test_page_numbering_moves_the_count_into_the_footer() -> None:
    assert CLASSIC.page_line is PageLine.HEADER
    assert with_knobs(CLASSIC, (Knob.PAGE_NUMBERING,)).page_line is PageLine.FOOTER


def test_customer_vat_position_moves_the_id_into_the_reference_block() -> None:
    assert CLASSIC.customer_vat is CustomerVat.PARTY_BLOCK
    changed = with_knobs(CLASSIC, (Knob.CUSTOMER_VAT_POSITION,))
    assert changed.customer_vat is CustomerVat.METADATA


def test_trap_labels_adds_the_dates_that_are_not_the_invoice_date() -> None:
    assert CLASSIC.traps is None
    assert with_knobs(CLASSIC, (Knob.TRAP_LABELS,)).traps == TRAPS
    assert TRAPS.kinds == ("order_date", "delivery_date", "print_date")


def test_discount_swaps_in_the_column_set_that_has_room_for_one() -> None:
    changed = with_knobs(CLASSIC, (Knob.DISCOUNT,))
    assert changed.items.columns == DISCOUNT_COLUMNS
    assert "discount" in {column.name for column in changed.items.columns}
    assert "discount" not in {column.name for column in CLASSIC.items.columns}


def test_the_discount_column_set_gives_the_description_the_width_it_takes() -> None:
    changed = with_knobs(CLASSIC, (Knob.DISCOUNT,))
    assert changed.items.description_width < CLASSIC.items.description_width


def test_every_column_set_stays_inside_the_page_and_in_order() -> None:
    for columns in (CLASSIC.items.columns, DISCOUNT_COLUMNS):
        anchors = [column.anchor for column in columns]
        assert anchors == sorted(anchors)
        assert min(anchors) >= CLASSIC.page.left
        assert max(anchors) <= CLASSIC.page.right


def test_party_blocks_makes_room_for_a_third_block() -> None:
    assert CLASSIC.parties is not None
    changed = with_knobs(CLASSIC, (Knob.PARTY_BLOCKS,))
    assert changed.parties is not None
    assert len(changed.parties.columns) == 3
    assert changed.parties.columns[0] == CLASSIC.parties.columns[0]
    assert changed.parties.columns[-1] == CLASSIC.parties.columns[-1]


def test_a_family_with_no_party_block_gains_none_from_the_knob() -> None:
    import dataclasses

    bare = dataclasses.replace(CLASSIC, parties=None)
    assert with_knobs(bare, (Knob.PARTY_BLOCKS,)).parties is None


def test_a_family_that_already_has_three_columns_keeps_them() -> None:
    import dataclasses

    wide = dataclasses.replace(
        CLASSIC, parties=dataclasses.replace(CLASSIC.parties, columns=(50.0, 200.0, 350.0))
    )
    assert with_knobs(wide, (Knob.PARTY_BLOCKS,)).parties == wide.parties


def test_knobs_compose_and_each_one_still_lands() -> None:
    changed = with_knobs(CLASSIC, (Knob.DISCOUNT, Knob.TRAP_LABELS, Knob.PAGE_NUMBERING))
    assert changed.items.columns == DISCOUNT_COLUMNS
    assert changed.traps == TRAPS
    assert changed.page_line is PageLine.FOOTER
    assert changed.pagination.carry_forward is True


def test_a_content_knob_leaves_the_declaration_alone() -> None:
    """`sub_items` and `section_subtotals` are drawn because the rows carry them."""
    for knob in (Knob.SUB_ITEMS, Knob.SECTION_SUBTOTALS, Knob.MULTI_PAGE):
        assert with_knobs(CLASSIC, (knob,)) == CLASSIC, knob
