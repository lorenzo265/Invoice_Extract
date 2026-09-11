"""What a template family is: a declaration of blocks, their placement and their style.

A family is a value, never a code path. The renderer reads this record and draws what it
says; `classic` sets every option to its maximal setting and the simpler families switch
blocks off. Nothing here knows about PyMuPDF — these are numbers on a page, in points.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from invoice_forge.families import Family


class Alignment(Enum):
    """Where a column's anchor is: its left edge, or the right edge it is flushed to."""

    LEFT = "left"
    RIGHT = "right"


class MetadataStyle(Enum):
    """How the header block prints label and value."""

    LIST = "list"
    TABLE = "table"
    STACKED = "stacked"


class VatSummaryStyle(Enum):
    """The four forms the tax summary takes, from absent to a coded table with a heading."""

    NONE = "none"
    LIST = "list"
    TABLE = "table"
    CODED = "coded"


class PageLine(Enum):
    """Where "page x of y" is printed, or that this family does not print it at all."""

    NONE = "none"
    HEADER = "header"
    FOOTER = "footer"


class CustomerVat(Enum):
    """Which block carries the customer's VAT id — the second is a trap for the first."""

    PARTY_BLOCK = "party_block"
    METADATA = "metadata"


class Weight(Enum):
    """The two faces a family draws with. The profile decides sans or serif."""

    REGULAR = "regular"
    BOLD = "bold"


@dataclass(frozen=True, slots=True)
class PageGeometry:
    """The paper and the four margins every block is placed against."""

    width: float
    height: float
    left: float
    right: float
    top: float
    bottom: float


@dataclass(frozen=True, slots=True)
class Column:
    """One column of the item table: which value, where its anchor is, how it is set."""

    name: str
    anchor: float
    align: Alignment


@dataclass(frozen=True, slots=True)
class LetterheadSpec:
    """The supplier block: name, address, VAT id."""

    x: float
    top: float
    name_size: float
    line_size: float
    leading: float


@dataclass(frozen=True, slots=True)
class TitleSpec:
    """The document type, and how far under it a copy stamp goes when one is printed."""

    x: float
    top: float
    size: float
    upper_case: bool
    stamp_gap: float = 18.0
    stamp_size: float = 16.0


@dataclass(frozen=True, slots=True)
class MetadataSpec:
    """The reference block: invoice number, dates, customer and order numbers.

    `LIST` sets the label at `label_x` and the value against `value_x`. `TABLE` rules a
    box around the same two columns. `STACKED` puts the value on the line under its
    label, which is the layout that defeats "the value is to the right of the label".
    """

    style: MetadataStyle
    label_x: float
    value_x: float
    top: float
    size: float
    leading: float
    align: Alignment
    # A stacked block needs two lines per row, and a bordered one needs a left edge.
    value_leading: float = 0.0
    left: float = 0.0
    pad: float = 3.0


@dataclass(frozen=True, slots=True)
class PartiesSpec:
    """One block per party the document names, side by side."""

    columns: tuple[float, ...]
    heading_size: float
    line_size: float
    leading: float
    gap_above: float
    gap_below: float


@dataclass(frozen=True, slots=True)
class ItemsSpec:
    """The table: its columns, whether it is ruled, and how a row is set.

    `standard_columns` says the column set is the one the column knobs have another value
    for. A family with columns of its own — subscription lines, say — sets it false and
    keeps them: the knobs offer the other value of the standard set's axis, not of its.
    """

    columns: tuple[Column, ...]
    ruled: bool
    description_width: float
    header_size: float
    row_size: float
    row_leading: float
    row_gap: float
    sub_item_indent: float = 12.0
    section_gap: float = 6.0
    standard_columns: bool = True


@dataclass(frozen=True, slots=True)
class PaginationSpec:
    """Where the table starts on each page, what a break carries, and what repeats."""

    first_page_gap: float
    later_page_top: float
    carry_forward: bool
    repeat_letterhead: bool = True


@dataclass(frozen=True, slots=True)
class TrapSpec:
    """Dates printed beside the real ones that an extractor should not read as them."""

    kinds: tuple[str, ...]
    label_x: float
    value_x: float
    size: float
    leading: float


@dataclass(frozen=True, slots=True)
class VatSummarySpec:
    """The tax summary. `CODED` puts a code column before the rate and a heading above."""

    style: VatSummaryStyle
    x: float
    base_x: float
    vat_x: float
    size: float
    leading: float
    code_x: float = 0.0


@dataclass(frozen=True, slots=True)
class TotalsSpec:
    """The block that adds it all up, and the lines a family prints under it.

    `stacked` sets the amount on the line below its label rather than across from it,
    the way the `stacked` family sets everything else.
    """

    label_x: float
    value_x: float
    size: float
    leading: float
    gap_above: float
    secondary_echo: bool
    stacked: bool = False
    amount_in_words: bool = False
    exemption: bool = False


@dataclass(frozen=True, slots=True)
class PaymentSpec:
    """The bank block, with a drawn box where a payment QR code would be."""

    x: float
    size: float
    leading: float
    gap_above: float
    box_width: float
    box_height: float


@dataclass(frozen=True, slots=True)
class TermsBlockSpec:
    """Payment terms as a block of their own rather than a line in the bank block."""

    x: float
    size: float
    leading: float
    gap_above: float


@dataclass(frozen=True, slots=True)
class FooterSpec:
    """Legal lines above the bottom margin, on every page."""

    x: float
    size: float
    leading: float
    height: float


@dataclass(frozen=True, slots=True)
class FamilySpec:
    """One template family, whole. A block set to `None` is a block this family omits."""

    family: Family
    page: PageGeometry
    letterhead: LetterheadSpec
    title: TitleSpec
    metadata: MetadataSpec
    items: ItemsSpec
    pagination: PaginationSpec
    totals: TotalsSpec
    footer: FooterSpec | None
    parties: PartiesSpec | None
    vat_summary: VatSummarySpec | None
    payment: PaymentSpec | None
    terms_block: TermsBlockSpec | None = None
    page_line: PageLine = PageLine.HEADER
    customer_vat: CustomerVat = CustomerVat.PARTY_BLOCK
    traps: TrapSpec | None = None
    copy_stamp: bool = False
