"""Identifiers are fictional, and shaped the way real ones are."""

from __future__ import annotations

import re
from random import Random

import pytest

from invoice_forge.profiles.loader import bundled_profile_ids, load_profile
from invoice_forge.sample.identifiers import (
    IBAN_BODIES,
    bic,
    iban,
    invoice_number,
    is_valid_iban,
    reference_number,
    vat_id,
)

COUNTRIES = (*IBAN_BODIES, "XX")
IBAN_LENGTHS = {"DE": 22, "GB": 22, "FR": 27, "SE": 24}


@pytest.mark.parametrize("country", COUNTRIES)
def test_every_generated_iban_passes_the_mod_97_check(country: str) -> None:
    for seed in range(25):
        assert is_valid_iban(iban(country, Random(seed))), country


@pytest.mark.parametrize(("country", "length"), sorted(IBAN_LENGTHS.items()))
def test_an_iban_is_as_long_as_its_country_makes_it(country: str, length: int) -> None:
    assert len(iban(country, Random(1)).replace(" ", "")) == length


def test_an_iban_is_printed_in_groups_of_four() -> None:
    printed = iban("DE", Random(2))
    assert all(len(group) <= 4 for group in printed.split(" "))
    assert printed.startswith("DE")


def test_a_tampered_iban_fails_the_check() -> None:
    printed = iban("DE", Random(3))
    digit = "1" if printed[2] != "1" else "2"
    assert not is_valid_iban(digit + printed[3:])


def test_something_too_short_to_be_an_iban_is_not_one() -> None:
    assert not is_valid_iban("DE1")


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_a_vat_id_matches_the_profile_that_asked_for_it(profile_id: str) -> None:
    pattern = load_profile(profile_id).vat_id_pattern
    for seed in range(20):
        assert re.fullmatch(pattern, vat_id(pattern, Random(seed))), profile_id


def test_a_bic_is_eleven_characters_naming_its_country() -> None:
    printed = bic("SE", Random(5))
    assert len(printed) == 11
    assert printed[4:6] == "SE"


@pytest.mark.parametrize("language", ["de", "en", "fr", "sv", "xx"])
def test_an_invoice_number_carries_its_year(language: str) -> None:
    assert "-2024-" in invoice_number(language, 2024, Random(6))


def test_a_reference_number_is_a_prefix_and_digits() -> None:
    assert re.fullmatch(r"PO-\d{6}", reference_number("PO", Random(7)))
    assert re.fullmatch(r"REF-\d{4}", reference_number("REF", Random(7), length=4))
