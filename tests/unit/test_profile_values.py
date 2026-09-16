"""One JSON value at a time: the three message shapes, and the lexicon behind a label."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from invoice_extractor.profile import reading
from invoice_extractor.profile.lexicon import expand, read_lexicon
from invoice_extractor.profile.loader import read_profile_json
from invoice_extractor.profile.schema import ProfileError

WORDS = {"header_labels": {"invoice_number": ["Rechnungsnummer"]}, "titles": ["RECHNUNG"]}


def test_a_missing_key_is_required() -> None:
    with pytest.raises(ProfileError, match="id is required"):
        reading.require({}, "id", "id")


def test_a_key_that_is_not_text_says_so() -> None:
    with pytest.raises(ProfileError, match="id must be a non-empty string"):
        reading.require_text({"id": 7}, "id", "id")


def test_an_empty_string_is_not_text() -> None:
    with pytest.raises(ProfileError, match="id must be a non-empty string"):
        reading.require_text({"id": ""}, "id", "id")


def test_a_prefix_left_out_falls_back() -> None:
    assert reading.optional_plain_text({}, "p", "p", "X") == "X"


def test_a_prefix_may_be_empty_but_not_a_number() -> None:
    assert reading.optional_plain_text({"p": ""}, "p", "p", "X") == ""
    with pytest.raises(ProfileError, match="p must be a string"):
        reading.optional_plain_text({"p": 7}, "p", "p", "X")


def test_a_list_of_strings_is_a_list_of_strings() -> None:
    with pytest.raises(ProfileError, match=r"labels must be a list of strings"):
        reading.as_strings(["a", 2], "labels")


def test_an_object_is_an_object() -> None:
    with pytest.raises(ProfileError, match="vat must be an object"):
        reading.as_mapping(["not", "an", "object"], "vat")


def test_a_list_of_objects_is_a_list() -> None:
    with pytest.raises(ProfileError, match="variants must be a list of objects"):
        reading.require_objects({"variants": {}}, "variants", "variants")


def test_a_flag_is_true_or_false() -> None:
    with pytest.raises(ProfileError, match="required must be true or false"):
        reading.optional_flag({"required": "yes"}, "required", "required", True)


def test_a_count_is_a_positive_whole_number() -> None:
    with pytest.raises(ProfileError, match="max_lines must be a positive whole number"):
        reading.optional_count({"max_lines": 0}, "max_lines", "max_lines", 6)


def test_a_fraction_is_a_number() -> None:
    with pytest.raises(ProfileError, match="cluster_gap must be a number"):
        reading.optional_fraction({"cluster_gap": "wide"}, "cluster_gap", "cluster_gap", 0.08)


def test_a_choice_lists_what_was_allowed() -> None:
    with pytest.raises(ProfileError, match="placement must be one of: right, below"):
        reading.require_choice({"placement": "above"}, "placement", "placement", ("right", "below"))


def test_a_decimal_is_written_as_a_string() -> None:
    assert reading.as_decimal("0.01", "tolerance") == Decimal("0.01")
    with pytest.raises(ProfileError, match="tolerance must be a decimal written as a string"):
        reading.as_decimal(0.01, "tolerance")


def test_a_decimal_that_is_not_a_number_says_so() -> None:
    with pytest.raises(ProfileError, match="tolerance must be a decimal written as a string"):
        reading.as_decimal("a cent", "tolerance")


def test_a_lexicon_that_is_not_there_names_the_language(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="lexicon zz is not readable"):
        read_lexicon("zz", tmp_path)


def test_a_lexicon_that_is_not_json_names_the_language(tmp_path: Path) -> None:
    (tmp_path / "zz.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(ProfileError, match="lexicon zz is not valid JSON"):
        read_lexicon("zz", tmp_path)


def test_a_lexicon_must_be_an_object(tmp_path: Path) -> None:
    (tmp_path / "zz.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ProfileError, match="lexicon zz must be an object"):
        read_lexicon("zz", tmp_path)


def test_a_lexicon_reads_back_as_the_words_it_holds(tmp_path: Path) -> None:
    (tmp_path / "zz.json").write_text(json.dumps(WORDS), encoding="utf-8")
    assert read_lexicon("zz", tmp_path) == WORDS


def test_a_reference_to_a_whole_list_expands_to_it() -> None:
    assert expand(["@titles"], WORDS, "document_types.invoice_titles") == ("RECHNUNG",)


def test_a_reference_to_a_map_no_entry_names_is_refused() -> None:
    with pytest.raises(ProfileError, match=r"references @headings\.bill_to"):
        expand(["@headings.bill_to"], WORDS, "parties.bill_to.labels")


def test_a_reference_to_a_key_no_map_holds_is_refused() -> None:
    with pytest.raises(ProfileError, match=r"references @header_labels\.lucky"):
        expand(["@header_labels.lucky"], WORDS, "fields.lucky.labels")


def test_a_reference_to_something_that_is_not_a_list_of_labels_is_refused() -> None:
    with pytest.raises(ProfileError, match="is not a list of labels"):
        expand(["@header_labels"], WORDS, "fields.invoice_number.labels")


def test_a_label_said_twice_is_kept_once() -> None:
    expanded = expand(["Rechnungsnummer", "@header_labels.invoice_number"], WORDS, "x")
    assert expanded == ("Rechnungsnummer",)


def test_a_profile_file_must_hold_an_object(tmp_path: Path) -> None:
    path = tmp_path / "xx-XX.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ProfileError, match=r"xx-XX\.json must be an object"):
        read_profile_json(path)
