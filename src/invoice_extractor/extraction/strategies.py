"""How a candidate is found on the page. Pure functions: text lines in, candidates out.

Each strategy reads the whole page and then keeps the candidates that landed in the
field's expected zones, or all of them if none did — a zone is a preference, not a fence.
The preference is applied to the candidate rather than to the lines searched, because a
zone says where the *value* is: a label at the last tab stop of the middle third and its
value flush right in the right third are one row of one block, and filtering the page
before searching would throw the label away and find nothing at all.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence

from invoice_extractor.document.model import BBox, TextLine
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.spec import Candidate
from invoice_extractor.profile.schema import FieldProfile

StrategyFn = Callable[[Sequence[TextLine], FieldProfile], list[Candidate]]

# What must follow a label for the rest of the line to be its value: a colon and
# something that is not whitespace. "Bill To" alone is a heading, not a labelled value.
AFTER_LABEL = re.compile(r"\s*:\s*\S")
# How much of the shorter box two lines must share vertically to be the same line of the
# page. Half of it: set at two sizes, a label and its value still overlap by more than
# that, and the line above or below never does.
SAME_LINE_SHARE = 0.5


def label_right(lines: Sequence[TextLine], field_profile: FieldProfile) -> list[Candidate]:
    """Lines of the form `<label>: <value>`; the whole line is the candidate's raw text."""
    return _preferring_zones(_label_right(lines, field_profile), field_profile)


def label_beside(lines: Sequence[TextLine], field_profile: FieldProfile) -> list[Candidate]:
    """The nearest line to the right of a line that is only the label, on the same baseline.

    The other half of `label_right`. A vendor that sets its labels at one tab stop and its
    values flush right at another prints no text between the two, so the reader sees two
    lines rather than one and `<label>: <value>` never appears anywhere on the page.
    """
    return _preferring_zones(_label_beside(lines, field_profile), field_profile)


def label_below(lines: Sequence[TextLine], field_profile: FieldProfile) -> list[Candidate]:
    """The nearest line under a line that is exactly the label, overlapping it horizontally."""
    return _preferring_zones(_label_below(lines, field_profile), field_profile)


def regex_anchor(lines: Sequence[TextLine], field_profile: FieldProfile) -> list[Candidate]:
    """Whatever the profile's own pattern matches. No pattern, no candidates."""
    return _preferring_zones(_regex_anchor(lines, field_profile), field_profile)


STRATEGIES: Mapping[Strategy, StrategyFn] = {
    Strategy.LABEL_RIGHT: label_right,
    Strategy.LABEL_BESIDE: label_beside,
    Strategy.LABEL_BELOW: label_below,
    Strategy.REGEX_ANCHOR: regex_anchor,
}


def _preferring_zones(found: list[Candidate], field_profile: FieldProfile) -> list[Candidate]:
    """The candidates in the field's own zones, or every one of them if none is."""
    inside = [candidate for candidate in found if candidate.zone in field_profile.zones]
    return inside or found


def _label_right(lines: Sequence[TextLine], field_profile: FieldProfile) -> list[Candidate]:
    return [
        _candidate(line, label, Strategy.LABEL_RIGHT, line.text, 0.0)
        for label in field_profile.labels
        for line in lines
        if _introduces_a_value(line.text.strip(), label)
    ]


def _introduces_a_value(text: str, label: str) -> bool:
    if not text.lower().startswith(label.lower()):
        return False
    return AFTER_LABEL.match(text[len(label) :]) is not None


def _label_beside(lines: Sequence[TextLine], field_profile: FieldProfile) -> list[Candidate]:
    found: list[Candidate] = []
    for label in field_profile.labels:
        for anchor in lines:
            if not _is_only_the_label(anchor.text, label):
                continue
            beside = _nearest_beside(anchor, lines)
            if beside is not None:
                gap = beside.bbox.x0 - anchor.bbox.x1
                found.append(_candidate(beside, label, Strategy.LABEL_BESIDE, beside.text, gap))
    return found


def _is_only_the_label(text: str, label: str) -> bool:
    """`Beleg-Nr.:` is the label, with the colon the tab stop left on the end of it."""
    return text.strip().removesuffix(":").strip().lower() == label.lower()


def _nearest_beside(anchor: TextLine, lines: Sequence[TextLine]) -> TextLine | None:
    """The first thing printed to the right of the label, and nothing further than that."""
    beside = [
        line
        for line in lines
        if line.page == anchor.page
        and line.bbox.x0 >= anchor.bbox.x1
        and _shares_a_line(line.bbox, anchor.bbox)
    ]
    return min(beside, key=lambda line: line.bbox.x0, default=None)


def _shares_a_line(left: BBox, right: BBox) -> bool:
    """Two boxes are the same line of the page when they overlap down most of their height."""
    overlap = min(left.y1, right.y1) - max(left.y0, right.y0)
    shorter = min(left.y1 - left.y0, right.y1 - right.y0)
    return overlap > shorter * SAME_LINE_SHARE


def _label_below(lines: Sequence[TextLine], field_profile: FieldProfile) -> list[Candidate]:
    found: list[Candidate] = []
    for label in field_profile.labels:
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


def _regex_anchor(lines: Sequence[TextLine], field_profile: FieldProfile) -> list[Candidate]:
    pattern = field_profile.pattern
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
