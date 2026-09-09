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
from invoice_extractor.domain.models import FieldResult, LineItem
from invoice_extractor.domain.money import quantize_cents, within_tolerance

INVARIANT_NAMES: tuple[str, ...] = ("totals_reconcile", "line_items_sum", "vat_rate_consistent")

PERCENT = Decimal(100)
# The one operand that is a table rather than a field, so no `Finding.field` names it.
LINE_ITEMS = "line_items"


def totals_reconcile(fields: Mapping[str, FieldResult]) -> Finding | None:
    """The subtotal plus the VAT should be what the invoice asks to be paid."""
    subtotal = _amount(fields, "subtotal")
    vat_amount = _amount(fields, "vat_amount")
    total = _amount(fields, "total_amount")
    if subtotal is None:
        return _skipped("totals_reconcile", "subtotal")
    if vat_amount is None:
        return _skipped("totals_reconcile", "vat_amount")
    if total is None:
        return _skipped("totals_reconcile", "total_amount")
    expected = subtotal + vat_amount
    if within_tolerance(expected, total):
        return None
    expression = f"{subtotal} + {vat_amount}"
    return _disagrees("totals_reconcile", expression, expected, "total_amount", total)


def line_items_sum(
    fields: Mapping[str, FieldResult], line_items: Sequence[LineItem]
) -> Finding | None:
    """The rows of the table should add up to the subtotal printed under them."""
    subtotal = _amount(fields, "subtotal")
    if subtotal is None:
        return _skipped("line_items_sum", "subtotal")
    if not line_items:
        return _skipped("line_items_sum", LINE_ITEMS)
    expected = sum((item.net_amount for item in line_items), Decimal(0))
    if within_tolerance(expected, subtotal):
        return None
    expression = " + ".join(str(item.net_amount) for item in line_items)
    return _disagrees("line_items_sum", expression, expected, "subtotal", subtotal)


def vat_rate_consistent(fields: Mapping[str, FieldResult]) -> Finding | None:
    """The VAT charged should be the printed rate applied to the subtotal, to the cent."""
    subtotal = _amount(fields, "subtotal")
    rate = _amount(fields, "vat_rate")
    vat_amount = _amount(fields, "vat_amount")
    if subtotal is None:
        return _skipped("vat_rate_consistent", "subtotal")
    if rate is None:
        return _skipped("vat_rate_consistent", "vat_rate")
    if vat_amount is None:
        return _skipped("vat_rate_consistent", "vat_amount")
    expected = quantize_cents(subtotal * rate / PERCENT)
    if within_tolerance(expected, vat_amount):
        return None
    expression = f"{rate}% x {subtotal}"
    return _disagrees("vat_rate_consistent", expression, expected, "vat_amount", vat_amount)


def check_all(
    fields: Mapping[str, FieldResult], line_items: Sequence[LineItem]
) -> tuple[Finding, ...]:
    """Every invariant, in `INVARIANT_NAMES` order, with the ones that held dropped."""
    checked = (
        totals_reconcile(fields),
        line_items_sum(fields, line_items),
        vat_rate_consistent(fields),
    )
    return tuple(finding for finding in checked if finding is not None)


def _amount(fields: Mapping[str, FieldResult], name: str) -> Decimal | None:
    result = fields.get(name)
    value = None if result is None else result.value
    return value if isinstance(value, Decimal) else None


def _skipped(name: str, operand: str) -> Finding:
    field = None if operand == LINE_ITEMS else operand
    return Finding(Severity.WARNING, name, f"{name} skipped: {operand} not found", field=field)


def _disagrees(
    name: str, expression: str, expected: Decimal, field: str, found: Decimal
) -> Finding:
    message = f"{expression} = {expected} but {field} is {found}"
    return Finding(Severity.ERROR, name, message, field=field)
