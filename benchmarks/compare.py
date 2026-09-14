"""One extracted result against one truth file, by the rules the ground-truth schema sets.

`docs/GROUND_TRUTH_SCHEMA.md` states them: identifiers and codes compare as strings,
dates as dates, money and rates as exact decimals with no tolerance, and line items row
for row and column for column, an extra or a missing row costing one error per column.

Four outcomes rather than two, because "wrong" and "not asked" are different failures:

| Outcome | The truth says | The extractor says |
|---|---|---|
| `HIT` | a value | the same value |
| `MISS` | a value | nothing, or a different one — or nothing was there and it read something |
| `ABSENT` | nothing | nothing |
| `NOT_COVERED` | a value | the field is not in its vocabulary at all |

A hit rate is `HIT / (HIT + MISS)`: agreeing that an absent field is absent is right but
is not extraction, and a field the extractor has never heard of is not its mistake.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import cast

from invoice_extractor.document.model import BBox
from invoice_extractor.domain.models import (
    Charge,
    Evidence,
    FieldResult,
    InvoiceResult,
    LineItem,
    Party,
    SecondaryAmounts,
    VatSummaryRow,
)
from invoice_extractor.extraction.specs import FIELD_ORDER
from invoice_forge.fields import METADATA_FIELDS

MONEY_FIELDS = frozenset({"vat_rate", "subtotal", "vat_amount", "total_amount"})
MONEY_COLUMNS = frozenset({"quantity", "unit_price", "net_amount", "rate", "base", "vat"})
# The columns the corpus records a box for, and so the only ones a cell can be scored on.
# A document prints more than it records — `pos`, `unit`, `discount_pct` and `vat_rate` are
# drawn but carry no box in the truth — and those are read and published without being
# measured here, because nothing in the truth says whether the page printed them.
SCORED_COLUMNS: tuple[str, ...] = (
    "part_number",
    "description",
    "quantity",
    "unit_price",
    "net_amount",
)
# The same for a VAT-summary line: the corpus records the numbers but not the code beside
# them, so a code this reader publishes is read and not scored.
SCORED_VAT_COLUMNS: tuple[str, ...] = ("rate", "base", "vat")
# What a party block is scored on. Its VAT id is a value the document need not print in
# the block at all — the customer's is a field of its own — so it is not scored here.
SCORED_PARTY_KEYS: tuple[str, ...] = ("name", "lines")
# How a charge is scored. A declared one is a row of the block and is scored as one, type
# and amount together. An undeclared one is nothing but a difference in the arithmetic —
# the page says neither what it is for nor how many of them there are — so what is scored
# is what the arithmetic can know: how much of the total nothing declared.
SCORED_CHARGE_KEYS: tuple[str, ...] = ("declared", "undeclared")
# The three parts of an echo in another currency.
SECONDARY_KEYS: tuple[str, ...] = ("currency", "total_amount", "exchange_rate")
# What the extractor does not read at all, and so is never scored on: the names the
# generator prints that no spec has learned yet.
NOT_COVERED: tuple[str, ...] = tuple(name for name in METADATA_FIELDS if name not in FIELD_ORDER)


class Outcome(Enum):
    HIT = "hit"
    MISS = "miss"
    ABSENT = "absent"
    NOT_COVERED = "not_covered"


@dataclass
class Counts:
    """How one column or one party key came out over a document: three outcomes, tallied."""

    hit: int = 0
    miss: int = 0
    absent: int = 0

    def count(self, outcome: Outcome) -> None:
        setattr(self, outcome.value, getattr(self, outcome.value) + 1)


@dataclass(frozen=True, slots=True)
class Scored:
    """One field on one document: what happened, how sure the extractor was, and where.

    `found_nothing` separates the two ways a field misses. Reading the wrong value is a
    ranking problem; finding no candidate at all is a strategy problem, and the report
    counts them apart because they are fixed in different places.
    """

    field: str
    outcome: Outcome
    confidence: float
    evidence_agreed: bool | None
    found_nothing: bool = False


@dataclass(frozen=True, slots=True)
class DocumentScore:
    """One document's whole result, tagged with the cell that produced it."""

    name: str
    profile: str
    family: str
    knobs: tuple[str, ...]
    fields: tuple[Scored, ...]
    columns: Mapping[str, Counts]
    rows_expected: int
    rows_found: int
    detected: bool
    parties: Mapping[str, Counts] = field(default_factory=dict)
    vat_columns: Mapping[str, Counts] = field(default_factory=dict)
    vat_rows_expected: int = 0
    vat_rows_found: int = 0
    charges: Mapping[str, Counts] = field(default_factory=dict)
    secondary: Mapping[str, Counts] = field(default_factory=dict)


def compare(name: str, truth: Mapping[str, object], result: InvoiceResult) -> DocumentScore:
    """Score one document against its truth file."""
    cell = _mapping(truth, "generator")
    fields = _mapping(truth, "fields")
    printed = str(cell.get("profile", ""))
    return DocumentScore(
        name=name,
        profile=printed,
        family=str(cell.get("template", "")),
        knobs=tuple(str(knob) for knob in _sequence(cell, "knobs")),
        fields=tuple(_score(name, fields, result) for name in (*FIELD_ORDER, *NOT_COVERED)),
        columns=_columns(truth, result.line_items),
        rows_expected=len(_sequence(truth, "line_items")),
        rows_found=len(result.line_items),
        detected=result.profile_id == printed,
        parties=_parties(truth, result.parties),
        vat_columns=_vat_columns(truth, result.vat_summary),
        vat_rows_expected=len(_printed_vat_rows(truth)),
        vat_rows_found=len(result.vat_summary),
        charges=_charges(truth, result.charges),
        secondary=_secondary(truth, result.secondary_amounts),
    )


def _score(name: str, fields: Mapping[str, object], result: InvoiceResult) -> Scored:
    wanted = _wanted(fields, name)
    if name in NOT_COVERED:
        return Scored(name, Outcome.NOT_COVERED, 0.0, None)
    if name not in result.fields:
        # No profile matched, so nothing was read: every value the document carries is a
        # miss that found nothing, which is what stopping costs and what it should cost.
        return Scored(name, Outcome.ABSENT if wanted is None else Outcome.MISS, 0.0, None, True)
    found = result.fields[name]
    empty = found.raw_text is None
    if wanted is None:
        outcome = Outcome.ABSENT if found.value is None else Outcome.MISS
        return Scored(name, outcome, found.confidence, None, empty and outcome is Outcome.MISS)
    hit = found.value is not None and _same(name, wanted, found.value)
    outcome = Outcome.HIT if hit else Outcome.MISS
    agreed = _evidence_agreed(found, fields, name, hit)
    return Scored(name, outcome, found.confidence, agreed, empty and not hit)


def _wanted(fields: Mapping[str, object], name: str) -> str | None:
    entry = fields.get(name)
    if not isinstance(entry, dict):
        return None
    value = entry.get("value")
    return None if value is None else str(value)


def _same(name: str, wanted: str, found: object) -> bool:
    """Money and rates compare as decimals, everything else as the string it normalises to."""
    if name in MONEY_FIELDS:
        return _decimal(wanted) == _decimal(str(found))
    return wanted == str(found)


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _evidence_agreed(
    found: FieldResult, fields: Mapping[str, object], name: str, hit: bool
) -> bool | None:
    """Reported apart from the value: a right answer read out of the wrong box is a warning."""
    evidence = found.evidence
    if not hit or evidence is None:
        return None
    entry = fields.get(name)
    claimed = _sequence(entry, "evidence") if isinstance(entry, dict) else ()
    return any(_overlaps(evidence, box) for box in claimed)


def _overlaps(evidence: Evidence, claimed: object) -> bool:
    if not isinstance(claimed, dict) or claimed.get("page") != evidence.page:
        return False
    corners = claimed.get("bbox")
    if not isinstance(corners, list) or len(corners) != len(_CORNERS):
        return False
    x0, y0, x1, y1 = (float(corner) for corner in corners)
    return _intersects(evidence.bbox, BBox(x0, y0, x1, y1))


_CORNERS = ("x0", "y0", "x1", "y1")


def _intersects(one: BBox, other: BBox) -> bool:
    return one.x0 < other.x1 and other.x0 < one.x1 and one.y0 < other.y1 and other.y0 < one.y1


def _columns(truth: Mapping[str, object], found: Sequence[LineItem]) -> Mapping[str, Counts]:
    """Per column, how the cells of the two tables compared, over the longer of the two."""
    rows = _sequence(truth, "line_items")
    tally = {column: Counts() for column in SCORED_COLUMNS}
    for index in range(max(len(rows), len(found))):
        wanted = rows[index] if index < len(rows) else None
        row = found[index] if index < len(found) else None
        for column in SCORED_COLUMNS:
            tally[column].count(_cell(column, wanted, None if row is None else row))
    return tally


def _vat_columns(
    truth: Mapping[str, object], found: Sequence[VatSummaryRow]
) -> Mapping[str, Counts]:
    """The same, for the VAT summary: only the lines the document actually printed.

    Every document knows what it charges per rate; not every document prints a summary
    of it, and the truth says which by recording a box for each line it drew.
    """
    rows = _printed_vat_rows(truth)
    tally = {column: Counts() for column in SCORED_VAT_COLUMNS}
    for index in range(max(len(rows), len(found))):
        wanted = rows[index] if index < len(rows) else None
        row = found[index] if index < len(found) else None
        for column in SCORED_VAT_COLUMNS:
            tally[column].count(_cell(column, wanted, row, printed=wanted is not None))
    return tally


def _printed_vat_rows(truth: Mapping[str, object]) -> Sequence[object]:
    return [
        row
        for row in _sequence(truth, "vat_summary")
        if isinstance(row, dict) and row.get("evidence")
    ]


def _cell(column: str, wanted: object, row: object, printed: bool | None = None) -> Outcome:
    """One cell against one cell: read right, read wrong, or never printed at all.

    A cell the page does not carry is `ABSENT` and scores nothing — the truth says which
    ones it carried by recording a box for each — while a value read where none was
    printed is a miss like any other.
    """
    expected = wanted.get(column) if isinstance(wanted, dict) else None
    drawn = printed if printed is not None else _was_printed(wanted, column)
    got = None if row is None else getattr(row, column, None)
    if not drawn or expected is None:
        return Outcome.ABSENT if got is None else Outcome.MISS
    if got is None:
        return Outcome.MISS
    return Outcome.HIT if _same_cell(column, str(expected), got) else Outcome.MISS


def _was_printed(wanted: object, column: str) -> bool:
    """The truth records a box per cell the page drew; a column with none was not drawn."""
    if not isinstance(wanted, dict):
        return False
    cells = wanted.get("cells")
    return isinstance(cells, dict) and column in cells


def _same_cell(column: str, expected: str, got: object) -> bool:
    if column in MONEY_COLUMNS:
        return _decimal(expected) == _decimal(str(got))
    return expected == str(got)


def _parties(truth: Mapping[str, object], found: Mapping[str, Party]) -> Mapping[str, Counts]:
    """Per party and key, whether the block the page printed was read as it was printed."""
    blocks = truth.get("parties")
    entries = blocks if isinstance(blocks, dict) else {}
    tally: dict[str, Counts] = {}
    for name, wanted in entries.items():
        for key in SCORED_PARTY_KEYS:
            tally.setdefault(f"{name}.{key}", Counts()).count(
                _party_cell(wanted, key, found.get(name))
            )
    return tally


def _party_cell(wanted: object, key: str, party: Party | None) -> Outcome:
    """A block the page does not print is absent however much the document knows about it."""
    printed = isinstance(wanted, dict) and bool(wanted.get("evidence"))
    read = None if party is None else getattr(party, key)
    if not printed:
        return Outcome.ABSENT if party is None else Outcome.MISS
    if party is None:
        return Outcome.MISS
    expected = cast(Mapping[str, object], wanted)[key]
    return Outcome.HIT if _same_party(expected, read) else Outcome.MISS


def _same_party(expected: object, read: object) -> bool:
    if isinstance(expected, list):
        lines = read if isinstance(read, tuple) else ()
        return tuple(str(line) for line in expected) == lines
    return (expected or None) == (read or None)


def _charges(truth: Mapping[str, object], found: Sequence[Charge]) -> Mapping[str, Counts]:
    """What the block declared, scored row for row, and what only the arithmetic knows."""
    wanted = [entry for entry in _sequence(truth, "charges") if isinstance(entry, dict)]
    tally = {key: Counts() for key in SCORED_CHARGE_KEYS}
    _named_charges(wanted, found, tally["declared"])
    _unnamed_charges(wanted, found, tally["undeclared"])
    return tally


def _named_charges(
    wanted: Sequence[Mapping[str, object]], found: Sequence[Charge], counts: Counts
) -> None:
    """Type and amount together: a shipping charge read as an environmental fee is wrong."""
    printed = [
        (str(entry.get("type")), _decimal(str(entry.get("amount"))))
        for entry in wanted
        if entry.get("declared")
    ]
    read = [(charge.type, charge.amount) for charge in found if charge.declared]
    _multiset(printed, read, counts)


def _unnamed_charges(
    wanted: Sequence[Mapping[str, object]], found: Sequence[Charge], counts: Counts
) -> None:
    """How much of the total no line declares, which is all such a document says at all."""
    printed = _summed([str(entry.get("amount")) for entry in wanted if not entry.get("declared")])
    read = sum((charge.amount for charge in found if not charge.declared), Decimal(0))
    if printed == 0 and read == 0:
        counts.count(Outcome.ABSENT)
        return
    counts.count(Outcome.HIT if printed == read else Outcome.MISS)


def _summed(amounts: Sequence[str]) -> Decimal:
    return sum((_decimal(amount) or Decimal(0) for amount in amounts), Decimal(0))


def _multiset(wanted: Sequence[object], found: Sequence[object], counts: Counts) -> None:
    """Two bags of values compared: every one matched is a hit, everything left over a miss."""
    remaining = list(found)
    for entry in wanted:
        if entry in remaining:
            remaining.remove(entry)
            counts.count(Outcome.HIT)
        else:
            counts.count(Outcome.MISS)
    for _ in remaining:
        counts.count(Outcome.MISS)
    if not wanted and not found:
        counts.count(Outcome.ABSENT)


def _secondary(truth: Mapping[str, object], found: SecondaryAmounts | None) -> Mapping[str, Counts]:
    """The echo in another currency, part by part; most documents print none at all."""
    entry = truth.get("secondary_amounts")
    printed = entry if isinstance(entry, dict) else {}
    tally = {key: Counts() for key in SECONDARY_KEYS}
    for key in SECONDARY_KEYS:
        tally[key].count(_secondary_cell(printed, key, found))
    return tally


def _secondary_cell(
    printed: Mapping[str, object], key: str, found: SecondaryAmounts | None
) -> Outcome:
    expected = printed.get(key)
    got = None if found is None else getattr(found, key)
    if expected is None:
        return Outcome.ABSENT if got is None else Outcome.MISS
    if got is None:
        return Outcome.MISS
    if key == "currency":
        return Outcome.HIT if str(expected) == str(got) else Outcome.MISS
    return Outcome.HIT if _decimal(str(expected)) == _decimal(str(got)) else Outcome.MISS


def _mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _sequence(data: Mapping[str, object], key: str) -> Sequence[object]:
    value = data.get(key)
    return value if isinstance(value, list) else ()
