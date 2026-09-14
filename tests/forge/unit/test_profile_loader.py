"""Every message the profile loader raises names the key that is wrong."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from dataspec import message, write

from invoice_forge.families import Family
from invoice_forge.jsonspec import SpecError
from invoice_forge.model import ChargeType, CreditNoteStyle
from invoice_forge.profiles.loader import load_profile, profile_ids
from invoice_forge.profiles.schema import DateFormat, FontFamily, PostalCodePosition


def base() -> dict[str, Any]:
    """A profile that loads cleanly; every test below breaks exactly one thing in it."""
    return {
        "id": "xx-XX",
        "country": "XX",
        "language": "xx",
        "lexicon": "xx",
        "number_format": {"decimal_separator": ",", "thousands_separators": [".", " "]},
        "date_formats": ["dd.mm.yyyy"],
        "currencies": ["EUR"],
        "vat": {
            "rates": {"standard": "19", "reduced": "7", "zero": "0"},
            "id_prefix": "XX",
            "id_pattern": "\\d{9}",
        },
        "supplier": {
            "name": "Beispiel Handel GmbH",
            "aliases": ["Beispiel"],
            "address_lines": ["Am Hafen 1", "47119 Duisburg"],
            "vat_id": "XX123456789",
        },
        "custom_fields": [{"name": "contract_number"}],
        "render": {
            "address_format": {"postal_code_position": "before_city", "country_line": True},
            "charges_used": ["SHIPPING"],
            "prints_supply_date": True,
            "credit_note_style": "negative_amounts",
            "families": ["classic"],
            "fonts": "sans",
        },
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


def test_a_profile_declares_the_vendor_it_describes(tmp_path: Path) -> None:
    """One vendor per profile (ADR-0006), so the supplier is data rather than a draw."""
    profile = load_profile(write(tmp_path, "profile", base()))
    assert profile.supplier.name == "Beispiel Handel GmbH"
    assert profile.supplier.address_lines == ("Am Hafen 1", "47119 Duisburg")
    assert profile.supplier.vat_id == "XX123456789"


def test_the_vat_id_pattern_is_the_prefix_and_the_digits_after_it(tmp_path: Path) -> None:
    assert load_profile(write(tmp_path, "profile", base())).vat_id_pattern == "XX\\d{9}"


@pytest.mark.parametrize("key", ["id", "country", "language", "lexicon"])
def test_a_missing_text_key_names_itself(tmp_path: Path, key: str) -> None:
    data = base()
    del data[key]
    assert error(tmp_path, data) == f"{key} is required"


def test_an_unknown_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["decimal_seperator"] = ","
    assert error(tmp_path, data) == "decimal_seperator is not a recognized profile key"


def test_a_key_the_extractor_reads_is_not_an_unknown_key(tmp_path: Path) -> None:
    """The file describes one vendor to two programs; each ignores the other's half."""
    data = base()
    data["fields"] = {"invoice_number": {"labels": ["Rechnungsnummer"]}}
    assert load_profile(write(tmp_path, "profile", data)).id == "xx-XX"


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
    data["number_format"]["decimal_separator"] = ",,"
    assert error(tmp_path, data) == "number_format.decimal_separator must be a single character"


def test_a_thousands_separator_is_one_character_or_none(tmp_path: Path) -> None:
    data = base()
    data["number_format"]["thousands_separators"] = ["  "]
    assert error(tmp_path, data) == (
        "number_format.thousands_separators[0] must be a single character or empty"
    )


def test_a_thousands_separator_may_not_be_the_decimal_one(tmp_path: Path) -> None:
    data = base()
    data["number_format"]["thousands_separators"] = [".", ","]
    assert error(tmp_path, data) == (
        "number_format.thousands_separators[1] must differ from decimal_separator"
    )


def test_at_least_one_thousands_separator_is_required(tmp_path: Path) -> None:
    data = base()
    data["number_format"]["thousands_separators"] = []
    assert error(tmp_path, data) == (
        "number_format.thousands_separators must be a non-empty list of strings"
    )


def test_at_least_one_currency_is_required(tmp_path: Path) -> None:
    data = base()
    data["currencies"] = []
    assert error(tmp_path, data) == "currencies must be a non-empty list of strings"


def test_an_unknown_date_format_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["date_formats"] = ["dd.mm.yyyy", "mm/dd/yyyy"]
    assert error(tmp_path, data).startswith("date_formats[1] must be one of: ")


def test_a_vat_rate_is_a_decimal_written_as_a_string(tmp_path: Path) -> None:
    data = base()
    data["vat"]["rates"]["standard"] = "nineteen"
    assert error(tmp_path, data) == "vat.rates.standard must be a decimal written as a string"


def test_a_missing_vat_rate_names_itself(tmp_path: Path) -> None:
    data = base()
    del data["vat"]["rates"]["zero"]
    assert error(tmp_path, data) == "vat.rates.zero is required"


def test_an_extra_vat_rate_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["vat"]["rates"]["luxury"] = "33"
    assert error(tmp_path, data) == "vat.rates.luxury is not a recognized rate"


def test_vat_rates_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["vat"]["rates"] = ["19", "7", "0"]
    assert error(tmp_path, data).startswith("vat.rates must be an object")


def test_an_unknown_vat_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["vat"]["checksum"] = "mod97"
    assert error(tmp_path, data) == "vat.checksum is not a recognized vat key"


def test_a_supplier_needs_an_address(tmp_path: Path) -> None:
    data = base()
    data["supplier"]["address_lines"] = []
    assert error(tmp_path, data) == "supplier.address_lines must be a non-empty list of strings"


def test_an_unknown_postal_code_position_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["render"]["address_format"]["postal_code_position"] = "inline"
    assert error(tmp_path, data).startswith(
        "render.address_format.postal_code_position must be one of: "
    )


def test_the_country_line_flag_must_be_a_boolean(tmp_path: Path) -> None:
    data = base()
    data["render"]["address_format"]["country_line"] = "yes"
    assert error(tmp_path, data) == "render.address_format.country_line must be true or false"


def test_an_extra_address_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["render"]["address_format"]["region"] = "north"
    assert error(tmp_path, data) == "render.address_format.region is not a recognized address key"


def test_an_extra_render_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["render"]["watermark"] = "COPY"
    assert error(tmp_path, data) == "render.watermark is not a recognized render key"


def test_an_unknown_charge_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["render"]["charges_used"] = ["SHIPPING", "GRATUITY"]
    assert error(tmp_path, data).startswith("render.charges_used[1] must be one of: ")


def test_custom_fields_must_be_a_list_of_objects(tmp_path: Path) -> None:
    data = base()
    data["custom_fields"] = ["contract_number"]
    assert error(tmp_path, data) == "custom_fields must be a list of objects"


def test_a_vat_prefix_must_be_a_string(tmp_path: Path) -> None:
    data = base()
    data["vat"]["id_prefix"] = 49
    assert error(tmp_path, data) == "vat.id_prefix must be a string"


def test_an_unknown_custom_field_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["custom_fields"] = [{"name": "lucky_number"}]
    assert error(tmp_path, data).startswith("custom_fields[0].name must be one of: ")


def test_an_unknown_family_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["render"]["families"] = ["baroque"]
    assert error(tmp_path, data).startswith("render.families[0] must be one of: ")


def test_an_unknown_credit_note_style_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["render"]["credit_note_style"] = "red_ink"
    assert error(tmp_path, data).startswith("render.credit_note_style must be one of: ")


def test_prints_supply_date_must_be_a_boolean(tmp_path: Path) -> None:
    data = base()
    data["render"]["prints_supply_date"] = "sometimes"
    assert error(tmp_path, data) == "render.prints_supply_date must be true or false"


def test_a_second_currency_is_the_one_a_document_echoes(tmp_path: Path) -> None:
    data = base()
    data["currencies"] = ["EUR", "USD"]
    assert load_profile(write(tmp_path, "profile", data)).secondary_currency == "USD"


def test_a_shipped_profile_loads_by_id() -> None:
    assert load_profile("de-DE").language == "de"


def test_every_shipped_profile_is_named_for_the_country_and_language_it_declares() -> None:
    """`fr-BE` is French printed in Belgium; the id is the only place that says so twice."""
    for profile_id in profile_ids():
        profile = load_profile(profile_id)
        assert profile.id == profile_id
        assert profile_id == f"{profile.language}-{profile.country}"
