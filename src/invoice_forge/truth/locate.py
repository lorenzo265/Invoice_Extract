"""Turning the placement log into boxes, by reading the finished PDF back.

The renderer knows what it drew and where it asked for it to go. What it does not know is
the box the glyphs actually occupy — that depends on the font, the size and the shaping,
and guessing it would make the truth a second opinion rather than a fact. So every
recorded string is searched for on the page it was recorded on, and the occurrence
nearest the point it was drawn at is the one that belongs to it.

A string the PDF does not contain is a generator fault, not a truth entry: `LocateError`
says which, and no corpus is written.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from invoice_forge.render.pdf import BBox, locate_all
from invoice_forge.render.placement import Placement


class LocateError(RuntimeError):
    """The renderer recorded a string the finished PDF does not contain."""


@dataclass(frozen=True, slots=True)
class Evidence:
    """One box on one page: where a printed value turned out to be."""

    page: int
    bbox: BBox

    def to_dict(self) -> dict[str, object]:
        return {"page": self.page, "bbox": list(self.bbox)}


def locate(path: Path, placements: Sequence[Placement]) -> tuple[Evidence, ...]:
    """One `Evidence` per placement, in the order the placements were recorded.

    Two placements at the same point on the same page are two readings of one printed
    string — a VAT rate that is also the document's headline rate — and share its box.
    Two at different points are two printings, and each claims its own occurrence.
    """
    found = _search(path, placements)
    taken: dict[tuple[int, str], set[int]] = {}
    boxes: dict[tuple[int, str, float, float], BBox] = {}
    missing: list[str] = []
    for placement in placements:
        point = (placement.page, placement.text, placement.x, placement.y)
        if point in boxes:
            continue
        key = (placement.page, placement.text)
        chosen = _nearest(found[key], taken.setdefault(key, set()), placement)
        if chosen is None:
            missing.append(f"page {placement.page}: {placement.text!r}")
            continue
        boxes[point] = chosen
    if missing:
        raise LocateError(f"printed strings not found in {path.name}: {'; '.join(missing)}")
    return tuple(
        Evidence(placement.page, boxes[placement.page, placement.text, placement.x, placement.y])
        for placement in placements
    )


def _search(path: Path, placements: Sequence[Placement]) -> Mapping[tuple[int, str], list[BBox]]:
    """Every box for every distinct string, in one pass over the document."""
    queries = sorted({(placement.page, placement.text) for placement in placements})
    results = locate_all(path, queries)
    return {query: list(boxes) for query, boxes in zip(queries, results, strict=True)}


def _nearest(boxes: list[BBox], used: set[int], placement: Placement) -> BBox | None:
    """The closest occurrence not already claimed by an earlier placement of the same string."""
    free = [(index, box) for index, box in enumerate(boxes) if index not in used]
    if not free:
        return None
    index, box = min(free, key=lambda pair: _distance(pair[1], placement))
    used.add(index)
    return box


def _distance(box: BBox, placement: Placement) -> float:
    """A box's left edge sits at the drawn x; its baseline is just above its bottom edge."""
    return abs(box[0] - placement.x) + abs(box[3] - placement.y)
