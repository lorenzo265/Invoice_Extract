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
    BlockSpec,
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
# What a vendor prints in its header block beside the fields the catalog names. A profile
# declares the ones it prints under `custom_fields`; a profile that declares none simply
# never resolves them.
DECLARED_BY_THE_VENDOR = (
    "contract_number",
    "our_reference",
    "your_reference",
    "credit_reference",
)
# The one extra that is a sentence rather than a reference: a vendor's terms of payment
# are words, and words are judged by reading like words rather than by a shape.
IN_WORDS = "payment_terms"


def _identifier(name: str, source: str = "fields") -> LabelSpec:
    return LabelSpec(
        name=name,
        normalizer="strip_label",
        validator="is_identifier",
        rankers=BY_LABEL,
        source=source,
    )


def _sentence(name: str) -> LabelSpec:
    return LabelSpec(
        name=name,
        normalizer="strip_label",
        validator="is_sentence",
        rankers=BY_LABEL,
        source="custom_fields",
    )


def _date(name: str) -> LabelSpec:
    return LabelSpec(name=name, normalizer="parse_date", validator="is_date", rankers=BY_LABEL)


HEADER: tuple[Spec, ...] = (
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
)
# The extras a vendor declares for itself, read the same way and named by the profile.
VENDOR: tuple[Spec, ...] = (
    *(_identifier(name, source="custom_fields") for name in DECLARED_BY_THE_VENDOR),
    _sentence(IN_WORDS),
)
SPECS: tuple[Spec, ...] = (*HEADER, *VENDOR)

# The totals block: the amounts it names are fields of the catalog, and the charges it
# names are not — a charge is a row of the block, published beside the fields (ADR-0007).
TOTALS = BlockSpec(name="totals", fields=("vat_rate", "subtotal", "vat_amount", "total_amount"))

# The order a report prints the fields in: the header block's, then the totals block's,
# then whatever this vendor prints that the catalog does not name.
FIELD_ORDER: tuple[str, ...] = (
    *(spec.name for spec in HEADER),
    *TOTALS.fields,
    *(spec.name for spec in VENDOR),
)

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

STRUCTURES: tuple[Structure, ...] = (*SECTIONS, *TABLES, TOTALS)

validate(SPECS, DERIVATIONS)
validate_structures(STRUCTURES)
