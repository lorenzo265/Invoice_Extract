"""`classify` maps a box's centre onto the page's nine zones."""

from __future__ import annotations

import pytest

from conftest import PAGE_HEIGHT, PAGE_WIDTH
from invoice_extractor.document.reader import BBox, Zone
from invoice_extractor.document.zones import classify

# One point inside each third: the page is 595 x 842, so the thirds break at
# x = 198.33 / 396.67 and y = 280.67 / 561.33.
LEFT, CENTER, RIGHT = 100.0, 300.0, 500.0
TOP, MIDDLE, BOTTOM = 100.0, 400.0, 700.0


def box_at(x: float, y: float) -> BBox:
    return BBox(x - 1, y - 1, x + 1, y + 1)


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (LEFT, TOP, Zone.TOP_LEFT),
        (CENTER, TOP, Zone.TOP_CENTER),
        (RIGHT, TOP, Zone.TOP_RIGHT),
        (LEFT, MIDDLE, Zone.MIDDLE_LEFT),
        (CENTER, MIDDLE, Zone.MIDDLE_CENTER),
        (RIGHT, MIDDLE, Zone.MIDDLE_RIGHT),
        (LEFT, BOTTOM, Zone.BOTTOM_LEFT),
        (CENTER, BOTTOM, Zone.BOTTOM_CENTER),
        (RIGHT, BOTTOM, Zone.BOTTOM_RIGHT),
    ],
)
def test_classify_maps_each_third_to_its_zone(x: float, y: float, expected: Zone) -> None:
    assert classify(box_at(x, y), PAGE_WIDTH, PAGE_HEIGHT) is expected


def test_classify_uses_bbox_centre_not_corner() -> None:
    # x0 sits in the left third; the centre, at x = 200, sits in the middle one.
    straddling = BBox(190.0, 10.0, 210.0, 20.0)
    assert classify(straddling, PAGE_WIDTH, PAGE_HEIGHT) is Zone.TOP_CENTER
