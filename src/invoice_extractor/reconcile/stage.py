"""Stage 5 itself: the five functions of `docs/ENGINE_SPEC.md` §5, run in one order.

The order is the argument. What a document leaves out is filled in first, because every
comparison after it is a comparison against the filled-in value; then the charges, which
are what the arithmetic has left over; then the two questions that only report — does the
summary agree with the block, and which line of it taxes which row.

Nothing here mutates what extraction published: each step takes the fields it was given
and returns the fields it made, and the pipeline keeps the last of them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TypeVar

from invoice_extractor.domain.findings import Finding
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge
from invoice_extractor.profile.schema import Profile
from invoice_extractor.reconcile.amounts import (
    backfill_vat,
    choose_currency_basis,
    resolve_charges,
)
from invoice_extractor.reconcile.summary import (
    cross_check_totals_vs_summary,
    link_items_to_vat_lines,
)

# The two kinds of row a VAT line taxes: something sold, and something charged for.
Row = TypeVar("Row", LineItem, Charge)


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """What stage 5 made of a document, for stages 6 and 7 to check and to score."""

    fields: Mapping[str, FieldResult]
    charges: tuple[Charge, ...]
    items: tuple[LineItem, ...]
    currency: str | None
    caps: Mapping[str, float]
    findings: tuple[Finding, ...]


def reconcile(
    fields: Mapping[str, FieldResult],
    charges: Sequence[Charge],
    items: Sequence[LineItem],
    summary: Sequence[VatSummaryRow],
    profile: Profile,
) -> Reconciliation:
    """Fill in what the document left out, then say where it disagrees with itself."""
    filled = backfill_vat(fields, charges, items, summary, profile)
    resolved = resolve_charges(filled.fields, charges, profile)
    crossed = cross_check_totals_vs_summary(resolved.fields, resolved.charges, summary, profile)
    links = link_items_to_vat_lines(items, resolved.charges, summary)
    return Reconciliation(
        fields=resolved.fields,
        charges=_linked(resolved.charges, links.charges),
        items=_linked(items, links.items),
        currency=choose_currency_basis(resolved.fields, resolved.charges, profile),
        caps=crossed.caps,
        findings=(*filled.findings, *resolved.findings, *crossed.findings, *links.findings),
    )


def _linked(rows: Sequence[Row], lines: Sequence[int | None]) -> tuple[Row, ...]:
    """Each row carrying the summary line that taxes it, which is what linking is for.

    `link_items_to_vat_lines` answers the question once; a result that did not carry the
    answer would make every later reader ask it again, and ADR-0002's rule that a value
    travels with where it came from is the same rule for a row and its tax.
    """
    return tuple(replace(row, vat_line=line) for row, line in zip(rows, lines, strict=True))
