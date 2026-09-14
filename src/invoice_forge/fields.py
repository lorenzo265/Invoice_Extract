"""The field names the generator writes, and the extras an invoice prints beside them.

`SCALAR_FIELDS` and `LINE_ITEM_COLUMNS` are the canonical names of
`docs/FIELD_CATALOG.md`, restated here rather than imported: the two packages share
their data (ADR-0006) and not their code, so a shared vocabulary is held in step by a
test rather than by an import. `tests/forge/unit/test_fields.py` is that test.

`METADATA_FIELDS` are the extras a real invoice prints in its header block beside the
scalar fields — a reference, an order number, a contract. The generator prints them and
records them in the truth. A vendor that prints one declares it in its profile's
`custom_fields`, which is how the extractor reads it; the benchmark reports the ones no
spec has learned as "not covered" rather than as misses.
"""

from __future__ import annotations

SCALAR_FIELDS: tuple[str, ...] = (
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

LINE_ITEM_COLUMNS: tuple[str, ...] = (
    "part_number",
    "description",
    "quantity",
    "unit_price",
    "net_amount",
)

METADATA_FIELDS: tuple[str, ...] = (
    "supply_date",
    "order_number",
    "customer_number",
    "contract_number",
    "our_reference",
    "your_reference",
    "payment_terms",
    "credit_reference",
)

# Every name a lexicon gives label synonyms for.
LABELLED_FIELDS: tuple[str, ...] = (*SCALAR_FIELDS, *METADATA_FIELDS)

# Every column a template family may print, beyond the five the extractor reads.
EXTRA_COLUMNS: tuple[str, ...] = (
    "pos",
    "unit",
    "discount_pct",
    "vat_rate",
    "subscription_id",
    "billing_cycle",
    "period",
    "share",
    "remaining_term",
)

TABLE_COLUMNS: tuple[str, ...] = (*LINE_ITEM_COLUMNS, *EXTRA_COLUMNS)
