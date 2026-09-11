"""What each layout knob does to a family's declaration, with no PDF in sight.

A knob is the other value of its axis: `classic` declares one, `with_knobs` replaces it.
The renderer never sees a `Knob`, so these are the whole of what a layout knob does.
"""

from __future__ import annotations

import dataclasses

import pytest

from invoice_forge.families import Family
from invoice_forge.knobs import KNOB_NAMES, Knob
from invoice_forge.layout import columns
from invoice_forge.layout.classic import CLASSIC, TRAPS, family_spec
from invoice_forge.layout.columns import ColumnSet
from invoice_forge.layout.spec import CustomerVat, MetadataStyle, PageLine, VatSummaryStyle
from invoice_forge.layout.variants import TERMS_BLOCK, with_knobs

LAYOUT_KNOBS = (
    Knob.CARRY_FORWARD,
    Knob.PAGE_NUMBERING,
    Knob.DISCOUNT,
    Knob.COLUMN_SET,
    Knob.PARTY_BLOCKS,
    Knob.TRAP_LABELS,
    Knob.CUSTOMER_VAT_POSITION,
    Knob.REPEAT_LETTERHEAD,
    Knob.VAT_SUMMARY_TABLE,
    Knob.AMOUNT_IN_WORDS,
    Knob.EXEMPTION_VERBIAGE,
    Knob.BANK_FOOTER,
    Knob.NOISE_FOOTER,
    Knob.PAYMENT_TERMS_BLOCK,
    Knob.STAMP_COPY,
)


def test_no_knobs_leaves_the_family_exactly_as_declared() -> None:
    assert with_knobs(CLASSIC, ()) == CLASSIC


@pytest.mark.parametrize("family", list(Family), ids=[f.value for f in Family])
def test_no_knobs_leaves_every_family_exactly_as_declared(family: Family) -> None:
    spec = family_spec(family)
    assert with_knobs(spec, ()) == spec


@pytest.mark.parametrize("knob", LAYOUT_KNOBS, ids=[k.value for k in LAYOUT_KNOBS])
def test_a_layout_knob_changes_the_declaration(knob: Knob) -> None:
    assert with_knobs(CLASSIC, (knob,)) != CLASSIC


@pytest.mark.parametrize("name", KNOB_NAMES)
def test_applying_a_knob_never_raises_whatever_it_names(name: str) -> None:
    for family in Family:
        assert with_knobs(family_spec(family), (Knob(name),)) is not None


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


def test_page_numbering_puts_no_count_on_a_family_that_prints_none() -> None:
    """`minimal` has no page line at all, so the knob has no axis to give another value of."""
    minimal = family_spec(Family.MINIMAL)
    assert minimal.page_line is PageLine.NONE
    assert with_knobs(minimal, (Knob.PAGE_NUMBERING,)).page_line is PageLine.NONE


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
    assert changed.items.columns == columns.CLASSIC_DISCOUNT.columns
    assert "discount" in {column.name for column in changed.items.columns}
    assert "discount" not in {column.name for column in CLASSIC.items.columns}


def test_the_discount_column_set_gives_the_description_the_width_it_takes() -> None:
    changed = with_knobs(CLASSIC, (Knob.DISCOUNT,))
    assert changed.items.description_width < CLASSIC.items.description_width


def test_column_set_takes_the_position_and_part_number_away_and_gives_a_unit() -> None:
    changed = with_knobs(CLASSIC, (Knob.COLUMN_SET,))
    named = {column.name for column in changed.items.columns}
    assert "unit" in named
    assert not {"pos", "sku"} & named


def test_the_two_column_knobs_compose_into_the_set_that_has_both() -> None:
    changed = with_knobs(CLASSIC, (Knob.COLUMN_SET, Knob.DISCOUNT))
    assert changed.items.columns == columns.COMPACT_DISCOUNT.columns


def test_a_family_with_columns_of_its_own_keeps_them() -> None:
    """Subscription columns are not the other value of the standard set's axis."""
    saas = family_spec(Family.SAAS)
    assert saas.items.standard_columns is False
    for knob in (Knob.COLUMN_SET, Knob.DISCOUNT):
        assert with_knobs(saas, (knob,)).items.columns == columns.SAAS.columns


@pytest.mark.parametrize("declared", columns.ALL_SETS, ids=range(len(columns.ALL_SETS)))
def test_every_column_set_stays_inside_the_page_and_in_order(declared: ColumnSet) -> None:
    anchors = [column.anchor for column in declared.columns]
    assert anchors == sorted(anchors)
    assert min(anchors) >= CLASSIC.page.left
    assert max(anchors) <= CLASSIC.page.right


@pytest.mark.parametrize("declared", columns.ALL_SETS, ids=range(len(columns.ALL_SETS)))
def test_every_column_set_can_be_carried_and_subtotalled(declared: ColumnSet) -> None:
    """A carry-forward line and a section subtotal are drawn in these two columns."""
    named = {column.name for column in declared.columns}
    assert {"description", "net_amount"} <= named


@pytest.mark.parametrize("declared", columns.ALL_SETS, ids=range(len(columns.ALL_SETS)))
def test_a_description_never_claims_more_width_than_its_column_has(declared: ColumnSet) -> None:
    anchors = [column.anchor for column in declared.columns]
    description = next(c for c in declared.columns if c.name == "description")
    after = min(anchor for anchor in anchors if anchor > description.anchor)
    assert declared.description_width <= after - description.anchor


def test_vat_summary_table_leaves_the_summary_a_list() -> None:
    """`classic` prints the richer value of the axis, so the knob is the plainer one."""
    assert CLASSIC.vat_summary is not None
    assert CLASSIC.vat_summary.style is VatSummaryStyle.TABLE
    changed = with_knobs(CLASSIC, (Knob.VAT_SUMMARY_TABLE,))
    assert changed.vat_summary is not None
    assert changed.vat_summary.style is VatSummaryStyle.LIST


def test_a_family_with_no_vat_summary_gains_none_from_the_knob() -> None:
    minimal = family_spec(Family.MINIMAL)
    assert minimal.vat_summary is None
    assert with_knobs(minimal, (Knob.VAT_SUMMARY_TABLE,)).vat_summary is None


def test_bank_footer_takes_the_block_that_says_where_to_pay_away() -> None:
    assert CLASSIC.payment is not None
    assert with_knobs(CLASSIC, (Knob.BANK_FOOTER,)).payment is None


def test_noise_footer_takes_the_legal_lines_away() -> None:
    assert CLASSIC.footer is not None
    assert with_knobs(CLASSIC, (Knob.NOISE_FOOTER,)).footer is None


def test_payment_terms_block_gives_the_terms_a_block_of_their_own() -> None:
    assert CLASSIC.terms_block is None
    assert with_knobs(CLASSIC, (Knob.PAYMENT_TERMS_BLOCK,)).terms_block == TERMS_BLOCK


def test_stamp_copy_marks_the_family_that_prints_one() -> None:
    assert CLASSIC.copy_stamp is False
    assert with_knobs(CLASSIC, (Knob.STAMP_COPY,)).copy_stamp is True


def test_amount_in_words_and_exemption_are_lines_the_totals_block_declares() -> None:
    assert CLASSIC.totals.amount_in_words is False
    assert CLASSIC.totals.exemption is False
    changed = with_knobs(CLASSIC, (Knob.AMOUNT_IN_WORDS, Knob.EXEMPTION_VERBIAGE))
    assert changed.totals.amount_in_words is True
    assert changed.totals.exemption is True


def test_party_blocks_makes_room_for_a_third_block() -> None:
    assert CLASSIC.parties is not None
    changed = with_knobs(CLASSIC, (Knob.PARTY_BLOCKS,))
    assert changed.parties is not None
    assert len(changed.parties.columns) == 3
    assert changed.parties.columns[0] == CLASSIC.parties.columns[0]
    assert changed.parties.columns[-1] == CLASSIC.parties.columns[-1]


def test_a_family_with_no_party_block_gains_none_from_the_knob() -> None:
    bare = dataclasses.replace(CLASSIC, parties=None)
    assert with_knobs(bare, (Knob.PARTY_BLOCKS,)).parties is None


def test_a_family_that_already_has_three_columns_keeps_them() -> None:
    wide = dataclasses.replace(
        CLASSIC, parties=dataclasses.replace(CLASSIC.parties, columns=(50.0, 200.0, 350.0))
    )
    assert with_knobs(wide, (Knob.PARTY_BLOCKS,)).parties == wide.parties


def test_knobs_compose_and_each_one_still_lands() -> None:
    changed = with_knobs(CLASSIC, (Knob.DISCOUNT, Knob.TRAP_LABELS, Knob.PAGE_NUMBERING))
    assert changed.items.columns == columns.CLASSIC_DISCOUNT.columns
    assert changed.traps == TRAPS
    assert changed.page_line is PageLine.FOOTER
    assert changed.pagination.carry_forward is True


def test_a_content_knob_leaves_the_declaration_alone() -> None:
    """`sub_items` and `section_subtotals` are drawn because the rows carry them."""
    content = (
        Knob.SUB_ITEMS,
        Knob.SECTION_SUBTOTALS,
        Knob.MULTI_PAGE,
        Knob.MULTI_RATE,
        Knob.CREDIT_NOTE,
        Knob.CHARGES,
        Knob.DECLARED_CHARGE,
        Knob.UNDECLARED_CHARGE,
        Knob.ROUNDING_TOTAL,
        Knob.DUAL_CURRENCY_ECHO,
        Knob.SUPPLY_DATE,
        Knob.EXTRA_REFERENCES,
        Knob.THOUSANDS_VARIANT,
        Knob.PLACEHOLDER_ADDRESSES,
        Knob.WRAPPED_DESCRIPTION,
    )
    for knob in content:
        assert with_knobs(CLASSIC, (knob,)) == CLASSIC, knob


def test_the_families_differ_from_classic_in_what_they_declare() -> None:
    for family in Family:
        spec = family_spec(family)
        assert spec.family is family
        assert (spec == CLASSIC) == (family is Family.CLASSIC), family


def test_tabular_rules_its_references_and_codes_its_summary() -> None:
    spec = family_spec(Family.TABULAR)
    assert spec.metadata.style is MetadataStyle.TABLE
    assert spec.vat_summary is not None
    assert spec.vat_summary.style is VatSummaryStyle.CODED
    assert spec.vat_summary.code_x < spec.vat_summary.x


def test_stacked_sets_every_value_under_its_label_and_rules_nothing() -> None:
    spec = family_spec(Family.STACKED)
    assert spec.metadata.style is MetadataStyle.STACKED
    assert spec.metadata.value_leading > 0
    assert spec.totals.stacked is True
    assert spec.items.ruled is False


def test_minimal_switches_off_every_block_it_is_defined_by() -> None:
    spec = family_spec(Family.MINIMAL)
    assert spec.vat_summary is None
    assert spec.payment is None
    assert spec.footer is None
    assert spec.page_line is PageLine.NONE
    assert spec.parties is not None
    assert len(spec.parties.columns) == 1
    assert spec.pagination.carry_forward is False
    assert spec.totals.secondary_echo is False
