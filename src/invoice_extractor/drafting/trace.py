"""What every drafted value is written beside: where it came from, and why.

A draft is a set of guesses for a person to correct, and a guess without its reason is
not correctable — the person has to redo the work to find out whether to keep it. So
each key the draft writes has a `Trace`: the value, one sentence of reason, and where on
the page it was read, in the same page, zone and box `inspect` prints. Where nothing was
found the value is a placeholder and the trace says what to fill in.
"""

from __future__ import annotations

from dataclasses import dataclass

from invoice_extractor.document.model import BBox
from invoice_extractor.drafting.pairs import Pair

#: What a draft writes where the page gave it nothing. The loader refuses most of them
#: by name, which is the point: a profile with a hole in it should not read a document.
PLACEHOLDER = "?"


@dataclass(frozen=True, slots=True)
class Trace:
    """One drafted key, its value as written, and the evidence it was written from."""

    key: str
    value: str
    reason: str
    page: int | None = None
    zone: str | None = None
    bbox: BBox | None = None

    @property
    def is_placeholder(self) -> bool:
        return self.value == PLACEHOLDER or not self.value

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "value": self.value,
            "reason": self.reason,
            "page": self.page,
            "zone": self.zone,
            "bbox": None
            if self.bbox is None
            else [self.bbox.x0, self.bbox.y0, self.bbox.x1, self.bbox.y1],
        }


def traced(key: str, value: str, reason: str, pair: Pair) -> Trace:
    """A trace that points at the value of one pair."""
    return Trace(
        key=key,
        value=value,
        reason=reason,
        page=pair.page,
        zone=pair.zone.name,
        bbox=pair.value_bbox,
    )


def missing(key: str, what: str) -> Trace:
    """A placeholder, and what the person has to supply in its place."""
    return Trace(key=key, value=PLACEHOLDER, reason=f"not found on the page — fill in {what}")
