"""What each content knob does to the document, with no PDF in sight.

One test per knob, each comparing the same seed with the knob on and off, so what the
knob changes is the only thing that differs. `docs/VARIATION_CATALOG.md` names the axis;
these say which value of it the knob picks.
"""

from __future__ import annotations

from random import Random

import pytest

from invoice_forge.knobs import Knob
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.model import Document
from invoice_forge.profiles.loader import load_profile
from invoice_forge.sample import variations
from invoice_forge.sample.catalogue import load_catalogue
from invoice_forge.sample.sampler import ITEM_RANGE, SampleRequest, sample_document

PROFILE = "de-DE"
SEED = 3
CONTENT_KNOBS = (
    Knob.MULTI_PAGE,
    Knob.WRAPPED_DESCRIPTION,
    Knob.SUB_ITEMS,
    Knob.SECTION_SUBTOTALS,
    Knob.DISCOUNT,
    Knob.PARTY_BLOCKS,
    Knob.PLACEHOLDER_ADDRESSES,
)


def drawn(*knobs: Knob, seed: int = SEED, profile_id: str = PROFILE) -> Document:
    profile = load_profile(profile_id)
    lexicon = load_lexicon(profile.lexicon)
    catalogue = load_catalogue(profile.lexicon)
    return sample_document(SampleRequest(profile, lexicon, catalogue, seed, knobs))


@pytest.mark.parametrize("knob", CONTENT_KNOBS)
def test_a_content_knob_changes_the_document(knob: Knob) -> None:
    assert drawn(knob) != drawn()


@pytest.mark.parametrize("knob", CONTENT_KNOBS)
def test_a_knobbed_document_is_as_reproducible_as_any_other(knob: Knob) -> None:
    assert drawn(knob) == drawn(knob)


def test_multi_page_asks_for_more_rows_than_one_page_holds() -> None:
    low = variations.MULTI_PAGE_RANGE[0]
    assert len(drawn(Knob.MULTI_PAGE).items) >= low
    assert variations.item_range((Knob.MULTI_PAGE,), ITEM_RANGE) == variations.MULTI_PAGE_RANGE
    assert variations.item_range((), ITEM_RANGE) == ITEM_RANGE


def test_wrapped_description_lengthens_a_description_past_the_column() -> None:
    plain = drawn().items
    long = drawn(Knob.WRAPPED_DESCRIPTION).items
    assert min(len(item.description) for item in long) >= variations.WRAP_LENGTH
    assert min(len(item.description) for item in plain) < variations.WRAP_LENGTH


def test_wrapped_description_only_ever_appends_the_catalogue_s_own_qualifiers() -> None:
    qualifiers = load_catalogue("de").qualifiers
    for item in drawn(Knob.WRAPPED_DESCRIPTION).items:
        head, *appended = item.description.split(", ")
        assert all(part in qualifiers or part in item.description for part in appended), head


def test_sub_items_hang_components_under_some_rows_and_not_all() -> None:
    items = drawn(Knob.SUB_ITEMS).items
    assert any(item.sub_items for item in items)
    assert any(not item.sub_items for item in items)
    assert all(not item.sub_items for item in drawn().items)


def test_a_sub_item_is_priced_or_it_is_not_but_never_half_priced() -> None:
    for item in drawn(Knob.SUB_ITEMS).items:
        for part in item.sub_items:
            assert (part.quantity is None) == (part.unit_price is None)
            assert part.description


def test_section_subtotals_group_the_rows_under_headings_the_lexicon_offers() -> None:
    headings = load_lexicon("de").section_headings
    items = drawn(Knob.SECTION_SUBTOTALS).items
    named = [item.section for item in items]
    assert set(named) <= set(headings)
    assert len(set(named)) >= 2
    assert all(item.section is None for item in drawn().items)


def test_the_sections_are_contiguous_so_a_group_is_drawn_once() -> None:
    items = drawn(Knob.SECTION_SUBTOTALS).items
    seen: list[str | None] = []
    for item in items:
        if not seen or seen[-1] != item.section:
            seen.append(item.section)
    assert len(seen) == len(set(seen))


def test_discount_puts_a_percentage_on_some_rows_and_leaves_others_alone() -> None:
    items = drawn(Knob.DISCOUNT).items
    discounted = [item for item in items if item.discount_percent is not None]
    assert discounted
    assert len(discounted) < len(items)
    assert all(str(item.discount_percent) in variations.DISCOUNTS for item in discounted)
    assert all(item.discount_percent is None for item in drawn().items)


def test_a_discount_comes_off_the_line_it_is_on() -> None:
    for item in drawn(Knob.DISCOUNT).items:
        gross = item.quantity * item.unit_price
        if item.discount_percent is None:
            assert item.exact_net == gross
        else:
            assert item.exact_net < gross


def test_party_blocks_adds_a_third_block_and_nothing_else() -> None:
    assert drawn().mail_to is None
    third = drawn(Knob.PARTY_BLOCKS).mail_to
    assert third is not None
    assert third.name
    assert third.lines


def test_placeholder_addresses_points_at_the_bill_to_block_instead_of_repeating_it() -> None:
    plain = drawn().ship_to
    placed = drawn(Knob.PLACEHOLDER_ADDRESSES).ship_to
    assert plain is not None and placed is not None
    assert plain.placeholder is None
    assert placed.placeholder in load_lexicon("de").address_placeholders
    assert placed.lines == ()
    assert placed.vat_id is None


def test_a_knob_the_sampler_does_not_own_leaves_the_content_alone() -> None:
    """`trap_labels` is a layout knob: the document it is drawn for is the same document."""
    assert drawn(Knob.TRAP_LABELS) == drawn()
    assert drawn(Knob.PAGE_NUMBERING) == drawn()
    assert drawn(Knob.CARRY_FORWARD) == drawn()


def test_two_knobs_compose_without_either_undoing_the_other() -> None:
    both = drawn(Knob.DISCOUNT, Knob.SUB_ITEMS)
    assert any(item.discount_percent is not None for item in both.items)
    assert any(item.sub_items for item in both.items)


def test_a_qualifier_is_appended_until_the_description_would_wrap() -> None:
    catalogue = load_catalogue("de")
    product = catalogue.products("industrial")[0]
    written = variations.described(product, catalogue, (Knob.WRAPPED_DESCRIPTION,), Random(1))
    assert len(written) >= variations.WRAP_LENGTH
    assert written.startswith(product.description)
