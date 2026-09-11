"""Every column set a table may be printed with, declared rather than computed.

A column set is a layout decision. Making room for a discount column is not arithmetic on
the classic anchors — every amount column moves and the description gives up the width it
needs to — so each combination is written out and a test holds it to the page.

The standard family has four sets, on two axes the catalog names: `column_set` swaps the
positions and part numbers for a unit column, and `discount` adds the per-line discount.
`saas` has a set of its own, which those knobs have nothing to offer: subscription columns
are not the other value of the standard set's axis.

Every anchor here leaves room for the **widest single word** any bundled lexicon heads
that column with, in either face — `Artikelbezeichnung`, `Faktureringsintervall` — because
a heading of several words wraps and one word cannot. `tests/forge/unit/test_columns.py`
measures it rather than trusting the numbers, in every language the corpus speaks.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from invoice_forge.layout.spec import Alignment, Column

LEFT, RIGHT = Alignment.LEFT, Alignment.RIGHT


@dataclass(frozen=True, slots=True)
class ColumnSet:
    """The columns of one table, and how wide a description may be before it wraps."""

    columns: tuple[Column, ...]
    description_width: float


CLASSIC = ColumnSet(
    columns=(
        Column("pos", 50.0, LEFT),
        Column("sku", 88.0, LEFT),
        Column("description", 152.0, LEFT),
        Column("quantity", 398.0, RIGHT),
        Column("unit_price", 448.0, RIGHT),
        Column("vat_rate", 494.0, RIGHT),
        Column("net_amount", 545.0, RIGHT),
    ),
    description_width=200.0,
)

CLASSIC_DISCOUNT = ColumnSet(
    columns=(
        Column("pos", 50.0, LEFT),
        Column("sku", 88.0, LEFT),
        Column("description", 152.0, LEFT),
        Column("quantity", 358.0, RIGHT),
        Column("unit_price", 408.0, RIGHT),
        Column("discount", 448.0, RIGHT),
        Column("vat_rate", 494.0, RIGHT),
        Column("net_amount", 545.0, RIGHT),
    ),
    description_width=162.0,
)

# No position and no part number, and the unit of measure in their place: the table that
# gives an extractor nothing to key a row on but its description.
COMPACT = ColumnSet(
    columns=(
        Column("description", 50.0, LEFT),
        Column("quantity", 344.0, RIGHT),
        Column("unit", 350.0, LEFT),
        Column("unit_price", 470.0, RIGHT),
        Column("net_amount", 545.0, RIGHT),
    ),
    description_width=250.0,
)

COMPACT_DISCOUNT = ColumnSet(
    columns=(
        Column("description", 50.0, LEFT),
        Column("quantity", 324.0, RIGHT),
        Column("unit", 330.0, LEFT),
        Column("unit_price", 453.0, RIGHT),
        Column("discount", 493.0, RIGHT),
        Column("net_amount", 545.0, RIGHT),
    ),
    description_width=230.0,
)

# A subscription line bills a period, not a piece, so the columns say which subscription,
# over what term, and at what share. Set smaller than the others because there are nine.
SAAS = ColumnSet(
    columns=(
        Column("subscription_id", 50.0, LEFT),
        Column("description", 110.0, LEFT),
        Column("period", 192.0, LEFT),
        Column("billing_cycle", 260.0, LEFT),
        Column("share", 372.0, RIGHT),
        Column("remaining_term", 421.0, RIGHT),
        Column("quantity", 457.0, RIGHT),
        Column("unit_price", 500.0, RIGHT),
        Column("net_amount", 545.0, RIGHT),
    ),
    description_width=78.0,
)

# Keyed by the two knobs that choose between them: `(column_set, discount)`.
STANDARD_SETS: Mapping[tuple[bool, bool], ColumnSet] = {
    (False, False): CLASSIC,
    (False, True): CLASSIC_DISCOUNT,
    (True, False): COMPACT,
    (True, True): COMPACT_DISCOUNT,
}

ALL_SETS: tuple[ColumnSet, ...] = (*STANDARD_SETS.values(), SAAS)
