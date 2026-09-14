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
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from invoice_extractor.document.model import BBox
from invoice_extractor.domain.models import (
    LINE_ITEM_COLUMNS,
    Evidence,
    FieldResult,
    InvoiceResult,
    LineItem,
)
from invoice_extractor.extraction.specs import FIELD_ORDER
from invoice_forge.fields import METADATA_FIELDS

MONEY_FIELDS = frozenset({"vat_rate", "subtotal", "vat_amount", "total_amount"})
MONEY_COLUMNS = frozenset({"quantity", "unit_price", "net_amount"})
# What the extractor does not read at all, and so is never scored on: the names the
# generator prints that no spec has learned yet.
NOT_COVERED: tuple[str, ...] = tuple(name for name in METADATA_FIELDS if name not in FIELD_ORDER)


class Outcome(Enum):
    HIT = "hit"
    MISS = "miss"
    ABSENT = "absent"
    NOT_COVERED = "not_covered"


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
    columns: Mapping[str, tuple[int, int]]
    rows_expected: int
    rows_found: int
    detected: bool


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
        fields=tuple(_score(field, fields, result) for field in (*FIELD_ORDER, *NOT_COVERED)),
        columns=_columns(truth, result.line_items),
        rows_expected=len(_sequence(truth, "line_items")),
        rows_found=len(result.line_items),
        detected=result.profile_id == printed,
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


def _columns(
    truth: Mapping[str, object], found: Sequence[LineItem]
) -> Mapping[str, tuple[int, int]]:
    """Per column, how many cells matched and how many did not, over the longer of the two."""
    rows = _sequence(truth, "line_items")
    tally = {column: [0, 0] for column in LINE_ITEM_COLUMNS}
    for index in range(max(len(rows), len(found))):
        wanted = rows[index] if index < len(rows) else None
        row = found[index] if index < len(found) else None
        for column in LINE_ITEM_COLUMNS:
            tally[column][0 if _cell_matches(column, wanted, row) else 1] += 1
    return {column: (hit, miss) for column, (hit, miss) in tally.items()}


def _cell_matches(column: str, wanted: object, row: LineItem | None) -> bool:
    """A row the other side does not have matches nothing, which is one error per column."""
    if row is None or not isinstance(wanted, dict) or wanted.get(column) is None:
        return False
    expected, got = str(wanted[column]), str(getattr(row, column))
    if column in MONEY_COLUMNS:
        return _decimal(expected) == _decimal(got)
    return expected == got


def _mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _sequence(data: Mapping[str, object], key: str) -> Sequence[object]:
    value = data.get(key)
    return value if isinstance(value, list) else ()
