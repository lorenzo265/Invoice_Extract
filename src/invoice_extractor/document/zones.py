"""Which zone of a page's grid a box falls in, judged by its centre.

The grid is the reader's, not a profile's: zones are computed once while the document is
read, before any profile is known (`docs/ENGINE_SPEC.md` §2, stage 0). A profile declares
the same grid, and `profile/loader.py` refuses one that disagrees, so a zone name written
in a profile always names a zone a page can actually produce.
"""

from __future__ import annotations

from invoice_extractor.document.model import BBox, Zone

# Thirds: enough to say "top right" and "bottom right", which is what a profile's zone
# preferences are for. Nothing in the format assumes three; `classify` takes the grid.
DEFAULT_GRID = (3, 3)

# The nine names of a 3x3 grid, accepted in a profile wherever `r<row>c<col>` is.
ALIASES = {
    "top_left": Zone(1, 1),
    "top_center": Zone(1, 2),
    "top_right": Zone(1, 3),
    "middle_left": Zone(2, 1),
    "middle_center": Zone(2, 2),
    "middle_right": Zone(2, 3),
    "bottom_left": Zone(3, 1),
    "bottom_center": Zone(3, 2),
    "bottom_right": Zone(3, 3),
}


def classify(
    bbox: BBox, page_width: float, page_height: float, grid: tuple[int, int] = DEFAULT_GRID
) -> Zone:
    """The zone `bbox` sits in: its centre, normalised against the page's own size."""
    rows, columns = grid
    x, y = bbox.center
    return Zone(row=_band(y, page_height, rows), col=_band(x, page_width, columns))


def every_zone(grid: tuple[int, int] = DEFAULT_GRID) -> tuple[Zone, ...]:
    """Every zone the grid can produce, in reading order."""
    rows, columns = grid
    return tuple(
        Zone(row, column) for row in range(1, rows + 1) for column in range(1, columns + 1)
    )


def _band(value: float, extent: float, bands: int) -> int:
    """1-based, clamped, so a box centred off the page still names a real zone."""
    return min(max(int(value * bands / extent) + 1, 1), bands)
