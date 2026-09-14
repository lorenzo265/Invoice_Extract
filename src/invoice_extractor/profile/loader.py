"""Read a profile and validate it, top down, into a `Profile`.

Three layers become one record: `profiles/_defaults.json`, which every vendor shares;
`profiles/<id>.json`, which is what this vendor does differently; and the language's
lexicon, which supplies the label vocabulary both this package and the generator print
from. A failure is a `ProfileError` naming the JSON key at fault, never a traceback.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from invoice_extractor.profile import blocks, parts
from invoice_extractor.profile.lexicon import LEXICON_ROOT, read_lexicon
from invoice_extractor.profile.merge import PROFILE_RULES, merge
from invoice_extractor.profile.reading import (
    optional_mapping,
    optional_objects,
    reject_unknown,
    require_mapping,
    require_strings,
    require_text,
)
from invoice_extractor.profile.schema import (
    PARTY_NAMES,
    CustomFieldProfile,
    FieldProfile,
    Profile,
    ProfileError,
    SectionProfile,
    TableProfile,
)

PROFILES_ROOT = Path("profiles")
DEFAULTS_ID = "_defaults"

# Keys this package reads. `render` is the generator's half of the shared file: the two
# programs describe one vendor, and each ignores what the other needs (ADR-0006).
TOP_LEVEL_KEYS = (
    "id",
    "language",
    "country",
    "lexicon",
    "number_format",
    "date_formats",
    "currencies",
    "vat",
    "supplier",
    "zones",
    "fields",
    "parties",
    "line_items",
    "vat_summary",
    "totals",
    "custom_fields",
    "variants",
    "document_types",
    "noise",
    "render",
)

# How each of the five ways a profile may print a date reads back. The two that spell a
# month sort last: `strptime` reads month names in the C locale, so a format that cannot
# read this language's words should not be tried before one that can read its digits.
DATE_PATTERNS: Mapping[str, str] = {
    "yyyy-mm-dd": "%Y-%m-%d",
    "dd.mm.yyyy": "%d.%m.%Y",
    "dd/mm/yyyy": "%d/%m/%Y",
    "d Month yyyy": "%d %B %Y",
    "dd-Mon-yyyy": "%d-%b-%Y",
}
SPELLED = ("d Month yyyy", "dd-Mon-yyyy")


def load_profile(id_or_path: str, root: Path = PROFILES_ROOT) -> Profile:
    """Load a profile by id under `root`, or by path. Raises `ProfileError`.

    The lexicons sit beside the profiles, because the two are one description of one
    vendor split by what varies per vendor and what varies per language.
    """
    declared = read_profile_json(_resolve(id_or_path, root))
    defaults = read_profile_json(root / f"{DEFAULTS_ID}.json")
    return parse(merge(defaults, declared, PROFILE_RULES), root.parent / LEXICON_ROOT)


def read_profile_json(path: Path) -> Mapping[str, object]:
    """One profile file as JSON, with a message that names the file when it cannot be read."""
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        raise ProfileError(f"no profile at {path}") from unreadable
    except json.JSONDecodeError as invalid:
        raise ProfileError(f"{path.name} is not valid JSON: {invalid.msg}") from invalid
    if not isinstance(parsed, dict):
        raise ProfileError(f"{path.name} must be an object")
    return parsed


def parse(data: Mapping[str, object], lexicon_root: Path = LEXICON_ROOT) -> Profile:
    """The merged JSON of one profile, validated into the record every stage reads."""
    reject_unknown(data, TOP_LEVEL_KEYS, "")
    language = require_text(data, "language", "language")
    lexicon = read_lexicon(require_text(data, "lexicon", "lexicon"), lexicon_root)
    return Profile(
        id=require_text(data, "id", "id"),
        language=language,
        country=require_text(data, "country", "country"),
        lexicon=require_text(data, "lexicon", "lexicon"),
        number_format=parts.number_format(
            require_mapping(data, "number_format", "number_format"), "number_format"
        ),
        date_formats=_date_formats(data),
        currencies=_currencies(data),
        vat=parts.vat_profile(require_mapping(data, "vat", "vat"), "vat"),
        supplier=parts.supplier_profile(require_mapping(data, "supplier", "supplier"), "supplier"),
        zones_grid=parts.grid(optional_mapping(data, "zones", "zones"), "zones"),
        fields=_fields(data, lexicon),
        parties=_parties(data, lexicon),
        line_items=blocks.table_profile(
            require_mapping(data, "line_items", "line_items"),
            "line_items",
            lexicon,
            blocks.ITEM_COLUMNS,
        ),
        vat_summary=_vat_summary(data, lexicon),
        totals=blocks.block_profile(require_mapping(data, "totals", "totals"), "totals", lexicon),
        custom_fields=_custom_fields(data, lexicon),
        variants=tuple(
            parts.variant(entry, f"variants[{index}]")
            for index, entry in enumerate(optional_objects(data, "variants", "variants"))
        ),
        document_types=parts.document_types(
            require_mapping(data, "document_types", "document_types"), "document_types", lexicon
        ),
        noise=parts.noise(optional_mapping(data, "noise", "noise"), "noise", lexicon),
    )


def _fields(
    data: Mapping[str, object], lexicon: Mapping[str, object]
) -> Mapping[str, FieldProfile]:
    declared = require_mapping(data, "fields", "fields")
    return {
        name: parts.field_profile(
            require_mapping(declared, name, f"fields.{name}"), f"fields.{name}", lexicon
        )
        for name in declared
    }


def _parties(
    data: Mapping[str, object], lexicon: Mapping[str, object]
) -> Mapping[str, SectionProfile]:
    declared = require_mapping(data, "parties", "parties")
    reject_unknown(declared, PARTY_NAMES, "parties.")
    return {
        name: parts.section_profile(
            require_mapping(declared, name, f"parties.{name}"), f"parties.{name}", lexicon
        )
        for name in declared
    }


def _vat_summary(data: Mapping[str, object], lexicon: Mapping[str, object]) -> TableProfile | None:
    declared = optional_mapping(data, "vat_summary", "vat_summary")
    if not declared:
        return None
    return blocks.table_profile(declared, "vat_summary", lexicon, blocks.SUMMARY_COLUMNS)


def _custom_fields(
    data: Mapping[str, object], lexicon: Mapping[str, object]
) -> tuple[CustomFieldProfile, ...]:
    declared = optional_objects(data, "custom_fields", "custom_fields")
    return tuple(
        parts.custom_field(entry, f"custom_fields[{index}]", lexicon)
        for index, entry in enumerate(declared)
    )


def _currencies(data: Mapping[str, object]) -> tuple[str, ...]:
    currencies = require_strings(data, "currencies", "currencies")
    if not currencies:
        raise ProfileError("currencies must name at least one currency")
    return currencies


def _date_formats(data: Mapping[str, object]) -> tuple[str, ...]:
    declared = require_strings(data, "date_formats", "date_formats")
    for index, name in enumerate(declared):
        if name not in DATE_PATTERNS:
            raise ProfileError(f"date_formats[{index}] must be one of: {', '.join(DATE_PATTERNS)}")
    ordered = sorted(declared, key=lambda name: name in SPELLED)
    return tuple(DATE_PATTERNS[name] for name in ordered)


def _resolve(id_or_path: str, root: Path) -> Path:
    looks_like_a_path = "/" in id_or_path or "\\" in id_or_path or id_or_path.endswith(".json")
    return Path(id_or_path) if looks_like_a_path else root / f"{id_or_path}.json"
