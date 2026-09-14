"""Fictional companies and the addresses they sit at.

Names are built from an invented stem, a trade word and the legal form the country uses.
No real company is copied, and none of these combinations names one; the hygiene scan
checks that structurally rather than against a list.

The words themselves are `sample/places.py`. Nothing here falls back to English: a
profile whose language or country no table covers is a document that would be printed in
the wrong words, so it is refused by name instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from random import Random
from typing import TypeVar

from invoice_forge.model import Party
from invoice_forge.profiles.schema import PostalCodePosition, VendorProfile
from invoice_forge.sample.patterns import fill
from invoice_forge.sample.places import (
    BANK_NAMES,
    CITIES,
    COUNTRY_NAMES,
    LEGAL_FORMS,
    NUMBER_FIRST_LANGUAGES,
    POSTAL_CODES,
    STEMS,
    STREETS,
    TRADES,
)

MAX_STREET_NUMBER = 199

Entry = TypeVar("Entry")


def company_name(language: str, country: str, rng: Random) -> str:
    stem = rng.choice(_one(STEMS, language, "stems"))
    trade = rng.choice(_one(TRADES, language, "trade words"))
    form = rng.choice(_one(LEGAL_FORMS, country, "legal forms"))
    return f"{stem} {trade} {form}"


def address_lines(profile: VendorProfile, country: str, rng: Random) -> tuple[str, ...]:
    """A street line, a locality line in the profile's order, and maybe a country line."""
    street = rng.choice(_one(STREETS, profile.language, "street names"))
    number = rng.randrange(1, MAX_STREET_NUMBER)
    postal = fill(_one(POSTAL_CODES, country, "postal code pattern"), rng)
    city = rng.choice(_one(CITIES, country, "cities"))
    lines = [_street_line(profile.language, street, number), _locality(profile, postal, city)]
    if profile.address_format.country_line:
        lines.append(_country_name(profile.language, country))
    return tuple(lines)


def party(profile: VendorProfile, country: str, vat_id: str | None, rng: Random) -> Party:
    return Party(
        name=company_name(profile.language, country, rng),
        lines=address_lines(profile, country, rng),
        vat_id=vat_id,
    )


def bank_name(language: str, rng: Random) -> str:
    """A bank that does not exist, named the way banks in that language are named."""
    stem = rng.choice(_one(STEMS, language, "stems"))
    return _one(BANK_NAMES, language, "bank name").format(stem=stem)


def _street_line(language: str, street: str, number: int) -> str:
    return f"{number} {street}" if language in NUMBER_FIRST_LANGUAGES else f"{street} {number}"


def _locality(profile: VendorProfile, postal: str, city: str) -> str:
    if profile.address_format.postal_code_position is PostalCodePosition.BEFORE_CITY:
        return f"{postal} {city}"
    return f"{city} {postal}"


def _country_name(language: str, country: str) -> str:
    named = _one(COUNTRY_NAMES, language, "country names")
    if country not in named:
        raise ValueError(f"no name for {country} in {language}; add it to places.COUNTRY_NAMES")
    return named[country]


def _one(table: Mapping[str, Entry], key: str, what: str) -> Entry:
    """Refuse rather than fall back: a missing entry is a document in the wrong words."""
    if key not in table:
        raise ValueError(f"no {what} for {key}; add it to invoice_forge.sample.places")
    return table[key]
