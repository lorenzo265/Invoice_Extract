"""What kind of thing a printed value is, read from its characters alone.

A date looks like a date in every language, a VAT id in a known country matches the
pattern that country's profile declares, and an amount carries its own separators. None
of that needs the label's language, which is why a draft can say `this vendor writes
decimals with a comma` before anyone has told it which vendor it is.

Nothing here parses to a typed value; that is the engine's job, and it does it with a
profile. This reads the *shape* and what the shape implies for the profile that will be
written — the decimal separator an amount was printed with, the format name a date fits,
the country a VAT id belongs to.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import Enum

CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
CURRENCY_SYMBOLS = "€$£"
IBAN = re.compile(r"^[A-Z]{2}\d{2}(?: ?[A-Z0-9]{1,4}){3,8}$")
PERCENT = re.compile(r"^\d{1,2}(?:[.,]\d{1,2})?\s?%$")
# What a vendor may put between groups of digits: a point, a comma, a space, a no-break
# space, an apostrophe straight or typographic. Escapes, so none reads as a lookalike.
SEPARATORS = ".,' " + "\u00a0\u2019"
# A number as a page prints one: digits, with any of those between them.
NUMBER = re.compile(f"^-?\\d[\\d{re.escape(SEPARATORS)}]*$")
# Letters and digits with the punctuation an invoice number carries, and no spaces.
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.-]{1,29}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DOTTED_DATE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")
SLASHED_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/\d{4}$")
SPELLED_DATE = re.compile(r"^\d{1,2} (\S+) \d{4}$")
ABBREVIATED_DATE = re.compile(r"^\d{1,2}-(\S+)-\d{4}$")
MONTHS_IN_A_YEAR = 12
# The `date_formats` names `profile/loader.py` accepts, as the shapes above find them.
SLASHED = ("dd/mm/yyyy", "mm/dd/yyyy")


class Shape(Enum):
    DATE = "date"
    AMOUNT = "amount"
    PERCENT = "percent"
    CURRENCY = "currency"
    VAT_ID = "vat_id"
    IBAN = "iban"
    IDENTIFIER = "identifier"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class KnownId:
    """The shape of a VAT id in one country a profile already describes."""

    country: str
    prefix: str
    pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class Reading:
    """A value's shape, and what the shape says: format names, separators, a country."""

    shape: Shape
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Separators:
    """How one amount was printed: the decimal separator, and the thousands ones."""

    decimal: str
    thousands: tuple[str, ...]


def read(value: str, months: Collection[str], known_ids: Sequence[KnownId]) -> Reading:
    """The one shape a value has, most specific first.

    `months` is every month name and abbreviation of every language the vocabulary
    knows, case-folded, so a spelled date is recognised whatever language spelled it.
    """
    text = value.strip()
    compact = text.replace(" ", "")
    country = _country_of(compact, known_ids)
    if country is not None:
        return Reading(Shape.VAT_ID, (country,))
    if IBAN.match(text):
        return Reading(Shape.IBAN)
    if PERCENT.match(text):
        return Reading(Shape.PERCENT, (text.rstrip("% "),))
    formats = date_formats_of(text, months)
    if formats:
        return Reading(Shape.DATE, formats)
    return _numeric_or_textual(text)


def _numeric_or_textual(text: str) -> Reading:
    bare = without_currency(text)
    if NUMBER.match(bare):
        separators = separators_of(bare)
        return Reading(Shape.AMOUNT, (separators.decimal, *separators.thousands))
    if CURRENCY_CODE.match(text):
        return Reading(Shape.CURRENCY, (text,))
    if IDENTIFIER.match(text) and any(character.isdigit() for character in text):
        return Reading(Shape.IDENTIFIER)
    return Reading(Shape.TEXT)


def _country_of(compact: str, known_ids: Sequence[KnownId]) -> str | None:
    """The country whose VAT id this is, by its prefix and what follows it.

    A country whose ids carry no prefix is not matched here: its pattern is a run of
    digits, and any telephone number would be read as a VAT id. Such an id is still
    found through the label that introduces it.
    """
    for known in known_ids:
        if not known.prefix or not compact.startswith(known.prefix):
            continue
        if known.pattern.fullmatch(compact[len(known.prefix) :]):
            return known.country
    return None


def date_formats_of(text: str, months: Collection[str]) -> tuple[str, ...]:
    """The `date_formats` names that read this text; both slashed ones where it cannot tell.

    `03/04/2024` is a day in March and a day in April under the two slashed formats, and
    which one a vendor means is the vendor's to declare (`profile/loader.py`). A day above
    twelve settles it; otherwise both names are returned, and the draft says so.
    """
    if ISO_DATE.match(text):
        return ("yyyy-mm-dd",)
    if DOTTED_DATE.match(text):
        return ("dd.mm.yyyy",)
    slashed = SLASHED_DATE.match(text)
    if slashed:
        return _slashed(int(slashed.group(1)), int(slashed.group(2)))
    return _spelled(text, months)


def _slashed(first: int, second: int) -> tuple[str, ...]:
    if first > MONTHS_IN_A_YEAR:
        return ("dd/mm/yyyy",)
    if second > MONTHS_IN_A_YEAR:
        return ("mm/dd/yyyy",)
    return SLASHED


def _spelled(text: str, months: Collection[str]) -> tuple[str, ...]:
    spelled = SPELLED_DATE.match(text)
    if spelled and spelled.group(1).casefold() in months:
        return ("d Month yyyy",)
    abbreviated = ABBREVIATED_DATE.match(text)
    if abbreviated and abbreviated.group(1).casefold() in months:
        return ("dd-Mon-yyyy",)
    return ()


def without_currency(text: str) -> str:
    """The amount without the code or symbol a vendor prints beside it."""
    stripped = text.strip(CURRENCY_SYMBOLS + " ")
    words = stripped.split()
    kept = [word for word in words if not CURRENCY_CODE.match(word)]
    return " ".join(kept).strip(CURRENCY_SYMBOLS + " ")


def separators_of(number: str) -> Separators:
    """Which separator is the decimal one and which the thousands, from the digits after each.

    A separator followed by exactly three digits and then another separator or the end is
    a thousands separator; one followed by any other count of digits is the decimal one,
    and a vendor prints at most one of those. `1.234` alone is read as a thousand and
    some, because that is what an amount with no decimals printed in a European format
    looks like — a vendor whose amounts genuinely carry three decimals is rare, and the
    draft records the amounts it read for the person to check.
    """
    groups = re.split(f"[{re.escape(SEPARATORS)}]", number.lstrip("-"))
    separators = [character for character in number if character in SEPARATORS]
    decimal = ""
    thousands: list[str] = []
    for separator, following in zip(separators, groups[1:], strict=True):
        if len(following) == 3:
            if separator not in thousands:
                thousands.append(separator)
        else:
            decimal = separator
    return Separators(decimal=decimal, thousands=tuple(thousands))
