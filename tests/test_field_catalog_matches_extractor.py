"""The field catalog is derived from the extractor's specs, never written beside them."""

from __future__ import annotations

import dataclasses

from make_field_catalog import CATALOG_PATH, KINDS, catalog_markdown, column_rows, scalar_rows

from invoice_extractor.domain.models import VALUE_TYPES, LineItem
from invoice_extractor.extraction.specs import FIELD_ORDER
from invoice_extractor.layout.schema import LINE_ITEM_COLUMNS

REGENERATE = "python scripts/make_field_catalog.py"


def test_field_catalog_matches_extractor() -> None:
    committed = CATALOG_PATH.read_text(encoding="utf-8")
    assert committed == catalog_markdown(), f"the catalog is stale; run {REGENERATE}"


def test_catalog_covers_every_scalar_field_in_order() -> None:
    assert tuple(row[0] for row in scalar_rows()) == FIELD_ORDER


def test_catalog_covers_every_line_item_column_in_order() -> None:
    assert tuple(row[0] for row in column_rows()) == LINE_ITEM_COLUMNS


def test_every_scalar_field_is_classified() -> None:
    assert tuple(KINDS) == FIELD_ORDER


def test_line_item_columns_are_the_line_item_record() -> None:
    assert tuple(field.name for field in dataclasses.fields(LineItem)) == LINE_ITEM_COLUMNS


def test_catalog_types_agree_with_value_types() -> None:
    for name, _, value_type, _ in scalar_rows():
        assert value_type == VALUE_TYPES[name].__name__
