"""The four families that are `classic` with blocks restyled or switched off.

Each one is `dataclasses.replace` on the maximal family and nothing else. That is the
whole claim of `docs/FORGE_SPEC.md` §3.3 — adding a family is adding a declaration and
its golden test, never a second renderer — and writing them this way is what keeps it
true: a block none of them mentions is the same block `classic` declares.

| Family | What it is |
|---|---|
| `tabular` | the references in a bordered table, and the tax summary with codes and a heading |
| `stacked` | every value on the line under its label, and an unruled table |
| `saas` | subscription columns, and the sub-items and section subtotals that go with them |
| `minimal` | one party, no tax summary, no bank block, no footer, no page line |
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from invoice_forge.families import Family
from invoice_forge.layout import columns
from invoice_forge.layout.spec import (
    Alignment,
    FamilySpec,
    ItemsSpec,
    MetadataSpec,
    MetadataStyle,
    PageLine,
    PaginationSpec,
    PartiesSpec,
    TotalsSpec,
    VatSummarySpec,
    VatSummaryStyle,
)

# A stacked block needs a second line per row, so it starts higher and sets smaller.
STACKED_METADATA_TOP = 74.0
STACKED_VALUE_LEADING = 10.0
STACKED_ROW_LEADING = 22.0
STACKED_TOTALS_LEADING = 20.0
# A bordered block pads its cells away from the rules around them.
TABLE_ROW_LEADING = 14.0
TABLE_PAD = 4.0
# What a code column ahead of the rate costs the rest of the summary.
CODE_COLUMN_WIDTH = 40.0
# Nine columns of subscription data need a smaller face than seven of goods do.
SAAS_ROW_SIZE = 8.0
SAAS_HEADER_SIZE = 7.0
SAAS_ROW_LEADING = 10.0
SAAS_ROW_GAP = 5.0


def derived_specs(classic: FamilySpec) -> Mapping[Family, FamilySpec]:
    """Every family but `classic`, each one that family with something else declared."""
    return {
        Family.TABULAR: _tabular(classic),
        Family.STACKED: _stacked(classic),
        Family.SAAS: _saas(classic),
        Family.MINIMAL: _minimal(classic),
    }


def _tabular(classic: FamilySpec) -> FamilySpec:
    """The references in a ruled box, and a tax summary that names its codes."""
    return dataclasses.replace(
        classic,
        family=Family.TABULAR,
        metadata=dataclasses.replace(
            classic.metadata,
            style=MetadataStyle.TABLE,
            leading=TABLE_ROW_LEADING,
            pad=TABLE_PAD,
        ),
        vat_summary=_coded(classic.vat_summary),
    )


def _coded(summary: VatSummarySpec | None) -> VatSummarySpec | None:
    """A code column ahead of the rate pushes the whole summary right by its width."""
    if summary is None:
        return None
    return dataclasses.replace(
        summary,
        style=VatSummaryStyle.CODED,
        code_x=summary.x,
        x=summary.x + CODE_COLUMN_WIDTH,
        base_x=summary.base_x + CODE_COLUMN_WIDTH,
        vat_x=summary.vat_x + CODE_COLUMN_WIDTH,
    )


def _stacked(classic: FamilySpec) -> FamilySpec:
    """Label above value, everywhere — the layout that defeats "the value is to the right"."""
    return dataclasses.replace(
        classic,
        family=Family.STACKED,
        metadata=MetadataSpec(
            style=MetadataStyle.STACKED,
            label_x=360.0,
            value_x=545.0,
            top=STACKED_METADATA_TOP,
            size=9.0,
            leading=STACKED_ROW_LEADING,
            align=Alignment.LEFT,
            value_leading=STACKED_VALUE_LEADING,
        ),
        items=dataclasses.replace(classic.items, ruled=False),
        totals=dataclasses.replace(classic.totals, stacked=True, leading=STACKED_TOTALS_LEADING),
    )


def _saas(classic: FamilySpec) -> FamilySpec:
    """Subscriptions, billed by period. Its columns are its own, so no knob swaps them."""
    return dataclasses.replace(
        classic,
        family=Family.SAAS,
        items=ItemsSpec(
            columns=columns.SAAS.columns,
            ruled=True,
            description_width=columns.SAAS.description_width,
            header_size=SAAS_HEADER_SIZE,
            row_size=SAAS_ROW_SIZE,
            row_leading=SAAS_ROW_LEADING,
            row_gap=SAAS_ROW_GAP,
            standard_columns=False,
        ),
    )


def _minimal(classic: FamilySpec) -> FamilySpec:
    """The one-page simple invoice: one party billed, and nothing under the total."""
    return dataclasses.replace(
        classic,
        family=Family.MINIMAL,
        parties=_one_party(classic.parties),
        pagination=PaginationSpec(
            first_page_gap=classic.pagination.first_page_gap,
            later_page_top=classic.pagination.later_page_top,
            carry_forward=False,
        ),
        totals=TotalsSpec(
            label_x=classic.totals.label_x,
            value_x=classic.totals.value_x,
            size=classic.totals.size,
            leading=classic.totals.leading,
            gap_above=classic.totals.gap_above,
            secondary_echo=False,
        ),
        vat_summary=None,
        payment=None,
        footer=None,
        page_line=PageLine.NONE,
    )


def _one_party(parties: PartiesSpec | None) -> PartiesSpec | None:
    """One column, so a ship-to the sampler drew has nowhere on the page to go."""
    if parties is None:
        return None
    return dataclasses.replace(parties, columns=parties.columns[:1])
