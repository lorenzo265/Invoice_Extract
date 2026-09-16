"""The scalar halves of a profile: fields, party sections, the vendor's own identity.

Each function takes the merged JSON for one key and returns the record
`profile/schema.py` declares for it. Tables and the totals block are large enough to
have a module of their own (`profile/blocks.py`); everything else is here.
"""

from __future__ import annotations

from collections.abc import Mapping

from invoice_extractor.document.model import Zone
from invoice_extractor.document.zones import ALIASES, DEFAULT_GRID
from invoice_extractor.profile.lexicon import expand
from invoice_extractor.profile.reading import (
    as_decimal,
    as_mapping,
    as_strings,
    optional_choice,
    optional_count,
    optional_flag,
    optional_objects,
    optional_pattern,
    optional_plain_text,
    optional_strings,
    reject_unknown,
    require_mapping,
    require_pattern,
    require_strings,
    require_text,
)
from invoice_extractor.profile.schema import (
    PLACEMENT_NAMES,
    Calendar,
    CustomFieldProfile,
    DocumentTypes,
    Exemption,
    FieldProfile,
    Invariants,
    Noise,
    NumberFormat,
    Placement,
    ProfileError,
    SectionProfile,
    SupplierProfile,
    Variant,
    VatProfile,
)

FIELD_KEYS = ("labels", "zones", "placement", "pattern", "required", "exclude_labels")
CUSTOM_FIELD_KEYS = ("name", *FIELD_KEYS)
SECTION_KEYS = ("labels", "stop_labels", "max_lines", "placeholders", "zones")
VAT_KEYS = ("rates", "id_pattern", "id_prefix")
SUPPLIER_KEYS = ("name", "aliases", "address_lines", "vat_id")
DOCUMENT_TYPE_KEYS = ("invoice_titles", "credit_note_titles", "credit_reference_labels")
NUMBER_FORMAT_KEYS = ("decimal_separator", "thousands_separators")
VARIANT_KEYS = ("id", "when", "overlay")
WHEN_KEYS = ("document_type", "any_text")
NOISE_KEYS = ("ignore_labels",)
INVARIANTS_KEYS = ("exempt",)
EXEMPTION_KEYS = ("code", "reason")

DEFAULT_SECTION_LINES = 6

ROWS, COLUMNS = DEFAULT_GRID


def number_format(data: Mapping[str, object], path: str) -> NumberFormat:
    reject_unknown(data, NUMBER_FORMAT_KEYS, f"{path}.")
    separator = require_text(data, "decimal_separator", f"{path}.decimal_separator")
    if len(separator) != 1:
        raise ProfileError(f"{path}.decimal_separator must be a single character")
    return NumberFormat(
        decimal_separator=separator,
        thousands_separators=require_strings(data, "thousands_separators", path),
    )


def field_profile(
    data: Mapping[str, object], path: str, lexicon: Mapping[str, object]
) -> FieldProfile:
    reject_unknown(data, FIELD_KEYS, f"{path}.")
    labels = expand(require_strings(data, "labels", f"{path}.labels"), lexicon, f"{path}.labels")
    if not labels:
        raise ProfileError(f"{path}.labels must name at least one label")
    placement = Placement(
        optional_choice(data, "placement", f"{path}.placement", PLACEMENT_NAMES, "right")
    )
    pattern = optional_pattern(data, "pattern", f"{path}.pattern")
    if placement is Placement.PATTERN and pattern is None:
        raise ProfileError(f"{path}.pattern is required when placement is pattern")
    return FieldProfile(
        labels=labels,
        zones=zones(optional_strings(data, "zones", f"{path}.zones"), f"{path}.zones"),
        placement=placement,
        pattern=pattern,
        required=optional_flag(data, "required", f"{path}.required", True),
        exclude_labels=expand(
            optional_strings(data, "exclude_labels", f"{path}.exclude_labels"),
            lexicon,
            f"{path}.exclude_labels",
        ),
    )


def custom_field(
    data: Mapping[str, object], path: str, lexicon: Mapping[str, object]
) -> CustomFieldProfile:
    reject_unknown(data, CUSTOM_FIELD_KEYS, f"{path}.")
    name = require_text(data, "name", f"{path}.name")
    declared = {key: value for key, value in data.items() if key != "name"}
    return CustomFieldProfile(name=name, field=field_profile(declared, path, lexicon))


def section_profile(
    data: Mapping[str, object], path: str, lexicon: Mapping[str, object]
) -> SectionProfile:
    reject_unknown(data, SECTION_KEYS, f"{path}.")
    return SectionProfile(
        labels=expand(require_strings(data, "labels", f"{path}.labels"), lexicon, f"{path}.labels"),
        stop_labels=expand(
            optional_strings(data, "stop_labels", f"{path}.stop_labels"),
            lexicon,
            f"{path}.stop_labels",
        ),
        max_lines=optional_count(data, "max_lines", f"{path}.max_lines", DEFAULT_SECTION_LINES),
        placeholders=expand(
            optional_strings(data, "placeholders", f"{path}.placeholders"),
            lexicon,
            f"{path}.placeholders",
        ),
        zones=zones(optional_strings(data, "zones", f"{path}.zones"), f"{path}.zones"),
    )


def calendar(lexicon: Mapping[str, object]) -> Calendar:
    """The language's month names, as the lexicon spells them and abbreviates them."""
    return Calendar(
        months=as_strings(lexicon.get("months", []), "lexicon.months"),
        abbreviations=as_strings(
            lexicon.get("month_abbreviations", []), "lexicon.month_abbreviations"
        ),
    )


def vat_profile(data: Mapping[str, object], path: str) -> VatProfile:
    reject_unknown(data, VAT_KEYS, f"{path}.")
    declared = require_mapping(data, "rates", f"{path}.rates")
    if not declared:
        raise ProfileError(f"{path}.rates must name at least one rate")
    return VatProfile(
        rates={name: as_decimal(value, f"{path}.rates.{name}") for name, value in declared.items()},
        id_prefix=optional_plain_text(data, "id_prefix", f"{path}.id_prefix", ""),
        id_pattern=require_pattern(data, "id_pattern", f"{path}.id_pattern"),
    )


def supplier_profile(data: Mapping[str, object], path: str) -> SupplierProfile:
    reject_unknown(data, SUPPLIER_KEYS, f"{path}.")
    return SupplierProfile(
        name=require_text(data, "name", f"{path}.name"),
        aliases=optional_strings(data, "aliases", f"{path}.aliases"),
        address_lines=require_strings(data, "address_lines", f"{path}.address_lines"),
        vat_id=require_text(data, "vat_id", f"{path}.vat_id"),
    )


def document_types(
    data: Mapping[str, object], path: str, lexicon: Mapping[str, object]
) -> DocumentTypes:
    reject_unknown(data, DOCUMENT_TYPE_KEYS, f"{path}.")
    return DocumentTypes(
        invoice_titles=_titles(data, "invoice_titles", path, lexicon),
        credit_note_titles=_titles(data, "credit_note_titles", path, lexicon),
        credit_reference_labels=_titles(data, "credit_reference_labels", path, lexicon),
    )


def noise(data: Mapping[str, object], path: str, lexicon: Mapping[str, object]) -> Noise:
    reject_unknown(data, NOISE_KEYS, f"{path}.")
    return Noise(ignore_labels=_titles(data, "ignore_labels", path, lexicon))


def invariants(data: Mapping[str, object], path: str) -> Invariants:
    """Which arithmetic rules this vendor is excused from. Most vendors are excused none."""
    reject_unknown(data, INVARIANTS_KEYS, f"{path}.")
    declared = optional_objects(data, "exempt", f"{path}.exempt")
    return Invariants(
        exempt=tuple(
            _exemption(entry, f"{path}.exempt[{index}]") for index, entry in enumerate(declared)
        )
    )


def _exemption(data: Mapping[str, object], path: str) -> Exemption:
    reject_unknown(data, EXEMPTION_KEYS, f"{path}.")
    return Exemption(
        code=require_text(data, "code", f"{path}.code"),
        reason=require_text(data, "reason", f"{path}.reason"),
    )


def variant(data: Mapping[str, object], path: str) -> Variant:
    reject_unknown(data, VARIANT_KEYS, f"{path}.")
    when = require_mapping(data, "when", f"{path}.when")
    reject_unknown(when, WHEN_KEYS, f"{path}.when.")
    return Variant(
        id=require_text(data, "id", f"{path}.id"),
        when={key: require_text(when, key, f"{path}.when.{key}") for key in when},
        overlay=as_mapping(require_mapping(data, "overlay", f"{path}.overlay"), f"{path}.overlay"),
    )


def zones(names: tuple[str, ...], path: str) -> tuple[Zone, ...]:
    return tuple(_zone(name, f"{path}[{index}]") for index, name in enumerate(names))


def grid(data: Mapping[str, object], path: str) -> tuple[int, int]:
    """The zone grid a profile writes its zone names on: the reader's, or nothing."""
    reject_unknown(data, ("grid",), f"{path}.")
    if "grid" not in data:
        return DEFAULT_GRID
    if data["grid"] != [ROWS, COLUMNS]:
        raise ProfileError(
            f"{path}.grid must be [{ROWS}, {COLUMNS}]: the grid a page is classified on"
        )
    return DEFAULT_GRID


def _titles(
    data: Mapping[str, object], key: str, path: str, lexicon: Mapping[str, object]
) -> tuple[str, ...]:
    declared = optional_strings(data, key, f"{path}.{key}")
    return expand(declared, lexicon, f"{path}.{key}")


def _zone(name: str, path: str) -> Zone:
    if name in ALIASES:
        return ALIASES[name]
    row, column = _coordinates(name, path)
    return Zone(row=row, col=column)


def _coordinates(name: str, path: str) -> tuple[int, int]:
    row, marker, column = name.removeprefix("r").partition("c")
    if not name.startswith("r") or not marker or not row.isdigit() or not column.isdigit():
        raise ProfileError(f"{path} must be a zone name such as r1c3 or top_right")
    if not (1 <= int(row) <= ROWS and 1 <= int(column) <= COLUMNS):
        raise ProfileError(f"{path} must name a zone inside a {ROWS} by {COLUMNS} grid")
    return int(row), int(column)


def as_label_map(
    data: Mapping[str, object], path: str, lexicon: Mapping[str, object]
) -> Mapping[str, tuple[str, ...]]:
    """A map of name to label synonyms, with every lexicon reference expanded."""
    return {
        name: expand(as_strings(value, f"{path}.{name}"), lexicon, f"{path}.{name}")
        for name, value in data.items()
    }
