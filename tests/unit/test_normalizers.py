"""Raw text to a typed value, under the profile's own separators and date formats."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from conftest import line, make_profile
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.normalizers import (
    parse_date,
    parse_money,
    parse_number,
    parse_percent,
    strip_label,
    upper_alnum,
)
from invoice_extractor.extraction.spec import Candidate


def candidate(raw_text: str, label: str | None = "Label") -> Candidate:
    source = line(raw_text, 400, 620)
    evidence = Evidence(1, source.bbox, label, Strategy.LABEL_RIGHT, raw_text)
    return Candidate(raw_text=raw_text, evidence=evidence, zone=source.zone, label_distance=0.0)


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
def test_parse_money(
    text: str, decimal_separator: str, thousands_separators: tuple[str, ...], expected: str
) -> None:
    profile = make_profile(
        decimal_separator=decimal_separator, thousands_separators=thousands_separators
    )
    assert parse_money(candidate(f"Label: {text}"), profile) == Decimal(expected)


def test_parse_money_returns_none_for_text_that_is_not_a_number() -> None:
    assert parse_money(candidate("Label: abc"), make_profile()) is None


def test_parse_number_reads_raw_text_without_a_label() -> None:
    profile = make_profile(decimal_separator=",", thousands_separators=(" ",))
    assert parse_number("2 670,00", profile) == Decimal("2670.00")


def test_parse_date_tries_formats_in_order() -> None:
    profile = make_profile(date_formats=("%d %b %Y", "%Y-%m-%d"))
    assert parse_date(candidate("Label: 15 Mar 2024"), profile) == date(2024, 3, 15)
    assert parse_date(candidate("Label: 2024-05-02"), profile) == date(2024, 5, 2)


def test_parse_date_returns_none_when_no_format_matches() -> None:
    assert parse_date(candidate("Label: 15/03/2024"), make_profile()) is None


def test_parse_percent_strips_percent_sign() -> None:
    profile = make_profile(decimal_separator=",", thousands_separators=(" ",))
    assert parse_percent(candidate("Label: 25,00%"), profile) == Decimal("25.00")


def test_upper_alnum_drops_punctuation() -> None:
    assert upper_alnum(candidate("Label: se-556 123 456 701"), make_profile()) == "SE556123456701"


def test_strip_label_keeps_a_colon_inside_a_value_the_label_did_not_introduce() -> None:
    """`label_beside` hands over the value alone, so a colon inside it is the value's own."""
    found = candidate("Ref: 12:30", label="Unsere Referenz")
    assert strip_label(found, make_profile()) == "Ref: 12:30"


def test_strip_label_without_label_returns_stripped_text() -> None:
    assert strip_label(candidate("  GB123456789  ", label=None), make_profile()) == "GB123456789"


def test_strip_label_keeps_a_labelless_line_whole_when_it_has_no_colon() -> None:
    assert (
        strip_label(candidate("Nordwind Logistik GmbH"), make_profile()) == "Nordwind Logistik GmbH"
    )
