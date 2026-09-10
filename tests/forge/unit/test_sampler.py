"""The same seed draws the same document, everywhere, forever."""

from __future__ import annotations

import re
from datetime import date

import pytest

from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.model import DocumentType
from invoice_forge.profiles.loader import bundled_profile_ids, load_profile
from invoice_forge.sample.catalogue import load_catalogue
from invoice_forge.sample.identifiers import is_valid_iban
from invoice_forge.sample.sampler import ITEM_RANGE, SampleRequest, sample_document

SEEDS = range(6)


def request_for(profile_id: str, seed: int) -> SampleRequest:
    profile = load_profile(profile_id)
    return SampleRequest(
        profile=profile,
        lexicon=load_lexicon(profile.lexicon),
        catalogue=load_catalogue(profile.lexicon),
        seed=seed,
    )


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_the_same_seed_draws_the_same_document(profile_id: str) -> None:
    for seed in SEEDS:
        assert sample_document(request_for(profile_id, seed)) == sample_document(
            request_for(profile_id, seed)
        )


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_different_seeds_draw_different_documents(profile_id: str) -> None:
    drawn = {sample_document(request_for(profile_id, seed)) for seed in SEEDS}
    assert len(drawn) == len(SEEDS)


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_a_drawn_document_speaks_its_profile(profile_id: str) -> None:
    profile = load_profile(profile_id)
    document = sample_document(request_for(profile_id, 1))
    assert document.type is DocumentType.INVOICE
    assert document.profile_id == profile_id
    assert document.language == profile.language
    assert document.currency == profile.currency
    assert document.secondary_currency == profile.secondary_currency


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_a_supply_date_is_printed_only_where_the_profile_prints_one(profile_id: str) -> None:
    profile = load_profile(profile_id)
    for seed in SEEDS:
        dates = sample_document(request_for(profile_id, seed)).dates
        assert (dates.supply_date is not None) is profile.prints_supply_date
        if dates.supply_date is not None:
            assert dates.supply_date <= dates.invoice_date
        assert dates.invoice_date < dates.due_date
        assert dates.invoice_date.year == date(2024, 1, 1).year


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_an_extension_is_carried_only_where_the_profile_asks_for_it(profile_id: str) -> None:
    profile = load_profile(profile_id)
    identifiers = sample_document(request_for(profile_id, 2)).identifiers
    for name in ("contract_number", "our_reference", "your_reference"):
        carried = getattr(identifiers, name) is not None
        assert carried is (name in profile.extensions), name


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_the_bank_block_is_fictional_but_well_formed(profile_id: str) -> None:
    profile = load_profile(profile_id)
    document = sample_document(request_for(profile_id, 3))
    payment = document.payment
    assert is_valid_iban(payment.iban)
    assert payment.iban.startswith(profile.country)
    assert payment.bic[4:6] == profile.country
    assert payment.account_holder == document.supplier.name
    assert payment.terms in load_lexicon(profile.lexicon).payment_terms


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_every_vat_id_matches_the_pattern_the_profile_declared(profile_id: str) -> None:
    profile = load_profile(profile_id)
    for seed in SEEDS:
        document = sample_document(request_for(profile_id, seed))
        for party in (document.supplier, document.bill_to):
            assert party.vat_id is not None
            assert re.fullmatch(profile.vat_id_pattern, party.vat_id), profile_id


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_the_rows_are_drawn_from_the_catalogue_within_the_declared_range(profile_id: str) -> None:
    catalogue = load_catalogue(load_profile(profile_id).lexicon)
    known = {item.sku for domain in catalogue.domains for item in catalogue.products(domain)}
    low, high = ITEM_RANGE
    for seed in SEEDS:
        items = sample_document(request_for(profile_id, seed)).items
        assert low <= len(items) <= high
        assert [item.pos for item in items] == list(range(1, len(items) + 1))
        assert {item.sku for item in items} <= known


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_a_charge_is_only_ever_one_the_profile_uses(profile_id: str) -> None:
    profile = load_profile(profile_id)
    for seed in SEEDS:
        for charge in sample_document(request_for(profile_id, seed)).charges:
            assert charge.type in profile.charges_used


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_the_rates_a_document_carries_are_rates_the_profile_declared(profile_id: str) -> None:
    rates = load_profile(profile_id).vat_rates
    declared = {rates.standard, rates.reduced, rates.zero}
    for seed in SEEDS:
        assert set(sample_document(request_for(profile_id, seed)).vat_rates) <= declared


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_the_total_is_the_rows_plus_the_charges_plus_the_tax(profile_id: str) -> None:
    for seed in SEEDS:
        totals = sample_document(request_for(profile_id, seed)).totals
        assert totals.total_amount == totals.subtotal + totals.charges_total + totals.vat_amount
        assert totals.total_amount > 0


def test_an_exchange_rate_is_drawn_only_for_a_second_currency() -> None:
    for profile_id in bundled_profile_ids():
        profile = load_profile(profile_id)
        document = sample_document(request_for(profile_id, 4))
        assert (document.exchange_rate is not None) is (profile.secondary_currency is not None)
