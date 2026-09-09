"""How a candidate is found on the page. Pure functions: text lines in, candidates out.

Each strategy searches the field's expected zones first and the whole page only if that
found nothing — a zone is a preference, not a fence.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence

from invoice_extractor.document.reader import BBox, TextLine
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.spec import Candidate
from invoice_extractor.layout.schema import FieldLayout

StrategyFn = Callable[[Sequence[TextLine], FieldLayout], list[Candidate]]

# What must follow a label for the rest of the line to be its value: a colon and
# something that is not whitespace. "Bill To" alone is a heading, not a labelled value.
AFTER_LABEL = re.compile(r"\s*:\s*\S")


def label_right(lines: Sequence[TextLine], field_layout: FieldLayout) -> list[Candidate]:
    """Lines of the form `<label>: <value>`; the whole line is the candidate's raw text."""
    return _preferring_zones(lines, field_layout, _label_right)


def label_below(lines: Sequence[TextLine], field_layout: FieldLayout) -> list[Candidate]:
    """The nearest line under a line that is exactly the label, overlapping it horizontally."""
    return _preferring_zones(lines, field_layout, _label_below)


def regex_anchor(lines: Sequence[TextLine], field_layout: FieldLayout) -> list[Candidate]:
    """Whatever the layout's own pattern matches. No pattern, no candidates."""
    return _preferring_zones(lines, field_layout, _regex_anchor)


STRATEGIES: Mapping[Strategy, StrategyFn] = {
    Strategy.LABEL_RIGHT: label_right,
    Strategy.LABEL_BELOW: label_below,
    Strategy.REGEX_ANCHOR: regex_anchor,
}


def _preferring_zones(
    lines: Sequence[TextLine], field_layout: FieldLayout, find: StrategyFn
) -> list[Candidate]:
    inside = [line for line in lines if line.zone in field_layout.zones]
    return find(inside, field_layout) or find(lines, field_layout)


def _label_right(lines: Sequence[TextLine], field_layout: FieldLayout) -> list[Candidate]:
    return [
        _candidate(line, label, Strategy.LABEL_RIGHT, line.text, 0.0)
        for label in field_layout.labels
        for line in lines
        if _introduces_a_value(line.text.strip(), label)
    ]


def _introduces_a_value(text: str, label: str) -> bool:
    if not text.lower().startswith(label.lower()):
        return False
    return AFTER_LABEL.match(text[len(label) :]) is not None


def _label_below(lines: Sequence[TextLine], field_layout: FieldLayout) -> list[Candidate]:
    found: list[Candidate] = []
    for label in field_layout.labels:
        for anchor in lines:
            if anchor.text.strip().lower() != label.lower():
                continue
            below = _nearest_below(anchor, lines)
            if below is not None:
                distance = below.bbox.y0 - anchor.bbox.y0
                found.append(_candidate(below, label, Strategy.LABEL_BELOW, below.text, distance))
    return found


def _nearest_below(anchor: TextLine, lines: Sequence[TextLine]) -> TextLine | None:
    under = [
        line
        for line in lines
        if line.page == anchor.page
        and line.bbox.y0 > anchor.bbox.y0
        and _overlaps_horizontally(line.bbox, anchor.bbox)
    ]
    return min(under, key=lambda line: line.bbox.y0, default=None)


def _overlaps_horizontally(left: BBox, right: BBox) -> bool:
    return left.x0 < right.x1 and right.x0 < left.x1


def _regex_anchor(lines: Sequence[TextLine], field_layout: FieldLayout) -> list[Candidate]:
    pattern = field_layout.regex
    if pattern is None:
        return []
    matches = ((line, pattern.search(line.text.strip())) for line in lines)
    return [
        _candidate(line, None, Strategy.REGEX_ANCHOR, match.group(0), 0.0)
        for line, match in matches
        if match is not None
    ]


def _candidate(
    line: TextLine, label: str | None, strategy: Strategy, raw_text: str, label_distance: float
) -> Candidate:
    evidence = Evidence(
        page=line.page,
        bbox=line.bbox,
        matched_label=label,
        strategy=strategy,
        raw_text=raw_text,
    )
    return Candidate(
        raw_text=raw_text,
        evidence=evidence,
        zone=line.zone,
        label_distance=label_distance,
    )
