"""Does a normalized value look like what this field is supposed to hold?

A validator answers yes or no; it never raises and never reports. A `False` becomes
`FieldResult.valid=False` on the result, which is the per-field form of ADR-0005.
"""

from __future__ import annotations

import re
from datetime import date

from invoice_extractor.domain.models import FieldValue
from invoice_extractor.extraction.candidate import Validator
from invoice_extractor.profile.schema import FieldProfile

IDENTIFIER = re.compile(r"[A-Z0-9][A-Z0-9/-]{2,}")
VAT_ID = re.compile(r"[A-Z]{0,2}[A-Z0-9]{5,14}")
# How long a line of a document runs before it is a paragraph of one. The longest terms
# the corpus prints are 54 characters; twice that is a line and not a page.
SENTENCE_LIMIT = 120


def matches_pattern(default: str) -> Validator:
    """A shape check. The profile's own `pattern` for this field overrides the default."""
    fallback = re.compile(default)

    def matches(value: FieldValue, field_profile: FieldProfile) -> bool:
        pattern = field_profile.pattern if field_profile.pattern is not None else fallback
        return pattern.fullmatch(str(value)) is not None

    return matches


def is_date(value: FieldValue, field_profile: FieldProfile) -> bool:
    return isinstance(value, date)


def is_sentence(value: FieldValue, field_profile: FieldProfile) -> bool:
    """Words, not a reference: what a vendor writes where its terms of payment go.

    An identifier is checked against a shape; a sentence has none worth declaring, so
    what is checked is that it reads like one — some letters in it, and short enough to
    be a line of a document rather than a paragraph of one.
    """
    text = str(value).strip()
    return bool(text) and len(text) <= SENTENCE_LIMIT and any(one.isalpha() for one in text)


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
