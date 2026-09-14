"""Read a language lexicon and validate it, top down, into a `Lexicon`.

Like profiles, lexicons are shared with the extractor and live in `lexicon/` at the root
of the working directory: `load_lexicon("de")` resolves there, and only an argument that
looks like a path is read as one.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from invoice_forge.jsonspec import (
    SpecError,
    read_object,
    reject_unknown,
    require_choice,
    require_filled_strings,
    require_mapping,
    require_text,
)
from invoice_forge.lexicon.schema import (
    AMOUNT_IN_WORDS_STYLES,
    MAX_SYNONYMS,
    MONTHS_IN_A_YEAR,
    SCALE_WORDS,
    SYNONYM_MAPS,
    AmountInWords,
    Lexicon,
)

LEXICON_DIR = Path("lexicon")
PLAIN_LISTS = (
    "page_numbering",
    "payment_terms",
    "legal_lines",
    "copy_stamps",
    "section_headings",
    "address_placeholders",
)
TOP_LEVEL_KEYS = (
    "language",
    *SYNONYM_MAPS,
    *PLAIN_LISTS,
    "months",
    "month_abbreviations",
    "diacritics",
    "amount_in_words",
)
WORDS_KEYS = (
    "style",
    "units",
    "tens",
    "scales",
    "scale_many",
    "million",
    "scale_one",
    "joiner",
    "currency_unit",
    "currency_fraction",
)
CURRENCY_WORD_FORMS = 2


def load_lexicon(id_or_path: str) -> Lexicon:
    """Load a bundled lexicon by language id, or any lexicon by path. Raises `SpecError`."""
    return _parse(read_object(_resolve(id_or_path), "lexicon"))


def bundled_lexicon_ids() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in LEXICON_DIR.glob("*.json")))


def _resolve(id_or_path: str) -> Path:
    looks_like_a_path = "/" in id_or_path or "\\" in id_or_path or id_or_path.endswith(".json")
    return Path(id_or_path) if looks_like_a_path else LEXICON_DIR / f"{id_or_path}.json"


def _parse(data: Mapping[str, object]) -> Lexicon:
    """Named one by one rather than splatted, so a renamed field is a type error here."""
    reject_unknown(data, TOP_LEVEL_KEYS, "", "lexicon key")
    maps = {name: _synonym_map(data, name) for name in SYNONYM_MAPS}
    lists = {name: require_filled_strings(data, name, name) for name in PLAIN_LISTS}
    return Lexicon(
        language=require_text(data, "language", "language"),
        document_titles=maps["document_titles"],
        header_labels=maps["header_labels"],
        totals_labels=maps["totals_labels"],
        charge_labels=maps["charge_labels"],
        column_headers=maps["column_headers"],
        vat_summary_headers=maps["vat_summary_headers"],
        party_headings=maps["party_headings"],
        trap_labels=maps["trap_labels"],
        carry_forward=maps["carry_forward"],
        exemption_sentences=maps["exemption_sentences"],
        page_numbering=lists["page_numbering"],
        payment_terms=lists["payment_terms"],
        legal_lines=lists["legal_lines"],
        copy_stamps=lists["copy_stamps"],
        section_headings=lists["section_headings"],
        address_placeholders=lists["address_placeholders"],
        months=_month_names(data, "months"),
        month_abbreviations=_month_names(data, "month_abbreviations"),
        diacritics=require_text(data, "diacritics", "diacritics"),
        amount_in_words=_amount_in_words(data),
    )


def _synonym_map(data: Mapping[str, object], name: str) -> Mapping[str, tuple[str, ...]]:
    """One entry per key the schema names, each 1 to 5 ways of saying the same thing."""
    keys = SYNONYM_MAPS[name]
    entries = require_mapping(data, name, name, f"an object with one entry per {name[:-1]}")
    reject_unknown(entries, keys, f"{name}.", "entry")
    return {key: _synonyms(entries, name, key) for key in keys}


def _synonyms(entries: Mapping[str, object], name: str, key: str) -> tuple[str, ...]:
    path = f"{name}.{key}"
    values = require_filled_strings(entries, key, path)
    if len(values) > MAX_SYNONYMS:
        raise SpecError(f"{path} must list at most {MAX_SYNONYMS} synonyms")
    if len(set(values)) != len(values):
        raise SpecError(f"{path} lists the same synonym twice")
    return values


def _month_names(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    names = require_filled_strings(data, key, key)
    if len(names) != MONTHS_IN_A_YEAR:
        raise SpecError(f"{key} must list {MONTHS_IN_A_YEAR} months")
    return names


def _amount_in_words(data: Mapping[str, object]) -> AmountInWords | None:
    """Absent where the language spells numbers by rules none of the styles carries.

    A lexicon that declared a style it does not follow would put words on a page that
    nobody writes, so the key is left out instead and no total is spelled in that language.
    """
    path = "amount_in_words"
    if path not in data:
        return None
    words = require_mapping(data, path, path, "an object describing how a total is spelled")
    reject_unknown(words, WORDS_KEYS, f"{path}.", "key")
    return AmountInWords(
        style=require_choice(words, "style", f"{path}.style", AMOUNT_IN_WORDS_STYLES),
        units=require_filled_strings(words, "units", f"{path}.units"),
        tens=require_filled_strings(words, "tens", f"{path}.tens"),
        scales=_scale_words(words, "scales", path),
        scale_many=_scale_words(words, "scale_many", path),
        million=_word_pair(words, "million", path),
        scale_one=_scale_one(words, path),
        joiner=require_text(words, "joiner", f"{path}.joiner"),
        currency_unit=_word_pair(words, "currency_unit", path),
        currency_fraction=_word_pair(words, "currency_fraction", path),
    )


def _scale_one(words: Mapping[str, object], path: str) -> str:
    """The word for one before a scale word, where the language puts one there.

    Turkish counts `yüz` and `bin` with nothing in front, so it declares none; German
    counts `einhundert` and could not do without it.
    """
    if "scale_one" not in words:
        return ""
    return require_text(words, "scale_one", f"{path}.scale_one")


def _scale_words(words: Mapping[str, object], key: str, path: str) -> tuple[str, ...]:
    values = require_filled_strings(words, key, f"{path}.{key}")
    if len(values) != SCALE_WORDS:
        raise SpecError(f"{path}.{key} must list the hundred and the thousand")
    return values


def _word_pair(words: Mapping[str, object], key: str, path: str) -> tuple[str, str]:
    values = require_filled_strings(words, key, f"{path}.{key}")
    if len(values) != CURRENCY_WORD_FORMS:
        raise SpecError(f"{path}.{key} must list the singular and the plural")
    return values[0], values[1]
