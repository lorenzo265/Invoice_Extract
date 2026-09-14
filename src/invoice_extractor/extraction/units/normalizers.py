"""Raw text to a typed value. Every one returns `None` on failure and never raises.

`parse_number` is the one implementation of the separator rules in
`docs/PROFILE_FORMAT.md`; money, rates and quantities all go through it, because a
vendor's decimal and thousands separators govern every number it prints. A vendor may
write more than one thousands separator, and every one it declares is removed, because
which one a document drew is the document's business.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.extraction.units.dates import parse_date as read_date
from invoice_extractor.profile.schema import Profile

DIGITS = "0123456789"
NOT_ALNUM = re.compile(r"[^A-Za-z0-9]")
# A percentage may be written with the sign, or with the word, or with neither.
PERCENT_SIGNS = ("%", "‰")


def parse_number(text: str, profile: Profile) -> Decimal | None:
    """Remove every thousands separator, make the decimal one a point, keep digits, parse."""
    numbers = profile.number_format
    cleaned = text.strip()
    for separator in numbers.thousands_separators:
        if separator:
            cleaned = cleaned.replace(separator, "")
    cleaned = cleaned.replace(numbers.decimal_separator, ".")
    sign = "-" if cleaned.lstrip().startswith("-") else ""
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
    return read_date(strip_label(candidate, profile), profile.date_formats, profile.calendar)


def parse_money(candidate: Candidate, profile: Profile) -> Decimal | None:
    return parse_number(without_currency(strip_label(candidate, profile), profile), profile)


def parse_percent(candidate: Candidate, profile: Profile) -> Decimal | None:
    text = strip_label(candidate, profile)
    for sign in PERCENT_SIGNS:
        text = text.replace(sign, "")
    return parse_number(text, profile)


def upper_alnum(candidate: Candidate, profile: Profile) -> str:
    """Letters and digits only, upper-cased — how a VAT id or currency code is compared."""
    return NOT_ALNUM.sub("", strip_label(candidate, profile)).upper()


def without_currency(text: str, profile: Profile) -> str:
    """A vendor may print its code beside the amount; the amount is what is parsed.

    `filters.looks_numeric` asks the same question before the parser does — `19.25 GBP` is
    an amount and not a sentence — so the rule is written once and both of them use it.
    """
    stripped = text
    for code in profile.currencies:
        stripped = stripped.replace(code, "").replace(code.lower(), "")
    return stripped
