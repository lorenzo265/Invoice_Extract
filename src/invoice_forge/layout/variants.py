"""What a knob does to a family's declaration.

**A knob is the other value of its axis.** `docs/VARIATION_CATALOG.md` names an axis and
the values in scope; the family declares one of them, and turning the knob on replaces it
with the other. `classic` stays the maximal family — every block present — so the knobs
that touch it mostly switch a block to its second form rather than adding one.

The renderer never sees a `Knob`. It reads the record this module returns, which is why
adding a family in PR F5 is a declaration and not a second renderer.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from invoice_forge.knobs import Knob
from invoice_forge.layout.classic import (
    DISCOUNT_COLUMNS,
    DISCOUNT_DESCRIPTION_WIDTH,
    TRAPS,
)
from invoice_forge.layout.spec import (
    CustomerVat,
    FamilySpec,
    ItemsSpec,
    PageLine,
    PaginationSpec,
    PartiesSpec,
)

# One party column per block the document may print; a family caps how many it has room for.
MAIL_TO_COLUMN = 3


def with_knobs(spec: FamilySpec, knobs: Sequence[Knob]) -> FamilySpec:
    """The family as this document's knobs leave it. Knobs it does not name change nothing."""
    turned = set(knobs)
    return dataclasses.replace(
        spec,
        items=_items(spec, turned),
        pagination=_pagination(spec, turned),
        parties=_parties(spec, turned),
        page_line=PageLine.FOOTER if Knob.PAGE_NUMBERING in turned else spec.page_line,
        customer_vat=_customer_vat(spec, turned),
        traps=TRAPS if Knob.TRAP_LABELS in turned else spec.traps,
    )


def _items(spec: FamilySpec, turned: set[Knob]) -> ItemsSpec:
    """A discount column is a column set, so it is declared rather than computed."""
    if Knob.DISCOUNT not in turned:
        return spec.items
    return dataclasses.replace(
        spec.items, columns=DISCOUNT_COLUMNS, description_width=DISCOUNT_DESCRIPTION_WIDTH
    )


def _pagination(spec: FamilySpec, turned: set[Knob]) -> PaginationSpec:
    return dataclasses.replace(
        spec.pagination,
        carry_forward=spec.pagination.carry_forward and Knob.CARRY_FORWARD not in turned,
        repeat_letterhead=spec.pagination.repeat_letterhead
        and Knob.REPEAT_LETTERHEAD not in turned,
    )


def _parties(spec: FamilySpec, turned: set[Knob]) -> PartiesSpec | None:
    """A third block needs a third column, which only a family with room for one can give."""
    if spec.parties is None or Knob.PARTY_BLOCKS not in turned:
        return spec.parties
    if len(spec.parties.columns) >= MAIL_TO_COLUMN:
        return spec.parties
    left, right = spec.parties.columns[0], spec.parties.columns[-1]
    return dataclasses.replace(spec.parties, columns=(left, (left + right) / 2, right))


def _customer_vat(spec: FamilySpec, turned: set[Knob]) -> CustomerVat:
    if Knob.CUSTOMER_VAT_POSITION not in turned:
        return spec.customer_vat
    return CustomerVat.METADATA
