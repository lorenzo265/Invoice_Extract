"""Spelled numbers, against a table of what each language actually writes.

A speller has no clever invariant to check it against — the only proof is that a native
spelling of a number comes out. So the table below is the specification, written by hand,
and the four styles are held to it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from invoice_forge.lexicon.loader import bundled_lexicon_ids, load_lexicon
from invoice_forge.lexicon.schema import AMOUNT_IN_WORDS_STYLES
from invoice_forge.lexicon.spelling import spell_amount, spell_number

SPELLED: dict[str, dict[int, str]] = {
    "en": {
        0: "zero",
        7: "seven",
        16: "sixteen",
        20: "twenty",
        21: "twenty-one",
        99: "ninety-nine",
        100: "one hundred",
        101: "one hundred and one",
        234: "two hundred and thirty-four",
        1000: "one thousand",
        1005: "one thousand and five",
        1234: "one thousand two hundred and thirty-four",
        45678: "forty-five thousand six hundred and seventy-eight",
        1000000: "one million",
        2500000: "two million five hundred thousand",
    },
    "de": {
        0: "null",
        7: "sieben",
        16: "sechzehn",
        20: "zwanzig",
        21: "einundzwanzig",
        99: "neunundneunzig",
        100: "einhundert",
        234: "zweihundertvierunddreißig",
        1000: "eintausend",
        1005: "eintausendfünf",
        1234: "eintausendzweihundertvierunddreißig",
        45678: "fünfundvierzigtausendsechshundertachtundsiebzig",
        1000000: "eine Million",
        2500000: "zwei Millionen fünfhunderttausend",
    },
    "sv": {
        0: "noll",
        7: "sju",
        16: "sexton",
        20: "tjugo",
        21: "tjugoett",
        99: "nittionio",
        200: "tvåhundra",
        234: "tvåhundra trettiofyra",
        1000: "ett tusen",
        12000: "tolvtusen",
        1000000: "en miljon",
        2500000: "två miljoner femhundratusen",
    },
    "fr": {
        0: "zéro",
        7: "sept",
        16: "seize",
        20: "vingt",
        21: "vingt et un",
        70: "soixante-dix",
        71: "soixante et onze",
        75: "soixante-quinze",
        79: "soixante-dix-neuf",
        80: "quatre-vingts",
        81: "quatre-vingt-un",
        90: "quatre-vingt-dix",
        91: "quatre-vingt-onze",
        99: "quatre-vingt-dix-neuf",
        100: "cent",
        200: "deux cents",
        234: "deux cent trente-quatre",
        1000: "mille",
        80000: "quatre-vingt mille",
        500000: "cinq cent mille",
        1234: "mille deux cent trente-quatre",
        1000000: "un million",
        2500000: "deux millions cinq cent mille",
    },
}

AMOUNTS: dict[str, str] = {
    "en": "nine thousand nine hundred and sixty-five pounds and twenty-four pence",
    "de": "neuntausendneunhundertfünfundsechzig Euro und vierundzwanzig Cent",
    "sv": "niotusen niohundra sextiofem kronor och tjugofyra öre",
    "fr": "neuf mille neuf cent soixante-cinq euros et vingt-quatre centimes",
}


@pytest.mark.parametrize("language", sorted(SPELLED))
def test_every_number_in_the_table_is_spelled_the_way_the_language_writes_it(
    language: str,
) -> None:
    words = load_lexicon(language).amount_in_words
    for value, expected in SPELLED[language].items():
        assert spell_number(value, words) == expected, value


@pytest.mark.parametrize("language", sorted(AMOUNTS))
def test_an_amount_carries_its_currency_and_its_fraction(language: str) -> None:
    words = load_lexicon(language).amount_in_words
    assert spell_amount(Decimal("9965.24"), words) == AMOUNTS[language]


@pytest.mark.parametrize("language", sorted(AMOUNTS))
def test_a_whole_amount_names_no_fraction(language: str) -> None:
    words = load_lexicon(language).amount_in_words
    spelled = spell_amount(Decimal("100.00"), words)
    assert words.currency_fraction[0] not in spelled
    assert words.currency_fraction[1] not in spelled


@pytest.mark.parametrize("language", sorted(AMOUNTS))
def test_one_of_a_currency_is_singular_and_two_are_plural(language: str) -> None:
    words = load_lexicon(language).amount_in_words
    assert spell_amount(Decimal("1.00"), words).endswith(words.currency_unit[0])
    assert spell_amount(Decimal("2.00"), words).endswith(words.currency_unit[1])


@pytest.mark.parametrize("language", sorted(AMOUNTS))
def test_a_credit_note_is_spelled_unsigned(language: str) -> None:
    """The figures above the line carry the sign; no lexicon has a word for minus."""
    words = load_lexicon(language).amount_in_words
    assert spell_amount(Decimal("-42.50"), words) == spell_amount(Decimal("42.50"), words)


@pytest.mark.parametrize("language", sorted(AMOUNTS))
def test_cents_are_rounded_to_the_cent_before_they_are_spelled(language: str) -> None:
    words = load_lexicon(language).amount_in_words
    assert spell_amount(Decimal("5.005"), words) == spell_amount(Decimal("5.01"), words)


def test_every_bundled_lexicon_declares_a_style_that_is_implemented() -> None:
    for language in bundled_lexicon_ids():
        style = load_lexicon(language).amount_in_words.style
        assert style in AMOUNT_IN_WORDS_STYLES
        assert spell_number(4321, load_lexicon(language).amount_in_words)


def test_every_style_in_the_vocabulary_is_used_by_a_bundled_lexicon() -> None:
    """A style nothing declares is a rule nothing proves, which is a rule to delete."""
    declared = {load_lexicon(language).amount_in_words.style for language in bundled_lexicon_ids()}
    assert declared == set(AMOUNT_IN_WORDS_STYLES)


@pytest.mark.parametrize("language", sorted(AMOUNTS))
def test_a_spelled_number_never_runs_words_together_across_a_space(language: str) -> None:
    """Every group has to come out as words, not as an empty string joined to another."""
    words = load_lexicon(language).amount_in_words
    for value in (0, 1, 19, 20, 100, 999, 1000, 99999, 1000000):
        spelled = spell_number(value, words)
        assert spelled.strip() == spelled
        assert "  " not in spelled
