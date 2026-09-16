"""Reading a date a vendor printed in its own language."""

from __future__ import annotations

from datetime import date

import pytest

from invoice_extractor.extraction.units.dates import parse_date
from invoice_extractor.profile.schema import Calendar

FRENCH = Calendar(
    months=(
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
    abbreviations=(
        "janv",
        "févr",
        "mars",
        "avr",
        "mai",
        "juin",
        "juil",
        "août",
        "sept",
        "oct",
        "nov",
        "déc",
    ),
)
NO_CALENDAR = Calendar(months=(), abbreviations=())


def test_a_numeric_format_reads_without_any_words() -> None:
    assert parse_date("15.03.2024", ("%d.%m.%Y",), NO_CALENDAR) == date(2024, 3, 15)


def test_the_first_format_that_reads_the_text_wins() -> None:
    formats = ("%Y-%m-%d", "%d.%m.%Y")
    assert parse_date("15.03.2024", formats, NO_CALENDAR) == date(2024, 3, 15)


def test_a_month_spelled_in_the_vendors_language_is_read() -> None:
    """`strptime` reads month names in the C locale, so `juin` needs the profile's own."""
    assert parse_date("14 juin 2024", ("%d %B %Y",), FRENCH) == date(2024, 6, 14)


def test_an_abbreviated_month_in_the_vendors_language_is_read() -> None:
    assert parse_date("14-juin-2024", ("%d-%b-%Y",), FRENCH) == date(2024, 6, 14)


def test_a_month_the_language_does_not_name_is_not_read() -> None:
    assert parse_date("14 June 2024", ("%d %B %Y",), FRENCH) is None


def test_a_spelled_format_with_no_calendar_reads_nothing() -> None:
    assert parse_date("14 juin 2024", ("%d %B %Y",), NO_CALENDAR) is None


def test_text_that_is_not_a_date_reads_as_nothing() -> None:
    assert parse_date("sometime in June", ("%d %B %Y", "%d.%m.%Y"), FRENCH) is None


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_reads_as_nothing(text: str) -> None:
    assert parse_date(text, ("%d.%m.%Y",), FRENCH) is None
