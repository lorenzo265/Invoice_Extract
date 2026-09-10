"""The shared validation vocabulary: every refusal names the key that caused it."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from invoice_forge.jsonspec import (
    SpecError,
    optional_text,
    read_object,
    reject_unknown,
    require_choice,
    require_choices,
    require_decimal,
    require_filled_strings,
    require_flag,
    require_mapping,
    require_strings,
    require_text,
    required,
)

ALLOWED = ("north", "south")


def test_a_missing_key_names_itself() -> None:
    with pytest.raises(SpecError, match=r"^a.b is required$"):
        required({}, "b", "a.b")


def test_a_present_key_is_returned_whatever_it_holds() -> None:
    assert required({"b": None}, "b", "a.b") is None


@pytest.mark.parametrize("value", [12, None, [], {}, ""])
def test_text_that_is_not_a_filled_string_is_refused(value: object) -> None:
    with pytest.raises(SpecError, match=r"^name must be a non-empty string$"):
        require_text({"name": value}, "name", "name")


@pytest.mark.parametrize("value", ["yes", 1, 0, None])
def test_a_flag_that_is_not_a_boolean_is_refused(value: object) -> None:
    with pytest.raises(SpecError, match=r"^on must be true or false$"):
        require_flag({"on": value}, "on", "on")


def test_a_flag_reads_both_ways() -> None:
    assert require_flag({"on": True}, "on", "on") is True
    assert require_flag({"on": False}, "on", "on") is False


def test_a_mapping_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(SpecError, match=r"^block must be a table of rates$"):
        require_mapping({"block": ["a"]}, "block", "block", "a table of rates")


@pytest.mark.parametrize("value", [["a", 2], "abc", {"a": "b"}, None])
def test_a_list_of_strings_that_is_not_one_is_refused(value: object) -> None:
    with pytest.raises(SpecError, match=r"^words must be a list of strings$"):
        require_strings({"words": value}, "words", "words")


def test_an_empty_list_of_strings_is_allowed_where_emptiness_is_meaningful() -> None:
    assert require_strings({"words": []}, "words", "words") == ()


def test_an_empty_list_is_refused_where_something_must_be_drawn_from_it() -> None:
    with pytest.raises(SpecError, match=r"^words must be a non-empty list of strings$"):
        require_filled_strings({"words": []}, "words", "words")


def test_a_decimal_is_read_from_a_string_and_never_from_a_number() -> None:
    assert require_decimal({"rate": "19.5"}, "rate", "rate") == Decimal("19.5")
    with pytest.raises(SpecError, match=r"^rate must be a non-empty string$"):
        require_decimal({"rate": 19.5}, "rate", "rate")


def test_something_that_is_not_a_number_at_all_is_refused() -> None:
    with pytest.raises(SpecError, match=r"^rate must be a decimal written as a string$"):
        require_decimal({"rate": "nineteen"}, "rate", "rate")


def test_a_choice_outside_the_list_is_refused_with_the_list() -> None:
    assert require_choice({"way": "north"}, "way", "way", ALLOWED) == "north"
    with pytest.raises(SpecError, match=r"^way must be one of: north, south$"):
        require_choice({"way": "east"}, "way", "way", ALLOWED)


def test_choices_are_refused_by_position() -> None:
    assert require_choices({"ways": ["north"]}, "ways", "ways", ALLOWED) == ("north",)
    with pytest.raises(SpecError, match=r"^ways\[1\] must be one of: north, south$"):
        require_choices({"ways": ["north", "east"]}, "ways", "ways", ALLOWED)


def test_an_optional_value_may_be_absent_or_null() -> None:
    assert optional_text({}, "note", "note") is None
    assert optional_text({"note": None}, "note", "note") is None
    assert optional_text({"note": "hello"}, "note", "note") == "hello"


def test_an_optional_value_that_is_present_still_has_to_be_text() -> None:
    with pytest.raises(SpecError, match=r"^note must be a non-empty string$"):
        optional_text({"note": 7}, "note", "note")


def test_an_unknown_key_is_named_with_its_prefix() -> None:
    with pytest.raises(SpecError, match=r"^block.extra is not a recognized knob$"):
        reject_unknown({"extra": 1}, ("known",), "block.", "knob")


def test_a_known_key_passes() -> None:
    reject_unknown({"known": 1}, ("known",), "block.", "knob")


def test_a_file_that_is_not_there_is_named(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match=r"^layout file not found: "):
        read_object(tmp_path / "absent.json", "layout")


def test_a_file_that_is_not_json_is_named(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{,}", encoding="utf-8")
    with pytest.raises(SpecError, match=r"^invalid JSON in "):
        read_object(path, "layout")


def test_a_file_that_is_json_but_not_an_object_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(SpecError, match=r"^layout must be a JSON object$"):
        read_object(path, "layout")


def test_a_spec_error_is_a_value_error() -> None:
    """Callers that only know `ValueError` still catch it."""
    assert issubclass(SpecError, ValueError)
