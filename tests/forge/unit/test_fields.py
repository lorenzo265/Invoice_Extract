"""The two packages name the same things the same way, and a test keeps them in step.

ADR-0004 settled that neither package imports the other. What the extractor reads and what
the generator writes must still agree exactly, so the agreement is asserted here — the one
place that is allowed to know both.
"""

from __future__ import annotations

import dataclasses

import pytest

from invoice_extractor.domain.models import LineItem as ExtractedItem
from invoice_extractor.extraction.specs import FIELD_ORDER
from invoice_forge.fields import (
    EXTRA_COLUMNS,
    LABELLED_FIELDS,
    LINE_ITEM_COLUMNS,
    METADATA_FIELDS,
    SCALAR_FIELDS,
    TABLE_COLUMNS,
)
from invoice_forge.lexicon.schema import HEADER_FIELDS, TOTALS_FIELDS
from invoice_forge.model import Identifiers
from invoice_forge.model.items import LineItem as ForgedItem


def test_the_generator_writes_exactly_the_fields_the_extractor_reads() -> None:
    assert SCALAR_FIELDS == FIELD_ORDER


def test_a_forged_row_carries_every_column_the_extractor_reads_from_a_row() -> None:
    extracted = {field.name for field in dataclasses.fields(ExtractedItem)}
    assert set(LINE_ITEM_COLUMNS) == extracted


def test_a_forged_row_can_answer_for_every_column_it_declares() -> None:
    forged = {field.name for field in dataclasses.fields(ForgedItem)}
    answerable = forged | {name for name in dir(ForgedItem) if not name.startswith("_")}
    for column in LINE_ITEM_COLUMNS:
        assert column in answerable, column


@pytest.mark.parametrize("name", METADATA_FIELDS)
def test_every_metadata_field_is_one_the_extractor_does_not_read_yet(name: str) -> None:
    assert name not in FIELD_ORDER


def test_the_identifiers_the_model_holds_are_metadata_fields_or_the_invoice_number() -> None:
    """A reference the model carries but nothing names is a value no truth file could hold."""
    named = {*METADATA_FIELDS, "invoice_number", "credit_reference"}
    for field in dataclasses.fields(Identifiers):
        assert field.name in named, field.name


def test_a_label_is_asked_for_once_and_in_one_place() -> None:
    assert LABELLED_FIELDS == SCALAR_FIELDS + METADATA_FIELDS
    assert set(HEADER_FIELDS) | set(TOTALS_FIELDS) == set(LABELLED_FIELDS)
    assert not set(HEADER_FIELDS) & set(TOTALS_FIELDS)


def test_the_table_columns_are_the_read_ones_then_the_rest() -> None:
    assert TABLE_COLUMNS == LINE_ITEM_COLUMNS + EXTRA_COLUMNS
    assert len(set(TABLE_COLUMNS)) == len(TABLE_COLUMNS)


def test_the_article_number_column_is_called_part_number_in_both_packages() -> None:
    """`docs/FIELD_CATALOG.md` names it `part_number`; `sku` was the older name."""
    assert "part_number" in LINE_ITEM_COLUMNS
    assert "sku" not in TABLE_COLUMNS


def test_no_name_is_declared_twice() -> None:
    assert len(set(LABELLED_FIELDS)) == len(LABELLED_FIELDS)
