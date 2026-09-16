"""What a printed value looks like, told from its characters and nothing else."""

from __future__ import annotations

import re

import pytest

from invoice_extractor.drafting.shapes import (
    KnownId,
    Separators,
    Shape,
    date_formats_of,
    read,
    separators_of,
    without_currency,
)

MONTHS = frozenset({"juni", "juin", "jun", "june"})
KNOWN = (
    KnownId("DE", "DE", re.compile(r"\d{9}")),
    KnownId("AT", "ATU", re.compile(r"\d{8}")),
    KnownId("TR", "", re.compile(r"\d{10}")),
)


@pytest.mark.parametrize(
    ("value", "shape", "details"),
    [
        ("DE879668745", Shape.VAT_ID, ("DE",)),
        ("ATU 67706955", Shape.VAT_ID, ("AT",)),
        ("DE60 4273 1672 3268 6563 55", Shape.IBAN, ()),
        ("19 %", Shape.PERCENT, ("19",)),
        ("7,5%", Shape.PERCENT, ("7,5",)),
        ("14.06.2024", Shape.DATE, ("dd.mm.yyyy",)),
        ("2024-06-14", Shape.DATE, ("yyyy-mm-dd",)),
        ("14 Juni 2024", Shape.DATE, ("d Month yyyy",)),
        ("14-Jun-2024", Shape.DATE, ("dd-Mon-yyyy",)),
        ("12.275,00", Shape.AMOUNT, (",", ".")),
        ("EUR 1 234,56", Shape.AMOUNT, (",", " ")),
        ("1,234.50 €", Shape.AMOUNT, (".", ",")),
        ("19", Shape.AMOUNT, ("",)),
        ("EUR", Shape.CURRENCY, ("EUR",)),
        ("RG-2024-442182", Shape.IDENTIFIER, ()),
        ("C-87584", Shape.IDENTIFIER, ()),
        ("Rheinwerk Elektronik GmbH", Shape.TEXT, ()),
        ("ABC", Shape.CURRENCY, ("ABC",)),
    ],
)
def test_each_shape_is_read_off_the_value(
    value: str, shape: Shape, details: tuple[str, ...]
) -> None:
    reading = read(value, MONTHS, KNOWN)
    assert (reading.shape, reading.details) == (shape, details)


def test_a_country_whose_ids_carry_no_prefix_is_not_matched_by_shape() -> None:
    """Ten digits are a telephone number as often as a Turkish VAT id."""
    assert read("5551234567", MONTHS, KNOWN).shape is Shape.AMOUNT


def test_a_slashed_date_with_both_parts_at_or_below_twelve_names_both_formats() -> None:
    assert date_formats_of("03/04/2024", MONTHS) == ("dd/mm/yyyy", "mm/dd/yyyy")


def test_a_slashed_date_settles_the_format_when_one_part_exceeds_twelve() -> None:
    assert date_formats_of("14/06/2024", MONTHS) == ("dd/mm/yyyy",)
    assert date_formats_of("06/14/2024", MONTHS) == ("mm/dd/yyyy",)


def test_a_spelled_month_no_lexicon_knows_is_not_a_date() -> None:
    assert date_formats_of("14 Brumaire 2024", MONTHS) == ()
    assert date_formats_of("14-Bru-2024", MONTHS) == ()


def test_currency_codes_and_symbols_are_taken_off_an_amount() -> None:
    assert without_currency("EUR 1.234,56") == "1.234,56"
    assert without_currency("1.234,56 €") == "1.234,56"
    assert without_currency("£ 19.25 GBP") == "19.25"


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("1.234,56", Separators(",", (".",))),
        ("1 234,56", Separators(",", (" ",))),
        ("1,234", Separators("", (",",))),
        ("2,5", Separators(",", ())),
        ("115,0000", Separators(",", ())),
        ("-0,60", Separators(",", ())),
        ("1'234.56", Separators(".", ("'",))),
        ("1.234.567,89", Separators(",", (".",))),
    ],
)
def test_the_decimal_separator_is_the_one_not_followed_by_three_digits(
    number: str, expected: Separators
) -> None:
    assert separators_of(number) == expected
