"""Reading a truth file back as data, without trusting anything in it.

`forge verify` runs over files it did not write in this process — a corpus generated last
week, or one somebody edited. So every access goes through here, and a truth that is not
shaped like `forge-truth/1` produces a named failure rather than a traceback.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from invoice_forge.render.pdf import BBox

BBOX_VALUES = 4


class TruthError(ValueError):
    """A truth file that cannot be read. The message says what is wrong with it."""


@dataclass(frozen=True, slots=True)
class Box:
    """One evidence entry: a page, a rectangle, and what it is supposed to say."""

    page: int
    bbox: BBox


def read_truth(path: Path) -> dict[str, object]:
    """The truth as a plain object, or `TruthError` naming what is wrong with the file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise TruthError(f"invalid JSON: {error}") from error
    except OSError as error:
        raise TruthError(f"cannot be read: {error}") from error
    if not isinstance(data, dict):
        raise TruthError("must be a JSON object")
    return dict(data)


def block(truth: dict[str, object], name: str) -> dict[str, object]:
    value = truth.get(name)
    if not isinstance(value, dict):
        raise TruthError(f"{name} must be an object")
    return dict(value)


def rows(truth: dict[str, object], name: str) -> list[dict[str, object]]:
    value = truth.get(name)
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise TruthError(f"{name} must be a list of objects")
    return [dict(row) for row in value]


def text(entry: dict[str, object], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str):
        raise TruthError(f"{where}.{key} must be a string")
    return value


def flag(entry: dict[str, object], key: str, where: str) -> bool:
    value = entry.get(key)
    if not isinstance(value, bool):
        raise TruthError(f"{where}.{key} must be true or false")
    return value


def whole(entry: dict[str, object], key: str, where: str) -> int:
    value = entry.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TruthError(f"{where}.{key} must be a whole number")
    return value


def amount(entry: dict[str, object], key: str, where: str) -> Decimal:
    """Money and rates are strings in the truth, so no value ever passes through a float."""
    try:
        return Decimal(text(entry, key, where))
    except InvalidOperation as error:
        raise TruthError(f"{where}.{key} must be a decimal written as a string") from error


def boxes(entry: dict[str, object], where: str, key: str = "evidence") -> tuple[Box, ...]:
    value = entry.get(key)
    if not isinstance(value, list):
        raise TruthError(f"{where}.{key} must be a list")
    return tuple(_box(item, f"{where}.{key}[{index}]") for index, item in enumerate(value))


def box_at(entry: dict[str, object], where: str) -> Box:
    """An entry that carries its page and box directly, as a noise record does."""
    return _box(entry, where)


def _box(item: object, where: str) -> Box:
    if not isinstance(item, dict):
        raise TruthError(f"{where} must be an object")
    return Box(page=whole(item, "page", where), bbox=_rectangle(item.get("bbox"), where))


def _rectangle(value: object, where: str) -> BBox:
    if not isinstance(value, list) or len(value) != BBOX_VALUES:
        raise TruthError(f"{where}.bbox must be four numbers")
    numbers = _numbers(value, where)
    if numbers[0] > numbers[2] or numbers[1] > numbers[3]:
        raise TruthError(f"{where}.bbox is inside out")
    return numbers


def _numbers(value: Sequence[object], where: str) -> BBox:
    numeric = (isinstance(n, int | float) and not isinstance(n, bool) for n in value)
    if not all(numeric):
        raise TruthError(f"{where}.bbox must be four numbers")
    x0, y0, x1, y1 = (float(number) for number in value)  # type: ignore[arg-type]  # checked above
    return (x0, y0, x1, y1)
