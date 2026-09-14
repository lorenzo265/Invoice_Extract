"""Stage 5, first half: what the block did not say, and what it did not name.

An invoice is allowed to leave things out. A document that charges several rates may
print no VAT amount at all and let its summary carry it; a document that adds a fee may
fold it into the total and name it nowhere. Reconciliation is where those are filled in —
from what the document does say, never from a guess — and where anything filled in is
said out loud as a `Finding` (ADR-0005).

Nothing here re-reads the page. Everything it reasons over was already published with its
evidence, and what it adds carries the evidence of whatever it was derived from (ADR-0002).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from invoice_extractor.domain.evidence import Evidence, Strategy
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge
from invoice_extractor.profile.schema import Profile

# The widest rate an implied one may be before it is not a VAT rate at all. A document
# whose total exceeds its net by more than this is not taxed that much: it is carrying
# something else, and calling that tax would be inventing one.
HIGHEST_IMPLIED_RATE = Decimal("0.30")
UNNAMED = "OTHER"
FROM_SUMMARY = "backfilled_from_summary"
FROM_ITEMS = "backfilled_from_line_items"
FROM_TOTAL = "vat_implied_from_total"
UNDECLARED = "undeclared_charge_inferred"
ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Reconciled:
    """What one reconciliation made of a document: its fields, its charges, what it says."""

    fields: Mapping[str, FieldResult]
    charges: tuple[Charge, ...] = ()
    findings: tuple[Finding, ...] = ()


def backfill_vat(
    fields: Mapping[str, FieldResult],
    charges: Sequence[Charge],
    items: Sequence[LineItem],
    summary: Sequence[VatSummaryRow],
    profile: Profile,
) -> Reconciled:
    """The tax and the rate a block did not state, taken from what the document did state.

    A document at several rates states none of them in its totals block — there is no one
    rate to state — and prints a summary instead. What that summary adds up to is the
    document's tax; the rate it is mostly at is the rate the document is at. Where it
    prints no summary either, its rows still say what each of them is charged at, and what
    the total adds to the net is the tax — but only when that could be a rate at all.
    """
    filled = dict(fields)
    findings: list[Finding] = []
    taxed = _taxed(fields, charges, summary, profile)
    if taxed is not None:
        filled["vat_amount"], found = taxed
        findings.append(found)
    rate = _rated(filled, items, summary)
    if rate is not None:
        filled["vat_rate"], found = rate
        findings.append(found)
    return Reconciled(filled, (), tuple(findings))


def implied_vat(
    fields: Mapping[str, FieldResult], charges: Sequence[Charge], profile: Profile
) -> FieldResult | None:
    """The tax a document implies by what it adds to its net, where that is a tax at all.

    `total - subtotal - charges` is only VAT when the rate it implies could be one: a
    difference of half the net again is a deposit, a charge or a misread, and reporting it
    as tax would be reporting a number no one printed.
    """
    net, total = _amount(fields, "subtotal"), _amount(fields, "total_amount")
    if net is None or total is None or net == ZERO:
        return None
    difference = total - net - _declared(charges)
    if difference != ZERO and (difference < ZERO) != (total < ZERO):
        return None
    if abs(difference / net) > HIGHEST_IMPLIED_RATE:
        return None
    return _derived("vat_amount", difference, fields["total_amount"])


def resolve_charges(
    fields: Mapping[str, FieldResult], charges: Sequence[Charge], profile: Profile
) -> Reconciled:
    """The charges the block named, and the one it did not.

    A vendor may add a fee to the total without printing a line for it. What says so is
    the arithmetic: net plus tax plus what was named does not come to the total, and the
    difference is a charge the document carries and never declares.
    """
    named = tuple(charges)
    difference = _unaccounted(fields, named, profile)
    if difference is None:
        return Reconciled(fields, named)
    inferred = Charge(type=UNNAMED, amount=difference, declared=False)
    return Reconciled(fields, (*named, inferred), (_undeclared(difference),))


def choose_currency_basis(
    fields: Mapping[str, FieldResult], charges: Sequence[Charge], profile: Profile
) -> str | None:
    """The currency whose amounts add up, which is the one the document is in.

    A document that echoes its total in another currency prints two sets of amounts, and
    only one of them is the invoice. The one that closes is that one; where neither does,
    nothing here decides — validation says so instead.
    """
    if _unaccounted(fields, charges, profile) is not None:
        return None
    found = fields.get("currency")
    return None if found is None or found.value is None else str(found.value)


def _taxed(
    fields: Mapping[str, FieldResult],
    charges: Sequence[Charge],
    summary: Sequence[VatSummaryRow],
    profile: Profile,
) -> tuple[FieldResult, Finding] | None:
    """The tax to fill in, where the block left one to fill in and the document says it."""
    stated = _amount(fields, "vat_amount")
    if stated is not None and stated != ZERO:
        return None
    summed = _summed_vat(summary)
    if summed is not None and not (stated == ZERO and summed.value == ZERO):
        return summed, _filled("vat_amount", "the VAT summary", FROM_SUMMARY)
    if stated is not None:
        return None
    implied = implied_vat(fields, charges, profile)
    if implied is None:
        return None
    return implied, _filled("vat_amount", "what the total adds to the net", FROM_TOTAL)


def _rated(
    fields: Mapping[str, FieldResult],
    items: Sequence[LineItem],
    summary: Sequence[VatSummaryRow],
) -> tuple[FieldResult, Finding] | None:
    """The one rate a document is at, where the block states none and the rest of it does."""
    if _amount(fields, "vat_rate") is not None:
        return None
    headline = _headline(summary)
    if headline is not None:
        return headline, _filled("vat_rate", "the rate its summary is mostly at", FROM_SUMMARY)
    charged = _charged(items)
    if charged is None:
        return None
    return charged, _filled("vat_rate", "the rate most of its rows are charged at", FROM_ITEMS)


def _charged(items: Sequence[LineItem]) -> FieldResult | None:
    """The rate the table is mostly at: the one the most of what was sold is charged at.

    A table that prints a rate per row says what the document is at even where no block
    and no summary states it, and it says it the same way a summary does — by how much is
    charged at each rate, not by how many rows are.
    """
    net: dict[Decimal, Decimal] = {}
    for item in items:
        if item.vat_rate is not None and item.net_amount is not None:
            net[item.vat_rate] = net.get(item.vat_rate, ZERO) + item.net_amount
    if not net:
        return None
    best = max(net, key=lambda rate: (net[rate], rate))
    row = next(item for item in items if item.vat_rate == best)
    return _derived("vat_rate", best, row.cells.get("vat_rate"))


def _unaccounted(
    fields: Mapping[str, FieldResult], charges: Sequence[Charge], profile: Profile
) -> Decimal | None:
    """What the total carries that nothing in the block accounts for, beyond tolerance."""
    net, total = _amount(fields, "subtotal"), _amount(fields, "total_amount")
    if net is None or total is None:
        return None
    taxed = _amount(fields, "vat_amount") or ZERO
    difference = total - (net + _declared(charges) + taxed)
    return None if abs(difference) <= profile.totals.tolerance.absolute else difference


def _declared(charges: Sequence[Charge]) -> Decimal:
    return sum((charge.amount for charge in charges if charge.declared), ZERO)


def _summed_vat(summary: Sequence[VatSummaryRow]) -> FieldResult | None:
    taxed = [row for row in summary if row.vat is not None]
    if not taxed:
        return None
    total = sum((row.vat or ZERO for row in taxed), ZERO)
    return _derived("vat_amount", total, _cell(taxed[0], "vat"))


def _headline(summary: Sequence[VatSummaryRow]) -> FieldResult | None:
    """The rate the document is mostly at: the largest base, and the higher rate on a tie."""
    rated = [row for row in summary if row.rate is not None]
    if not rated:
        return None
    best = max(rated, key=lambda row: (row.base or ZERO, row.rate or ZERO))
    return _derived("vat_rate", best.rate or ZERO, _cell(best, "rate"))


def _cell(row: VatSummaryRow, column: str) -> Evidence | None:
    return row.cells.get(column)


def _derived(name: str, value: Decimal, source: FieldResult | Evidence | None) -> FieldResult:
    """A value reconciliation worked out, pointing at what it worked it out from."""
    evidence = source.evidence if isinstance(source, FieldResult) else source
    return FieldResult(
        name=name,
        value=value,
        raw_text=str(value),
        evidence=None if evidence is None else _as_derived(evidence),
        valid=True,
    )


def _as_derived(evidence: Evidence) -> Evidence:
    return Evidence(
        page=evidence.page,
        bbox=evidence.bbox,
        matched_label=evidence.matched_label,
        strategy=Strategy.DERIVED,
        raw_text=evidence.raw_text,
    )


def _amount(fields: Mapping[str, FieldResult], name: str) -> Decimal | None:
    found = fields.get(name)
    return found.value if found is not None and isinstance(found.value, Decimal) else None


def _filled(name: str, source: str, code: str) -> Finding:
    return Finding(
        severity=Severity.INFO,
        code=code,
        message=f"{name} was not stated in the totals block; it comes from {source}",
        field=name,
    )


def _undeclared(amount: Decimal) -> Finding:
    return Finding(
        severity=Severity.WARNING,
        code=UNDECLARED,
        message=f"the total carries {amount} that no line of the block declares",
    )
