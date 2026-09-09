"""Exact money: the only place this project rounds or compares a monetary value.

Everything here is `Decimal`. A `float` cannot promise that `subtotal + vat_amount`
equals `total_amount` to the cent, which is the whole point of `validation/invariants.py`.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

CENT: Decimal = Decimal("0.01")


def quantize_cents(value: Decimal) -> Decimal:
    """Round to the cent, half to even — the rule a ledger uses to avoid drifting up."""
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def within_tolerance(left: Decimal, right: Decimal, tolerance: Decimal = CENT) -> bool:
    """Whether two amounts agree. The tolerance measures a supplier's rounding, nothing else."""
    return abs(left - right) <= tolerance
