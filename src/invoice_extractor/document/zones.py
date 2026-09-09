"""Which of a page's nine zones a box falls in, judged by its centre."""

from __future__ import annotations

from invoice_extractor.document.reader import BBox, Zone

THIRDS = 3
GRID = (
    (Zone.TOP_LEFT, Zone.TOP_CENTER, Zone.TOP_RIGHT),
    (Zone.MIDDLE_LEFT, Zone.MIDDLE_CENTER, Zone.MIDDLE_RIGHT),
    (Zone.BOTTOM_LEFT, Zone.BOTTOM_CENTER, Zone.BOTTOM_RIGHT),
)


def classify(bbox: BBox, page_width: float, page_height: float) -> Zone:
    """The zone `bbox` sits in: its centre, normalised against the page's own size."""
    x, y = bbox.center
    return GRID[_third(y, page_height)][_third(x, page_width)]


def _third(value: float, extent: float) -> int:
    """0, 1 or 2 — clamped, so a box centred off the page still names a real zone."""
    return min(max(int(value * THIRDS / extent), 0), THIRDS - 1)
