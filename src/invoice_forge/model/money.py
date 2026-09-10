"""Money the way an invoice does arithmetic: exact, and rounded the way a supplier rounds."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

CENT = Decimal("0.01")
PERCENT = Decimal(100)


def to_cents(value: Decimal) -> Decimal:
    """Round to the cent, half away from zero — the commercial rounding a supplier prints.

    The extractor rounds half to even, because it is asking whether two printed numbers
    agree to within a cent. The generator is deciding what would have been printed, and
    an invoice printed by a business rounds up at the half.
    """
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


class ChargeType(Enum):
    """What a line in the totals block, other than the tax, can be for."""

    SHIPPING = "SHIPPING"
    ENVIRONMENTAL_FEE = "ENVIRONMENTAL_FEE"
    SURCHARGE = "SURCHARGE"
    CONSOLIDATION_FEE = "CONSOLIDATION_FEE"
    RECYCLING_FEE = "RECYCLING_FEE"
    ROUNDING = "ROUNDING"


CHARGE_TYPE_NAMES: tuple[str, ...] = tuple(charge.value for charge in ChargeType)


class RoundingPolicy(Enum):
    """Where the cents are decided: on every line, or once on the sum."""

    PER_LINE = "per_line"
    TOTAL = "total"


ROUNDING_POLICY_NAMES: tuple[str, ...] = tuple(policy.value for policy in RoundingPolicy)


@dataclass(frozen=True, slots=True)
class Money:
    """An amount and the currency it is in. Never a bare number crossing a boundary."""

    amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class Charge:
    """An amount added to the invoice that is not an item.

    An undeclared charge is folded into the total without a line of its own: the document
    then genuinely does not add up, which is the point of the knob, and the truth says so.
    """

    type: ChargeType
    amount: Decimal
    vat_rate: Decimal
    declared: bool


@dataclass(frozen=True, slots=True)
class VatLine:
    """One row of the VAT summary: a rate, what it was applied to, and what it came to."""

    rate: Decimal
    base: Decimal
    vat: Decimal


@dataclass(frozen=True, slots=True)
class Totals:
    """Every number in the totals block. Computed from the items, never stored by hand."""

    subtotal: Decimal
    charges_total: Decimal
    vat_lines: tuple[VatLine, ...]
    vat_amount: Decimal
    undeclared_total: Decimal
    total_amount: Decimal
