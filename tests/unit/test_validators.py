"""Each validator, in both directions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from conftest import make_field_layout
from invoice_extractor.extraction.validators import (
    is_currency_code,
    is_date,
    is_percent,
    is_positive_money,
    matches_pattern,
)

ANY_FIELD = make_field_layout()


def test_matches_pattern_accepts_and_rejects_by_shape() -> None:
    validator = matches_pattern(r"[A-Z0-9][A-Z0-9/-]{2,}")
    assert validator("INV-2024-0042", ANY_FIELD)
    assert not validator("x", ANY_FIELD)


def test_matches_pattern_prefers_layout_regex() -> None:
    validator = matches_pattern(r"[A-Z]{3}")
    with_regex = make_field_layout(regex=r"\d{4}-\d{5}")
    assert validator("2024-00873", with_regex)
    assert not validator("ABC", with_regex)


def test_is_date() -> None:
    assert is_date(date(2024, 3, 15), ANY_FIELD)
    assert not is_date("2024-03-15", ANY_FIELD)


def test_is_positive_money() -> None:
    assert is_positive_money(Decimal("0.01"), ANY_FIELD)
    assert not is_positive_money(Decimal("0.00"), ANY_FIELD)
    assert not is_positive_money("490.00", ANY_FIELD)


def test_is_currency_code() -> None:
    assert is_currency_code("GBP", ANY_FIELD)
    assert not is_currency_code("GB", ANY_FIELD)
    assert not is_currency_code("gbp", ANY_FIELD)


def test_is_percent() -> None:
    assert is_percent(Decimal("0"), ANY_FIELD)
    assert is_percent(Decimal("100"), ANY_FIELD)
    assert not is_percent(Decimal("100.01"), ANY_FIELD)
    assert not is_percent(Decimal("-1"), ANY_FIELD)
    assert not is_percent("20.00", ANY_FIELD)
