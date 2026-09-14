"""Every `LayoutError` message docs/LAYOUT_FORMAT.md promises, one test each."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from invoice_extractor.document.reader import Zone
from invoice_extractor.layout.loader import TOP_LEVEL_KEYS, load_layout
from invoice_extractor.layout.schema import FIELD_NAMES, LINE_ITEM_COLUMNS, LayoutError


def base() -> dict[str, Any]:
    """A layout that loads cleanly; every test below breaks exactly one thing in it."""
    return {
        "id": "test",
        "language": "en",
        "decimal_separator": ".",
        "thousands_separator": ",",
        "date_formats": ["%d %b %Y"],
        "currency_symbols": {"GBP": "£"},
        "fields": {name: {"labels": [name], "zones": ["TOP_RIGHT"]} for name in FIELD_NAMES},
        "line_items": {
            "header_labels": {column: [column] for column in LINE_ITEM_COLUMNS},
            "stop_labels": ["Subtotal"],
        },
    }


def write(tmp_path: Path, data: object) -> str:
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def message(tmp_path: Path, data: object) -> str:
    with pytest.raises(LayoutError) as raised:
        load_layout(write(tmp_path, data))
    return str(raised.value)


def test_a_valid_layout_loads(tmp_path: Path) -> None:
    layout = load_layout(write(tmp_path, base()))
    assert layout.id == "test"
    assert layout.fields["invoice_number"].zones == (Zone.TOP_RIGHT,)
    assert layout.fields["invoice_number"].regex is None
    assert layout.line_items.stop_labels == ("Subtotal",)


@pytest.mark.parametrize("key", TOP_LEVEL_KEYS)
def test_missing_required_key_names_the_key(tmp_path: Path, key: str) -> None:
    data = base()
    del data[key]
    assert message(tmp_path, data) == f"{key} is required"


def test_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["decimal_seperator"] = "."
    assert message(tmp_path, data) == "decimal_seperator is not a recognized top-level key"


def test_layout_must_be_a_json_object(tmp_path: Path) -> None:
    assert message(tmp_path, ["not", "an", "object"]) == "layout must be a JSON object"


@pytest.mark.parametrize("key", ["id", "language"])
def test_identity_keys_must_be_non_empty_strings(tmp_path: Path, key: str) -> None:
    data = base()
    data[key] = ""
    assert message(tmp_path, data) == f"{key} must be a non-empty string"


def test_decimal_separator_must_be_a_single_character(tmp_path: Path) -> None:
    data = base()
    data["decimal_separator"] = ".."
    assert message(tmp_path, data) == "decimal_separator must be a single character"


def test_thousands_separator_may_be_empty(tmp_path: Path) -> None:
    data = base()
    data["thousands_separator"] = ""
    assert load_layout(write(tmp_path, data)).thousands_separator == ""


def test_thousands_separator_must_be_a_single_character_or_empty(tmp_path: Path) -> None:
    data = base()
    data["thousands_separator"] = "  "
    assert message(tmp_path, data) == "thousands_separator must be a single character or empty"


def test_separators_must_differ(tmp_path: Path) -> None:
    data = base()
    data["thousands_separator"] = "."
    assert message(tmp_path, data) == "decimal_separator and thousands_separator must be different"


def test_date_formats_must_be_a_non_empty_list_of_strings(tmp_path: Path) -> None:
    data = base()
    data["date_formats"] = []
    assert message(tmp_path, data) == "date_formats must be a non-empty list of strings"


def test_currency_symbols_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["currency_symbols"] = ["GBP"]
    expected = "currency_symbols must be an object mapping currency codes to symbols"
    assert message(tmp_path, data) == expected


def test_currency_symbols_value_must_be_a_string(tmp_path: Path) -> None:
    data = base()
    data["currency_symbols"] = {"GBP": 1}
    expected = "currency_symbols must be an object mapping currency codes to symbols"
    assert message(tmp_path, data) == expected


def test_currency_symbols_key_must_be_a_currency_code(tmp_path: Path) -> None:
    data = base()
    data["currency_symbols"] = {"pounds": "£"}
    expected = "currency_symbols has a key that is not a 3-letter uppercase currency code: pounds"
    assert message(tmp_path, data) == expected


def test_fields_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["fields"] = []
    assert (
        message(tmp_path, data) == "fields must be an object mapping field names to field layouts"
    )


def test_extra_field_name_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["fields"]["vatrate"] = {"labels": ["VAT Rate"], "zones": ["BOTTOM_RIGHT"]}
    assert message(tmp_path, data) == "fields.vatrate is not a recognized field"


def test_missing_field_is_reported(tmp_path: Path) -> None:
    data = base()
    del data["fields"]["due_date"]
    assert message(tmp_path, data) == "fields.due_date is required"


def test_field_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["fields"]["currency"] = "Currency"
    assert message(tmp_path, data) == "fields.currency must be an object"


def test_unknown_key_inside_a_field_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["fields"]["currency"]["zone"] = "TOP_RIGHT"
    assert message(tmp_path, data) == "fields.currency.zone is not a recognized key"


@pytest.mark.parametrize("labels", [[], "Invoice Number", [1, 2]])
def test_field_labels_must_be_non_empty_list(tmp_path: Path, labels: object) -> None:
    data = base()
    data["fields"]["invoice_number"]["labels"] = labels
    expected = "fields.invoice_number.labels must be a non-empty list of strings"
    assert message(tmp_path, data) == expected


def test_field_zones_must_be_non_empty_list(tmp_path: Path) -> None:
    data = base()
    data["fields"]["invoice_number"]["zones"] = []
    assert (
        message(tmp_path, data) == "fields.invoice_number.zones must be a non-empty list of strings"
    )


def test_unknown_zone_name_reports_index(tmp_path: Path) -> None:
    data = base()
    data["fields"]["invoice_number"]["zones"] = ["TOP_RIGHT", "MIDDLE"]
    expected = "fields.invoice_number.zones[1] is not a recognized zone name: MIDDLE"
    assert message(tmp_path, data) == expected


def test_regex_must_be_a_string(tmp_path: Path) -> None:
    data = base()
    data["fields"]["invoice_number"]["regex"] = 42
    assert message(tmp_path, data) == "fields.invoice_number.regex must be a string"


def test_invalid_regex_reports_re_error(tmp_path: Path) -> None:
    data = base()
    data["fields"]["invoice_number"]["regex"] = "[unterminated"
    assert message(tmp_path, data).startswith(
        "fields.invoice_number.regex is not a valid regular expression: "
    )


def test_regex_is_compiled_at_load_time(tmp_path: Path) -> None:
    data = base()
    data["fields"]["invoice_number"]["regex"] = r"INV-\d{4}-\d{4}"
    compiled = load_layout(write(tmp_path, data)).fields["invoice_number"].regex
    assert compiled is not None
    assert compiled.fullmatch("INV-2024-0042")


def test_line_items_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["line_items"] = []
    assert (
        message(tmp_path, data) == "line_items must be an object with header_labels and stop_labels"
    )


def test_unknown_key_inside_line_items_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["line_items"]["footer_labels"] = []
    assert message(tmp_path, data) == "line_items.footer_labels is not a recognized key"


def test_missing_line_item_column_is_reported(tmp_path: Path) -> None:
    data = base()
    del data["line_items"]["header_labels"]["quantity"]
    assert message(tmp_path, data) == "line_items.header_labels.quantity is required"


def test_unknown_line_item_column_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["line_items"]["header_labels"]["vat"] = ["VAT"]
    assert message(tmp_path, data) == "line_items.header_labels.vat is not a recognized column"


def test_header_labels_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["line_items"]["header_labels"] = []
    expected = "line_items.header_labels must be an object mapping columns to header words"
    assert message(tmp_path, data) == expected


def test_line_item_column_must_be_a_non_empty_list(tmp_path: Path) -> None:
    data = base()
    data["line_items"]["header_labels"]["sku"] = []
    expected = "line_items.header_labels.sku must be a non-empty list of strings"
    assert message(tmp_path, data) == expected


def test_stop_labels_must_be_a_list_of_strings(tmp_path: Path) -> None:
    data = base()
    data["line_items"]["stop_labels"] = "Subtotal"
    assert message(tmp_path, data) == "line_items.stop_labels must be a list of strings"


def test_stop_labels_may_be_empty(tmp_path: Path) -> None:
    data = base()
    data["line_items"]["stop_labels"] = []
    assert load_layout(write(tmp_path, data)).line_items.stop_labels == ()


def test_file_not_found_message_names_resolved_path() -> None:
    with pytest.raises(LayoutError) as raised:
        load_layout("no_such_vendor")
    expected = Path("layouts") / "no_such_vendor.json"
    assert str(raised.value) == f"layout file not found: {expected}"


def test_invalid_json_message(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(LayoutError) as raised:
        load_layout(str(path))
    assert str(raised.value).startswith(f"invalid JSON in {path}: ")


def test_id_resolves_to_layouts_directory() -> None:
    assert load_layout("acme").id == "acme"


def test_path_with_slash_is_used_directly() -> None:
    assert load_layout("layouts/nordic.json").id == "nordic"
