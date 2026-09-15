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
# An IBAN is a country, two check digits and a national account number: never shorter
# than Norway's fifteen characters, never longer than the standard's thirty-four.
IBAN = re.compile(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}")
IBAN_COUNTRY = 4
IBAN_REMAINDER = 1
ALPHABET_OFFSET = 55


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


def is_iban(value: FieldValue, field_profile: FieldProfile) -> bool:
    """The shape, and then the checksum the standard defines (`docs/FIELD_CATALOG.md`).

    The one validator a profile's own `pattern` does not override. Everywhere else the
    vendor knows the shape better than this package does — each country writes its VAT
    id differently — but an IBAN is ISO 13616's to define, and a vendor that wrote a
    looser shape would only be widening what it accepts. The profile's pattern is what
    `label_pattern` looks *for*; this is what an IBAN *is*.

    The shape alone would accept a VAT id, which is also two letters and then digits, and
    an Irish one carries letters after them too. The length is the first thing that tells
    them apart and the checksum is the second: moving the country and the check digits to
    the end and reading the whole as one number base 36 leaves a remainder of 1 when, and
    only when, it is right.
    """
    text = str(value)
    if IBAN.fullmatch(text) is None:
        return False
    return _mod97(text[IBAN_COUNTRY:] + text[:IBAN_COUNTRY]) == IBAN_REMAINDER


def _mod97(rearranged: str) -> int:
    """Each letter as its two-digit number, the whole read as one integer, modulo 97."""
    digits = "".join(
        one if one.isdigit() else str(ord(one) - ALPHABET_OFFSET) for one in rearranged
    )
    return int(digits) % 97


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
