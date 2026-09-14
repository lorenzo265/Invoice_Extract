"""Raw text to a typed value. Every one returns `None` on failure and never raises.

`parse_number` is the one implementation of the four separator steps in
`docs/PROFILE_FORMAT.md`; money and percentages both go through it, because a vendor's
decimal and thousands separators govern every number it prints, not just its totals.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from invoice_extractor.extraction.spec import Candidate
from invoice_extractor.profile.schema import Profile

DIGITS = "0123456789"
NOT_ALNUM = re.compile(r"[^A-Za-z0-9]")


def parse_number(text: str, profile: Profile) -> Decimal | None:
    """Remove every thousands separator, make the decimal one a point, keep digits, parse."""
    numbers = profile.number_format
    cleaned = text.strip()
    for separator in numbers.thousands_separators:
        if separator:
            cleaned = cleaned.replace(separator, "")
    cleaned = cleaned.replace(numbers.decimal_separator, ".")
    sign = "-" if cleaned.startswith("-") else ""
    kept = "".join(character for character in cleaned if character in DIGITS or character == ".")
    try:
        return Decimal(f"{sign}{kept}")
    except InvalidOperation:
        return None


def strip_label(candidate: Candidate, profile: Profile) -> str:
    """The text after the label's colon, where the label is part of the text at all.

    `label_beside` and `label_below` hand over the value on its own — the label is a line
    of its own somewhere else — so a colon inside such a value is the value's, not a
    separator, and the whole text is kept. What decides is whether the text *starts* with
    the label that was matched, which only `label_right` ever produces.
    """
    text = candidate.raw_text.strip()
    label = candidate.evidence.matched_label
    if label is None or not text.lower().startswith(label.lower()):
        return text
    _, colon, remainder = text.partition(":")
    return remainder.strip() if colon else text


def parse_date(candidate: Candidate, profile: Profile) -> date | None:
    """The first of the profile's formats that reads this text, in the profile's order."""
    text = strip_label(candidate, profile)
    for pattern in profile.date_formats:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def parse_money(candidate: Candidate, profile: Profile) -> Decimal | None:
    return parse_number(strip_label(candidate, profile), profile)


def parse_percent(candidate: Candidate, profile: Profile) -> Decimal | None:
    return parse_number(strip_label(candidate, profile).removesuffix("%"), profile)


def upper_alnum(candidate: Candidate, profile: Profile) -> str:
    """Letters and digits only, upper-cased — how a VAT id or currency code is compared."""
    return NOT_ALNUM.sub("", strip_label(candidate, profile)).upper()
