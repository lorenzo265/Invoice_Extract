"""Spelled numbers, against a table of what each language actually writes.

A speller has no clever invariant to check it against — the only proof is that a native
spelling of a number comes out. So the table below is the specification, written by hand,
and the five styles are held to it.
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
    # Dutch, Danish and Norwegian all count the unit before the ten, and all three write the
    # formal `een`/`et`/`ett` before a lone hundred or thousand that a deed or an invoice uses.
    "nl": {
        0: "nul",
        7: "zeven",
        16: "zestien",
        20: "twintig",
        21: "eenentwintig",
        99: "negenennegentig",
        100: "eenhonderd",
        234: "tweehonderdvierendertig",
        1000: "eenduizend",
        1005: "eenduizendvijf",
        1234: "eenduizendtweehonderdvierendertig",
        45678: "vijfenveertigduizendzeshonderdachtenzeventig",
        1000000: "een miljoen",
        2500000: "twee miljoen vijfhonderdduizend",
    },
    "da": {
        0: "nul",
        7: "syv",
        16: "seksten",
        20: "tyve",
        21: "enogtyve",
        50: "halvtreds",
        99: "nioghalvfems",
        100: "ethundrede",
        234: "tohundredefireogtredive",
        1000: "ettusind",
        1005: "ettusindfem",
        45678: "femogfyrretusindsekshundredeotteoghalvfjerds",
        1000000: "en million",
        2500000: "to millioner femhundredetusind",
    },
    "no": {
        0: "null",
        7: "sju",
        16: "seksten",
        20: "tjue",
        21: "tjueett",
        99: "nittini",
        200: "tohundre",
        234: "tohundre trettifire",
        1000: "ett tusen",
        12000: "tolvtusen",
        1000000: "en million",
        2500000: "to millioner femhundretusen",
    },
    # Turkish glues nothing and counts no lone scale word: a thousand is `bin`, not `bir bin`.
    "tr": {
        0: "sıfır",
        7: "yedi",
        16: "on altı",
        20: "yirmi",
        21: "yirmi bir",
        99: "doksan dokuz",
        100: "yüz",
        234: "iki yüz otuz dört",
        1000: "bin",
        1005: "bin beş",
        1234: "bin iki yüz otuz dört",
        45678: "kırk beş bin altı yüz yetmiş sekiz",
        1000000: "bir milyon",
        2500000: "iki milyon beş yüz bin",
    },
}

AMOUNTS: dict[str, str] = {
    "en": "nine thousand nine hundred and sixty-five pounds and twenty-four pence",
    "de": "neuntausendneunhundertfünfundsechzig Euro und vierundzwanzig Cent",
    "sv": "niotusen niohundra sextiofem kronor och tjugofyra öre",
    "fr": "neuf mille neuf cent soixante-cinq euros et vingt-quatre centimes",
    "nl": "negenduizendnegenhonderdvijfenzestig euro en vierentwintig cent",
    "da": "nitusindnihundredefemogtres kroner og fireogtyve øre",
    "no": "nitusen nihundre sekstifem kroner og tjuefire øre",
    "tr": "dokuz bin dokuz yüz altmış beş lira ve yirmi dört kuruş",
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


def test_every_bundled_lexicon_that_spells_declares_a_style_that_is_implemented() -> None:
    """A lexicon may spell no numbers at all; what it may not do is name a style nothing does."""
    for language in bundled_lexicon_ids():
        words = load_lexicon(language).amount_in_words
        if words is None:
            continue
        assert words.style in AMOUNT_IN_WORDS_STYLES, language
        assert spell_number(4321, words), language


def test_every_style_in_the_vocabulary_is_used_by_a_bundled_lexicon() -> None:
    """A style nothing declares is a rule nothing proves, which is a rule to delete."""
    declared = {
        words.style
        for words in (load_lexicon(language).amount_in_words for language in bundled_lexicon_ids())
        if words is not None
    }
    assert declared == set(AMOUNT_IN_WORDS_STYLES)


def test_a_lexicon_spells_amounts_only_where_the_five_styles_write_its_numbers() -> None:
    """Half of Europe declines its numerals; those lexicons spell nothing rather than badly."""
    spelling = {
        language for language in bundled_lexicon_ids() if load_lexicon(language).amount_in_words
    }
    assert spelling == set(AMOUNTS)


@pytest.mark.parametrize("language", sorted(AMOUNTS))
def test_a_spelled_number_never_runs_words_together_across_a_space(language: str) -> None:
    """Every group has to come out as words, not as an empty string joined to another."""
    words = load_lexicon(language).amount_in_words
    for value in (0, 1, 19, 20, 100, 999, 1000, 99999, 1000000):
        spelled = spell_number(value, words)
        assert spelled.strip() == spelled
        assert "  " not in spelled
