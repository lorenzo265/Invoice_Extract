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
from dataclasses import dataclass

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
    Linked,
    cross_check_totals_vs_summary,
    link_items_to_vat_lines,
)


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """What stage 5 made of a document, for stages 6 and 7 to check and to score."""

    fields: Mapping[str, FieldResult]
    charges: tuple[Charge, ...]
    currency: str | None
    links: Linked
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
        charges=resolved.charges,
        currency=choose_currency_basis(resolved.fields, resolved.charges, profile),
        links=links,
        caps=crossed.caps,
        findings=(*filled.findings, *resolved.findings, *crossed.findings, *links.findings),
    )
