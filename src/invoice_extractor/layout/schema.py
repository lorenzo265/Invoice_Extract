"""The typed shape of a layout — what `layouts/*.json` means once it has been validated.

The two closed vocabularies below, `FIELD_NAMES` and `LINE_ITEM_COLUMNS`, are the only
thing this package and `extraction/` share: they agree through these strings and nothing
else (ADR-0004). `docs/LAYOUT_FORMAT.md` is the contract for the JSON that produces them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from invoice_extractor.document.reader import Zone

FIELD_NAMES: tuple[str, ...] = (
    "invoice_number",
    "invoice_date",
    "due_date",
    "supplier_vat_id",
    "customer_vat_id",
    "currency",
    "vat_rate",
    "subtotal",
    "vat_amount",
    "total_amount",
)

LINE_ITEM_COLUMNS: tuple[str, ...] = ("sku", "description", "quantity", "unit_price", "net_amount")


class LayoutError(ValueError):
    """A layout file that cannot be used. The message names the exact JSON key at fault."""


@dataclass(frozen=True, slots=True)
class FieldLayout:
    """Where one scalar field is printed on this vendor's invoices, and what it looks like."""

    labels: tuple[str, ...]
    zones: tuple[Zone, ...]
    regex: re.Pattern[str] | None = None


@dataclass(frozen=True, slots=True)
class LineItemsLayout:
    """The table's column headers, and the words that mark where the table ends."""

    header_labels: Mapping[str, tuple[str, ...]]
    stop_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Layout:
    """One vendor's format: labels, zones, and how this vendor writes numbers and dates."""

    id: str
    language: str
    decimal_separator: str
    thousands_separator: str
    date_formats: tuple[str, ...]
    currency_symbols: Mapping[str, str]
    fields: Mapping[str, FieldLayout]
    line_items: LineItemsLayout
