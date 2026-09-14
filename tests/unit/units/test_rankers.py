"""How candidates are ordered when a field found more than one. Lower sorts first."""

from __future__ import annotations

from decimal import Decimal

from conftest import line, make_field_profile
from invoice_extractor.document.model import Zone
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.candidate import Candidate, Evaluated
from invoice_extractor.extraction.units.rankers import (
    best_match,
    closest_to_label,
    last_page_first,
    top_most,
    valid_first,
    zone_priority,
)

BOTTOM_RIGHT = Zone(3, 3)
MIDDLE_RIGHT = Zone(2, 3)
EXPECTED = make_field_profile(zones=(BOTTOM_RIGHT, MIDDLE_RIGHT))


def evaluated(
    zone: Zone = BOTTOM_RIGHT,
    valid: bool = True,
    distance: float = 0.0,
    page: int = 1,
    y: float = 100.0,
    ratio: float = 1.0,
) -> Evaluated:
    drawn = line("588.00", 400, y, page=page)
    evidence = Evidence(page, drawn.bbox, "Total", Strategy.LABEL_BESIDE, "588.00")
    candidate = Candidate(
        raw_text="588.00",
        evidence=evidence,
        zone=zone,
        label_distance=distance,
        match_ratio=ratio,
    )
    return Evaluated(candidate=candidate, value=Decimal("588.00"), valid=valid)


def test_valid_first_puts_a_parsed_value_ahead_of_an_unparsed_one() -> None:
    assert valid_first(evaluated(valid=True), EXPECTED) < valid_first(
        evaluated(valid=False), EXPECTED
    )


def test_zone_priority_follows_the_order_the_profile_lists() -> None:
    assert zone_priority(evaluated(zone=BOTTOM_RIGHT), EXPECTED) == 0.0
    assert zone_priority(evaluated(zone=MIDDLE_RIGHT), EXPECTED) == 1.0


def test_zone_priority_sorts_anywhere_else_after_every_zone_named() -> None:
    assert zone_priority(evaluated(zone=Zone(1, 1)), EXPECTED) == 2.0


def test_closest_to_label_is_the_gap_the_strategy_measured() -> None:
    assert closest_to_label(evaluated(distance=12.0), EXPECTED) == 12.0


def test_top_most_is_where_the_value_sits_down_the_page() -> None:
    assert top_most(evaluated(y=100.0), EXPECTED) < top_most(evaluated(y=400.0), EXPECTED)


def test_last_page_first_prefers_the_end_of_the_document() -> None:
    assert last_page_first(evaluated(page=3), EXPECTED) < last_page_first(
        evaluated(page=1), EXPECTED
    )


def test_best_match_prefers_an_exact_hit_over_a_near_one() -> None:
    assert best_match(evaluated(ratio=1.0), EXPECTED) < best_match(evaluated(ratio=0.9), EXPECTED)
