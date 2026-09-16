"""Companies that do not exist, at addresses written the way that country writes them."""

from __future__ import annotations

import dataclasses
from random import Random

import pytest

from invoice_forge.profiles.loader import load_profile, profile_ids
from invoice_forge.profiles.schema import PostalCodePosition, VendorProfile
from invoice_forge.sample.parties import address_lines, bank_name, company_name, party
from invoice_forge.sample.places import CITIES, LEGAL_FORMS, NUMBER_FIRST_LANGUAGES

LOCALITY_LINE = 1
ADDRESS_LINES_WITHOUT_A_COUNTRY = 2
LANGUAGES = tuple(sorted({load_profile(name).language for name in profile_ids()}))


def profile_for(profile_id: str) -> VendorProfile:
    return load_profile(profile_id)


def without_a_country_line(profile: VendorProfile) -> VendorProfile:
    address = dataclasses.replace(profile.address_format, country_line=False)
    return dataclasses.replace(profile, address_format=address)


@pytest.mark.parametrize("profile_id", profile_ids())
def test_a_name_ends_in_the_legal_form_its_country_uses(profile_id: str) -> None:
    profile = profile_for(profile_id)
    forms = LEGAL_FORMS[profile.country]
    for seed in range(10):
        name = company_name(profile.language, profile.country, Random(seed))
        assert any(name.endswith(form) for form in forms), name


def test_a_country_nobody_has_legal_forms_for_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="no legal forms for ZZ"):
        company_name("en", "ZZ", Random(0))


def test_a_language_nobody_has_words_for_is_refused_by_name() -> None:
    """English would render, and it would render a Dutch vendor's invoice in English."""
    with pytest.raises(ValueError, match="no stems for xx"):
        company_name("xx", "GB", Random(0))


@pytest.mark.parametrize("profile_id", profile_ids())
def test_an_address_prints_a_country_line_when_the_profile_asks_for_one(profile_id: str) -> None:
    profile = profile_for(profile_id)
    lines = address_lines(profile, profile.country, Random(1))
    assert len(lines) == ADDRESS_LINES_WITHOUT_A_COUNTRY + 1
    assert lines[-1] != ""


@pytest.mark.parametrize("profile_id", profile_ids())
def test_an_address_stops_at_the_locality_when_it_does_not(profile_id: str) -> None:
    lines = address_lines(without_a_country_line(profile_for(profile_id)), "DE", Random(1))
    assert len(lines) == ADDRESS_LINES_WITHOUT_A_COUNTRY


def test_a_country_the_language_has_no_word_for_is_refused_by_name() -> None:
    """A German invoice knows the word for Austria; printing `TR` instead is not the fix."""
    with pytest.raises(ValueError, match="no name for TR in de"):
        address_lines(profile_for("de-DE"), "TR", Random(2))


@pytest.mark.parametrize("profile_id", profile_ids())
def test_the_house_number_goes_where_the_language_puts_it(profile_id: str) -> None:
    profile = profile_for(profile_id)
    street = address_lines(profile, profile.country, Random(3))[0]
    first, last = street.split(" ")[0], street.split(" ")[-1]
    numbered = first if profile.language in NUMBER_FIRST_LANGUAGES else last
    assert numbered.isdigit(), street


@pytest.mark.parametrize("profile_id", profile_ids())
def test_the_postal_code_goes_where_the_profile_puts_it(profile_id: str) -> None:
    profile = profile_for(profile_id)
    locality = address_lines(profile, profile.country, Random(4))[LOCALITY_LINE]
    # Found rather than assumed to be a digit: `L-1672` and `D02 XY45` are postal codes too.
    city = max((name for name in CITIES[profile.country] if name in locality), key=len)
    before = profile.address_format.postal_code_position is PostalCodePosition.BEFORE_CITY
    assert locality.endswith(city) is before, locality


def test_both_postal_code_positions_are_printed() -> None:
    profile = profile_for("de-DE")
    after = dataclasses.replace(
        profile.address_format, postal_code_position=PostalCodePosition.AFTER_CITY
    )
    reversed_profile = dataclasses.replace(profile, address_format=after)
    before_line = address_lines(profile, "DE", Random(5))[LOCALITY_LINE]
    after_line = address_lines(reversed_profile, "DE", Random(5))[LOCALITY_LINE]
    assert before_line.split(" ") == after_line.split(" ")[::-1]


def test_a_country_with_no_postal_code_pattern_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="no postal code pattern for ZZ"):
        address_lines(profile_for("de-DE"), "ZZ", Random(6))


@pytest.mark.parametrize("profile_id", profile_ids())
def test_a_party_carries_the_vat_id_it_was_handed(profile_id: str) -> None:
    profile = profile_for(profile_id)
    drawn = party(profile, profile.country, "XX999", Random(7))
    assert drawn.vat_id == "XX999"
    assert drawn.name
    assert drawn.lines
    assert party(profile, profile.country, None, Random(7)).vat_id is None


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_bank_is_named_the_way_that_language_names_banks(language: str) -> None:
    name = bank_name(language, Random(8))
    assert name
    assert name == name.strip()


def test_each_language_builds_its_bank_name_its_own_way() -> None:
    assert bank_name("de", Random(9)).endswith("bank")
    assert bank_name("sv", Random(9)).endswith("banken")
    assert bank_name("fr", Random(9)).startswith("Banque ")
    assert bank_name("en", Random(9)).endswith(" Bank")


def test_the_same_seed_names_the_same_company() -> None:
    assert company_name("de", "DE", Random(10)) == company_name("de", "DE", Random(10))
