"""Reading a JSON data file into typed values, with errors that name the offending key.

Both of the generator's data loaders — profiles and lexicons — validate the same way the
extractor's layout loader does: top down, raising on the first key that is wrong, with a
message that starts with that key's dotted path. The person reading the message is
editing JSON, not a Python traceback.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast


class SpecError(ValueError):
    """A data file that cannot be used. The message names the exact JSON key at fault."""


def read_object(path: Path, what: str) -> Mapping[str, object]:
    """Read a JSON object, or raise naming the file and what was wrong with it."""
    if not path.is_file():
        raise SpecError(f"{what} file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SpecError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(data, dict):
        raise SpecError(f"{what} must be a JSON object")
    return cast(Mapping[str, object], data)


def reject_unknown(
    data: Mapping[str, object], allowed: Sequence[str], prefix: str, noun: str
) -> None:
    for key in data:
        if key not in allowed:
            raise SpecError(f"{prefix}{key} is not a recognized {noun}")


def required(data: Mapping[str, object], key: str, path: str) -> object:
    if key not in data:
        raise SpecError(f"{path} is required")
    return data[key]


def require_text(data: Mapping[str, object], key: str, path: str) -> str:
    value = required(data, key, path)
    if not isinstance(value, str) or not value:
        raise SpecError(f"{path} must be a non-empty string")
    return value


def require_flag(data: Mapping[str, object], key: str, path: str) -> bool:
    value = required(data, key, path)
    if not isinstance(value, bool):
        raise SpecError(f"{path} must be true or false")
    return value


def require_mapping(
    data: Mapping[str, object], key: str, path: str, description: str
) -> Mapping[str, object]:
    value = required(data, key, path)
    if not isinstance(value, dict):
        raise SpecError(f"{path} must be {description}")
    return cast(Mapping[str, object], value)


def require_strings(data: Mapping[str, object], key: str, path: str) -> tuple[str, ...]:
    """A list of strings, possibly empty."""
    value = required(data, key, path)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SpecError(f"{path} must be a list of strings")
    return tuple(cast(Sequence[str], value))


def require_filled_strings(data: Mapping[str, object], key: str, path: str) -> tuple[str, ...]:
    values = require_strings(data, key, path)
    if not values:
        raise SpecError(f"{path} must be a non-empty list of strings")
    return values


def require_decimal(data: Mapping[str, object], key: str, path: str) -> Decimal:
    """A number written as a string, so no value ever passes through a float."""
    text = require_text(data, key, path)
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise SpecError(f"{path} must be a decimal written as a string") from error


def require_choice(data: Mapping[str, object], key: str, path: str, allowed: Sequence[str]) -> str:
    value = require_text(data, key, path)
    if value not in allowed:
        raise SpecError(f"{path} must be one of: {', '.join(allowed)}")
    return value


def require_choices(
    data: Mapping[str, object], key: str, path: str, allowed: Sequence[str]
) -> tuple[str, ...]:
    values = require_filled_strings(data, key, path)
    for index, value in enumerate(values):
        if value not in allowed:
            raise SpecError(f"{path}[{index}] must be one of: {', '.join(allowed)}")
    return values


def optional_text(data: Mapping[str, object], key: str, path: str) -> str | None:
    if key not in data or data[key] is None:
        return None
    return require_text(data, key, path)
