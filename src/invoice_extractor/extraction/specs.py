"""The ten fields, declared. Adding an eleventh is one entry here plus a test (ADR-0001).

Nothing in this file knows a vendor's vocabulary — the labels, zones and formats live in
`layouts/*.json`. What a spec names is behaviour: how to find the text, how to read it,
how to judge it, how to break a tie, and what to report when nothing passes.
"""

from __future__ import annotations

from invoice_extractor.domain.models import Strategy
from invoice_extractor.extraction.normalizers import (
    parse_date,
    parse_money,
    parse_percent,
    strip_label,
    upper_alnum,
)
from invoice_extractor.extraction.rankers import (
    closest_to_label,
    top_most,
    valid_first,
    zone_priority,
)
from invoice_extractor.extraction.spec import FieldSpec, OnAllInvalid
from invoice_extractor.extraction.validators import (
    is_currency_code,
    is_date,
    is_percent,
    is_positive_money,
    matches_pattern,
)

INVOICE_NUMBER_PATTERN = r"[A-Z0-9][A-Z0-9/-]{2,}"
VAT_ID_PATTERN = r"[A-Z]{2}[A-Z0-9]{2,12}"

BY_POSITION = (valid_first, zone_priority, top_most)
BY_LABEL_DISTANCE = (valid_first, zone_priority, closest_to_label)
# Every field is labelled, and a labelled value sits either in the label's own run of
# text or at the next tab stop along. Which of the two a vendor uses is the vendor's
# business, so every field looks both ways and the rankers sort out what comes back.
BESIDE_OR_IN_LINE = (Strategy.LABEL_RIGHT, Strategy.LABEL_BESIDE)

FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec(
        name="invoice_number",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=strip_label,
        validator=matches_pattern(INVOICE_NUMBER_PATTERN),
        rankers=BY_POSITION,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="invoice_date",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=parse_date,
        validator=is_date,
        rankers=BY_POSITION,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="due_date",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=parse_date,
        validator=is_date,
        rankers=BY_POSITION,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="supplier_vat_id",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=upper_alnum,
        validator=matches_pattern(VAT_ID_PATTERN),
        rankers=BY_POSITION,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="customer_vat_id",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=upper_alnum,
        validator=matches_pattern(VAT_ID_PATTERN),
        rankers=BY_POSITION,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="currency",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=upper_alnum,
        validator=is_currency_code,
        rankers=BY_POSITION,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="vat_rate",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=parse_percent,
        validator=is_percent,
        rankers=BY_LABEL_DISTANCE,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="subtotal",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=parse_money,
        validator=is_positive_money,
        rankers=BY_LABEL_DISTANCE,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="vat_amount",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=parse_money,
        validator=is_positive_money,
        rankers=BY_LABEL_DISTANCE,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
    FieldSpec(
        name="total_amount",
        strategies=BESIDE_OR_IN_LINE,
        normalizer=parse_money,
        validator=is_positive_money,
        rankers=BY_LABEL_DISTANCE,
        on_all_invalid=OnAllInvalid.NOT_FOUND,
    ),
)

FIELD_ORDER: tuple[str, ...] = tuple(spec.name for spec in FIELD_SPECS)
