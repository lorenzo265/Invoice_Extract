"""Does a normalized value look like what this field is supposed to hold?

A validator answers yes or no; it never raises and never reports. A `False` becomes
`FieldResult.valid=False` on the result, which is the per-field form of ADR-0005.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from invoice_extractor.domain.models import FieldValue
from invoice_extractor.extraction.candidate import Validator
from invoice_extractor.profile.schema import FieldProfile

IDENTIFIER = re.compile(r"[A-Z0-9][A-Z0-9/-]{2,}")
VAT_ID = re.compile(r"[A-Z]{0,2}[A-Z0-9]{5,14}")
PERCENT_RANGE = (Decimal(0), Decimal(100))


def matches_pattern(default: str) -> Validator:
    """A shape check. The profile's own `pattern` for this field overrides the default."""
    fallback = re.compile(default)

    def matches(value: FieldValue, field_profile: FieldProfile) -> bool:
        pattern = field_profile.pattern if field_profile.pattern is not None else fallback
        return pattern.fullmatch(str(value)) is not None

    return matches


def is_date(value: FieldValue, field_profile: FieldProfile) -> bool:
    return isinstance(value, date)


def is_money(value: FieldValue, field_profile: FieldProfile) -> bool:
    """Any amount, including a negative one: a credit note reverses what it credits."""
    return isinstance(value, Decimal)


def is_percent(value: FieldValue, field_profile: FieldProfile) -> bool:
    low, high = PERCENT_RANGE
    return isinstance(value, Decimal) and low <= value <= high


def is_identifier(value: FieldValue, field_profile: FieldProfile) -> bool:
    return matches_pattern(IDENTIFIER.pattern)(value, field_profile)


def is_vat_id(value: FieldValue, field_profile: FieldProfile) -> bool:
    """A country prefix and a registration number — and a registration number has digits.

    Requiring one is what separates a VAT id from the label that introduces it: strip the
    punctuation out of `Kunden-USt-IdNr.` and what is left is the right length and the
    right alphabet, and is not an identifier at all.
    """
    text = str(value)
    return matches_pattern(VAT_ID.pattern)(value, field_profile) and any(
        character.isdigit() for character in text
    )
