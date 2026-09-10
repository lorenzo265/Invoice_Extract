"""What the renderer records about every value it prints.

The truth builder never re-derives where something is: it reads this log, searches the
finished PDF for each recorded string on the page it was recorded on, and takes the box
nearest the point it was drawn at. That last part is why the point is recorded — a string
an invoice prints twice would otherwise be located at whichever occurrence came first.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Slot(Enum):
    """What kind of thing a placement is, which decides where it lands in the truth."""

    FIELD = "field"
    CELL = "cell"
    CHARGE = "charge"
    VAT_LINE = "vat_line"
    SECONDARY = "secondary"
    PARTY = "party"
    NOISE = "noise"


@dataclass(frozen=True, slots=True)
class Mark:
    """Which truth entry a placement belongs to, decided at the call that draws it."""

    slot: Slot
    name: str
    index: int = 0
    label: str | None = None


@dataclass(frozen=True, slots=True)
class Placement:
    """One drawn string: what it says, which page it is on, and where it starts."""

    mark: Mark
    text: str
    page: int
    x: float
    y: float


def field(name: str, label: str | None = None) -> Mark:
    return Mark(Slot.FIELD, name, label=label)


def cell(pos: int, column: str) -> Mark:
    return Mark(Slot.CELL, column, index=pos)


def charge(index: int, label: str) -> Mark:
    return Mark(Slot.CHARGE, "amount", index=index, label=label)


def vat_cell(index: int, component: str) -> Mark:
    return Mark(Slot.VAT_LINE, component, index=index)


def secondary(name: str) -> Mark:
    return Mark(Slot.SECONDARY, name)


def party_part(kind: str, part: str) -> Mark:
    return Mark(Slot.PARTY, part, label=kind)


def noise(kind: str, label: str | None = None) -> Mark:
    return Mark(Slot.NOISE, kind, label=label)
