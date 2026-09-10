"""A lexicon says everything an invoice says, and the loader names whatever is missing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from dataspec import message, write

from invoice_forge.lexicon.loader import (
    LEXICON_DIR,
    PLAIN_LISTS,
    bundled_lexicon_ids,
    load_lexicon,
)
from invoice_forge.lexicon.schema import MAX_SYNONYMS, MONTHS_IN_A_YEAR, SYNONYM_MAPS


def base() -> dict[str, Any]:
    """The bundled English lexicon as raw JSON; every test below breaks one thing in it."""
    data: dict[str, Any] = json.loads((LEXICON_DIR / "en.json").read_text(encoding="utf-8"))
    return data


def error(tmp_path: Path, data: object) -> str:
    return message(load_lexicon, tmp_path, "lexicon", data)


def test_a_valid_lexicon_loads(tmp_path: Path) -> None:
    lexicon = load_lexicon(write(tmp_path, "lexicon", base()))
    assert lexicon.language == "en"
    assert lexicon.months[0] == "January"
    assert lexicon.amount_in_words.style == "english"
    assert lexicon.amount_in_words.currency_unit == ("pound", "pounds")


@pytest.mark.parametrize("language", bundled_lexicon_ids())
def test_every_bundled_lexicon_loads(language: str) -> None:
    assert load_lexicon(language).language == language


def test_the_bundled_lexicons_are_the_four_this_pull_request_ships() -> None:
    assert bundled_lexicon_ids() == ("de", "en", "fr", "sv")


@pytest.mark.parametrize("name", sorted(SYNONYM_MAPS))
def test_a_missing_synonym_map_names_itself(tmp_path: Path, name: str) -> None:
    data = base()
    del data[name]
    assert error(tmp_path, data) == f"{name} is required"


@pytest.mark.parametrize("name", sorted(SYNONYM_MAPS))
def test_a_synonym_map_must_be_an_object(tmp_path: Path, name: str) -> None:
    data = base()
    data[name] = ["a list of words"]
    assert error(tmp_path, data).startswith(f"{name} must be an object with one entry per ")


@pytest.mark.parametrize("name", sorted(SYNONYM_MAPS))
def test_every_entry_a_synonym_map_needs_is_required(tmp_path: Path, name: str) -> None:
    key = SYNONYM_MAPS[name][0]
    data = base()
    del data[name][key]
    assert error(tmp_path, data) == f"{name}.{key} is required"


def test_an_unknown_entry_in_a_synonym_map_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["header_labels"]["salesperson"] = ["Salesperson"]
    assert error(tmp_path, data) == "header_labels.salesperson is not a recognized entry"


def test_an_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["footer_labels"] = {}
    assert error(tmp_path, data) == "footer_labels is not a recognized lexicon key"


def test_a_field_needs_at_least_one_way_of_saying_it(tmp_path: Path) -> None:
    data = base()
    data["totals_labels"]["subtotal"] = []
    assert error(tmp_path, data) == "totals_labels.subtotal must be a non-empty list of strings"


def test_too_many_synonyms_are_refused(tmp_path: Path) -> None:
    data = base()
    data["totals_labels"]["subtotal"] = [f"Word {n}" for n in range(MAX_SYNONYMS + 1)]
    expected = f"totals_labels.subtotal must list at most {MAX_SYNONYMS} synonyms"
    assert error(tmp_path, data) == expected


def test_the_same_synonym_twice_is_refused(tmp_path: Path) -> None:
    data = base()
    data["totals_labels"]["subtotal"] = ["Subtotal", "Subtotal"]
    assert error(tmp_path, data) == "totals_labels.subtotal lists the same synonym twice"


@pytest.mark.parametrize("key", ["months", "month_abbreviations"])
def test_a_year_has_twelve_months(tmp_path: Path, key: str) -> None:
    data = base()
    data[key] = data[key][:11]
    assert error(tmp_path, data) == f"{key} must list {MONTHS_IN_A_YEAR} months"


@pytest.mark.parametrize("name", PLAIN_LISTS)
def test_a_plain_list_may_not_be_empty(tmp_path: Path, name: str) -> None:
    data = base()
    data[name] = []
    assert error(tmp_path, data) == f"{name} must be a non-empty list of strings"


def test_an_unknown_spelling_style_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["amount_in_words"]["style"] = "roman"
    assert error(tmp_path, data).startswith("amount_in_words.style must be one of: ")


def test_a_currency_word_needs_a_singular_and_a_plural(tmp_path: Path) -> None:
    data = base()
    data["amount_in_words"]["currency_unit"] = ["pound"]
    expected = "amount_in_words.currency_unit must list the singular and the plural"
    assert error(tmp_path, data) == expected


def test_an_unknown_spelling_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["amount_in_words"]["hundreds"] = ["hundred"]
    assert error(tmp_path, data) == "amount_in_words.hundreds is not a recognized key"


def test_the_spelling_block_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["amount_in_words"] = "english"
    assert error(tmp_path, data).startswith("amount_in_words must be an object describing ")


def test_a_lexicon_by_path_is_read_from_that_path(tmp_path: Path) -> None:
    path = write(tmp_path, "lexicon", base())
    assert load_lexicon(path).language == "en"


@pytest.mark.parametrize("language", bundled_lexicon_ids())
def test_every_bundled_lexicon_offers_the_font_something_hard_to_print(language: str) -> None:
    """`diacritics` is the sample string the renderer proves its font against, not a set."""
    assert not load_lexicon(language).diacritics.isascii(), language
