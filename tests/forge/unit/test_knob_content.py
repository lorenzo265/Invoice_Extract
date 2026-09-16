"""What each content knob does to the document, with no PDF in sight.

One test per knob, each comparing the same seed with the knob on and off, so what the
knob changes is the only thing that differs. `docs/VARIATION_CATALOG.md` names the axis;
these say which value of it the knob picks.
"""

from __future__ import annotations

from random import Random

import pytest

from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.model import CreditNoteStyle, Document, DocumentType, RoundingPolicy
from invoice_forge.profiles.loader import load_profile
from invoice_forge.sample import variations
from invoice_forge.sample.catalogue import load_catalogue
from invoice_forge.sample.sampler import (
    ITEM_RANGE,
    OPTIONAL_REFERENCES,
    SampleRequest,
    sample_document,
)

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
    Knob.MULTI_RATE,
    Knob.CHARGES,
    Knob.DECLARED_CHARGE,
    Knob.UNDECLARED_CHARGE,
    Knob.DUAL_CURRENCY_ECHO,
    Knob.CREDIT_NOTE,
    Knob.SUPPLY_DATE,
    Knob.EXTRA_REFERENCES,
)
# The two knobs that pin a value the sampler would otherwise draw. Pinning the value it
# happened to draw changes nothing, which is right, so they are not held to that rule.
PINNING_KNOBS = (Knob.ROUNDING_PER_LINE, Knob.ROUNDING_TOTAL)


def drawn(
    *knobs: Knob,
    seed: int = SEED,
    profile_id: str = PROFILE,
    family: Family = Family.CLASSIC,
) -> Document:
    profile = load_profile(profile_id)
    lexicon = load_lexicon(profile.lexicon)
    catalogue = load_catalogue(profile.lexicon)
    return sample_document(SampleRequest(profile, lexicon, catalogue, family, seed, knobs))


@pytest.mark.parametrize("knob", CONTENT_KNOBS)
def test_a_content_knob_changes_the_document(knob: Knob) -> None:
    assert drawn(knob) != drawn()


@pytest.mark.parametrize("knob", (*CONTENT_KNOBS, *PINNING_KNOBS))
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
    discounted = [item for item in items if item.discount_pct is not None]
    assert discounted
    assert len(discounted) < len(items)
    assert all(str(item.discount_pct) in variations.DISCOUNTS for item in discounted)
    assert all(item.discount_pct is None for item in drawn().items)


def test_a_discount_comes_off_the_line_it_is_on() -> None:
    for item in drawn(Knob.DISCOUNT).items:
        gross = item.quantity * item.unit_price
        if item.discount_pct is None:
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
    for knob in (
        Knob.TRAP_LABELS,
        Knob.PAGE_NUMBERING,
        Knob.CARRY_FORWARD,
        Knob.VAT_SUMMARY_TABLE,
        Knob.AMOUNT_IN_WORDS,
        Knob.BANK_FOOTER,
        Knob.NOISE_FOOTER,
        Knob.PAYMENT_TERMS_BLOCK,
        Knob.STAMP_COPY,
        Knob.COLUMN_SET,
        Knob.THOUSANDS_VARIANT,
        Knob.EXEMPTION_VERBIAGE,
    ):
        assert drawn(knob) == drawn(), knob


def test_multi_rate_puts_a_document_at_more_than_one_rate() -> None:
    rates = load_profile(PROFILE).vat_rates
    assert set(drawn().vat_rates) == {rates.standard}
    mixed = {rate for seed in range(8) for rate in drawn(Knob.MULTI_RATE, seed=seed).vat_rates}
    assert mixed > {rates.standard}
    assert mixed <= {rates.standard, rates.reduced, rates.zero}


def test_each_charge_knob_puts_exactly_one_charge_on_the_document() -> None:
    assert drawn().charges == ()
    assert [charge.declared for charge in drawn(Knob.DECLARED_CHARGE).charges] == [True]
    assert [charge.declared for charge in drawn(Knob.UNDECLARED_CHARGE).charges] == [False]
    assert len(drawn(Knob.CHARGES).charges) == 1
    every = drawn(Knob.CHARGES, Knob.DECLARED_CHARGE, Knob.UNDECLARED_CHARGE).charges
    assert len(every) == 3
    assert {charge.declared for charge in every[1:]} == {True, False}


def test_an_undeclared_charge_is_in_the_total_and_on_no_line() -> None:
    hidden = drawn(Knob.UNDECLARED_CHARGE)
    totals = hidden.totals
    assert totals.charges_total == 0
    assert totals.undeclared_total == hidden.charges[0].amount
    assert totals.total_amount > totals.subtotal + totals.vat_amount


def test_the_rounding_knobs_pin_the_policy_and_an_unpinned_corpus_has_both() -> None:
    assert drawn(Knob.ROUNDING_TOTAL).rounding is RoundingPolicy.TOTAL
    assert drawn(Knob.ROUNDING_PER_LINE).rounding is RoundingPolicy.PER_LINE
    unpinned = {drawn(seed=seed).rounding for seed in range(12)}
    assert unpinned == set(RoundingPolicy)


def test_a_credit_note_reverses_the_invoice_and_names_it() -> None:
    invoice, note = drawn(), drawn(Knob.CREDIT_NOTE)
    assert invoice.type is DocumentType.INVOICE
    assert note.type is DocumentType.CREDIT_NOTE
    assert note.identifiers.credit_reference == invoice.identifiers.invoice_number
    assert note.identifiers.invoice_number != invoice.identifiers.invoice_number
    style = load_profile(PROFILE).credit_note_style
    reversed_amounts = style is CreditNoteStyle.NEGATIVE_AMOUNTS
    assert (note.totals.total_amount < 0) is reversed_amounts


def test_supply_date_is_the_other_value_of_whatever_the_profile_prints() -> None:
    for profile_id in ("de-DE", "en-GB"):
        prints = load_profile(profile_id).prints_supply_date
        plain = drawn(profile_id=profile_id).dates.supply_date is not None
        turned = drawn(Knob.SUPPLY_DATE, profile_id=profile_id).dates.supply_date is not None
        assert plain is prints
        assert turned is not prints


def test_extra_references_carries_every_optional_reference_at_once() -> None:
    every = drawn(Knob.EXTRA_REFERENCES).identifiers
    assert all(getattr(every, name) is not None for name in OPTIONAL_REFERENCES)
    profile = load_profile(PROFILE)
    plain = drawn().identifiers
    carried = {name for name in OPTIONAL_REFERENCES if getattr(plain, name) is not None}
    assert carried == set(profile.extensions)


def test_the_saas_family_bills_subscriptions_in_sections_with_components() -> None:
    """A family implies content too, and `saas` is what that means."""
    goods = drawn(family=Family.CLASSIC)
    subscribed = drawn(family=Family.SAAS)
    assert all(item.subscription is None for item in goods.items)
    assert all(item.subscription is not None for item in subscribed.items)
    assert {item.section for item in subscribed.items} != {None}
    assert any(item.sub_items for item in subscribed.items)


def test_a_subscription_carries_every_column_the_saas_table_prints() -> None:
    for item in drawn(family=Family.SAAS).items:
        period = item.subscription
        assert period is not None
        assert period.subscription_id.startswith("SUB-")
        assert period.billing_cycle in variations.BILLING_CYCLES
        assert period.period_start and period.period_end
        assert period.share_percent is not None
        assert period.remaining_term


def test_two_knobs_compose_without_either_undoing_the_other() -> None:
    both = drawn(Knob.DISCOUNT, Knob.SUB_ITEMS)
    assert any(item.discount_pct is not None for item in both.items)
    assert any(item.sub_items for item in both.items)


def test_a_qualifier_is_appended_until_the_description_would_wrap() -> None:
    catalogue = load_catalogue("de")
    product = catalogue.products("industrial")[0]
    written = variations.described(product, catalogue, (Knob.WRAPPED_DESCRIPTION,), Random(1))
    assert len(written) >= variations.WRAP_LENGTH
    assert written.startswith(product.description)
