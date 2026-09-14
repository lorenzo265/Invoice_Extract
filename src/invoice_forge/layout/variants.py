"""What a knob does to a family's declaration.

**A knob is the other value of its axis.** `docs/VARIATION_CATALOG.md` names an axis and
the values in scope; the family declares one of them, and turning the knob on replaces it
with the other. `classic` stays the maximal family — every block present — so the knobs
that touch it mostly switch a block to its second form rather than adding one. That is
why `bank_footer` takes the bank block away and `vat_summary_table` leaves a list: the
maximal family already has the richer value, and the knob is the other one.

A knob whose axis a family does not have changes nothing on that family. A third party
block needs a third column, a VAT summary knob needs a VAT summary, and a family that
declares neither keeps what it declared.

The renderer never sees a `Knob`. It reads the record this module returns, which is what
lets `tabular`, `stacked`, `saas` and `minimal` be declarations rather than code paths.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from invoice_forge.knobs import Knob
from invoice_forge.layout.classic import TRAPS
from invoice_forge.layout.columns import STANDARD_SETS
from invoice_forge.layout.spec import (
    CustomerVat,
    FamilySpec,
    FooterSpec,
    ItemsSpec,
    MetadataSpec,
    PageLine,
    PaginationSpec,
    PartiesSpec,
    PaymentSpec,
    TermsBlockSpec,
    TotalsSpec,
    VatSummarySpec,
    VatSummaryStyle,
)

# One party column per block the document may print; a family caps how many it has room for.
SIDE_BY_SIDE = 2
# Payment terms as a block of their own, under the totals and above the bank block.
TERMS_BLOCK = TermsBlockSpec(x=50.0, size=8.0, leading=11.0, gap_above=14.0)
# What a copy stamp costs the block under it. `ΑΝΤΙΓΡΑΦΟ` set at sixteen points reaches
# most of the way across the metadata column, so the references start a line lower.
STAMP_LINE = 16.0


def with_knobs(spec: FamilySpec, knobs: Sequence[Knob]) -> FamilySpec:
    """The family as this document's knobs leave it. Knobs it does not name change nothing."""
    turned = set(knobs)
    return dataclasses.replace(
        spec,
        items=_items(spec, turned),
        metadata=_metadata(spec, turned),
        pagination=_pagination(spec, turned),
        parties=_parties(spec, turned),
        page_line=_page_line(spec, turned),
        customer_vat=_customer_vat(spec, turned),
        traps=TRAPS if Knob.TRAP_LABELS in turned else spec.traps,
        vat_summary=_vat_summary(spec, turned),
        totals=_totals(spec, turned),
        payment=_payment(spec, turned),
        footer=_footer(spec, turned),
        terms_block=_terms_block(spec, turned),
        copy_stamp=Knob.STAMP_COPY in turned or spec.copy_stamp,
    )


def _items(spec: FamilySpec, turned: set[Knob]) -> ItemsSpec:
    """The column set is declared, never computed: every anchor moves when one column does."""
    items = spec.items
    if not items.standard_columns:
        return items
    chosen = STANDARD_SETS[Knob.COLUMN_SET in turned, Knob.DISCOUNT in turned]
    return dataclasses.replace(
        items, columns=chosen.columns, description_width=chosen.description_width
    )


def _metadata(spec: FamilySpec, turned: set[Knob]) -> MetadataSpec:
    """A stamped document starts its references under the stamp rather than beside it."""
    if Knob.STAMP_COPY not in turned and not spec.copy_stamp:
        return spec.metadata
    return dataclasses.replace(spec.metadata, top=spec.metadata.top + STAMP_LINE)


def _pagination(spec: FamilySpec, turned: set[Knob]) -> PaginationSpec:
    return dataclasses.replace(
        spec.pagination,
        carry_forward=spec.pagination.carry_forward and Knob.CARRY_FORWARD not in turned,
        repeat_letterhead=spec.pagination.repeat_letterhead
        and Knob.REPEAT_LETTERHEAD not in turned,
    )


def _parties(spec: FamilySpec, turned: set[Knob]) -> PartiesSpec | None:
    """A third block needs a third column, which only a family with room for one can give.

    `minimal` prints one block and has nowhere to put a second, let alone a third: giving
    it three columns at the same x would print three companies on top of each other. So
    the knob divides the room a family already sets two blocks in, and nothing else.
    """
    if spec.parties is None or Knob.PARTY_BLOCKS not in turned:
        return spec.parties
    if len(spec.parties.columns) != SIDE_BY_SIDE:
        return spec.parties
    left, right = spec.parties.columns[0], spec.parties.columns[-1]
    return dataclasses.replace(spec.parties, columns=(left, (left + right) / 2, right))


def _page_line(spec: FamilySpec, turned: set[Knob]) -> PageLine:
    """The knob moves the count between the two places it goes, never onto a page without one."""
    if Knob.PAGE_NUMBERING not in turned or spec.page_line is PageLine.NONE:
        return spec.page_line
    return PageLine.FOOTER


def _customer_vat(spec: FamilySpec, turned: set[Knob]) -> CustomerVat:
    if Knob.CUSTOMER_VAT_POSITION not in turned:
        return spec.customer_vat
    return CustomerVat.METADATA


def _vat_summary(spec: FamilySpec, turned: set[Knob]) -> VatSummarySpec | None:
    """A table of rates against a list of them: the summary a smaller vendor prints."""
    summary = spec.vat_summary
    if summary is None or Knob.VAT_SUMMARY_TABLE not in turned:
        return summary
    return dataclasses.replace(summary, style=VatSummaryStyle.LIST)


def _totals(spec: FamilySpec, turned: set[Knob]) -> TotalsSpec:
    return dataclasses.replace(
        spec.totals,
        amount_in_words=Knob.AMOUNT_IN_WORDS in turned or spec.totals.amount_in_words,
        exemption=Knob.EXEMPTION_VERBIAGE in turned or spec.totals.exemption,
    )


def _payment(spec: FamilySpec, turned: set[Knob]) -> PaymentSpec | None:
    """The other value of "does this invoice print where to pay it" is that it does not."""
    return None if Knob.BANK_FOOTER in turned else spec.payment


def _footer(spec: FamilySpec, turned: set[Knob]) -> FooterSpec | None:
    return None if Knob.NOISE_FOOTER in turned else spec.footer


def _terms_block(spec: FamilySpec, turned: set[Knob]) -> TermsBlockSpec | None:
    """Terms as a block of their own rather than the last line of the bank block."""
    if Knob.PAYMENT_TERMS_BLOCK not in turned:
        return spec.terms_block
    return TERMS_BLOCK
