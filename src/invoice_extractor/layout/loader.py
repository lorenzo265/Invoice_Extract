"""Read a layout file and validate it, top down, into a typed `Layout`.

This is the only module that knows what the JSON looks like. Every message it raises
names the dotted path of the offending key, because the person reading it is editing
JSON, not a Python traceback — `docs/LAYOUT_FORMAT.md` is the contract, message by
message.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from invoice_extractor.document.reader import Zone
from invoice_extractor.layout.schema import (
    FIELD_NAMES,
    LINE_ITEM_COLUMNS,
    FieldLayout,
    Layout,
    LayoutError,
    LineItemsLayout,
)

LAYOUTS_DIR = Path("layouts")
CURRENCY_CODE = re.compile(r"[A-Z]{3}")
TOP_LEVEL_KEYS = (
    "id",
    "language",
    "decimal_separator",
    "thousands_separator",
    "date_formats",
    "currency_symbols",
    "fields",
    "line_items",
)
FIELD_KEYS = ("labels", "zones", "regex")
LINE_ITEM_KEYS = ("header_labels", "stop_labels")
STRING_LIST = "a list of strings"
NON_EMPTY_STRING_LIST = "a non-empty list of strings"
CURRENCY_SYMBOLS_SHAPE = "an object mapping currency codes to symbols"


def load_layout(id_or_path: str) -> Layout:
    """Load a layout by built-in id or by path. Raises `LayoutError` naming the bad key."""
    return _parse(_read(_resolve(id_or_path)))


def _resolve(id_or_path: str) -> Path:
    """A path if it looks like one, otherwise a built-in id under `layouts/`."""
    looks_like_a_path = "/" in id_or_path or "\\" in id_or_path or id_or_path.endswith(".json")
    return Path(id_or_path) if looks_like_a_path else LAYOUTS_DIR / f"{id_or_path}.json"


def _read(path: Path) -> Mapping[str, object]:
    if not path.is_file():
        raise LayoutError(f"layout file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise LayoutError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(data, dict):
        raise LayoutError("layout must be a JSON object")
    return cast(Mapping[str, object], data)


def _parse(data: Mapping[str, object]) -> Layout:
    _reject_unknown(data, TOP_LEVEL_KEYS, "", "top-level key")
    identifier = _require_text(data, "id", "id")
    language = _require_text(data, "language", "language")
    decimal_separator, thousands_separator = _parse_separators(data)
    return Layout(
        id=identifier,
        language=language,
        decimal_separator=decimal_separator,
        thousands_separator=thousands_separator,
        date_formats=_require_filled_strings(data, "date_formats", "date_formats"),
        currency_symbols=_parse_currency_symbols(data),
        fields=_parse_fields(data),
        line_items=_parse_line_items(data),
    )


def _parse_separators(data: Mapping[str, object]) -> tuple[str, str]:
    decimal = _require_separator(data, "decimal_separator", (1,), "a single character")
    thousands = _require_separator(
        data, "thousands_separator", (0, 1), "a single character or empty"
    )
    if decimal == thousands:
        raise LayoutError("decimal_separator and thousands_separator must be different")
    return decimal, thousands


def _parse_currency_symbols(data: Mapping[str, object]) -> Mapping[str, str]:
    raw = _require_mapping(data, "currency_symbols", "currency_symbols", CURRENCY_SYMBOLS_SHAPE)
    for code, symbol in raw.items():
        if not CURRENCY_CODE.fullmatch(code):
            raise LayoutError(
                f"currency_symbols has a key that is not a 3-letter uppercase currency code: {code}"
            )
        if not isinstance(symbol, str):
            raise LayoutError(f"currency_symbols must be {CURRENCY_SYMBOLS_SHAPE}")
    return {code: str(symbol) for code, symbol in raw.items()}


def _parse_fields(data: Mapping[str, object]) -> Mapping[str, FieldLayout]:
    shape = "an object mapping field names to field layouts"
    raw = _require_mapping(data, "fields", "fields", shape)
    _reject_unknown(raw, FIELD_NAMES, "fields.", "field")
    return {name: _parse_field(raw, name) for name in FIELD_NAMES}


def _parse_field(raw: Mapping[str, object], name: str) -> FieldLayout:
    path = f"fields.{name}"
    entry = _require_mapping(raw, name, path, "an object")
    _reject_unknown(entry, FIELD_KEYS, f"{path}.", "key")
    return FieldLayout(
        labels=_require_filled_strings(entry, "labels", f"{path}.labels"),
        zones=_parse_zones(entry, path),
        regex=_parse_regex(entry, path),
    )


def _parse_zones(entry: Mapping[str, object], path: str) -> tuple[Zone, ...]:
    names = _require_filled_strings(entry, "zones", f"{path}.zones")
    return tuple(_parse_zone(name, index, path) for index, name in enumerate(names))


def _parse_zone(name: str, index: int, path: str) -> Zone:
    try:
        return Zone[name]
    except KeyError as error:
        raise LayoutError(f"{path}.zones[{index}] is not a recognized zone name: {name}") from error


def _parse_regex(entry: Mapping[str, object], path: str) -> re.Pattern[str] | None:
    if "regex" not in entry:
        return None
    pattern = entry["regex"]
    if not isinstance(pattern, str):
        raise LayoutError(f"{path}.regex must be a string")
    try:
        return re.compile(pattern)
    except re.error as error:
        raise LayoutError(f"{path}.regex is not a valid regular expression: {error}") from error


def _parse_line_items(data: Mapping[str, object]) -> LineItemsLayout:
    shape = "an object with header_labels and stop_labels"
    raw = _require_mapping(data, "line_items", "line_items", shape)
    _reject_unknown(raw, LINE_ITEM_KEYS, "line_items.", "key")
    headers = _require_mapping(
        raw,
        "header_labels",
        "line_items.header_labels",
        "an object mapping columns to header words",
    )
    _reject_unknown(headers, LINE_ITEM_COLUMNS, "line_items.header_labels.", "column")
    return LineItemsLayout(
        header_labels={column: _parse_column(headers, column) for column in LINE_ITEM_COLUMNS},
        stop_labels=_require_strings(raw, "stop_labels", "line_items.stop_labels", STRING_LIST),
    )


def _parse_column(headers: Mapping[str, object], column: str) -> tuple[str, ...]:
    return _require_filled_strings(headers, column, f"line_items.header_labels.{column}")


def _reject_unknown(
    data: Mapping[str, object], allowed: Sequence[str], prefix: str, noun: str
) -> None:
    for key in data:
        if key not in allowed:
            raise LayoutError(f"{prefix}{key} is not a recognized {noun}")


def _required(data: Mapping[str, object], key: str, path: str) -> object:
    if key not in data:
        raise LayoutError(f"{path} is required")
    return data[key]


def _require_text(data: Mapping[str, object], key: str, path: str) -> str:
    value = _required(data, key, path)
    if not isinstance(value, str) or not value:
        raise LayoutError(f"{path} must be a non-empty string")
    return value


def _require_separator(
    data: Mapping[str, object], key: str, lengths: tuple[int, ...], description: str
) -> str:
    value = _required(data, key, key)
    if not isinstance(value, str) or len(value) not in lengths:
        raise LayoutError(f"{key} must be {description}")
    return value


def _require_mapping(
    data: Mapping[str, object], key: str, path: str, description: str
) -> Mapping[str, object]:
    value = _required(data, key, path)
    if not isinstance(value, dict):
        raise LayoutError(f"{path} must be {description}")
    return cast(Mapping[str, object], value)


def _require_strings(
    data: Mapping[str, object], key: str, path: str, description: str
) -> tuple[str, ...]:
    """A list of strings — empty is allowed; the caller says so through `description`."""
    value = _required(data, key, path)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise LayoutError(f"{path} must be {description}")
    return tuple(cast(Sequence[str], value))


def _require_filled_strings(data: Mapping[str, object], key: str, path: str) -> tuple[str, ...]:
    values = _require_strings(data, key, path, NON_EMPTY_STRING_LIST)
    if not values:
        raise LayoutError(f"{path} must be {NON_EMPTY_STRING_LIST}")
    return values
