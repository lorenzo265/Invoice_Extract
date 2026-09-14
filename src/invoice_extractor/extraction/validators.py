"""Does a normalized value look like what this field is supposed to hold?

A validator answers yes or no; it never raises and never reports. A `False` becomes
`FieldResult.valid=False` on the result, which is the per-field form of ADR-0005.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from invoice_extractor.domain.models import FieldValue
from invoice_extractor.extraction.spec import Validator
from invoice_extractor.profile.schema import FieldProfile

CURRENCY_CODE = re.compile(r"[A-Z]{3}")
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


def is_positive_money(value: FieldValue, field_profile: FieldProfile) -> bool:
    return isinstance(value, Decimal) and value > 0


def is_currency_code(value: FieldValue, field_profile: FieldProfile) -> bool:
    return CURRENCY_CODE.fullmatch(str(value)) is not None


def is_percent(value: FieldValue, field_profile: FieldProfile) -> bool:
    low, high = PERCENT_RANGE
    return isinstance(value, Decimal) and low <= value <= high
