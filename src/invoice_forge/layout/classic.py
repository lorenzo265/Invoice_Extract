"""`classic` — the maximal family, and the lookup that resolves a `Family` to its spec.

Every block a European invoice can have is present here: letterhead, title, a metadata
list, two party blocks, a ruled table with wrapped descriptions and carry-forward, a VAT
summary table, totals with charges and a secondary-currency echo, a payment block with a
QR placeholder, and a legal footer. The simpler families are this one with blocks
switched off, which is why they cost a declaration rather than a renderer.

The numbers are A4 points, measured from the top-left corner, and follow the rendered
prototype in `docs/reference/forge/prototype/`.
"""

from __future__ import annotations

from invoice_forge.families import Family
from invoice_forge.layout.spec import (
    Alignment,
    Column,
    FamilySpec,
    FooterSpec,
    ItemsSpec,
    LetterheadSpec,
    MetadataSpec,
    MetadataStyle,
    PageGeometry,
    PaginationSpec,
    PartiesSpec,
    PaymentSpec,
    TitleSpec,
    TotalsSpec,
    VatSummarySpec,
    VatSummaryStyle,
)

A4 = PageGeometry(width=595.0, height=842.0, left=50.0, right=545.0, top=50.0, bottom=790.0)

CLASSIC_COLUMNS: tuple[Column, ...] = (
    Column("pos", 50.0, Alignment.LEFT),
    Column("sku", 72.0, Alignment.LEFT),
    Column("description", 140.0, Alignment.LEFT),
    Column("quantity", 372.0, Alignment.RIGHT),
    Column("unit_price", 432.0, Alignment.RIGHT),
    Column("vat_rate", 470.0, Alignment.RIGHT),
    Column("net_amount", 545.0, Alignment.RIGHT),
)

CLASSIC = FamilySpec(
    family=Family.CLASSIC,
    page=A4,
    letterhead=LetterheadSpec(x=50.0, top=62.0, name_size=13.0, line_size=9.0, leading=12.0),
    title=TitleSpec(x=360.0, top=62.0, size=13.0, upper_case=True),
    metadata=MetadataSpec(
        style=MetadataStyle.LIST,
        label_x=360.0,
        value_x=545.0,
        top=80.0,
        size=9.0,
        leading=12.0,
        align=Alignment.RIGHT,
    ),
    items=ItemsSpec(
        columns=CLASSIC_COLUMNS,
        ruled=True,
        description_width=192.0,
        header_size=8.0,
        row_size=9.0,
        row_leading=11.0,
        row_gap=6.0,
    ),
    pagination=PaginationSpec(first_page_gap=26.0, later_page_top=200.0, carry_forward=True),
    totals=TotalsSpec(
        label_x=340.0,
        value_x=545.0,
        size=9.0,
        leading=13.0,
        gap_above=6.0,
        secondary_echo=True,
    ),
    footer=FooterSpec(x=50.0, size=7.0, leading=10.0, height=44.0),
    parties=PartiesSpec(
        columns=(50.0, 320.0),
        heading_size=8.0,
        line_size=9.0,
        leading=12.0,
        gap_above=18.0,
        gap_below=14.0,
    ),
    vat_summary=VatSummarySpec(
        style=VatSummaryStyle.TABLE,
        x=50.0,
        base_x=200.0,
        vat_x=280.0,
        size=9.0,
        leading=12.0,
    ),
    payment=PaymentSpec(
        x=50.0,
        size=8.0,
        leading=11.0,
        gap_above=18.0,
        box_width=54.0,
        box_height=54.0,
    ),
)

FAMILY_SPECS: dict[Family, FamilySpec] = {Family.CLASSIC: CLASSIC}


def family_spec(family: Family) -> FamilySpec:
    """The declaration for a family, or a refusal naming the families that exist yet."""
    spec = FAMILY_SPECS.get(family)
    if spec is None:
        built = ", ".join(sorted(known.value for known in FAMILY_SPECS))
        raise ValueError(f"family {family.value} is not built yet; built families: {built}")
    return spec
