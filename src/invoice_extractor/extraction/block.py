"""`BlockSpec`: what the totals block says, once `units/totals_block.py` has found it.

A totals block is not a set of labelled fields scattered over a page. It is a short
column of rows that add up, and reading it as a block is what tells an amount under its
label from an amount beside it, a delivery charge from the net it is added to, and the
invoice's own currency from the one it is echoed in.

Two rules do the reading:

- **The identity chooses the column of amounts.** A block may print its amounts twice —
  in the invoice's currency and in another — and the one that is the document's is the
  one where net plus tax plus charges comes to the total.
- **A row is read where its label is.** An amount the vendor sets under its label is the
  number at the label's own x on the next row, never whatever else that row carries.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from invoice_extractor.document.model import Document, Page, TextPart
from invoice_extractor.document.rows import CellRow
from invoice_extractor.document.zones import classify
from invoice_extractor.domain.evidence import Evidence, Strategy
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.totals import Charge, SecondaryAmounts
from invoice_extractor.extraction.engine import Extraction
from invoice_extractor.extraction.spec import BlockSpec
from invoice_extractor.extraction.units.normalizers import (
    numbers_in,
    parse_number,
    without_currency,
)
from invoice_extractor.extraction.units.totals_block import (
    Named,
    amounts,
    at,
    component_of,
    find_block,
)
from invoice_extractor.profile.schema import ComponentKind, Profile

PERCENT = "%"
# An echo says two numbers: what the total comes to, and what it was converted at.
TWO = 2


@dataclass(frozen=True, slots=True)
class Amount:
    """One value the block printed: what it says, and where it was drawn."""

    value: Decimal
    text: str
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class Reading:
    """What the totals block says: its components, its charges, and what it echoed."""

    components: Mapping[str, Amount]
    charges: tuple[Charge, ...] = ()
    secondary: SecondaryAmounts | None = None
    columns: int = 0


@dataclass(frozen=True, slots=True)
class Totals:
    """The block as the pipeline receives it: fields like any other, plus what has none."""

    extractions: Mapping[str, Extraction]
    charges: tuple[Charge, ...] = ()
    secondary: SecondaryAmounts | None = None


def read_totals(spec: BlockSpec, document: Document, profile: Profile) -> Totals:
    """Run one `BlockSpec`: the components it names become fields, the rest stays a block.

    A block publishes what the engine publishes — a value, its evidence, and the zone it
    was drawn in — so the totals are scored by the same signals as every other field.
    """
    reading = read_block(document, profile)
    page = document.page(document.page_count)
    return Totals(
        extractions={
            name: _published(name, reading.components.get(name), page) for name in spec.fields
        },
        charges=reading.charges,
        secondary=reading.secondary,
    )


def _published(name: str, amount: Amount | None, page: Page) -> Extraction:
    """A component the block printed, or the same absence the engine publishes (ADR-0005)."""
    if amount is None:
        return Extraction(FieldResult(name, None, None, None, valid=False), 0, None)
    field = FieldResult(
        name=name,
        value=amount.value,
        raw_text=amount.text,
        evidence=amount.evidence,
        valid=True,
    )
    return Extraction(field, 1, classify(amount.evidence.bbox, page.width, page.height))


def read_block(document: Document, profile: Profile) -> Reading:
    """Read the totals block off the page that carries it, or report an empty one."""
    block = find_block(document, profile)
    if not block.rows:
        return Reading({})
    components = profile.totals.components
    named = [(row, component_of(row, components, block.edge)) for row in block.rows]
    read = _read_column(named, profile, _promoted(named, profile))
    return Reading(
        components=read.components,
        charges=read.charges,
        secondary=_echo(block.rows, named, profile),
        columns=_widest(named),
    )


@dataclass(frozen=True, slots=True)
class _Column:
    """The components and charges one column of amounts came to."""

    components: Mapping[str, Amount]
    charges: tuple[Charge, ...]


def _read_column(
    named: Sequence[tuple[CellRow, Named | None]], profile: Profile, column: int
) -> _Column:
    components: dict[str, Amount] = {}
    charges: list[Charge] = []
    for index, (_, found) in enumerate(named):
        if found is None:
            continue
        amount = _amount_of(named, index, found, column, profile)
        if amount is None:
            continue
        if found.component.kind is ComponentKind.CHARGE:
            # A block may charge twice for the same thing — two surcharges, two fees — and
            # each row is a charge of its own, where an amount is read once.
            charges.append(_charge(found, amount))
        components.setdefault(found.name, amount)
    return _Column(components, tuple(charges))


def _charge(found: Named, amount: Amount) -> Charge:
    return Charge(
        type=found.component.charge_type or "OTHER",
        amount=amount.value,
        declared=True,
        evidence=amount.evidence,
    )


def _amount_of(
    named: Sequence[tuple[CellRow, Named | None]],
    index: int,
    found: Named,
    column: int,
    profile: Profile,
) -> Amount | None:
    """This row's amount: beside its label, or under it where the vendor sets it that way."""
    row = named[index][0]
    beside = amounts(row, found)
    if beside:
        return _parsed(beside[min(column, len(beside) - 1)], profile, found, row.page)
    under = named[index + 1] if index + 1 < len(named) else None
    if under is None or under[1] is not None:
        return None
    edge = found.label.bbox.x0
    printed = [cell for cell in under[0].cells if _is_number(cell, profile) and at(cell, edge)]
    return _parsed(printed[0], profile, found, under[0].page) if printed else None


def _promoted(named: Sequence[tuple[CellRow, Named | None]], profile: Profile) -> int:
    """The column whose amounts close the identity: net plus tax plus charges is the total.

    A block that prints one column of amounts has one candidate and this settles nothing.
    A block that prints two — the invoice's currency and another — is read in the one the
    document is actually in, which is the one that adds up.
    """
    for column in reversed(range(_widest(named))):
        if _closes(_read_column(named, profile, column), profile):
            return column
    return 0


def _widest(named: Sequence[tuple[CellRow, Named | None]]) -> int:
    return max((len(amounts(row, label)) for row, label in named if label), default=0)


def _closes(read: _Column, profile: Profile) -> bool:
    components = read.components
    total = components.get("total_amount")
    net = components.get("subtotal")
    if total is None or net is None:
        return False
    tax = components.get("vat_amount")
    added = sum((charge.amount for charge in read.charges), Decimal(0))
    expected = net.value + added + (Decimal(0) if tax is None else tax.value)
    return abs(expected - total.value) <= profile.totals.tolerance.absolute


def _parsed(cell: TextPart, profile: Profile, found: Named, page: int) -> Amount | None:
    text = cell.text.strip()
    stripped = text.replace(PERCENT, "") if found.component.kind is ComponentKind.RATE else text
    value = parse_number(without_currency(stripped, profile), profile)
    if value is None:
        return None
    return Amount(value, text, _evidence(cell, found, page))


def _is_number(cell: TextPart, profile: Profile) -> bool:
    return parse_number(without_currency(cell.text, profile), profile) is not None


def _evidence(cell: TextPart, found: Named, page: int) -> Evidence:
    return Evidence(
        page=page,
        bbox=cell.bbox,
        matched_label=found.label.text.strip().rstrip(":"),
        strategy=Strategy.BLOCK_ROW,
        raw_text=cell.text.strip(),
    )


def _echo(
    rows: Sequence[CellRow],
    named: Sequence[tuple[CellRow, Named | None]],
    profile: Profile,
) -> SecondaryAmounts | None:
    """The total said again in a currency the invoice is not in, with the rate beside it."""
    claimed = {id(row) for row, found in named if found is not None}
    for row in rows:
        if id(row) in claimed:
            continue
        found = _echoed(row, profile)
        if found is not None:
            return found
    return None


def _echoed(row: CellRow, profile: Profile) -> SecondaryAmounts | None:
    text = " ".join(cell.text for cell in row.cells)
    code = next((found for found in profile.currencies[1:] if found in text), None)
    if code is None:
        return None
    printed = numbers_in(without_currency(text, profile), profile)
    if len(printed) < TWO:
        return None
    return SecondaryAmounts(
        currency=code,
        total_amount=printed[0],
        exchange_rate=printed[-1],
        evidence=_line_evidence(row),
    )


def _line_evidence(row: CellRow) -> Evidence:
    first = row.cells[0]
    return Evidence(
        page=row.page,
        bbox=first.bbox,
        matched_label=None,
        strategy=Strategy.BLOCK_ROW,
        raw_text=" ".join(cell.text.strip() for cell in row.cells),
    )
