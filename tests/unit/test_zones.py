"""`classify` maps a box's centre onto the page's nine zones."""

from __future__ import annotations

import pytest

from conftest import PAGE_HEIGHT, PAGE_WIDTH
from invoice_extractor.document.model import BBox, Zone
from invoice_extractor.document.zones import ALIASES, classify, every_zone

# One point inside each third: the page is 595 x 842, so the thirds break at
# x = 198.33 / 396.67 and y = 280.67 / 561.33.
LEFT, CENTER, RIGHT = 100.0, 300.0, 500.0
TOP, MIDDLE, BOTTOM = 100.0, 400.0, 700.0


def box_at(x: float, y: float) -> BBox:
    return BBox(x - 1, y - 1, x + 1, y + 1)


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (LEFT, TOP, Zone(1, 1)),
        (CENTER, TOP, Zone(1, 2)),
        (RIGHT, TOP, Zone(1, 3)),
        (LEFT, MIDDLE, Zone(2, 1)),
        (CENTER, MIDDLE, Zone(2, 2)),
        (RIGHT, MIDDLE, Zone(2, 3)),
        (LEFT, BOTTOM, Zone(3, 1)),
        (CENTER, BOTTOM, Zone(3, 2)),
        (RIGHT, BOTTOM, Zone(3, 3)),
    ],
)
def test_classify_maps_each_third_to_its_zone(x: float, y: float, expected: Zone) -> None:
    assert classify(box_at(x, y), PAGE_WIDTH, PAGE_HEIGHT) == expected


def test_classify_uses_bbox_centre_not_corner() -> None:
    # x0 sits in the left third; the centre, at x = 200, sits in the middle one.
    straddling = BBox(190.0, 10.0, 210.0, 20.0)
    assert classify(straddling, PAGE_WIDTH, PAGE_HEIGHT) == Zone(1, 2)


def test_a_finer_grid_names_more_zones() -> None:
    """The grid is a parameter, so a page could be cut into more than thirds."""
    assert classify(box_at(500.0, 100.0), PAGE_WIDTH, PAGE_HEIGHT, (4, 4)) == Zone(1, 4)


def test_every_zone_of_a_grid_can_be_listed() -> None:
    assert every_zone((2, 2)) == (Zone(1, 1), Zone(1, 2), Zone(2, 1), Zone(2, 2))


def test_a_box_centred_off_the_page_still_names_a_real_zone() -> None:
    assert classify(BBox(-20.0, -20.0, -10.0, -10.0), PAGE_WIDTH, PAGE_HEIGHT) == Zone(1, 1)
    beyond = BBox(PAGE_WIDTH + 10, PAGE_HEIGHT + 10, PAGE_WIDTH + 20, PAGE_HEIGHT + 20)
    assert classify(beyond, PAGE_WIDTH, PAGE_HEIGHT) == Zone(3, 3)


def test_the_nine_names_of_a_three_by_three_grid_are_accepted_aliases() -> None:
    assert ALIASES["top_right"] == Zone(1, 3)
    assert set(ALIASES.values()) == set(every_zone())
