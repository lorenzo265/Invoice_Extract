"""Raw text to a typed value, under the layout's own separators and date formats."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from conftest import line, make_layout
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
    ("text", "decimal_separator", "thousands_separator", "expected"),
    [
        ("1,234.56", ".", ",", "1234.56"),
        ("3 216,00", ",", " ", "3216.00"),
        ("-12.5", ".", "", "-12.5"),
        ("490.00", ".", ",", "490.00"),
    ],
)
def test_parse_money(
    text: str, decimal_separator: str, thousands_separator: str, expected: str
) -> None:
    layout = make_layout(
        decimal_separator=decimal_separator, thousands_separator=thousands_separator
    )
    assert parse_money(candidate(f"Label: {text}"), layout) == Decimal(expected)


def test_parse_money_returns_none_for_text_that_is_not_a_number() -> None:
    assert parse_money(candidate("Label: abc"), make_layout()) is None


def test_parse_number_reads_raw_text_without_a_label() -> None:
    layout = make_layout(decimal_separator=",", thousands_separator=" ")
    assert parse_number("2 670,00", layout) == Decimal("2670.00")


def test_parse_date_tries_formats_in_order() -> None:
    layout = make_layout(date_formats=("%d %b %Y", "%Y-%m-%d"))
    assert parse_date(candidate("Label: 15 Mar 2024"), layout) == date(2024, 3, 15)
    assert parse_date(candidate("Label: 2024-05-02"), layout) == date(2024, 5, 2)


def test_parse_date_returns_none_when_no_format_matches() -> None:
    assert parse_date(candidate("Label: 15/03/2024"), make_layout()) is None


def test_parse_percent_strips_percent_sign() -> None:
    layout = make_layout(decimal_separator=",", thousands_separator=" ")
    assert parse_percent(candidate("Label: 25,00%"), layout) == Decimal("25.00")


def test_upper_alnum_drops_punctuation() -> None:
    assert upper_alnum(candidate("Label: se-556 123 456 701"), make_layout()) == "SE556123456701"


def test_strip_label_without_label_returns_stripped_text() -> None:
    assert strip_label(candidate("  GB123456789  ", label=None), make_layout()) == "GB123456789"


def test_strip_label_keeps_a_labelless_line_whole_when_it_has_no_colon() -> None:
    assert (
        strip_label(candidate("Nordwind Logistik GmbH"), make_layout()) == "Nordwind Logistik GmbH"
    )
