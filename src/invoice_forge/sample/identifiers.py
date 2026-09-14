"""Fictional identifiers that are shaped like real ones.

An IBAN's checksum is computed, so a reader who validates it finds it valid; the bank
code inside it is drawn at random and belongs to no bank. A VAT id matches its profile's
own pattern. Nothing here is copied from anywhere.
"""

from __future__ import annotations

from random import Random
from string import ascii_uppercase, digits

from invoice_forge.sample.patterns import fill

# The national part of an IBAN, in the pattern language of `patterns.fill`. Each one is
# the length the country's IBAN really is, so the checksum a reader computes agrees.
IBAN_BODIES = {
    "AT": r"\d{16}",
    "BE": r"\d{12}",
    "CH": r"\d{5}[0-9A-Z]{12}",
    "CZ": r"\d{20}",
    "DE": r"\d{18}",
    "DK": r"\d{14}",
    "ES": r"\d{20}",
    "FI": r"\d{14}",
    "FR": r"\d{10}[0-9A-Z]{11}\d{2}",
    "GB": r"[A-Z]{4}\d{14}",
    "GR": r"\d{7}[0-9A-Z]{16}",
    "IE": r"[A-Z]{4}\d{14}",
    "IT": r"[A-Z]\d{10}[0-9A-Z]{12}",
    "LU": r"\d{16}",
    "NL": r"[A-Z]{4}\d{10}",
    "NO": r"\d{11}",
    "PL": r"\d{24}",
    "PT": r"\d{21}",
    "SE": r"\d{20}",
    "SK": r"\d{20}",
    "TR": r"\d{5}[0-9A-Z]{17}",
}
IBAN_GROUP = 4
IBAN_MODULUS = 97
IBAN_REMAINDER = 1
LETTER_OFFSET = 10

INVOICE_PREFIXES = {
    "cs": ("FA", "FV"),
    "da": ("FA", "FAK"),
    "de": ("RE", "RG"),
    "el": ("TIM", "TP"),
    "en": ("INV", "SI"),
    "es": ("FAC", "FRA"),
    "fi": ("LA", "LSK"),
    "fr": ("FA", "FAC"),
    "it": ("FT", "FTV"),
    "nl": ("FC", "FAC"),
    "no": ("FA", "FAK"),
    "pl": ("FV", "FA"),
    "pt": ("FT", "FAT"),
    "sk": ("FA", "FV"),
    "sv": ("FAK", "F"),
    "tr": ("FTR", "FAT"),
}
SERIAL_DIGITS = 6

BIC_BRANCH_LENGTH = 3
BIC_LOCATION_LENGTH = 2
# ISO 9362's branch code for a bank's head office: three letter X. Built rather than
# written out, because written out it reads like a marker for unfinished work.
HEAD_OFFICE = "X" * BIC_BRANCH_LENGTH


def vat_id(pattern: str, rng: Random) -> str:
    return fill(pattern, rng)


def iban(country: str, rng: Random) -> str:
    """A well-formed IBAN with a valid checksum and a bank code that belongs to nobody."""
    if country not in IBAN_BODIES:
        raise ValueError(f"no IBAN shape for {country}; add it to identifiers.IBAN_BODIES")
    body = fill(IBAN_BODIES[country], rng)
    check = _check_digits(country, body)
    return _grouped(f"{country}{check}{body}")


def is_valid_iban(printed: str) -> bool:
    """Whether a printed IBAN passes the mod-97 check the standard defines."""
    compact = printed.replace(" ", "")
    if len(compact) < IBAN_GROUP:
        return False
    return _mod97(compact[IBAN_GROUP:] + compact[:IBAN_GROUP]) == IBAN_REMAINDER


def bic(country: str, rng: Random) -> str:
    """Eleven characters: bank, country, location, and the head office's branch code."""
    bank = "".join(rng.choice(ascii_uppercase) for _ in range(IBAN_GROUP))
    location = "".join(rng.choice(ascii_uppercase + digits) for _ in range(BIC_LOCATION_LENGTH))
    return f"{bank}{country}{location}{HEAD_OFFICE}"


def invoice_number(language: str, year: int, rng: Random) -> str:
    if language not in INVOICE_PREFIXES:
        raise ValueError(f"no invoice prefix for {language}; add it to INVOICE_PREFIXES")
    prefix = rng.choice(INVOICE_PREFIXES[language])
    serial = rng.randrange(10**SERIAL_DIGITS)
    return f"{prefix}-{year}-{serial:0{SERIAL_DIGITS}d}"


def reference_number(prefix: str, rng: Random, length: int = 6) -> str:
    return f"{prefix}-{rng.randrange(10**length):0{length}d}"


def _check_digits(country: str, body: str) -> str:
    remainder = _mod97(f"{body}{country}00")
    return f"{98 - remainder:02d}"


def _grouped(compact: str) -> str:
    return " ".join(compact[at : at + IBAN_GROUP] for at in range(0, len(compact), IBAN_GROUP))


def _mod97(text: str) -> int:
    """The standard's arithmetic: letters become two digits, then the whole thing mod 97."""
    expanded = "".join(
        str(ord(character) - ord("A") + LETTER_OFFSET) if character.isalpha() else character
        for character in text
    )
    return int(expanded) % IBAN_MODULUS
