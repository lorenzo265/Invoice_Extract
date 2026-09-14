"""Shared fixtures: a document made of text lines, with no PDF anywhere near it."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal

from invoice_extractor.document.anchors import anchors_of
from invoice_extractor.document.model import BBox, Document, Page, TextLine, TextPart, Zone
from invoice_extractor.document.zones import classify
from invoice_extractor.domain.rows import LINE_ITEM_COLUMNS, VAT_SUMMARY_COLUMNS
from invoice_extractor.extraction.specs import FIELD_ORDER
from invoice_extractor.profile.schema import (
    BlockProfile,
    Calendar,
    ComponentKind,
    ComponentProfile,
    DocumentTypes,
    FieldProfile,
    Noise,
    NumberFormat,
    PageBounds,
    Placement,
    Profile,
    SectionProfile,
    SupplierProfile,
    TableEdge,
    TableProfile,
    Tolerance,
    VatProfile,
)

PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0

# A test profile speaks English, so its calendar is the one `strptime` already reads;
# `tests/unit/units/test_dates.py` is where another language's months are exercised.
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
ABBREVIATIONS = tuple(name[:3] for name in MONTHS)

# A text font at 10 pt, measured from the drawn baseline, so a fake page lays out in the
# same coordinates a rendered one does.
ASCENT = 10.75
DESCENT = 2.99
CHAR_WIDTH = 5.5

Entry = tuple[int, str, float, float, float, float]


def line(text: str, x: float, y: float, page: int = 1, bold: bool = False) -> TextLine:
    """A `TextLine` whose text is drawn at baseline `y`, starting at `x`."""
    bbox = BBox(x, y - ASCENT, x + CHAR_WIDTH * len(text), y + DESCENT)
    return TextLine(
        page,
        text,
        bbox,
        classify(bbox, PAGE_WIDTH, PAGE_HEIGHT),
        parts=(TextPart(text, bbox, bold=bold),),
    )


def make_document(entries: Sequence[Entry], source_path: str = "fake.pdf") -> Document:
    """A `Document` built from `(page, text, x0, y0, x1, y1)` tuples, with no PDF anywhere."""
    lines = [_from_entry(entry) for entry in entries]
    numbers = sorted({line.page for line in lines})
    return Document(
        pages=tuple(make_page(number, lines) for number in numbers), source_path=source_path
    )


def make_page(number: int, lines: Sequence[TextLine]) -> Page:
    """One page of a fake document, with the anchors its own lines produce."""
    on_page = tuple(line for line in lines if line.page == number)
    return Page(
        number=number,
        width=PAGE_WIDTH,
        height=PAGE_HEIGHT,
        lines=on_page,
        anchors=anchors_of(on_page, PAGE_HEIGHT),
    )


def _from_entry(entry: Entry) -> TextLine:
    page, text, x0, y0, x1, y1 = entry
    bbox = BBox(x0, y0, x1, y1)
    return TextLine(page, text, bbox, classify(bbox, PAGE_WIDTH, PAGE_HEIGHT))


def make_field_profile(
    labels: Sequence[str] = ("Label",),
    zones: Sequence[Zone] = (Zone(1, 3),),
    pattern: str | None = None,
) -> FieldProfile:
    """A `FieldProfile` for one field, with the pieces a test does not care about filled in."""
    return FieldProfile(
        labels=tuple(labels),
        zones=tuple(zones),
        placement=Placement.RIGHT,
        pattern=None if pattern is None else re.compile(pattern),
        required=True,
        exclude_labels=(),
    )


def make_table_profile(
    columns: Mapping[str, Sequence[str]] | None = None,
    stop_labels: Sequence[str] = (),
    carry_forward_labels: Sequence[str] = (),
    min_header_matches: int | None = None,
    end: TableEdge = TableEdge.STOP_LABEL,
) -> TableProfile:
    """A `TableProfile` whose header words are the column names themselves."""
    declared = columns or {column: (column,) for column in LINE_ITEM_COLUMNS}
    return TableProfile(
        columns={name: tuple(labels) for name, labels in declared.items()},
        min_header_matches=len(declared) if min_header_matches is None else min_header_matches,
        stop_labels=tuple(stop_labels),
        page_bounds=PageBounds(start="header", end=end),
        carry_forward_labels=tuple(carry_forward_labels),
        sub_item_indent=8.0,
        number_columns=("quantity", "unit_price", "net_amount"),
    )


def make_vat_table_profile(stop_labels: Sequence[str] = ()) -> TableProfile:
    """The VAT summary's own table: a rate, what it was charged on, and what it came to."""
    return make_table_profile(
        columns={column: (column,) for column in VAT_SUMMARY_COLUMNS},
        stop_labels=stop_labels,
        min_header_matches=2,
    )


def make_section_profile(
    labels: Sequence[str] = ("Bill To",),
    stop_labels: Sequence[str] = (),
    placeholders: Sequence[str] = (),
    max_lines: int = 6,
) -> SectionProfile:
    """A party block's description: what opens it, what closes it, what it says when it defers."""
    return SectionProfile(
        labels=tuple(labels),
        stop_labels=tuple(stop_labels),
        max_lines=max_lines,
        placeholders=tuple(placeholders),
        zones=(Zone(2, 1),),
    )


def make_block_profile() -> BlockProfile:
    """A totals block with the three components every profile must name."""
    return BlockProfile(
        components={
            name: ComponentProfile(
                labels=(name,), kind=ComponentKind.AMOUNT, charge_type=None, accumulate=False
            )
            for name in ("subtotal", "vat_amount", "total_amount")
        },
        cluster_gap=0.08,
        secondary_echo=None,
        tolerance=Tolerance(absolute=Decimal("0.01"), relative=Decimal("0.005")),
    )


def make_profile(
    fields: Mapping[str, FieldProfile] | None = None,
    decimal_separator: str = ".",
    thousands_separators: Sequence[str] = (",",),
    date_formats: Sequence[str] = ("%d %b %Y",),
    line_items: TableProfile | None = None,
    parties: Mapping[str, SectionProfile] | None = None,
    vat_summary: TableProfile | None = None,
) -> Profile:
    """A `Profile` built in memory, so a unit test never reads `profiles/*.json`."""
    return Profile(
        id="test",
        language="en",
        country="GB",
        lexicon="en",
        number_format=NumberFormat(decimal_separator, tuple(thousands_separators)),
        date_formats=tuple(date_formats),
        currencies=("GBP",),
        vat=VatProfile(
            rates={"standard": Decimal("20")},
            id_prefix="GB",
            id_pattern=re.compile(r"\d{9}"),
        ),
        supplier=SupplierProfile(
            name="Test Supplies Ltd", aliases=(), address_lines=("1 Test Street",), vat_id="GB1"
        ),
        calendar=Calendar(months=MONTHS, abbreviations=ABBREVIATIONS),
        zones_grid=(3, 3),
        fields=dict(fields or {name: make_field_profile() for name in FIELD_ORDER}),
        parties=dict(parties or {}),
        line_items=line_items or make_table_profile(),
        vat_summary=vat_summary,
        totals=make_block_profile(),
        custom_fields=(),
        variants=(),
        document_types=DocumentTypes(
            invoice_titles=("INVOICE",),
            credit_note_titles=("CREDIT NOTE",),
            credit_reference_labels=("Original invoice",),
        ),
        noise=Noise(ignore_labels=()),
    )
