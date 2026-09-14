"""Reading one JSON value, strictly, with the key path in every message.

`docs/PROFILE_FORMAT.md` promises three message shapes and nothing else: `<path> is not
a recognized key`, `<path> is required`, `<path> must be <description>`. Every helper
here produces one of the three, so a profile author never has to read a traceback to
find out which key is wrong.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from invoice_extractor.profile.schema import ProfileError


def reject_unknown(data: Mapping[str, object], allowed: Sequence[str], prefix: str) -> None:
    for key in data:
        if key not in allowed:
            raise ProfileError(f"{prefix}{key} is not a recognized key")


def require(data: Mapping[str, object], key: str, path: str) -> object:
    if key not in data:
        raise ProfileError(f"{path} is required")
    return data[key]


def require_text(data: Mapping[str, object], key: str, path: str) -> str:
    value = require(data, key, path)
    if not isinstance(value, str) or not value:
        raise ProfileError(f"{path} must be a non-empty string")
    return value


def optional_text(data: Mapping[str, object], key: str, path: str, fallback: str) -> str:
    return require_text(data, key, path) if key in data else fallback


def optional_plain_text(data: Mapping[str, object], key: str, path: str, fallback: str) -> str:
    """Like `optional_text`, but empty is a value: a VAT id in Turkey carries no prefix."""
    if key not in data:
        return fallback
    value = data[key]
    if not isinstance(value, str):
        raise ProfileError(f"{path} must be a string")
    return value


def require_strings(data: Mapping[str, object], key: str, path: str) -> tuple[str, ...]:
    return as_strings(require(data, key, path), path)


def optional_strings(data: Mapping[str, object], key: str, path: str) -> tuple[str, ...]:
    return require_strings(data, key, path) if key in data else ()


def as_strings(value: object, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProfileError(f"{path} must be a list of strings")
    return tuple(str(item) for item in value)


def require_mapping(data: Mapping[str, object], key: str, path: str) -> Mapping[str, object]:
    return as_mapping(require(data, key, path), path)


def optional_mapping(data: Mapping[str, object], key: str, path: str) -> Mapping[str, object]:
    return require_mapping(data, key, path) if key in data else {}


def as_mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProfileError(f"{path} must be an object")
    return {str(key): item for key, item in value.items()}


def require_objects(
    data: Mapping[str, object], key: str, path: str
) -> tuple[Mapping[str, object], ...]:
    value = require(data, key, path)
    if not isinstance(value, list):
        raise ProfileError(f"{path} must be a list of objects")
    return tuple(as_mapping(entry, f"{path}[{index}]") for index, entry in enumerate(value))


def optional_objects(
    data: Mapping[str, object], key: str, path: str
) -> tuple[Mapping[str, object], ...]:
    return require_objects(data, key, path) if key in data else ()


def optional_flag(data: Mapping[str, object], key: str, path: str, fallback: bool) -> bool:
    if key not in data:
        return fallback
    value = data[key]
    if not isinstance(value, bool):
        raise ProfileError(f"{path} must be true or false")
    return value


def optional_count(data: Mapping[str, object], key: str, path: str, fallback: int) -> int:
    if key not in data:
        return fallback
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ProfileError(f"{path} must be a positive whole number")
    return value


def optional_fraction(data: Mapping[str, object], key: str, path: str, fallback: float) -> float:
    if key not in data:
        return fallback
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProfileError(f"{path} must be a number")
    return float(value)


def require_choice(data: Mapping[str, object], key: str, path: str, allowed: Sequence[str]) -> str:
    value = require_text(data, key, path)
    if value not in allowed:
        raise ProfileError(f"{path} must be one of: {', '.join(allowed)}")
    return value


def optional_choice(
    data: Mapping[str, object], key: str, path: str, allowed: Sequence[str], fallback: str
) -> str:
    return require_choice(data, key, path, allowed) if key in data else fallback


def as_decimal(value: object, path: str) -> Decimal:
    if not isinstance(value, str):
        raise ProfileError(f"{path} must be a decimal written as a string")
    try:
        return Decimal(value)
    except InvalidOperation as invalid:
        raise ProfileError(f"{path} must be a decimal written as a string") from invalid


def optional_decimal(data: Mapping[str, object], key: str, path: str, fallback: Decimal) -> Decimal:
    return as_decimal(data[key], path) if key in data else fallback


def require_pattern(data: Mapping[str, object], key: str, path: str) -> re.Pattern[str]:
    return as_pattern(require_text(data, key, path), path)


def optional_pattern(data: Mapping[str, object], key: str, path: str) -> re.Pattern[str] | None:
    return as_pattern(require_text(data, key, path), path) if key in data else None


def as_pattern(source: str, path: str) -> re.Pattern[str]:
    try:
        return re.compile(source)
    except re.error as invalid:
        raise ProfileError(f"{path} must be a valid regular expression: {invalid}") from invalid
