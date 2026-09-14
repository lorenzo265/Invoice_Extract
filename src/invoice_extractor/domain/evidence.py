"""Where a value came from, and how it was found (ADR-0002).

Every value the pipeline publishes carries one of these — a field, a cell of a table, a
line of an address. It lives on its own so that a row can point at the page without the
result record and the row record having to import each other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto
from typing import cast

from invoice_extractor.document.model import BBox


class Strategy(Enum):
    """How a candidate was found. It lives here, beside the `Evidence` that records it.

    `LABEL_RIGHT` and `LABEL_BESIDE` are the same reading of a page — the value follows
    its label along the line — found two ways, because a PDF has no idea what a line is.
    A vendor that writes `Invoice Number: INV-42` in one run gives the reader one line;
    a vendor that sets the label at one tab stop and the number flush right at another
    gives it two, and the text between them is white space that was never drawn.
    `LABEL_BELOW` is the third way: a stacked layout prints the value under its label.

    `ANCHOR` is not a search at all — the value was expected from the profile and found
    on the page — and `DERIVED` names a value no line carries, computed from ones that
    do, with the evidence pointing at the line it was computed from.

    `TABLE_CELL` and `SECTION_LINE` are values no label introduced: a cell is what its
    column says it is, and a line of an address is what the block it sits in says.
    """

    LABEL_RIGHT = auto()
    LABEL_BESIDE = auto()
    LABEL_BELOW = auto()
    LABEL_PATTERN = auto()
    ANCHOR = auto()
    DERIVED = auto()
    TABLE_CELL = auto()
    SECTION_LINE = auto()


@dataclass(frozen=True, slots=True)
class Evidence:
    """Where a value came from: the page and box, the label matched, the text before parsing."""

    page: int
    bbox: BBox
    matched_label: str | None
    strategy: Strategy
    raw_text: str

    def to_dict(self) -> dict[str, object]:
        box = self.bbox
        return {
            "page": self.page,
            "bbox": {"x0": box.x0, "y0": box.y0, "x1": box.x1, "y1": box.y1},
            "matched_label": self.matched_label,
            "strategy": self.strategy.name,
            "raw_text": self.raw_text,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Evidence:
        box = cast(Mapping[str, float], data["bbox"])
        label = data["matched_label"]
        return cls(
            page=cast(int, data["page"]),
            bbox=BBox(x0=box["x0"], y0=box["y0"], x1=box["x1"], y1=box["y1"]),
            matched_label=None if label is None else str(label),
            strategy=Strategy[str(data["strategy"])],
            raw_text=str(data["raw_text"]),
        )


def optional(raw: object) -> Evidence | None:
    """An evidence entry that a value may not have, read back from JSON."""
    return None if raw is None else Evidence.from_dict(cast(Mapping[str, object], raw))
