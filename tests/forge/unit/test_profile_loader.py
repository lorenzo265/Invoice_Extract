"""Every message the profile loader raises names the key that is wrong."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from dataspec import message, write

from invoice_forge.families import Family
from invoice_forge.jsonspec import SpecError
from invoice_forge.model import ChargeType, CreditNoteStyle
from invoice_forge.profiles.loader import bundled_profile_ids, load_profile
from invoice_forge.profiles.schema import DateFormat, FontFamily, PostalCodePosition


def base() -> dict[str, Any]:
    """A profile that loads cleanly; every test below breaks exactly one thing in it."""
    return {
        "id": "xx-XX",
        "country": "XX",
        "language": "xx",
        "currency": "EUR",
        "secondary_currency": None,
        "decimal_separator": ",",
        "thousands_separators": [".", " "],
        "date_formats": ["dd.mm.yyyy"],
        "vat_rates": {"standard": "19", "reduced": "7", "zero": "0"},
        "vat_id_pattern": "XX\\d{9}",
        "address_format": {"postal_code_position": "before_city", "country_line": True},
        "lexicon": "xx",
        "charges_used": ["SHIPPING"],
        "prints_supply_date": True,
        "credit_note_style": "negative_amounts",
        "extensions": ["contract_number"],
        "families": ["classic"],
        "fonts": "sans",
    }


def error(tmp_path: Path, data: object) -> str:
    return message(load_profile, tmp_path, "profile", data)


def test_a_valid_profile_loads(tmp_path: Path) -> None:
    profile = load_profile(write(tmp_path, "profile", base()))
    assert profile.id == "xx-XX"
    assert profile.date_formats == (DateFormat.DAY_DOT_MONTH,)
    assert profile.charges_used == (ChargeType.SHIPPING,)
    assert profile.credit_note_style is CreditNoteStyle.NEGATIVE_AMOUNTS
    assert profile.families == (Family.CLASSIC,)
    assert profile.fonts is FontFamily.SANS
    assert profile.address_format.postal_code_position is PostalCodePosition.BEFORE_CITY
    assert profile.secondary_currency is None


@pytest.mark.parametrize("key", ["id", "country", "language", "currency", "lexicon"])
def test_a_missing_text_key_names_itself(tmp_path: Path, key: str) -> None:
    data = base()
    del data[key]
    assert error(tmp_path, data) == f"{key} is required"


def test_an_unknown_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["decimal_seperator"] = ","
    assert error(tmp_path, data) == "decimal_seperator is not a recognized profile key"


def test_a_profile_must_be_an_object(tmp_path: Path) -> None:
    assert error(tmp_path, ["not", "an", "object"]) == "profile must be a JSON object"


def test_a_missing_file_names_the_path_it_looked_for() -> None:
    with pytest.raises(SpecError, match="profile file not found"):
        load_profile("no_such_vendor")


def test_invalid_json_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(SpecError, match="invalid JSON in"):
        load_profile(str(path))


def test_a_decimal_separator_is_one_character(tmp_path: Path) -> None:
    data = base()
    data["decimal_separator"] = ",,"
    assert error(tmp_path, data) == "decimal_separator must be a single character"


def test_a_thousands_separator_is_one_character_or_none(tmp_path: Path) -> None:
    data = base()
    data["thousands_separators"] = ["  "]
    assert error(tmp_path, data) == "thousands_separators[0] must be a single character or empty"


def test_a_thousands_separator_may_not_be_the_decimal_one(tmp_path: Path) -> None:
    data = base()
    data["thousands_separators"] = [".", ","]
    assert error(tmp_path, data) == "thousands_separators[1] must differ from decimal_separator"


def test_at_least_one_thousands_separator_is_required(tmp_path: Path) -> None:
    data = base()
    data["thousands_separators"] = []
    assert error(tmp_path, data) == "thousands_separators must be a non-empty list of strings"


def test_an_unknown_date_format_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["date_formats"] = ["dd.mm.yyyy", "mm/dd/yyyy"]
    assert error(tmp_path, data).startswith("date_formats[1] must be one of: ")


def test_a_vat_rate_is_a_decimal_written_as_a_string(tmp_path: Path) -> None:
    data = base()
    data["vat_rates"]["standard"] = "nineteen"
    assert error(tmp_path, data) == "vat_rates.standard must be a decimal written as a string"


def test_a_missing_vat_rate_names_itself(tmp_path: Path) -> None:
    data = base()
    del data["vat_rates"]["zero"]
    assert error(tmp_path, data) == "vat_rates.zero is required"


def test_an_extra_vat_rate_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["vat_rates"]["luxury"] = "33"
    assert error(tmp_path, data) == "vat_rates.luxury is not a recognized rate"


def test_vat_rates_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["vat_rates"] = ["19", "7", "0"]
    assert error(tmp_path, data).startswith("vat_rates must be an object")


def test_an_unknown_postal_code_position_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["address_format"]["postal_code_position"] = "inline"
    assert error(tmp_path, data).startswith("address_format.postal_code_position must be one of: ")


def test_the_country_line_flag_must_be_a_boolean(tmp_path: Path) -> None:
    data = base()
    data["address_format"]["country_line"] = "yes"
    assert error(tmp_path, data) == "address_format.country_line must be true or false"


def test_an_extra_address_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["address_format"]["region"] = "north"
    assert error(tmp_path, data) == "address_format.region is not a recognized address key"


def test_an_unknown_charge_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["charges_used"] = ["SHIPPING", "GRATUITY"]
    assert error(tmp_path, data).startswith("charges_used[1] must be one of: ")


def test_an_unknown_extension_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["extensions"] = ["lucky_number"]
    assert error(tmp_path, data).startswith("extensions[0] must be one of: ")


def test_an_unknown_family_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["families"] = ["baroque"]
    assert error(tmp_path, data).startswith("families[0] must be one of: ")


def test_an_unknown_credit_note_style_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["credit_note_style"] = "red_ink"
    assert error(tmp_path, data).startswith("credit_note_style must be one of: ")


def test_prints_supply_date_must_be_a_boolean(tmp_path: Path) -> None:
    data = base()
    data["prints_supply_date"] = "sometimes"
    assert error(tmp_path, data) == "prints_supply_date must be true or false"


def test_a_secondary_currency_may_be_given(tmp_path: Path) -> None:
    data = base()
    data["secondary_currency"] = "USD"
    assert load_profile(write(tmp_path, "profile", data)).secondary_currency == "USD"


def test_a_bundled_profile_loads_by_id() -> None:
    assert load_profile("de-DE").language == "de"


def test_the_bundled_profiles_are_the_four_this_pull_request_ships() -> None:
    assert bundled_profile_ids() == ("de-DE", "en-GB", "fr-FR", "sv-SE")
