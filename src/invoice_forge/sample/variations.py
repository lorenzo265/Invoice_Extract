"""What a knob does to the content of a document.

The other half of "a knob is the other value of its axis": these change what the document
contains rather than how it is laid out. The renderer draws whatever the rows carry — a
row with sub-items gets its components printed, a row with a section joins a group — so
none of this reaches the renderer as a `Knob`.

A family can imply content too. `saas` bills subscriptions in sections with components
under them, and that is what the family *is*, so `content_knobs` turns those on for it.
The truth still records the knobs the plan asked for: the plan asked for `saas`.

Every draw here comes off the same `Random` the rest of the sampler uses, so a knobbed
document is as reproducible as an unknobbed one.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from decimal import Decimal
from random import Random

from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.model import (
    Charge,
    ChargeType,
    LineItem,
    Party,
    RoundingPolicy,
    SubItem,
    Subscription,
)
from invoice_forge.profiles.schema import VatRates, VendorProfile
from invoice_forge.sample.catalogue import Catalogue, Product

# Enough rows that the classic table cannot hold them on one page.
MULTI_PAGE_RANGE = (30, 40)
DISCOUNTS = ("2.5", "5", "7.5", "10", "15")
# One row in three carries the variation, so a document shows both kinds of line.
ONE_ROW_IN = 3
SUB_ITEM_RANGE = (1, 3)
SECTION_RANGE = (2, 3)
# A qualifier is appended until the description is long enough to wrap in the table.
WRAP_LENGTH = 46
PRICED_SUB_ITEMS_IN = 2
CHARGE_AMOUNTS = ("9.90", "24.90", "45.00", "120.00")
# A document at several rates draws from two, and one in three from all three.
THREE_RATE_IN = 3
BILLING_CYCLES = ("monthly", "quarterly", "annual")
CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "annual": 12}
SHARES = ("100", "50", "33.3", "25")
TERM_RANGE = (1, 23)
MONTHS_IN_A_YEAR = 12
BASE_YEAR = 2024

# What a family means by being itself, on top of whatever the plan's knobs ask for.
IMPLIED: Mapping[Family, tuple[Knob, ...]] = {
    Family.SAAS: (Knob.SUB_ITEMS, Knob.SECTION_SUBTOTALS),
}
# And what it bills. A subscription invoice does not sell bearings, so `saas` draws from
# the two domains that are billed by the period rather than by the piece.
SUBSCRIBED_DOMAINS: tuple[str, ...] = ("software", "services")


def content_knobs(family: Family, knobs: Sequence[Knob]) -> tuple[Knob, ...]:
    """The knobs the sampler works from: the plan's, and the ones the family implies."""
    return (*knobs, *IMPLIED.get(family, ()))


def domains(family: Family, every: Sequence[str]) -> tuple[str, ...]:
    """Which catalogue domains a family's rows are drawn from."""
    if family is not Family.SAAS:
        return tuple(every)
    return SUBSCRIBED_DOMAINS


def item_range(knobs: Sequence[Knob], natural: tuple[int, int]) -> tuple[int, int]:
    """How many rows to draw. `multi_page` asks for more than one page can hold."""
    return MULTI_PAGE_RANGE if Knob.MULTI_PAGE in knobs else natural


def described(product: Product, catalogue: Catalogue, knobs: Sequence[Knob], rng: Random) -> str:
    """A description, lengthened past the column width when `wrapped_description` is on."""
    if Knob.WRAPPED_DESCRIPTION not in knobs:
        return product.description
    written = product.description
    while len(written) < WRAP_LENGTH:
        written = f"{written}, {rng.choice(catalogue.qualifiers)}"
    return written


def discount_percent(knobs: Sequence[Knob], rng: Random) -> Decimal | None:
    if Knob.DISCOUNT not in knobs or rng.randrange(ONE_ROW_IN):
        return None
    return Decimal(rng.choice(DISCOUNTS))


def vat_rate(rates: VatRates, knobs: Sequence[Knob], rng: Random) -> Decimal:
    """The rate one row is at. Off, the whole document is at the standard rate."""
    if Knob.MULTI_RATE not in knobs:
        return rates.standard
    return rng.choice(_rate_set(rates, rng))


def rounding(knobs: Sequence[Knob], rng: Random) -> RoundingPolicy:
    """Where the cents are decided. Each knob pins one value; unpinned, a vendor has a habit."""
    if Knob.ROUNDING_TOTAL in knobs:
        return RoundingPolicy.TOTAL
    if Knob.ROUNDING_PER_LINE in knobs:
        return RoundingPolicy.PER_LINE
    return rng.choice(tuple(RoundingPolicy))


def charges(profile: VendorProfile, knobs: Sequence[Knob], rng: Random) -> tuple[Charge, ...]:
    """One charge per knob that asks for one: a document without them prints none.

    `charges` draws whether its charge is declared, the way a vendor's habit would;
    `declared_charge` and `undeclared_charge` pin it, because the catalog counts the two
    kinds apart and an undeclared charge is the one that makes a document not add up.
    """
    asked = [
        (Knob.CHARGES, None),
        (Knob.DECLARED_CHARGE, True),
        (Knob.UNDECLARED_CHARGE, False),
    ]
    wanted = [declared for knob, declared in asked if knob in knobs]
    if not wanted or not profile.charges_used:
        return ()
    return tuple(_charge(profile, declared, rng) for declared in wanted)


def secondary_currency(profile: VendorProfile, knobs: Sequence[Knob]) -> str | None:
    """A second currency is echoed where the knob asks and the vendor deals in one."""
    if Knob.DUAL_CURRENCY_ECHO not in knobs:
        return None
    return profile.secondary_currency


def prints_supply_date(profile: VendorProfile, knobs: Sequence[Knob]) -> bool:
    return profile.prints_supply_date != (Knob.SUPPLY_DATE in knobs)


def extensions(
    profile: VendorProfile, knobs: Sequence[Knob], every: Sequence[str]
) -> tuple[str, ...]:
    """Which optional references are printed: the vendor's few, or all of them."""
    if Knob.EXTRA_REFERENCES not in knobs:
        return profile.extensions
    return tuple(every)


def subscription(family: Family, rng: Random) -> Subscription | None:
    """The period a row bills, drawn only for the family whose columns print one."""
    if family is not Family.SAAS:
        return None
    cycle = rng.choice(BILLING_CYCLES)
    start = rng.randrange(MONTHS_IN_A_YEAR)
    months = CYCLE_MONTHS[cycle]
    return Subscription(
        subscription_id=f"SUB-{rng.randrange(10000, 99999)}",
        billing_cycle=cycle,
        period_start=_month(start),
        period_end=_month(start + months - 1),
        share_percent=Decimal(rng.choice(SHARES)),
        remaining_term=f"{rng.randint(*TERM_RANGE)}/{MONTHS_IN_A_YEAR * 2}",
    )


def sub_items(
    domain: str, catalogue: Catalogue, knobs: Sequence[Knob], rng: Random
) -> tuple[SubItem, ...]:
    """Components under a parent row, drawn from the domain the parent came from."""
    if Knob.SUB_ITEMS not in knobs or rng.randrange(ONE_ROW_IN):
        return ()
    low, high = SUB_ITEM_RANGE
    available = catalogue.products(domain)
    parts = rng.sample(available, min(rng.randint(low, high), len(available)))
    priced = rng.randrange(PRICED_SUB_ITEMS_IN) == 0
    return tuple(_sub_item(part, priced) for part in parts)


def sectioned(
    items: tuple[LineItem, ...], headings: Sequence[str], knobs: Sequence[Knob], rng: Random
) -> tuple[LineItem, ...]:
    """Group the rows under two or three headings, each of which gets its own subtotal."""
    if Knob.SECTION_SUBTOTALS not in knobs or not items:
        return items
    low, high = SECTION_RANGE
    groups = min(rng.randint(low, high), len(items), len(headings))
    named = rng.sample(list(headings), groups)
    size = -(-len(items) // groups)
    return tuple(
        dataclasses.replace(item, section=named[min(index // size, groups - 1)])
        for index, item in enumerate(items)
    )


def placeholder(party: Party, wording: str, knobs: Sequence[Knob]) -> Party:
    """A ship-to block that says "as bill-to" rather than repeating the address."""
    if Knob.PLACEHOLDER_ADDRESSES not in knobs:
        return party
    return Party(name=party.name, lines=(), vat_id=None, placeholder=wording)


def _rate_set(rates: VatRates, rng: Random) -> tuple[Decimal, ...]:
    """Two rates, or all three where the document also carries an exempt line."""
    pair = (rates.standard, rates.reduced)
    return (*pair, rates.zero) if rng.randrange(THREE_RATE_IN) == 0 else pair


def _charge(profile: VendorProfile, declared: bool | None, rng: Random) -> Charge:
    kind: ChargeType = rng.choice(profile.charges_used)
    drawn = rng.choice((True, False))
    return Charge(
        type=kind,
        amount=Decimal(rng.choice(CHARGE_AMOUNTS)),
        vat_rate=profile.vat_rates.standard,
        declared=drawn if declared is None else declared,
    )


def _month(offset: int) -> str:
    """A period bound as `mm.yy`, which is how a table nine columns wide can print one."""
    year, month = divmod(offset, MONTHS_IN_A_YEAR)
    return f"{month + 1:02d}.{(BASE_YEAR + year) % 100:02d}"


def _sub_item(part: Product, priced: bool) -> SubItem:
    if not priced:
        return SubItem(description=part.description)
    return SubItem(description=part.description, quantity=Decimal(1), unit_price=part.price)
