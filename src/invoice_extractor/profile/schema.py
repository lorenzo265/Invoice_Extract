"""The typed shape of a vendor profile — what `profiles/*.json` means once validated.

A profile is data (ADR-0006): one vendor's language, locale, currencies, VAT rules,
label vocabulary, party blocks, tables, totals block and variants. `profile/loader.py`
is the only module that parses the JSON; every other module reads the records below.
`docs/PROFILE_FORMAT.md` is the contract for the JSON that produces them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from invoice_extractor.document.model import Zone


class ProfileError(ValueError):
    """A profile that cannot be used. The message names the exact JSON key at fault."""


class Placement(Enum):
    """Which label strategy leads for a field; the others follow in a fixed order."""

    RIGHT = "right"
    BELOW = "below"
    PATTERN = "pattern"


class ComponentKind(Enum):
    """What a totals-block component is: a named amount, or a charge folded into the total."""

    AMOUNT = "amount"
    CHARGE = "charge"


class TableEdge(Enum):
    """What ends a table on a page: the anchor above the totals, or one of its stop labels."""

    TOTALS_ANCHOR = "totals_anchor"
    STOP_LABEL = "stop_label"


PLACEMENT_NAMES: tuple[str, ...] = tuple(placement.value for placement in Placement)
COMPONENT_KIND_NAMES: tuple[str, ...] = tuple(kind.value for kind in ComponentKind)
TABLE_EDGE_NAMES: tuple[str, ...] = tuple(edge.value for edge in TableEdge)

# The components every totals block must name, whatever else a vendor prints beside them.
REQUIRED_COMPONENTS: tuple[str, ...] = ("subtotal", "vat_amount", "total_amount")
# The party blocks a profile describes. `bill_to` is the only one every invoice carries.
PARTY_NAMES: tuple[str, ...] = ("bill_to", "ship_to", "mail_to")


@dataclass(frozen=True, slots=True)
class NumberFormat:
    """How this vendor writes numbers. There is no fallback for these anywhere in code."""

    decimal_separator: str
    thousands_separators: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldProfile:
    """Where one labelled field is printed on this vendor's invoices, and what it looks like."""

    labels: tuple[str, ...]
    zones: tuple[Zone, ...]
    placement: Placement
    pattern: re.Pattern[str] | None
    required: bool
    exclude_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SectionProfile:
    """A party block: where it starts, what ends it, and what it says when it defers."""

    labels: tuple[str, ...]
    stop_labels: tuple[str, ...]
    max_lines: int
    placeholders: tuple[str, ...]
    zones: tuple[Zone, ...]


@dataclass(frozen=True, slots=True)
class PageBounds:
    """Where a table starts on a page and what closes it."""

    start: str
    end: TableEdge


@dataclass(frozen=True, slots=True)
class TableProfile:
    """One table: the header labels per canonical column, and the rules that bound its rows."""

    columns: Mapping[str, tuple[str, ...]]
    min_header_matches: int
    stop_labels: tuple[str, ...]
    page_bounds: PageBounds
    carry_forward_labels: tuple[str, ...]
    sub_item_indent: float
    number_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComponentProfile:
    """One line of the totals block: what it is called, and whether it is a charge."""

    labels: tuple[str, ...]
    kind: ComponentKind
    charge_type: str | None
    accumulate: bool


@dataclass(frozen=True, slots=True)
class SecondaryEcho:
    """The second-currency echo some vendors print under the total, with its rate."""

    labels: tuple[str, ...]
    rate_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Tolerance:
    """How far an identity may miss before it is a disagreement rather than a rounding."""

    absolute: Decimal
    relative: Decimal


@dataclass(frozen=True, slots=True)
class BlockProfile:
    """The totals block: its components, what closes it, and what closing means."""

    components: Mapping[str, ComponentProfile]
    cluster_gap: float
    secondary_echo: SecondaryEcho | None
    tolerance: Tolerance


@dataclass(frozen=True, slots=True)
class CustomFieldProfile:
    """A field this vendor prints that the field catalog does not name. Declared, not coded."""

    name: str
    field: FieldProfile


@dataclass(frozen=True, slots=True)
class Variant:
    """A partial profile applied when its fingerprint matches (ENGINE_SPEC.md §2, stage 2)."""

    id: str
    when: Mapping[str, str]
    overlay: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class DocumentTypes:
    """The titles that say what kind of document this is, and how a credit note cites one."""

    invoice_titles: tuple[str, ...]
    credit_note_titles: tuple[str, ...]
    credit_reference_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VatProfile:
    """The rates this vendor charges and the shape of a VAT id in its country."""

    rates: Mapping[str, Decimal]
    id_prefix: str
    id_pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class SupplierProfile:
    """The values an `AnchorSpec` expects to find: this vendor, as it prints itself."""

    name: str
    aliases: tuple[str, ...]
    address_lines: tuple[str, ...]
    vat_id: str


@dataclass(frozen=True, slots=True)
class Noise:
    """Labels known to be traps: an order date beside the invoice date, a print date."""

    ignore_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Profile:
    """One vendor's invoices, described. The unit of configuration (ADR-0006)."""

    id: str
    language: str
    country: str
    lexicon: str
    number_format: NumberFormat
    date_formats: tuple[str, ...]
    currencies: tuple[str, ...]
    vat: VatProfile
    supplier: SupplierProfile
    zones_grid: tuple[int, int]
    fields: Mapping[str, FieldProfile]
    parties: Mapping[str, SectionProfile]
    line_items: TableProfile
    vat_summary: TableProfile | None
    totals: BlockProfile
    custom_fields: tuple[CustomFieldProfile, ...]
    variants: tuple[Variant, ...]
    document_types: DocumentTypes
    noise: Noise
