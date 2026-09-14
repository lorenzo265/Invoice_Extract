"""Reading a date a vendor printed in its own language.

`datetime.strptime` reads `%B` and `%b` in the C locale, which is English, so a French
invoice's `14 juin 2024` is unreadable by the pattern that describes it. The profile
carries its language's month names (from the same lexicon its labels come from), so a
spelled month is turned into its number before the pattern is applied and the pattern is
turned into the numeric one that then reads it.

Nothing here guesses: a text no declared format reads comes back as `None`, and the field
is reported missing rather than filled in with a date that was not printed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from invoice_extractor.profile.schema import Calendar

SPELLED = ("%B", "%b")
NUMERIC_MONTH = "%m"


def parse_date(text: str, formats: Sequence[str], calendar: Calendar) -> date | None:
    """The first of the profile's formats that reads this text, in the profile's order."""
    cleaned = text.strip()
    for pattern in formats:
        read = _read(cleaned, pattern, calendar)
        if read is not None:
            return read
    return None


def _read(text: str, pattern: str, calendar: Calendar) -> date | None:
    if any(marker in pattern for marker in SPELLED):
        return _spelled(text, pattern, calendar)
    return _strptime(text, pattern)


def _spelled(text: str, pattern: str, calendar: Calendar) -> date | None:
    """Swap the month this language names for its number, then read the numeric pattern."""
    numbered = _numbered(text, calendar)
    if numbered is None:
        return None
    for marker in SPELLED:
        pattern = pattern.replace(marker, NUMERIC_MONTH)
    return _strptime(numbered, pattern)


def _numbered(text: str, calendar: Calendar) -> str | None:
    """The text with its month name replaced by the month's number, or `None` if it has none."""
    folded = text.casefold()
    for start, length, month in _matches(folded, calendar):
        return f"{text[:start]}{month:02d}{text[start + length :]}"
    return None


def _matches(folded: str, calendar: Calendar) -> list[tuple[int, int, int]]:
    """Where each month name this language knows sits in the text, longest name first."""
    found = []
    for month, name in _names(calendar):
        at = folded.find(name.casefold())
        if at >= 0:
            found.append((at, len(name), month))
    return sorted(found, key=lambda entry: -entry[1])


def _names(calendar: Calendar) -> list[tuple[int, str]]:
    spelled = [(number, name) for number, name in enumerate(calendar.months, start=1) if name]
    short = [(number, name) for number, name in enumerate(calendar.abbreviations, start=1) if name]
    return spelled + short


def _strptime(text: str, pattern: str) -> date | None:
    try:
        return datetime.strptime(text, pattern).date()  # a printed date carries no time zone
    except ValueError:
        return None
