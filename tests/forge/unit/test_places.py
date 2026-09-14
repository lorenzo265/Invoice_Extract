"""The word tables, held to the profiles that read them.

`places.py` is data with no logic to test, so what is worth checking is that it covers
exactly the languages and countries the bundled profiles ask for. Too little and a
profile refuses to render; too much and a table has grown an entry nothing proves.
"""

from __future__ import annotations

from random import Random

import pytest

from invoice_forge.profiles.loader import load_profile, profile_ids
from invoice_forge.sample.patterns import fill
from invoice_forge.sample.places import (
    BANK_NAMES,
    CITIES,
    COUNTRY_NAMES,
    LEGAL_FORMS,
    NUMBER_FIRST_LANGUAGES,
    POSTAL_CODES,
    STEMS,
    STREETS,
    TRADES,
)

WORD_LISTS = {"stems": STEMS, "trades": TRADES, "streets": STREETS}
BY_LANGUAGE = {**WORD_LISTS, "banks": BANK_NAMES}
BY_COUNTRY = {"legal forms": LEGAL_FORMS, "cities": CITIES, "postal codes": POSTAL_CODES}
# Enough of each that two invoices from one vendor rarely read as the same company.
MIN_CHOICES = 3


def languages() -> frozenset[str]:
    return frozenset(load_profile(name).language for name in profile_ids())


def countries() -> frozenset[str]:
    return frozenset(load_profile(name).country for name in profile_ids())


@pytest.mark.parametrize("name", sorted(BY_LANGUAGE))
def test_a_table_keyed_by_language_covers_the_languages_and_no_others(name: str) -> None:
    assert frozenset(BY_LANGUAGE[name]) == languages()


@pytest.mark.parametrize("name", sorted(BY_COUNTRY))
def test_a_table_keyed_by_country_covers_the_countries_and_no_others(name: str) -> None:
    assert frozenset(BY_COUNTRY[name]) == countries()


def test_every_language_names_every_country_its_own_profiles_print_in() -> None:
    """`fr` needs France, Belgium and Luxembourg; it does not need Poland."""
    needed: dict[str, set[str]] = {}
    for name in profile_ids():
        profile = load_profile(name)
        needed.setdefault(profile.language, set()).add(profile.country)
    assert {language: set(names) for language, names in COUNTRY_NAMES.items()} == needed


def test_the_languages_that_write_the_number_first_are_languages_a_profile_speaks() -> None:
    assert languages() >= NUMBER_FIRST_LANGUAGES


@pytest.mark.parametrize("name", sorted(WORD_LISTS))
def test_a_word_list_offers_a_choice_and_every_word_in_it_is_a_word(name: str) -> None:
    for key, words in WORD_LISTS[name].items():
        assert len(words) >= MIN_CHOICES, key
        for word in words:
            assert word and word == word.strip(), (key, word)


@pytest.mark.parametrize("country", sorted(POSTAL_CODES))
def test_every_postal_code_pattern_draws_a_code_of_a_fixed_shape(country: str) -> None:
    """The pattern language is literals and character classes, so the length never varies."""
    drawn = {fill(POSTAL_CODES[country], Random(seed)) for seed in range(20)}
    assert len({len(code) for code in drawn}) == 1, drawn
    assert len(drawn) > 1, drawn


@pytest.mark.parametrize("country", sorted(CITIES))
def test_no_city_is_listed_twice_for_one_country(country: str) -> None:
    assert len(set(CITIES[country])) == len(CITIES[country])


@pytest.mark.parametrize("language", sorted(BANK_NAMES))
def test_every_bank_name_is_built_from_the_stem_it_is_given(language: str) -> None:
    assert "{stem}" in BANK_NAMES[language], language
