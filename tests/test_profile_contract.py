"""No profile key is accepted and then dropped, and none is read that cannot be written.

`docs/PROFILE_FORMAT.md` promises that a profile file is read into `profile/schema.py`'s
records and nothing else: every key the loader accepts becomes a field of the record it
builds, and every field of every record comes from a key the loader accepts. The two
directions together are the reader manifest `docs/ENGINE_PLAN.md` §3 asks E0 for — a key
with no reader fails here rather than silently doing nothing in production.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

import pytest

from invoice_extractor.profile import blocks, parts
from invoice_extractor.profile.loader import TOP_LEVEL_KEYS, load_profile
from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.profile.schema import (
    BlockProfile,
    ComponentProfile,
    CustomFieldProfile,
    DocumentTypes,
    FieldProfile,
    Noise,
    NumberFormat,
    PageBounds,
    Profile,
    SecondaryEcho,
    SectionProfile,
    SupplierProfile,
    TableProfile,
    Tolerance,
    Variant,
    VatProfile,
)

# The generator's half of the shared file. This package names it so that it is not an
# unknown key, and reads nothing inside it (ADR-0006).
GENERATOR_SECTIONS = ("render",)
# The one key whose record field is named for what it holds rather than for the key:
# the profile writes `zones: {grid: [3, 3]}` and the record keeps the grid itself.
RENAMED = {"zones": "zones_grid"}
# What the loader reads out of the language's lexicon rather than out of a profile key,
# for the same reason labels are read from there: it is the language's, not the vendor's.
FROM_THE_LEXICON = ("calendar",)

RECORDS: tuple[tuple[Sequence[str], type], ...] = (
    (parts.FIELD_KEYS, FieldProfile),
    (parts.SECTION_KEYS, SectionProfile),
    (parts.VAT_KEYS, VatProfile),
    (parts.SUPPLIER_KEYS, SupplierProfile),
    (parts.DOCUMENT_TYPE_KEYS, DocumentTypes),
    (parts.NUMBER_FORMAT_KEYS, NumberFormat),
    (parts.NOISE_KEYS, Noise),
    (parts.VARIANT_KEYS, Variant),
    (blocks.TABLE_KEYS, TableProfile),
    (blocks.BLOCK_KEYS, BlockProfile),
    (blocks.COMPONENT_KEYS, ComponentProfile),
    (blocks.ECHO_KEYS, SecondaryEcho),
    (blocks.TOLERANCE_KEYS, Tolerance),
    (blocks.PAGE_BOUNDS_KEYS, PageBounds),
)


def field_names(record: type) -> set[str]:
    return {field.name for field in dataclasses.fields(record)}


@pytest.mark.parametrize(
    ("keys", "record"), RECORDS, ids=lambda value: getattr(value, "__name__", "")
)
def test_every_key_a_record_accepts_is_a_field_of_it(keys: Sequence[str], record: type) -> None:
    assert set(keys) == field_names(record)


def test_a_custom_field_is_a_field_profile_under_a_name() -> None:
    assert set(parts.CUSTOM_FIELD_KEYS) == {"name", *parts.FIELD_KEYS}
    assert field_names(CustomFieldProfile) == {"name", "field"}


def test_every_top_level_key_is_read_into_the_profile() -> None:
    read = {RENAMED.get(key, key) for key in TOP_LEVEL_KEYS if key not in GENERATOR_SECTIONS}
    assert read | set(FROM_THE_LEXICON) == field_names(Profile)


def test_the_generator_half_of_the_file_is_named_but_not_read() -> None:
    """Naming it is what keeps it from being reported as a typo in the other program."""
    assert set(GENERATOR_SECTIONS) <= set(TOP_LEVEL_KEYS)
    assert not set(GENERATOR_SECTIONS) & field_names(Profile)


def test_every_shipped_profile_is_read_by_the_same_loader() -> None:
    """The one strict loader, over every file: `docs/PROFILE_FORMAT.md`'s first promise."""
    registry = ProfileRegistry()
    assert registry.ids()
    for profile_id in registry.ids():
        assert load_profile(profile_id).id == profile_id
