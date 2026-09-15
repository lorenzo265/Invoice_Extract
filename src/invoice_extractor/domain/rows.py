"""The rows of an invoice's two tables, and what each of their cells was read from.

A row is not a field: nothing ranked it, and no label introduced it — it is what the
column it sits under says it is. What it shares with a field is evidence, one box per
cell (ADR-0002), so a quantity in a report can be pointed at on the page it came from.

Every column is optional because every column is a vendor's choice. A table that prints
no article number has rows without one, and a reader that insisted would be reading a
table this vendor does not print. `docs/FIELD_CATALOG.md` names them all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import cast

from invoice_extractor.domain.evidence import Evidence

# The columns of a line item, in the order a report prints them.
LINE_ITEM_COLUMNS: tuple[str, ...] = (
    "pos",
    "part_number",
    "description",
    "quantity",
    "unit",
    "unit_price",
    "discount_pct",
    "vat_rate",
    "net_amount",
)
# The columns of a VAT summary line.
VAT_SUMMARY_COLUMNS: tuple[str, ...] = ("code", "rate", "base", "vat")
Cells = Mapping[str, Evidence]


@dataclass(frozen=True, slots=True)
class SubItem:
    """A component printed under its row: what it is, and what it is charged at."""

    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "description": self.description,
            "quantity": _number(self.quantity),
            "unit_price": _number(self.unit_price),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> SubItem:
        return cls(
            description=str(data["description"]),
            quantity=_decimal(data.get("quantity")),
            unit_price=_decimal(data.get("unit_price")),
        )


@dataclass(frozen=True, slots=True)
class LineItem:
    """One row of the invoice's table, with the box every cell of it was read from."""

    pos: int | None = None
    part_number: str | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    discount_pct: Decimal | None = None
    vat_rate: Decimal | None = None
    net_amount: Decimal | None = None
    sub_items: tuple[SubItem, ...] = ()
    cells: Cells = field(default_factory=dict)
    # Which line of the VAT summary taxes this row, by position; `None` where the
    # document prints no summary, or where more than one of its lines could be this
    # row's (ENGINE_SPEC §5 — an ambiguous linkage is a finding, never a guess).
    vat_line: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "pos": self.pos,
            "part_number": self.part_number,
            "description": self.description,
            "quantity": _number(self.quantity),
            "unit": self.unit,
            "unit_price": _number(self.unit_price),
            "discount_pct": _number(self.discount_pct),
            "vat_rate": _number(self.vat_rate),
            "net_amount": _number(self.net_amount),
            "sub_items": [sub.to_dict() for sub in self.sub_items],
            "cells": {name: found.to_dict() for name, found in self.cells.items()},
            "vat_line": self.vat_line,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> LineItem:
        return cls(
            pos=_whole(data.get("pos")),
            part_number=_text(data.get("part_number")),
            description=_text(data.get("description")),
            quantity=_decimal(data.get("quantity")),
            unit=_text(data.get("unit")),
            unit_price=_decimal(data.get("unit_price")),
            discount_pct=_decimal(data.get("discount_pct")),
            vat_rate=_decimal(data.get("vat_rate")),
            net_amount=_decimal(data.get("net_amount")),
            sub_items=tuple(SubItem.from_dict(sub) for sub in _rows(data, "sub_items")),
            cells=_cells(data),
            vat_line=_whole(data.get("vat_line")),
        )


@dataclass(frozen=True, slots=True)
class VatSummaryRow:
    """One line of the VAT summary: a rate, what it was charged on, and what it came to."""

    code: str | None = None
    rate: Decimal | None = None
    base: Decimal | None = None
    vat: Decimal | None = None
    cells: Cells = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "rate": _number(self.rate),
            "base": _number(self.base),
            "vat": _number(self.vat),
            "cells": {name: found.to_dict() for name, found in self.cells.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> VatSummaryRow:
        return cls(
            code=_text(data.get("code")),
            rate=_decimal(data.get("rate")),
            base=_decimal(data.get("base")),
            vat=_decimal(data.get("vat")),
            cells=_cells(data),
        )


def _text(raw: object) -> str | None:
    return None if raw is None else str(raw)


def _whole(raw: object) -> int | None:
    return None if raw is None else int(str(raw))


def _cells(data: Mapping[str, object]) -> dict[str, Evidence]:
    found = data.get("cells")
    entries = cast(Mapping[str, Mapping[str, object]], found if isinstance(found, dict) else {})
    return {name: Evidence.from_dict(entry) for name, entry in entries.items()}


def _rows(data: Mapping[str, object], key: str) -> Sequence[Mapping[str, object]]:
    found = data.get(key)
    return cast(Sequence[Mapping[str, object]], found if isinstance(found, list) else ())


def _number(value: Decimal | None) -> str | None:
    """A `Decimal` is written as its own digits, never as a JSON number (ADR-0003)."""
    return None if value is None else str(value)


def _decimal(raw: object) -> Decimal | None:
    return None if raw is None else Decimal(str(raw))
