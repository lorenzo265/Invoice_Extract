"""What is being billed: one row of the table, and the pieces a row can be made of."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from invoice_forge.model.money import PERCENT, to_cents


@dataclass(frozen=True, slots=True)
class SubItem:
    """A component printed under its parent, with or without a price of its own."""

    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Subscription:
    """The columns a subscription line carries beyond a physical one."""

    subscription_id: str
    billing_cycle: str
    period_start: str
    period_end: str
    share_percent: Decimal | None = None
    remaining_term: str | None = None


@dataclass(frozen=True, slots=True)
class LineItem:
    """One billed row. `net_amount` is derived, so a row can never disagree with itself."""

    pos: int
    sku: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    vat_rate: Decimal
    discount_percent: Decimal | None = None
    section: str | None = None
    sub_items: tuple[SubItem, ...] = ()
    subscription: Subscription | None = None

    @property
    def exact_net(self) -> Decimal:
        """Quantity times price, less any discount, before anyone decides on cents."""
        gross = self.quantity * self.unit_price
        if self.discount_percent is None:
            return gross
        return gross - gross * self.discount_percent / PERCENT

    @property
    def net_amount(self) -> Decimal:
        """What the row prints. A page has cents, whatever the rounding policy is."""
        return to_cents(self.exact_net)
