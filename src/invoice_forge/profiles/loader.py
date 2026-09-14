"""Read a vendor profile and validate it, top down, into a `VendorProfile`.

The profile files are shared with the extractor (ADR-0006): one file describes one
vendor, the generator draws what it says and the extractor reads it back. Each program
validates the half it needs and names the other half without parsing it, so neither can
quietly stop describing the same vendor.

Profiles live in `profiles/` at the root of the working directory, beside the lexicons —
the same convention every command in this repository already runs under.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from invoice_forge.families import FAMILY_NAMES, Family
from invoice_forge.fields import METADATA_FIELDS
from invoice_forge.jsonspec import (
    SpecError,
    read_object,
    reject_unknown,
    require_choice,
    require_choices,
    require_decimal,
    require_flag,
    require_mapping,
    require_object_list,
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
    SupplierDetails,
    VatRates,
    VendorProfile,
)

PROFILES_DIR = Path("profiles")
DEFAULTS_ID = "_defaults"

# What the generator reads, and what the extractor reads. A key in neither list is a
# typo; a key in the other program's list is simply not this program's business.
GENERATOR_KEYS = (
    "id",
    "country",
    "language",
    "lexicon",
    "number_format",
    "date_formats",
    "currencies",
    "vat",
    "supplier",
    "custom_fields",
    "render",
)
EXTRACTOR_KEYS = (
    "zones",
    "fields",
    "parties",
    "line_items",
    "vat_summary",
    "totals",
    "variants",
    "document_types",
    "noise",
)
TOP_LEVEL_KEYS = (*GENERATOR_KEYS, *EXTRACTOR_KEYS)
RENDER_KEYS = (
    "address_format",
    "charges_used",
    "prints_supply_date",
    "credit_note_style",
    "families",
    "fonts",
)
NUMBER_FORMAT_KEYS = ("decimal_separator", "thousands_separators")
VAT_KEYS = ("rates", "id_prefix", "id_pattern")
VAT_RATE_KEYS = ("standard", "reduced", "zero")
SUPPLIER_KEYS = ("name", "aliases", "address_lines", "vat_id")
ADDRESS_KEYS = ("postal_code_position", "country_line")


def load_profile(id_or_path: str) -> VendorProfile:
    """Load a profile by id under `profiles/`, or by path. Raises `SpecError`."""
    return _parse(read_object(_resolve(id_or_path), "profile"))


def profile_ids() -> tuple[str, ...]:
    """Every vendor under `profiles/`, in name order. The shared defaults are not one."""
    return tuple(
        sorted(path.stem for path in PROFILES_DIR.glob("*.json") if path.stem != DEFAULTS_ID)
    )


def _resolve(id_or_path: str) -> Path:
    looks_like_a_path = "/" in id_or_path or "\\" in id_or_path or id_or_path.endswith(".json")
    return Path(id_or_path) if looks_like_a_path else PROFILES_DIR / f"{id_or_path}.json"


def _parse(data: Mapping[str, object]) -> VendorProfile:
    reject_unknown(data, TOP_LEVEL_KEYS, "", "profile key")
    render = _render(data)
    currencies = _currencies(data)
    numbers = require_mapping(data, "number_format", "number_format", "an object of separators")
    reject_unknown(numbers, NUMBER_FORMAT_KEYS, "number_format.", "number format key")
    return VendorProfile(
        id=require_text(data, "id", "id"),
        country=require_text(data, "country", "country"),
        language=require_text(data, "language", "language"),
        currency=currencies[0],
        secondary_currency=currencies[1] if len(currencies) > 1 else None,
        decimal_separator=_decimal_separator(numbers),
        thousands_separators=_thousands_separators(numbers),
        date_formats=_date_formats(data),
        vat_rates=_vat_rates(data),
        vat_id_pattern=_vat_id_pattern(data),
        address_format=_address_format(render),
        lexicon=require_text(data, "lexicon", "lexicon"),
        charges_used=_charges_used(render),
        prints_supply_date=require_flag(render, "prints_supply_date", "render.prints_supply_date"),
        credit_note_style=_credit_note_style(render),
        extensions=_extensions(data),
        families=_families(render),
        fonts=FontFamily(require_choice(render, "fonts", "render.fonts", FONT_FAMILY_NAMES)),
        supplier=_supplier(data),
    )


def _render(data: Mapping[str, object]) -> Mapping[str, object]:
    render = require_mapping(data, "render", "render", "an object of drawing settings")
    reject_unknown(render, RENDER_KEYS, "render.", "render key")
    return render


def _currencies(data: Mapping[str, object]) -> tuple[str, ...]:
    currencies = require_strings(data, "currencies", "currencies")
    if not currencies:
        raise SpecError("currencies must be a non-empty list of strings")
    return currencies


def _supplier(data: Mapping[str, object]) -> SupplierDetails:
    supplier = require_mapping(data, "supplier", "supplier", "an object describing the vendor")
    reject_unknown(supplier, SUPPLIER_KEYS, "supplier.", "supplier key")
    lines = require_strings(supplier, "address_lines", "supplier.address_lines")
    if not lines:
        raise SpecError("supplier.address_lines must be a non-empty list of strings")
    return SupplierDetails(
        name=require_text(supplier, "name", "supplier.name"),
        address_lines=lines,
        vat_id=require_text(supplier, "vat_id", "supplier.vat_id"),
    )


def _decimal_separator(numbers: Mapping[str, object]) -> str:
    separator = require_text(numbers, "decimal_separator", "number_format.decimal_separator")
    if len(separator) != 1:
        raise SpecError("number_format.decimal_separator must be a single character")
    return separator


def _thousands_separators(numbers: Mapping[str, object]) -> tuple[str, ...]:
    path = "number_format.thousands_separators"
    separators = require_strings(numbers, "thousands_separators", path)
    if not separators:
        raise SpecError(f"{path} must be a non-empty list of strings")
    decimal_separator = _decimal_separator(numbers)
    for index, separator in enumerate(separators):
        if len(separator) > 1:
            raise SpecError(f"{path}[{index}] must be a single character or empty")
        if separator == decimal_separator:
            raise SpecError(f"{path}[{index}] must differ from decimal_separator")
    return separators


def _date_formats(data: Mapping[str, object]) -> tuple[DateFormat, ...]:
    names = require_choices(data, "date_formats", "date_formats", DATE_FORMAT_NAMES)
    return tuple(DateFormat(name) for name in names)


def _vat(data: Mapping[str, object]) -> Mapping[str, object]:
    vat = require_mapping(data, "vat", "vat", "an object with rates, id_prefix and id_pattern")
    reject_unknown(vat, VAT_KEYS, "vat.", "vat key")
    return vat


def _vat_rates(data: Mapping[str, object]) -> VatRates:
    path = "vat.rates"
    rates = require_mapping(_vat(data), "rates", path, "an object with standard, reduced and zero")
    reject_unknown(rates, VAT_RATE_KEYS, f"{path}.", "rate")
    return VatRates(
        standard=require_decimal(rates, "standard", f"{path}.standard"),
        reduced=require_decimal(rates, "reduced", f"{path}.reduced"),
        zero=require_decimal(rates, "zero", f"{path}.zero"),
    )


def _vat_id_pattern(data: Mapping[str, object]) -> str:
    """The country prefix a vendor's VAT id carries, then the digits after it."""
    vat = _vat(data)
    prefix = vat.get("id_prefix", "")
    if not isinstance(prefix, str):
        raise SpecError("vat.id_prefix must be a string")
    return prefix + require_text(vat, "id_pattern", "vat.id_pattern")


def _address_format(render: Mapping[str, object]) -> AddressFormat:
    path = "render.address_format"
    address = require_mapping(render, "address_format", path, "an object describing the address")
    reject_unknown(address, ADDRESS_KEYS, f"{path}.", "address key")
    position = require_choice(
        address, "postal_code_position", f"{path}.postal_code_position", POSTAL_CODE_POSITIONS
    )
    return AddressFormat(
        postal_code_position=PostalCodePosition(position),
        country_line=require_flag(address, "country_line", f"{path}.country_line"),
    )


def _charges_used(render: Mapping[str, object]) -> tuple[ChargeType, ...]:
    names = require_strings(render, "charges_used", "render.charges_used")
    for index, name in enumerate(names):
        if name not in CHARGE_TYPE_NAMES:
            raise SpecError(
                f"render.charges_used[{index}] must be one of: {', '.join(CHARGE_TYPE_NAMES)}"
            )
    return tuple(ChargeType(name) for name in names)


def _credit_note_style(render: Mapping[str, object]) -> CreditNoteStyle:
    path = "render.credit_note_style"
    return CreditNoteStyle(
        require_choice(render, "credit_note_style", path, CREDIT_NOTE_STYLE_NAMES)
    )


def _extensions(data: Mapping[str, object]) -> tuple[str, ...]:
    """The optional references this vendor prints, named by its own custom fields."""
    declared = require_object_list(data, "custom_fields", "custom_fields")
    names = tuple(
        require_text(entry, "name", f"custom_fields[{index}].name")
        for index, entry in enumerate(declared)
    )
    for index, name in enumerate(names):
        if name not in METADATA_FIELDS:
            raise SpecError(
                f"custom_fields[{index}].name must be one of: {', '.join(METADATA_FIELDS)}"
            )
    return names


def _families(render: Mapping[str, object]) -> tuple[Family, ...]:
    names = require_choices(render, "families", "render.families", FAMILY_NAMES)
    return tuple(Family(name) for name in names)
