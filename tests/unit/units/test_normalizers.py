"""Raw text to a typed value, in the vendor's own separators and words."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from conftest import line, make_profile
from invoice_extractor.document.model import Zone
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.extraction.units.normalizers import (
    parse_date,
    parse_number,
    strip_label,
    upper_alnum,
    without_currency,
)


def candidate(text: str, label: str | None = "Label") -> Candidate:
    drawn = line(text, 400, 76)
    evidence = Evidence(1, drawn.bbox, label, Strategy.LABEL_RIGHT, text)
    return Candidate(raw_text=text, evidence=evidence, zone=Zone(1, 3), label_distance=0.0)


@pytest.mark.parametrize(
    ("text", "decimal_separator", "thousands_separators", "expected"),
    [
        ("1,234.56", ".", (",",), "1234.56"),
        ("3 216,00", ",", (" ",), "3216.00"),
        ("-12.5", ".", ("",), "-12.5"),
        ("490.00", ".", (",",), "490.00"),
        ("1.234 567,89", ",", (".", " "), "1234567.89"),
    ],
)
def test_parse_number_reads_a_vendors_own_separators(
    text: str, decimal_separator: str, thousands_separators: tuple[str, ...], expected: str
) -> None:
    profile = make_profile(
        decimal_separator=decimal_separator, thousands_separators=thousands_separators
    )
    assert parse_number(text, profile) == Decimal(expected)


def test_a_currency_code_printed_beside_an_amount_comes_off_before_it_is_parsed() -> None:
    profile = make_profile()
    assert parse_number(without_currency("1,234.56 GBP", profile), profile) == Decimal("1234.56")


def test_parse_number_returns_none_for_text_that_is_not_a_number() -> None:
    assert parse_number("abc", make_profile()) is None


def test_parse_date_tries_the_formats_in_the_profile_order() -> None:
    profile = make_profile(date_formats=("%d %b %Y", "%Y-%m-%d"))
    assert parse_date(candidate("Label: 15 Mar 2024"), profile) == date(2024, 3, 15)
    assert parse_date(candidate("Label: 2024-05-02"), profile) == date(2024, 5, 2)


def test_parse_date_returns_none_when_no_format_reads_the_text() -> None:
    assert parse_date(candidate("Label: sometime"), make_profile()) is None


def test_strip_label_keeps_a_value_handed_over_on_its_own() -> None:
    """`label_beside` gives the value alone, so a colon inside it is the value's."""
    assert strip_label(candidate("14:30", label="Label"), make_profile()) == "14:30"


def test_strip_label_drops_the_label_the_line_starts_with() -> None:
    assert strip_label(candidate("Label: INV-42"), make_profile()) == "INV-42"


def test_strip_label_keeps_everything_when_no_label_was_matched() -> None:
    assert strip_label(candidate("INV-42", label=None), make_profile()) == "INV-42"


def test_upper_alnum_keeps_letters_and_digits_only() -> None:
    assert upper_alnum(candidate("Label: de 811 234 567"), make_profile()) == "DE811234567"
