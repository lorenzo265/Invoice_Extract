"""The normalised value behind every printed string.

The truth records what the extractor should arrive at, not what the page says: an ISO
date where the page says "15.03.2024", a plain decimal where it says "9.965,24 EUR", an
upper-cased identifier where it says "USt-IdNr.: DE811234567". `docs/FIELD_CATALOG.md`
states the rule for each name; this module applies it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from invoice_forge.model import Document, LineItem, SubItem


def field_values(document: Document, headline_rate: Decimal | None) -> dict[str, str]:
    """Every canonical field this document carries, normalised. Absent names are absent."""
    values = {**_references(document), **_dates(document), **_amounts(document)}
    if headline_rate is not None:
        values["vat_rate"] = str(headline_rate)
    return {name: value for name, value in values.items() if value is not None}


def item_row(item: LineItem, cells: Mapping[str, list[dict[str, object]]]) -> dict[str, object]:
    """One line of the truth's table: the row's values, then the box of every read column."""
    return {
        "pos": item.pos,
        "part_number": item.part_number,
        "description": item.description,
        "quantity": str(item.quantity),
        "unit": item.unit,
        "unit_price": str(item.unit_price),
        "discount_pct": None if item.discount_pct is None else str(item.discount_pct),
        "vat_rate": str(item.vat_rate),
        "net_amount": str(item.net_amount),
        "section": item.section,
        "cells": {name: list(boxes) for name, boxes in cells.items()},
        "sub_items": [_sub_item(sub) for sub in item.sub_items],
    }


def _sub_item(sub: SubItem) -> dict[str, object]:
    return {
        "description": sub.description,
        "quantity": None if sub.quantity is None else str(sub.quantity),
        "unit_price": None if sub.unit_price is None else str(sub.unit_price),
    }


def _references(document: Document) -> dict[str, str | None]:
    identifiers = document.identifiers
    return {
        "invoice_number": identifiers.invoice_number,
        "order_number": identifiers.order_number,
        "customer_number": identifiers.customer_number,
        "contract_number": identifiers.contract_number,
        "our_reference": identifiers.our_reference,
        "your_reference": identifiers.your_reference,
        "credit_reference": identifiers.credit_reference,
        "supplier_vat_id": _identifier(document.supplier.vat_id),
        "customer_vat_id": _identifier(document.bill_to.vat_id),
        "currency": document.currency,
        "payment_terms": document.payment.terms,
        # Printed in groups of four, normalised without them: `docs/FIELD_CATALOG.md`
        # says an IBAN is read with its spaces removed and upper-cased.
        "iban": _identifier(document.payment.iban),
    }


def _dates(document: Document) -> dict[str, str | None]:
    dates = document.dates
    return {
        "invoice_date": _iso(dates.invoice_date),
        "due_date": _iso(dates.due_date),
        "supply_date": _iso(dates.supply_date),
    }


def _amounts(document: Document) -> dict[str, str | None]:
    totals = document.totals
    return {
        "subtotal": str(totals.subtotal),
        "vat_amount": str(totals.vat_amount),
        "total_amount": str(totals.total_amount),
    }


def _identifier(value: str | None) -> str | None:
    """Letters and digits only, upper-cased — what `upper_alnum` normalises a VAT id to."""
    if value is None:
        return None
    return "".join(character for character in value if character.isalnum()).upper()


def _iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()
