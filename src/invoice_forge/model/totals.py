"""The one function that turns items and charges into a totals block.

The rounding policy is the argument, not a setting: `PER_LINE` decides the cents on every
row and adds those up; `TOTAL` adds the exact values and decides the cents once. With
integer quantities and two-decimal prices the two agree; with a fractional quantity or a
four-decimal price they differ by a cent or two, and the document says so on its face.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from invoice_forge.model.items import LineItem
from invoice_forge.model.money import (
    PERCENT,
    Charge,
    RoundingPolicy,
    Totals,
    VatLine,
    to_cents,
)


def compute_totals(
    items: Sequence[LineItem], charges: Sequence[Charge], policy: RoundingPolicy
) -> Totals:
    """Every number in the totals block, derived from the rows above it."""
    declared = [charge for charge in charges if charge.declared]
    undeclared = [charge for charge in charges if not charge.declared]
    subtotal = _summed((item.exact_net for item in items), policy)
    charges_total = _summed((charge.amount for charge in declared), policy)
    vat_lines = _vat_lines(items, declared, policy)
    vat_amount = to_cents(sum((line.vat for line in vat_lines), Decimal(0)))
    undeclared_total = _summed((charge.amount for charge in undeclared), policy)
    return Totals(
        subtotal=subtotal,
        charges_total=charges_total,
        vat_lines=vat_lines,
        vat_amount=vat_amount,
        undeclared_total=undeclared_total,
        total_amount=to_cents(subtotal + charges_total + vat_amount + undeclared_total),
    )


def _summed(values: Iterable[Decimal], policy: RoundingPolicy) -> Decimal:
    if policy is RoundingPolicy.PER_LINE:
        return sum((to_cents(value) for value in values), Decimal(0))
    return to_cents(sum(values, Decimal(0)))


def _vat_lines(
    items: Sequence[LineItem], charges: Sequence[Charge], policy: RoundingPolicy
) -> tuple[VatLine, ...]:
    """One row per rate that appears, lowest rate first, as a VAT summary prints them."""
    bases: dict[Decimal, list[Decimal]] = {}
    for item in items:
        bases.setdefault(item.vat_rate, []).append(item.exact_net)
    for charge in charges:
        bases.setdefault(charge.vat_rate, []).append(charge.amount)
    return tuple(_vat_line(rate, _summed(bases[rate], policy)) for rate in sorted(bases))


def _vat_line(rate: Decimal, base: Decimal) -> VatLine:
    return VatLine(rate=rate, base=base, vat=to_cents(base * rate / PERCENT))
