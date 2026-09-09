"""Each ranker's score, on its own. Lower sorts first."""

from __future__ import annotations

from conftest import line, make_field_layout
from invoice_extractor.document.reader import Zone
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.rankers import (
    closest_to_label,
    top_most,
    valid_first,
    zone_priority,
)
from invoice_extractor.extraction.spec import Candidate, Evaluated

ZONED = make_field_layout(zones=(Zone.TOP_RIGHT, Zone.BOTTOM_RIGHT))


def evaluated(text: str, x: float, y: float, label_distance: float, valid: bool) -> Evaluated:
    source = line(text, x, y)
    evidence = Evidence(1, source.bbox, "Label", Strategy.LABEL_RIGHT, text)
    candidate = Candidate(text, evidence, source.zone, label_distance)
    return Evaluated(candidate=candidate, value=text, valid=valid)


def test_valid_first_sorts_a_valid_candidate_ahead() -> None:
    assert valid_first(evaluated("a", 400, 76, 0.0, valid=True), ZONED) == 0.0
    assert valid_first(evaluated("a", 400, 76, 0.0, valid=False), ZONED) == 1.0


def test_zone_priority_is_the_position_in_the_layouts_zone_list() -> None:
    assert zone_priority(evaluated("a", 400, 76, 0.0, valid=True), ZONED) == 0.0
    assert zone_priority(evaluated("a", 400, 700, 0.0, valid=True), ZONED) == 1.0


def test_zone_priority_sorts_an_unexpected_zone_after_every_expected_one() -> None:
    assert zone_priority(evaluated("a", 56, 76, 0.0, valid=True), ZONED) == 2.0


def test_closest_to_label_is_the_distance_the_strategy_recorded() -> None:
    assert closest_to_label(evaluated("a", 400, 76, 16.0, valid=True), ZONED) == 16.0


def test_top_most_is_the_line_top() -> None:
    assert top_most(evaluated("a", 400, 76, 0.0, valid=True), ZONED) == line("a", 400, 76).bbox.y0
