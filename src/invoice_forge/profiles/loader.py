"""Read a vendor profile and validate it, top down, into a `VendorProfile`.

Profiles are package data, not files in the working directory: a corpus must generate
identically wherever it is generated from. `load_profile("de-DE")` therefore resolves
inside the package, and only an argument that looks like a path is read as one.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from invoice_forge.families import FAMILY_NAMES, Family
from invoice_forge.fields import METADATA_FIELDS
from invoice_forge.jsonspec import (
    SpecError,
    optional_text,
    read_object,
    reject_unknown,
    require_choice,
    require_choices,
    require_decimal,
    require_flag,
    require_mapping,
    require_strings,
    require_text,
)
from invoice_forge.model import CHARGE_TYPE_NAMES, ChargeType, CreditNoteStyle
from invoice_forge.model.document import CREDIT_NOTE_STYLE_NAMES
from invoice_forge.profiles.schema import (
    DATE_FORMAT_NAMES,
    FONT_FAMILY_NAMES,
    POSTAL_CODE_POSITIONS,
    AddressFormat,
    DateFormat,
    FontFamily,
    PostalCodePosition,
    VatRates,
    VendorProfile,
)

PROFILES_DIR = Path(__file__).parent
TOP_LEVEL_KEYS = (
    "id",
    "country",
    "language",
    "currency",
    "secondary_currency",
    "decimal_separator",
    "thousands_separators",
    "date_formats",
    "vat_rates",
    "vat_id_pattern",
    "address_format",
    "lexicon",
    "charges_used",
    "prints_supply_date",
    "credit_note_style",
    "extensions",
    "families",
    "fonts",
)
VAT_RATE_KEYS = ("standard", "reduced", "zero")
ADDRESS_KEYS = ("postal_code_position", "country_line")


def load_profile(id_or_path: str) -> VendorProfile:
    """Load a bundled profile by id, or any profile by path. Raises `SpecError`."""
    return _parse(read_object(_resolve(id_or_path), "profile"))


def bundled_profile_ids() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in PROFILES_DIR.glob("*.json")))


def _resolve(id_or_path: str) -> Path:
    looks_like_a_path = "/" in id_or_path or "\\" in id_or_path or id_or_path.endswith(".json")
    return Path(id_or_path) if looks_like_a_path else PROFILES_DIR / f"{id_or_path}.json"


def _parse(data: Mapping[str, object]) -> VendorProfile:
    reject_unknown(data, TOP_LEVEL_KEYS, "", "profile key")
    return VendorProfile(
        id=require_text(data, "id", "id"),
        country=require_text(data, "country", "country"),
        language=require_text(data, "language", "language"),
        currency=require_text(data, "currency", "currency"),
        secondary_currency=optional_text(data, "secondary_currency", "secondary_currency"),
        decimal_separator=_decimal_separator(data),
        thousands_separators=_thousands_separators(data),
        date_formats=_date_formats(data),
        vat_rates=_vat_rates(data),
        vat_id_pattern=require_text(data, "vat_id_pattern", "vat_id_pattern"),
        address_format=_address_format(data),
        lexicon=require_text(data, "lexicon", "lexicon"),
        charges_used=_charges_used(data),
        prints_supply_date=require_flag(data, "prints_supply_date", "prints_supply_date"),
        credit_note_style=_credit_note_style(data),
        extensions=_extensions(data),
        families=_families(data),
        fonts=FontFamily(require_choice(data, "fonts", "fonts", FONT_FAMILY_NAMES)),
    )


def _decimal_separator(data: Mapping[str, object]) -> str:
    separator = require_text(data, "decimal_separator", "decimal_separator")
    if len(separator) != 1:
        raise SpecError("decimal_separator must be a single character")
    return separator


def _thousands_separators(data: Mapping[str, object]) -> tuple[str, ...]:
    path = "thousands_separators"
    separators = require_strings(data, "thousands_separators", path)
    if not separators:
        raise SpecError(f"{path} must be a non-empty list of strings")
    decimal_separator = _decimal_separator(data)
    for index, separator in enumerate(separators):
        if len(separator) > 1:
            raise SpecError(f"{path}[{index}] must be a single character or empty")
        if separator == decimal_separator:
            raise SpecError(f"{path}[{index}] must differ from decimal_separator")
    return separators


def _date_formats(data: Mapping[str, object]) -> tuple[DateFormat, ...]:
    names = require_choices(data, "date_formats", "date_formats", DATE_FORMAT_NAMES)
    return tuple(DateFormat(name) for name in names)


def _vat_rates(data: Mapping[str, object]) -> VatRates:
    path = "vat_rates"
    rates = require_mapping(data, "vat_rates", path, "an object with standard, reduced and zero")
    reject_unknown(rates, VAT_RATE_KEYS, f"{path}.", "rate")
    return VatRates(
        standard=require_decimal(rates, "standard", f"{path}.standard"),
        reduced=require_decimal(rates, "reduced", f"{path}.reduced"),
        zero=require_decimal(rates, "zero", f"{path}.zero"),
    )


def _address_format(data: Mapping[str, object]) -> AddressFormat:
    path = "address_format"
    address = require_mapping(data, "address_format", path, "an object describing the address")
    reject_unknown(address, ADDRESS_KEYS, f"{path}.", "address key")
    position = require_choice(
        address, "postal_code_position", f"{path}.postal_code_position", POSTAL_CODE_POSITIONS
    )
    return AddressFormat(
        postal_code_position=PostalCodePosition(position),
        country_line=require_flag(address, "country_line", f"{path}.country_line"),
    )


def _charges_used(data: Mapping[str, object]) -> tuple[ChargeType, ...]:
    names = require_strings(data, "charges_used", "charges_used")
    for index, name in enumerate(names):
        if name not in CHARGE_TYPE_NAMES:
            raise SpecError(f"charges_used[{index}] must be one of: {', '.join(CHARGE_TYPE_NAMES)}")
    return tuple(ChargeType(name) for name in names)


def _credit_note_style(data: Mapping[str, object]) -> CreditNoteStyle:
    path = "credit_note_style"
    return CreditNoteStyle(require_choice(data, path, path, CREDIT_NOTE_STYLE_NAMES))


def _extensions(data: Mapping[str, object]) -> tuple[str, ...]:
    names = require_strings(data, "extensions", "extensions")
    for index, name in enumerate(names):
        if name not in METADATA_FIELDS:
            raise SpecError(f"extensions[{index}] must be one of: {', '.join(METADATA_FIELDS)}")
    return names


def _families(data: Mapping[str, object]) -> tuple[Family, ...]:
    names = require_choices(data, "families", "families", FAMILY_NAMES)
    return tuple(Family(name) for name in names)
