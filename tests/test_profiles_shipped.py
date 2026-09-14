"""The profiles this repository ships, and the catalog every name in them comes from.

One vendor per file, one vocabulary across both packages: what the generator prints, what
the extractor reads back and what `docs/FIELD_CATALOG.md` names are the same strings, and
a test rather than an import is what holds them in step.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from invoice_extractor.domain.models import LINE_ITEM_COLUMNS
from invoice_extractor.extraction.specs import FIELD_ORDER
from invoice_extractor.profile.registry import ProfileRegistry
from invoice_forge.fields import LINE_ITEM_COLUMNS as GENERATED_COLUMNS
from invoice_forge.fields import METADATA_FIELDS, SCALAR_FIELDS
from invoice_forge.profiles.loader import load_profile, profile_ids

CATALOG = Path("docs/FIELD_CATALOG.md")
SHIPPED = ProfileRegistry()
NAMED_IN_CATALOG = frozenset(re.findall(r"`([a-z_]+)`", CATALOG.read_text(encoding="utf-8")))


@pytest.mark.parametrize("profile_id", SHIPPED.ids())
def test_every_shipped_profile_loads(profile_id: str) -> None:
    assert SHIPPED.get(profile_id).id == profile_id


@pytest.mark.parametrize("profile_id", SHIPPED.ids())
def test_every_field_the_extractor_reads_is_declared_with_labels(profile_id: str) -> None:
    profile = SHIPPED.get(profile_id)
    assert set(FIELD_ORDER) <= set(profile.fields)
    assert all(profile.fields[name].labels for name in FIELD_ORDER)


@pytest.mark.parametrize("profile_id", SHIPPED.ids())
def test_every_field_the_extractor_reads_is_given_a_zone(profile_id: str) -> None:
    profile = SHIPPED.get(profile_id)
    assert all(profile.fields[name].zones for name in FIELD_ORDER)


@pytest.mark.parametrize("profile_id", SHIPPED.ids())
def test_every_column_the_extractor_reads_has_a_header_word(profile_id: str) -> None:
    columns = SHIPPED.get(profile_id).line_items.columns
    assert all(columns[column] for column in LINE_ITEM_COLUMNS)


@pytest.mark.parametrize("profile_id", SHIPPED.ids())
def test_a_profile_declares_the_vendor_it_describes(profile_id: str) -> None:
    supplier = SHIPPED.get(profile_id).supplier
    assert supplier.name and supplier.address_lines and supplier.vat_id


@pytest.mark.parametrize("profile_id", SHIPPED.ids())
def test_a_declared_vat_id_matches_the_pattern_the_profile_declares(profile_id: str) -> None:
    profile = SHIPPED.get(profile_id)
    body = profile.supplier.vat_id.removeprefix(profile.vat.id_prefix)
    assert profile.vat.id_pattern.fullmatch(body), profile.supplier.vat_id


@pytest.mark.parametrize("profile_id", SHIPPED.ids())
def test_a_format_that_reads_digits_is_tried_before_one_that_spells_a_month(
    profile_id: str,
) -> None:
    """`%B` reads month names in the C locale only, so it must never be tried first."""
    formats = SHIPPED.get(profile_id).date_formats
    spelled = [index for index, pattern in enumerate(formats) if "%B" in pattern or "%b" in pattern]
    assert all(index >= len(formats) - len(spelled) for index in spelled)


@pytest.mark.parametrize("profile_id", SHIPPED.ids())
def test_both_packages_read_the_same_file_for_one_vendor(profile_id: str) -> None:
    printed = load_profile(profile_id)
    read_back = SHIPPED.get(profile_id)
    assert printed.language == read_back.language
    assert printed.country == read_back.country
    assert printed.decimal_separator == read_back.number_format.decimal_separator
    assert printed.currency == read_back.currencies[0]
    assert printed.supplier.name == read_back.supplier.name
    assert printed.supplier.vat_id == read_back.supplier.vat_id


def test_every_profile_the_generator_prints_is_one_the_extractor_can_read() -> None:
    assert profile_ids() == SHIPPED.ids()


def test_every_name_the_generator_writes_is_in_the_field_catalog() -> None:
    written = {*SCALAR_FIELDS, *GENERATED_COLUMNS, *METADATA_FIELDS}
    assert written <= NAMED_IN_CATALOG, sorted(written - NAMED_IN_CATALOG)


def test_every_name_the_extractor_reads_is_in_the_field_catalog() -> None:
    read = {*FIELD_ORDER, *LINE_ITEM_COLUMNS}
    assert read <= NAMED_IN_CATALOG, sorted(read - NAMED_IN_CATALOG)


def test_the_two_packages_agree_on_the_line_item_columns() -> None:
    assert GENERATED_COLUMNS == LINE_ITEM_COLUMNS
