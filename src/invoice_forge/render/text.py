"""Turning values into the exact strings a page shows.

A profile decides how a number reads — "9.965,24" in Germany, "9 965,24" in Sweden,
"9,965.24" in Britain — and a lexicon decides how a date reads. Both are printing
decisions, so nothing here ever changes a value: `money` formats a `Decimal` that was
already rounded, and the truth records the unformatted value beside the printed one.

Wrapping takes the width function as an argument rather than a font, so this module
measures nothing itself and stays free of PyMuPDF.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invoice_forge.lexicon.schema import Lexicon
from invoice_forge.model import to_cents
from invoice_forge.profiles.schema import DateFormat

GROUP = 3
MONEY_DECIMALS = 2
Measure = Callable[[str], float]


@dataclass(frozen=True, slots=True)
class NumberFormat:
    """The two separators a vendor prints numbers with, drawn once per document."""

    decimal: str
    thousands: str


def money(value: Decimal, number_format: NumberFormat) -> str:
    """An amount at two decimals, grouped and separated the way the profile writes it."""
    return _grouped(f"{to_cents(value):.{MONEY_DECIMALS}f}", number_format)


def price(value: Decimal, number_format: NumberFormat) -> str:
    """A unit price at its own precision, and never at fewer than two decimals.

    A supplier that quotes 38.0450 per unit prints all four digits — that is what a
    four-decimal price is for. Printing it as 38.05 would put a number on the page that
    the truth, and the line's own arithmetic, disagree with.
    """
    exponent = value.as_tuple().exponent
    places = max(-exponent, MONEY_DECIMALS) if isinstance(exponent, int) else MONEY_DECIMALS
    return _grouped(f"{value:.{places}f}", number_format)


def quantity(value: Decimal, number_format: NumberFormat) -> str:
    """A quantity without trailing zeros: 25, not 25.00, and 2,5 rather than 2.5."""
    return _grouped(plain(value), number_format)


def rate(value: Decimal, number_format: NumberFormat) -> str:
    """A rate as it is printed: whole where it is whole, and 5,5 where the profile uses commas."""
    return _grouped(plain(value), number_format)


def plain(value: Decimal) -> str:
    """The shortest exact spelling of a decimal, never in exponent notation.

    `Decimal("100").normalize()` is `1E+2`, which is why the whole values are quantized
    back rather than formatted straight from `normalize`.
    """
    trimmed = value.normalize()
    whole = trimmed.to_integral_value()
    return f"{whole:f}" if trimmed == whole else f"{trimmed:f}"


def date_text(value: date, date_format: DateFormat, lexicon: Lexicon) -> str:
    """One date in one of the six formats a profile may declare."""
    if date_format is DateFormat.ISO:
        return value.isoformat()
    if date_format is DateFormat.DAY_DOT_MONTH:
        return f"{value.day:02d}.{value.month:02d}.{value.year}"
    if date_format is DateFormat.DAY_SLASH_MONTH:
        return f"{value.day:02d}/{value.month:02d}/{value.year}"
    if date_format is DateFormat.MONTH_SLASH_DAY:
        return f"{value.month:02d}/{value.day:02d}/{value.year}"
    if date_format is DateFormat.DAY_MONTH_NAME:
        return f"{value.day} {lexicon.months[value.month - 1]} {value.year}"
    return f"{value.day:02d}-{lexicon.month_abbreviations[value.month - 1]}-{value.year}"


def wrap(text: str, width: float, measure: Measure) -> tuple[str, ...]:
    """Break on spaces to fit `width`; a word too long for the line gets a line anyway."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and measure(trial) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    return (*lines, current) if current else tuple(lines)


def _grouped(text: str, number_format: NumberFormat) -> str:
    """Group the integer part in threes and swap in the profile's decimal separator."""
    negative = text.startswith("-")
    whole, _, fraction = text.lstrip("-").partition(".")
    groups = [whole[max(at - GROUP, 0) : at] for at in range(len(whole), 0, -GROUP)]
    joined = number_format.thousands.join(reversed(groups))
    printed = f"{joined}{number_format.decimal}{fraction}" if fraction else joined
    return f"-{printed}" if negative else printed
