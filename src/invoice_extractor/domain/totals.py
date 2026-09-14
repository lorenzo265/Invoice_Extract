"""What the totals block adds up: the charges it names, and the currency it echoes.

The three amounts themselves — subtotal, VAT, total — are fields like any other, because
that is what a reader asks an invoice for. What has no field of its own is everything a
vendor may add between them: a delivery charge, a recycling fee, a rounding line, and the
same total said again in another currency.

A charge is `declared` when the page names it. One that is only in the total is inferred
from the arithmetic (`docs/ENGINE_SPEC.md` §5), carries no evidence, and says so.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from invoice_extractor.domain.evidence import Evidence

# The charges a vendor may print, as `docs/FIELD_CATALOG.md` names them. A charge whose
# label no profile claims is `OTHER`: it was printed, and what it is for is the vendor's.
CHARGE_TYPES: tuple[str, ...] = (
    "SHIPPING",
    "ENVIRONMENTAL_FEE",
    "SURCHARGE",
    "CONSOLIDATION_FEE",
    "RECYCLING_FEE",
    "ROUNDING",
    "OTHER",
)


@dataclass(frozen=True, slots=True)
class Charge:
    """One line of the totals block that is neither the net, the tax, nor the total."""

    type: str
    amount: Decimal
    vat_rate: Decimal | None = None
    declared: bool = True
    evidence: Evidence | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "amount": str(self.amount),
            "vat_rate": None if self.vat_rate is None else str(self.vat_rate),
            "declared": self.declared,
            "evidence": None if self.evidence is None else self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Charge:
        rate = data.get("vat_rate")
        found = data.get("evidence")
        return cls(
            type=str(data["type"]),
            amount=Decimal(str(data["amount"])),
            vat_rate=None if rate is None else Decimal(str(rate)),
            declared=bool(data.get("declared", True)),
            evidence=None
            if found is None
            else Evidence.from_dict(cast(Mapping[str, object], found)),
        )


@dataclass(frozen=True, slots=True)
class SecondaryAmounts:
    """The total said again in another currency, and the rate the vendor converted at."""

    currency: str
    total_amount: Decimal | None = None
    exchange_rate: Decimal | None = None
    evidence: Evidence | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "total_amount": _number(self.total_amount),
            "exchange_rate": _number(self.exchange_rate),
            "evidence": None if self.evidence is None else self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> SecondaryAmounts:
        found = data.get("evidence")
        return cls(
            currency=str(data["currency"]),
            total_amount=_decimal(data.get("total_amount")),
            exchange_rate=_decimal(data.get("exchange_rate")),
            evidence=None
            if found is None
            else Evidence.from_dict(cast(Mapping[str, object], found)),
        )


def _number(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _decimal(raw: object) -> Decimal | None:
    return None if raw is None else Decimal(str(raw))
