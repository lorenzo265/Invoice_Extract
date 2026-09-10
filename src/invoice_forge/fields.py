"""The field names the generator writes, and the extras an invoice prints beside them.

`SCALAR_FIELDS` and `LINE_ITEM_COLUMNS` are the extractor's canonical names, restated
here rather than imported: the two packages are independent, and ADR-0004 already settled
that a shared vocabulary is held in step by a test, not by an import.
`tests/forge/unit/test_fields.py` is that test.

`METADATA_FIELDS` are the values a real invoice prints in its header block that the
extractor does not read yet. The generator prints them, records them in the truth, and
the benchmark reports them as "not covered" until the extractor learns them.
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
    "sku",
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
)

# Every name a lexicon gives label synonyms for.
LABELLED_FIELDS: tuple[str, ...] = (*SCALAR_FIELDS, *METADATA_FIELDS)

# Every column a template family may print, beyond the five the extractor reads. The
# article number is `sku`, the catalog's name for it; `part_number` in the ground-truth
# schema's worked example was the same column under an older name.
EXTRA_COLUMNS: tuple[str, ...] = (
    "pos",
    "unit",
    "discount",
    "vat_rate",
    "subscription_id",
    "billing_cycle",
    "period",
    "share",
    "remaining_term",
)

TABLE_COLUMNS: tuple[str, ...] = (*LINE_ITEM_COLUMNS, *EXTRA_COLUMNS)
