"""The ten declared fields, and the two other files they must agree with."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_extractor.domain.models import VALUE_TYPES, Strategy
from invoice_extractor.extraction.normalizers import (
    parse_date,
    parse_money,
    parse_percent,
    strip_label,
    upper_alnum,
)
from invoice_extractor.extraction.spec import Normalizer
from invoice_extractor.extraction.specs import FIELD_ORDER, FIELD_SPECS
from invoice_extractor.extraction.strategies import STRATEGIES
from invoice_extractor.layout.schema import FIELD_NAMES

# The ten names, in the order docs/LAYOUT_FORMAT.md lists them.
DOCUMENTED_ORDER = (
    "invoice_number",
    "invoice_date",
    "due_date",
    "supplier_vat_id",
    "customer_vat_id",
    "currency",
    "vat_rate",
    "subtotal",
    "vat_amount",
    "total_amount",
)

NORMALIZER_TYPES: dict[Normalizer, type] = {
    strip_label: str,
    upper_alnum: str,
    parse_date: date,
    parse_money: Decimal,
    parse_percent: Decimal,
}


def test_field_order_matches_layout_format_document() -> None:
    assert FIELD_ORDER == DOCUMENTED_ORDER
    assert FIELD_NAMES == DOCUMENTED_ORDER


def test_value_types_agree_with_models() -> None:
    assert tuple(VALUE_TYPES) == FIELD_ORDER
    for spec in FIELD_SPECS:
        assert NORMALIZER_TYPES[spec.normalizer] is VALUE_TYPES[spec.name], spec.name


def test_every_spec_names_at_least_one_strategy_the_engine_knows() -> None:
    for spec in FIELD_SPECS:
        assert spec.strategies, spec.name
        assert all(strategy in STRATEGIES for strategy in spec.strategies), spec.name


def test_every_labelled_field_looks_both_ways_along_its_line() -> None:
    """A label and its value in one run, and the same pair at two tab stops, are one idea."""
    for spec in FIELD_SPECS:
        assert Strategy.LABEL_RIGHT in spec.strategies, spec.name
        assert Strategy.LABEL_BESIDE in spec.strategies, spec.name


def test_no_spec_names_the_same_strategy_twice() -> None:
    """Which would double every candidate it finds, and with it the candidate count."""
    for spec in FIELD_SPECS:
        assert len(set(spec.strategies)) == len(spec.strategies), spec.name


def test_every_ranker_list_starts_with_valid_first() -> None:
    # Ranking that did not put a parsed value ahead of an unparsed one would make
    # `on_all_invalid` unreachable for a field with one good and one bad candidate.
    assert all(spec.rankers[0].__name__ == "valid_first" for spec in FIELD_SPECS)
