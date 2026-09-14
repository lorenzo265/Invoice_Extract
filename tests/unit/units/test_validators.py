"""Does a normalized value look like what the field is supposed to hold?"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import make_field_profile
from invoice_extractor.extraction.units.validators import (
    is_date,
    is_identifier,
    is_vat_id,
    matches_pattern,
)

ANY = make_field_profile()


def test_matches_pattern_uses_the_default_when_the_profile_declares_none() -> None:
    assert matches_pattern(r"[A-Z]{3}")("EUR", ANY)
    assert not matches_pattern(r"[A-Z]{3}")("EURO", ANY)


def test_matches_pattern_prefers_the_profiles_own_pattern() -> None:
    declared = make_field_profile(pattern=r"\d{4}-\d{5}")
    matches = matches_pattern(r"[A-Z]{3}")
    assert matches("2024-00042", declared)
    assert not matches("EUR", declared)


def test_is_date_accepts_only_a_date() -> None:
    assert is_date(date(2024, 3, 15), ANY)
    assert not is_date("2024-03-15", ANY)


def test_is_identifier_wants_something_shaped_like_a_reference() -> None:
    assert is_identifier("INV-2024/0042", ANY)
    assert not is_identifier("X", ANY)


@pytest.mark.parametrize("value", ["DE811234567", "ATU67706955", "0826555744"])
def test_is_vat_id_accepts_a_registration_number(value: str) -> None:
    assert is_vat_id(value, ANY)


def test_is_vat_id_refuses_a_label_with_its_punctuation_taken_out() -> None:
    """`Kunden-USt-IdNr.` folds to the right length and the right alphabet, and is a label."""
    assert not is_vat_id("KUNDENUSTIDNR", ANY)
