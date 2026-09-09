"""Raw text to a typed value. Every one returns `None` on failure and never raises.

`parse_number` is the one implementation of the four separator steps in
`docs/LAYOUT_FORMAT.md`; money and percentages both go through it, because a vendor's
decimal and thousands separators govern every number it prints, not just its totals.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from invoice_extractor.extraction.spec import Candidate
from invoice_extractor.layout.schema import Layout

DIGITS = "0123456789"
NOT_ALNUM = re.compile(r"[^A-Za-z0-9]")


def parse_number(text: str, layout: Layout) -> Decimal | None:
    """Remove the thousands separator, make the decimal one a point, keep digits, parse."""
    cleaned = text.strip()
    if layout.thousands_separator:
        cleaned = cleaned.replace(layout.thousands_separator, "")
    cleaned = cleaned.replace(layout.decimal_separator, ".")
    sign = "-" if cleaned.startswith("-") else ""
    kept = "".join(character for character in cleaned if character in DIGITS or character == ".")
    try:
        return Decimal(f"{sign}{kept}")
    except InvalidOperation:
        return None


def strip_label(candidate: Candidate, layout: Layout) -> str:
    """The text after the label's colon. A line with no colon is already its own value."""
    _, colon, remainder = candidate.raw_text.partition(":")
    if candidate.evidence.matched_label is None or not colon:
        return candidate.raw_text.strip()
    return remainder.strip()


def parse_date(candidate: Candidate, layout: Layout) -> date | None:
    """The first of the layout's formats that reads this text. Order is the layout's choice."""
    text = strip_label(candidate, layout)
    for pattern in layout.date_formats:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def parse_money(candidate: Candidate, layout: Layout) -> Decimal | None:
    return parse_number(strip_label(candidate, layout), layout)


def parse_percent(candidate: Candidate, layout: Layout) -> Decimal | None:
    return parse_number(strip_label(candidate, layout).removesuffix("%"), layout)


def upper_alnum(candidate: Candidate, layout: Layout) -> str:
    """Letters and digits only, upper-cased — how a VAT id or currency code is compared."""
    return NOT_ALNUM.sub("", strip_label(candidate, layout)).upper()
