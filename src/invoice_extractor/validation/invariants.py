"""Does the invoice's own arithmetic add up?

Each invariant returns `None` when it holds, a WARNING when an operand it needs is
missing, and an ERROR naming both sides when the numbers disagree by more than a cent.
None of them raises: a supplier's rounding mistake describes the document, it is not a
defect in this program (ADR-0005).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import Charge, FieldResult, LineItem, VatSummaryRow
from invoice_extractor.domain.money import quantize_cents, within_tolerance

INVARIANT_NAMES: tuple[str, ...] = ("totals_reconcile", "line_items_sum", "vat_rate_consistent")

PERCENT = Decimal(100)
# The one operand that is a table rather than a field, so no `Finding.field` names it.
LINE_ITEMS = "line_items"


def totals_reconcile(
    fields: Mapping[str, FieldResult], charges: Sequence[Charge] = ()
) -> Finding | None:
    """The subtotal, what was added to it and the VAT should be what the invoice asks for.

    A charge is part of that sum whether the block declared it or stage 5 worked it out:
    both are amounts the document carries, and neither is in the net.
    """
    subtotal = _amount(fields, "subtotal")
    vat_amount = _amount(fields, "vat_amount")
    total = _amount(fields, "total_amount")
    if subtotal is None:
        return _skipped("totals_reconcile", "subtotal")
    if vat_amount is None:
        return _skipped("totals_reconcile", "vat_amount")
    if total is None:
        return _skipped("totals_reconcile", "total_amount")
    added = _added(charges)
    expected = subtotal + added + vat_amount
    if within_tolerance(expected, total):
        return None
    expression = " + ".join(str(part) for part in (subtotal, *_parts(added), vat_amount))
    return _disagrees("totals_reconcile", expression, expected, "total_amount", total)


def _added(charges: Sequence[Charge], declared_only: bool = False) -> Decimal:
    wanted = [charge for charge in charges if charge.declared or not declared_only]
    return sum((charge.amount for charge in wanted), Decimal(0))


def _parts(added: Decimal) -> tuple[Decimal, ...]:
    """A sum names what it is made of, and a document with no charges has no term for them."""
    return () if added == 0 else (added,)


def line_items_sum(
    fields: Mapping[str, FieldResult], line_items: Sequence[LineItem]
) -> Finding | None:
    """The rows of the table should add up to the subtotal printed under them."""
    subtotal = _amount(fields, "subtotal")
    if subtotal is None:
        return _skipped("line_items_sum", "subtotal")
    if not line_items:
        return _skipped("line_items_sum", LINE_ITEMS)
    amounts = [item.net_amount for item in line_items if item.net_amount is not None]
    if len(amounts) != len(line_items):
        # A row whose amount could not be read is a row this sum cannot be made of, and
        # reporting a shortfall the document does not have would be the wrong finding.
        return _skipped("line_items_sum", LINE_ITEMS)
    expected = sum(amounts, Decimal(0))
    if within_tolerance(expected, subtotal):
        return None
    expression = " + ".join(str(amount) for amount in amounts)
    return _disagrees("line_items_sum", expression, expected, "subtotal", subtotal)


def vat_rate_consistent(
    fields: Mapping[str, FieldResult],
    charges: Sequence[Charge] = (),
    summary: Sequence[VatSummaryRow] = (),
) -> Finding | None:
    """The VAT charged should be the printed rate applied to what is taxed, to the cent.

    What is taxed is the net plus the charges the block declared: a vendor that bills for
    delivery charges tax on the delivery. A charge no line declares is a charge nothing
    says the tax on either, so it is not taxed here.

    A document at several rates has no one rate to multiply by — its summary says so, one
    line per rate — and this is a check on a single-rate document only.
    """
    if len(_rates(summary)) > 1:
        return _not_applicable("vat_rate_consistent", "the document is at more than one rate")
    subtotal = _amount(fields, "subtotal")
    rate = _amount(fields, "vat_rate")
    vat_amount = _amount(fields, "vat_amount")
    if subtotal is None:
        return _skipped("vat_rate_consistent", "subtotal")
    if rate is None:
        return _skipped("vat_rate_consistent", "vat_rate")
    if vat_amount is None:
        return _skipped("vat_rate_consistent", "vat_amount")
    taxed = subtotal + _added(charges, declared_only=True)
    expected = quantize_cents(taxed * rate / PERCENT)
    if within_tolerance(expected, vat_amount):
        return None
    expression = f"{rate}% x {taxed}"
    return _disagrees("vat_rate_consistent", expression, expected, "vat_amount", vat_amount)


def check_all(
    fields: Mapping[str, FieldResult],
    line_items: Sequence[LineItem],
    charges: Sequence[Charge] = (),
    summary: Sequence[VatSummaryRow] = (),
) -> tuple[Finding, ...]:
    """Every invariant, in `INVARIANT_NAMES` order, with the ones that held dropped."""
    checked = (
        totals_reconcile(fields, charges),
        line_items_sum(fields, line_items),
        vat_rate_consistent(fields, charges, summary),
    )
    return tuple(finding for finding in checked if finding is not None)


def _rates(summary: Sequence[VatSummaryRow]) -> frozenset[Decimal]:
    return frozenset(row.rate for row in summary if row.rate is not None)


def _amount(fields: Mapping[str, FieldResult], name: str) -> Decimal | None:
    result = fields.get(name)
    value = None if result is None else result.value
    return value if isinstance(value, Decimal) else None


def _skipped(name: str, operand: str) -> Finding:
    field = None if operand == LINE_ITEMS else operand
    return Finding(Severity.WARNING, name, f"{name} skipped: {operand} not found", field=field)


def _not_applicable(name: str, why: str) -> Finding:
    """A check this document is not the kind of document for. It ran; it does not apply."""
    return Finding(Severity.INFO, name, f"{name} not applicable: {why}")


def _disagrees(
    name: str, expression: str, expected: Decimal, field: str, found: Decimal
) -> Finding:
    message = f"{expression} = {expected} but {field} is {found}"
    return Finding(Severity.ERROR, name, message, field=field)
