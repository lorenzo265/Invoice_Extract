"""The typed shape of a vendor profile — everything that varies from vendor to vendor.

A profile is data: `profiles/*.json`, validated by `profiles/loader.py` into the record
below. Adding a vendor is adding a JSON file and a lexicon, never a code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from invoice_forge.families import Family
from invoice_forge.model import ChargeType, CreditNoteStyle


class DateFormat(Enum):
    """The five ways the corpus prints a date. The words come from the lexicon."""

    DAY_DOT_MONTH = "dd.mm.yyyy"
    DAY_SLASH_MONTH = "dd/mm/yyyy"
    ISO = "yyyy-mm-dd"
    DAY_MONTH_NAME = "d Month yyyy"
    DAY_MONTH_ABBREVIATION = "dd-Mon-yyyy"


DATE_FORMAT_NAMES: tuple[str, ...] = tuple(fmt.value for fmt in DateFormat)


class PostalCodePosition(Enum):
    BEFORE_CITY = "before_city"
    AFTER_CITY = "after_city"


POSTAL_CODE_POSITIONS: tuple[str, ...] = tuple(place.value for place in PostalCodePosition)


class FontFamily(Enum):
    SANS = "sans"
    SERIF = "serif"


FONT_FAMILY_NAMES: tuple[str, ...] = tuple(font.value for font in FontFamily)


@dataclass(frozen=True, slots=True)
class VatRates:
    """The three rates a European vendor charges. `zero` covers exempt and reverse charge."""

    standard: Decimal
    reduced: Decimal
    zero: Decimal


@dataclass(frozen=True, slots=True)
class AddressFormat:
    postal_code_position: PostalCodePosition
    country_line: bool


@dataclass(frozen=True, slots=True)
class SupplierDetails:
    """The vendor itself, as it prints itself on every page of every document it sends.

    A profile describes one vendor (ADR-0006), so the supplier is declared rather than
    drawn: the same name, address and VAT id on every document the profile produces, and
    the values the extractor's supplier anchors expect to find.
    """

    name: str
    address_lines: tuple[str, ...]
    vat_id: str


@dataclass(frozen=True, slots=True)
class VendorProfile:
    """One vendor's format: its language, its numbers, its dates, its blocks."""

    id: str
    country: str
    language: str
    currency: str
    secondary_currency: str | None
    decimal_separator: str
    thousands_separators: tuple[str, ...]
    date_formats: tuple[DateFormat, ...]
    vat_rates: VatRates
    vat_id_pattern: str
    address_format: AddressFormat
    lexicon: str
    charges_used: tuple[ChargeType, ...]
    prints_supply_date: bool
    credit_note_style: CreditNoteStyle
    extensions: tuple[str, ...]
    families: tuple[Family, ...]
    fonts: FontFamily
    supplier: SupplierDetails
