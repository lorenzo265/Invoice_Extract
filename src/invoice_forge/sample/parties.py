"""Fictional companies and the addresses they sit at.

Names are built from an invented stem, a trade word and the legal form the country uses.
No real company is copied, and none of these combinations names one; the hygiene scan
checks that structurally rather than against a list.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from random import Random

from invoice_forge.model import Party
from invoice_forge.profiles.schema import PostalCodePosition, VendorProfile
from invoice_forge.sample.patterns import fill

STEMS = {
    "de": ("Rheinwerk", "Nordlicht", "Elbtal", "Schwarzbach", "Hafenkante", "Sturmfels"),
    "en": ("Ashcroft", "Wearside", "Kestrel", "Mallowfield", "Brackenhill", "Thornby"),
    "fr": ("Valmont", "Bellerive", "Clairbois", "Hautfort", "Rivegauche", "Montclair"),
    "sv": ("Fjordvik", "Bergslund", "Strandby", "Norrsken", "Almvik", "Tallhöjd"),
}
TRADES = {
    "de": ("Industriebedarf", "Technik", "Handelsgesellschaft", "Systeme", "Elektronik"),
    "en": ("Components", "Industrial Supplies", "Systems", "Technologies", "Trading"),
    "fr": ("Composants", "Fournitures Industrielles", "Systèmes", "Technologies"),
    "sv": ("Elektronik", "Industri", "System", "Teknik", "Handel"),
}
LEGAL_FORMS = {
    "DE": ("GmbH", "GmbH & Co. KG", "AG"),
    "GB": ("Ltd", "Limited", "PLC"),
    "FR": ("SARL", "SAS", "SA"),
    "SE": ("AB", "AB", "HB"),
}
STREETS = {
    "de": ("Am Hafen", "Industrieweg", "Lindenstraße", "Gutenbergstraße", "Talweg"),
    "en": ("Foundry Road", "Kestrel Way", "Millbrook Lane", "Harbour Street", "Elm Close"),
    "fr": ("rue des Ateliers", "avenue du Port", "chemin des Vignes", "rue Lavoisier"),
    "sv": ("Industrivägen", "Hamngatan", "Verkstadsgatan", "Björkstigen"),
}
CITIES = {
    "DE": ("Duisburg", "Hamburg", "Leipzig", "Augsburg", "Kassel"),
    "GB": ("Manchester", "Leeds", "Bristol", "Sheffield", "Coventry"),
    "FR": ("Lyon", "Nantes", "Strasbourg", "Rennes", "Toulouse"),
    "SE": ("Göteborg", "Malmö", "Uppsala", "Norrköping", "Örebro"),
}
COUNTRY_NAMES = {
    "de": {"DE": "Deutschland", "GB": "Großbritannien", "FR": "Frankreich", "SE": "Schweden"},
    "en": {"DE": "Germany", "GB": "United Kingdom", "FR": "France", "SE": "Sweden"},
    "fr": {"DE": "Allemagne", "GB": "Royaume-Uni", "FR": "France", "SE": "Suède"},
    "sv": {"DE": "Tyskland", "GB": "Storbritannien", "FR": "Frankrike", "SE": "Sverige"},
}
POSTAL_CODES = {
    "DE": r"\d{5}",
    "GB": r"[A-Z]{2}\d \d[A-Z]{2}",
    "FR": r"\d{5}",
    "SE": r"\d{3} \d{2}",
}
DEFAULT_POSTAL_CODE = r"\d{5}"
MAX_STREET_NUMBER = 199
# How each language builds a bank's name from a place word.
COMPOUND_BANK_WORDS = {"de": "bank", "sv": "banken"}
# Where the house number goes. German and Swedish put it after the street name.
NUMBER_FIRST_LANGUAGES = frozenset({"en", "fr"})


def company_name(language: str, country: str, rng: Random) -> str:
    stem = rng.choice(_words(STEMS, language))
    trade = rng.choice(_words(TRADES, language))
    form = rng.choice(LEGAL_FORMS.get(country, ("Ltd",)))
    return f"{stem} {trade} {form}"


def address_lines(profile: VendorProfile, country: str, rng: Random) -> tuple[str, ...]:
    """A street line, a locality line in the profile's order, and maybe a country line."""
    street = rng.choice(_words(STREETS, profile.language))
    number = rng.randrange(1, MAX_STREET_NUMBER)
    postal = fill(POSTAL_CODES.get(country, DEFAULT_POSTAL_CODE), rng)
    city = rng.choice(CITIES.get(country, CITIES["DE"]))
    lines = [_street_line(profile.language, street, number), _locality(profile, postal, city)]
    if profile.address_format.country_line:
        lines.append(_names(COUNTRY_NAMES, profile.language).get(country, country))
    return tuple(lines)


def party(profile: VendorProfile, country: str, vat_id: str | None, rng: Random) -> Party:
    return Party(
        name=company_name(profile.language, country, rng),
        lines=address_lines(profile, country, rng),
        vat_id=vat_id,
    )


def bank_name(language: str, rng: Random) -> str:
    """A bank that does not exist, named the way banks in that language are named."""
    stem = rng.choice(_words(STEMS, language))
    compound = COMPOUND_BANK_WORDS.get(language)
    if compound is not None:
        return f"{stem}{compound}"
    return f"Banque {stem}" if language == "fr" else f"{stem} Bank"


def _street_line(language: str, street: str, number: int) -> str:
    return f"{number} {street}" if language in NUMBER_FIRST_LANGUAGES else f"{street} {number}"


def _locality(profile: VendorProfile, postal: str, city: str) -> str:
    if profile.address_format.postal_code_position is PostalCodePosition.BEFORE_CITY:
        return f"{postal} {city}"
    return f"{city} {postal}"


def _words(table: Mapping[str, Sequence[str]], language: str) -> Sequence[str]:
    """English is the fallback: a profile may name a language no table has words for yet."""
    return table.get(language, table["en"])


def _names(table: Mapping[str, Mapping[str, str]], language: str) -> Mapping[str, str]:
    return table.get(language, table["en"])
