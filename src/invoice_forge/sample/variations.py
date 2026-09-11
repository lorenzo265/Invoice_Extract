"""What a knob does to the content of a document.

The other half of "a knob is the other value of its axis": these change what the document
contains rather than how it is laid out. The renderer draws whatever the rows carry — a
row with sub-items gets its components printed, a row with a section joins a group — so
none of this reaches the renderer as a `Knob`.

Every draw here comes off the same `Random` the rest of the sampler uses, so a knobbed
document is as reproducible as an unknobbed one.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from decimal import Decimal
from random import Random

from invoice_forge.knobs import Knob
from invoice_forge.model import LineItem, Party, SubItem
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


def _sub_item(part: Product, priced: bool) -> SubItem:
    if not priced:
        return SubItem(description=part.description)
    return SubItem(description=part.description, quantity=Decimal(1), unit_price=part.price)
