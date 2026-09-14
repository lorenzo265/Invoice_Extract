"""The fields, declared. Adding one is an entry here plus a test (ADR-0001).

Nothing in this file knows a vendor's vocabulary — the labels, zones and formats live in
`profiles/*.json`. What a spec names is behaviour: how to find the text, how to read it,
how to judge it, how to break a tie, and what to report when nothing passes.

The order below is the order a report prints them in; the order they are *run* in is
`engine.order`, which puts a field before the ones derived from it.
"""

from __future__ import annotations

from invoice_extractor.domain.rows import LINE_ITEM_COLUMNS, VAT_SUMMARY_COLUMNS
from invoice_extractor.extraction.spec import (
    AnchorSpec,
    DerivedSpec,
    LabelSpec,
    SectionSpec,
    Spec,
    Structure,
    TableSpec,
    validate,
    validate_structures,
)
from invoice_extractor.extraction.units.derivations import DERIVATIONS

# A value that parsed, in the expected zone, nearest the label that introduced it,
# highest on the page. One order for every labelled field: which of the three ways a
# vendor printed a label is the document's business, and the distance settles it.
BY_LABEL = ("valid_first", "zone_priority", "closest_to_label", "top_most")
# An amount is asked for once, at the end: the last page settles a label a running table
# prints on every one of them.
BY_AMOUNT = ("valid_first", "last_page_first", "zone_priority", "closest_to_label")
# Only what is a number gets to be one.
NUMERIC = ("not_a_trap", "looks_numeric")
# What a vendor prints in its header block beside the fields the catalog names. A profile
# declares the ones it prints under `custom_fields`; a profile that declares none simply
# never resolves them.
DECLARED_BY_THE_VENDOR = (
    "contract_number",
    "our_reference",
    "your_reference",
    "credit_reference",
)


def _identifier(name: str, source: str = "fields") -> LabelSpec:
    return LabelSpec(
        name=name,
        normalizer="strip_label",
        validator="is_identifier",
        rankers=BY_LABEL,
        source=source,
    )


def _date(name: str) -> LabelSpec:
    return LabelSpec(name=name, normalizer="parse_date", validator="is_date", rankers=BY_LABEL)


def _money(name: str) -> LabelSpec:
    return LabelSpec(
        name=name,
        normalizer="parse_money",
        validator="is_money",
        rankers=BY_AMOUNT,
        filters=NUMERIC,
    )


SPECS: tuple[Spec, ...] = (
    _identifier("invoice_number"),
    _identifier("order_number"),
    _identifier("customer_number"),
    _date("invoice_date"),
    _date("supply_date"),
    _date("due_date"),
    AnchorSpec(
        name="supplier_vat_id",
        expected="supplier.vat_id",
        normalizer="upper_alnum",
        validator="is_vat_id",
    ),
    LabelSpec(
        name="customer_vat_id",
        normalizer="upper_alnum",
        validator="is_vat_id",
        rankers=BY_LABEL,
    ),
    DerivedSpec(name="currency", derive="currency"),
    LabelSpec(
        name="vat_rate",
        normalizer="parse_percent",
        validator="is_percent",
        rankers=BY_AMOUNT,
        filters=NUMERIC,
    ),
    _money("subtotal"),
    _money("vat_amount"),
    _money("total_amount"),
    *(_identifier(name, source="custom_fields") for name in DECLARED_BY_THE_VENDOR),
)

FIELD_ORDER: tuple[str, ...] = tuple(spec.name for spec in SPECS)

# The line-item table: a row is a row when it says what was charged and what for.
LINE_ITEMS = TableSpec(
    name="line_items",
    source="line_items",
    required_columns=("description", "net_amount"),
    columns=LINE_ITEM_COLUMNS,
)
# The VAT summary: a line of it is a rate and the tax that rate came to.
VAT_SUMMARY = TableSpec(
    name="vat_summary",
    source="vat_summary",
    required_columns=("rate", "vat"),
    columns=VAT_SUMMARY_COLUMNS,
)
TABLES: tuple[TableSpec, ...] = (LINE_ITEMS, VAT_SUMMARY)

# The party blocks, in the order a report prints them. The supplier's has no heading of
# its own: it is the letterhead, found at the name the vendor prints itself under.
SECTIONS: tuple[SectionSpec, ...] = (
    SectionSpec(name="supplier", source="supplier"),
    SectionSpec(name="bill_to", source="bill_to"),
    SectionSpec(name="ship_to", source="ship_to"),
    SectionSpec(name="mail_to", source="mail_to"),
)

STRUCTURES: tuple[Structure, ...] = (*SECTIONS, *TABLES)

validate(SPECS, DERIVATIONS)
validate_structures(STRUCTURES)
