"""What a candidate has to survive before it is ranked.

A strategy reads the whole page, which is what makes it able to find a value wherever a
vendor drew it. A filter is where that generosity is paid for: a candidate introduced by
a label this field is not is dropped before the rankers are asked to choose between it
and a real one.

Only what is *wrong* is filtered. Where a field usually sits is a preference, not a
fence, so it is a ranker (`zone_priority`) rather than a filter: a vendor that moved a
block has not printed a different invoice, and a filter would throw the value away.
"""

from __future__ import annotations

from collections.abc import Sequence

from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.extraction.units.normalizers import strip_label, without_currency
from invoice_extractor.profile.schema import FieldProfile, Profile

# How much of a number's text has to be the number. A line that is mostly words is a
# sentence that happens to contain digits — a bank account, a page count, a date — and
# stripping its punctuation out would produce an amount no one printed.
NUMERIC_SHARE = 0.6


def not_a_trap(
    found: Sequence[Candidate], field: FieldProfile, profile: Profile
) -> list[Candidate]:
    """Drop what a trap label introduced: an order date is not the invoice date.

    A trap is a label the vendor prints beside the one this field wants, and the profile
    names them twice over — per field in `exclude_labels`, and once for the whole vendor
    in `noise.ignore_labels`. A label the field itself declares is never a trap for it,
    however many other fields call it one.
    """
    traps = _traps(field, profile)
    if not traps:
        return list(found)
    return [candidate for candidate in found if not _introduced_by(candidate, traps)]


def _traps(field: FieldProfile, profile: Profile) -> frozenset[str]:
    own = {label.casefold() for label in field.labels}
    named = (*field.exclude_labels, *profile.noise.ignore_labels)
    return frozenset(label.casefold() for label in named if label.casefold() not in own)


def _introduced_by(candidate: Candidate, traps: frozenset[str]) -> bool:
    matched = candidate.evidence.matched_label
    if matched is not None and matched.casefold() in traps:
        return True
    text = candidate.evidence.raw_text.strip().casefold()
    return any(text.startswith(trap) for trap in traps)


def looks_numeric(
    found: Sequence[Candidate], field: FieldProfile, profile: Profile
) -> list[Candidate]:
    """Drop what is a sentence rather than an amount.

    `IBAN SE81 2663 9935 1456 5769 3224 · Summa att betala` carries plenty of digits, and
    a parser that keeps the digits of whatever it is given reads a twenty-two figure
    total off it. A number is mostly its own characters; a sentence is not.

    The currency code comes off first, exactly as the parser takes it off: `19.25 GBP` is
    an amount printed the way a vendor prints one, not a line of prose about money.
    """
    return [candidate for candidate in found if _mostly_a_number(candidate, profile)]


def _mostly_a_number(candidate: Candidate, profile: Profile) -> bool:
    text = without_currency(strip_label(candidate, profile), profile).strip()
    allowed = _number_characters(profile)
    kept = sum(1 for character in text if character in allowed)
    return bool(text) and kept / len(text) >= NUMERIC_SHARE


def _number_characters(profile: Profile) -> frozenset[str]:
    """Digits, a sign, a percent, and the separators this vendor writes — nothing else.

    A space counts only where the vendor writes its thousands with one, which is what
    keeps `IBAN SE81 2663 9935` from reading as a number in a country that does not.
    """
    numbers = profile.number_format
    return frozenset(
        {*"0123456789+-%", numbers.decimal_separator, *numbers.thousands_separators} - {""}
    )
