"""Numbers and dates read the way the profile that printed them writes them."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.profiles.schema import DateFormat
from invoice_forge.render.text import NumberFormat, date_text, money, plain, quantity, rate, wrap

GERMAN = NumberFormat(decimal=",", thousands=".")
BRITISH = NumberFormat(decimal=".", thousands=",")
SWEDISH = NumberFormat(decimal=",", thousands=" ")
UNGROUPED = NumberFormat(decimal=",", thousands="")

# A width function that needs no font: every character is four points wide.
CHARACTER_WIDTH = 4.0


def measure(text: str) -> float:
    return len(text) * CHARACTER_WIDTH


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("9965.24", "9.965,24"),
        ("0", "0,00"),
        ("100", "100,00"),
        ("1234567.5", "1.234.567,50"),
        ("-10841.27", "-10.841,27"),
        ("0.005", "0,01"),
    ],
)
def test_money_is_grouped_and_separated_the_german_way(value: str, expected: str) -> None:
    assert money(Decimal(value), GERMAN) == expected


def test_the_same_amount_reads_differently_in_each_profile() -> None:
    amount = Decimal("1234567.89")
    assert money(amount, GERMAN) == "1.234.567,89"
    assert money(amount, BRITISH) == "1,234,567.89"
    assert money(amount, SWEDISH) == "1 234 567,89"
    assert money(amount, UNGROUPED) == "1234567,89"


def test_money_always_shows_the_cents() -> None:
    assert money(Decimal("40"), BRITISH) == "40.00"


def test_a_quantity_drops_the_zeros_money_keeps() -> None:
    assert quantity(Decimal("25.00"), GERMAN) == "25"
    assert quantity(Decimal("2.5"), GERMAN) == "2,5"
    assert quantity(Decimal("0.500"), GERMAN) == "0,5"


def test_a_round_hundred_is_not_printed_in_exponent_notation() -> None:
    """`Decimal("100").normalize()` is `1E+2`; nothing printed may ever read like that."""
    assert quantity(Decimal("100"), GERMAN) == "100"
    assert rate(Decimal("20"), GERMAN) == "20"
    assert plain(Decimal("1000")) == "1000"


def test_a_rate_is_whole_where_it_is_whole() -> None:
    assert rate(Decimal("19"), BRITISH) == "19"
    assert rate(Decimal("19.00"), BRITISH) == "19"
    assert rate(Decimal("5.5"), BRITISH) == "5.5"


def test_a_fractional_rate_reads_the_way_the_profile_writes_numbers() -> None:
    assert rate(Decimal("5.5"), GERMAN) == "5,5"
    assert rate(Decimal("5.5"), SWEDISH) == "5,5"


@pytest.mark.parametrize(
    ("date_format", "expected"),
    [
        (DateFormat.ISO, "2024-03-05"),
        (DateFormat.DAY_DOT_MONTH, "05.03.2024"),
        (DateFormat.DAY_SLASH_MONTH, "05/03/2024"),
        (DateFormat.MONTH_SLASH_DAY, "03/05/2024"),
        (DateFormat.DAY_MONTH_NAME, "5 March 2024"),
        (DateFormat.DAY_MONTH_ABBREVIATION, "05-Mar-2024"),
    ],
)
def test_every_date_format_a_profile_may_declare(date_format: DateFormat, expected: str) -> None:
    assert date_text(date(2024, 3, 5), date_format, load_lexicon("en")) == expected


def test_the_two_slashed_formats_write_the_same_day_two_ways() -> None:
    """Which of the two a document is in cannot be read off it, only declared: this is
    the fifth of March under one and the third of May under the other."""
    written = date(2024, 3, 5)
    english = load_lexicon("en")
    assert date_text(written, DateFormat.DAY_SLASH_MONTH, english) == "05/03/2024"
    assert date_text(written, DateFormat.MONTH_SLASH_DAY, english) == "03/05/2024"


def test_a_date_takes_its_month_names_from_the_language() -> None:
    written = date_text(date(2024, 3, 5), DateFormat.DAY_MONTH_NAME, load_lexicon("de"))
    assert written == "5 März 2024"


def test_wrapping_breaks_on_spaces_to_fit_the_column() -> None:
    lines = wrap("Sechskantschraube M8 x 40, verzinkt, DIN 933", 100.0, measure)
    assert all(measure(line) <= 100.0 for line in lines)
    assert " ".join(lines) == "Sechskantschraube M8 x 40, verzinkt, DIN 933"


def test_a_short_string_is_one_line() -> None:
    assert wrap("Kurz", 100.0, measure) == ("Kurz",)


def test_a_word_too_long_for_the_column_still_gets_a_line() -> None:
    assert wrap("Donaudampfschifffahrtsgesellschaft", 20.0, measure) == (
        "Donaudampfschifffahrtsgesellschaft",
    )


def test_nothing_wraps_to_nothing() -> None:
    assert wrap("", 100.0, measure) == ()
    assert wrap("   ", 100.0, measure) == ()
