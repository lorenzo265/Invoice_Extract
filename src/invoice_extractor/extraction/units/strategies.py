"""How a candidate is found on the page. Pure functions: lines in, candidates out.

Four ways a labelled value is printed, and one way an expected value is found:

| Unit | What it reads |
|---|---|
| `label_right` | `<label>: <value>` in one run of text |
| `label_beside` | the nearest thing to the right of a line that is only the label |
| `label_below` | the nearest thing under a line that is only the label, overlapping it |
| `label_pattern` | whatever the field's own pattern matches |
| `anchor_value` | an expected value from the profile, exactly or close to it |

`label_right` and `label_beside` are one reading of a page found two ways, because a PDF
has no idea what a line is: a vendor that sets its label at one tab stop and its value
flush right at another draws no text between them. `label_below` is the third: a stacked
layout puts the value under the label rather than after it. Every strategy runs for every
labelled field and the rankers choose, because which of the three a vendor used is a
property of the document, not of the vendor.

Geometry, never stream order: no unit here indexes `lines[i + 1]`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

from invoice_extractor.document.model import BBox, TextLine
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.candidate import Candidate

# What must follow a label for the rest of the line to be its value: a colon and
# something that is not whitespace. "Bill To" alone is a heading, not a labelled value.
AFTER_LABEL = re.compile(r"\s*:\s*\S")
# How much of the shorter box two lines must share vertically to be the same line of the
# page. Half of it: set at two sizes, a label and its value still overlap by more than
# that, and the line above or below never does.
SAME_LINE_SHARE = 0.5
# How alike two strings must be before one is read as the other, badly printed.
FUZZY_RATIO = 0.85


def label_right(lines: Sequence[TextLine], labels: Sequence[str]) -> list[Candidate]:
    """Lines of the form `<label>: <value>`; the whole line is the candidate's raw text."""
    return [
        _candidate(line, label, Strategy.LABEL_RIGHT, line.text, 0.0)
        for label in labels
        for line in lines
        if _introduces_a_value(line.text.strip(), label)
    ]


def label_beside(lines: Sequence[TextLine], labels: Sequence[str]) -> list[Candidate]:
    """The nearest line to the right of a line that is only the label, on the same baseline."""
    found: list[Candidate] = []
    for label, anchor in _anchors(lines, labels):
        beside = _nearest_beside(anchor, lines)
        if beside is not None:
            gap = beside.bbox.x0 - anchor.bbox.x1
            found.append(_candidate(beside, label, Strategy.LABEL_BESIDE, beside.text, gap))
    return found


def label_below(lines: Sequence[TextLine], labels: Sequence[str]) -> list[Candidate]:
    """The nearest line under a line that is only the label, overlapping it horizontally."""
    found: list[Candidate] = []
    for label, anchor in _anchors(lines, labels):
        below = _nearest_below(anchor, lines)
        if below is not None:
            drop = below.bbox.y0 - anchor.bbox.y1
            found.append(_candidate(below, label, Strategy.LABEL_BELOW, below.text, drop))
    return found


def label_pattern(lines: Sequence[TextLine], patterns: Sequence[str]) -> list[Candidate]:
    """Whatever the field's own pattern matches, wherever it matches it."""
    compiled = [re.compile(source) for source in patterns]
    matches = ((line, pattern.search(line.text.strip())) for pattern in compiled for line in lines)
    return [
        _candidate(line, None, Strategy.LABEL_PATTERN, match.group(0), 0.0)
        for line, match in matches
        if match is not None
    ]


def anchor_value(lines: Sequence[TextLine], expected: Sequence[str]) -> list[Candidate]:
    """An expected value from the profile, found exactly, by its digits, or close to it.

    A vendor's own name and VAT id are known before the document is opened, so finding
    them is a comparison rather than a search. What is published is the value that was
    expected rather than the line it was found on — the line may introduce it with a
    label, and the label is not part of the value. The ratio the match came back with
    stays on the candidate, so the rankers can prefer an exact hit over a near one.
    """
    found: list[Candidate] = []
    for wanted in expected:
        for line in lines:
            ratio = _likeness(line.text, wanted)
            if ratio > 0.0:
                found.append(_candidate(line, wanted, Strategy.ANCHOR, wanted, 0.0, ratio))
    return found


def _anchors(lines: Sequence[TextLine], labels: Sequence[str]) -> list[tuple[str, TextLine]]:
    """Every line that is exactly one of the labels, paired with the label it is."""
    return [
        (label, line) for label in labels for line in lines if _is_only_the_label(line.text, label)
    ]


def _introduces_a_value(text: str, label: str) -> bool:
    if not text.lower().startswith(label.lower()):
        return False
    return AFTER_LABEL.match(text[len(label) :]) is not None


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


def _nearest_below(anchor: TextLine, lines: Sequence[TextLine]) -> TextLine | None:
    under = [
        line
        for line in lines
        if line.page == anchor.page
        and line.bbox.y0 > anchor.bbox.y0
        and _overlaps_horizontally(line.bbox, anchor.bbox)
    ]
    return min(under, key=lambda line: line.bbox.y0, default=None)


def _shares_a_line(left: BBox, right: BBox) -> bool:
    """Two boxes are the same line of the page when they overlap down most of their height."""
    overlap = min(left.y1, right.y1) - max(left.y0, right.y0)
    shorter = min(left.y1 - left.y0, right.y1 - right.y0)
    return overlap > shorter * SAME_LINE_SHARE


def _overlaps_horizontally(left: BBox, right: BBox) -> bool:
    return left.x0 < right.x1 and right.x0 < left.x1


def _likeness(text: str, wanted: str) -> float:
    """1.0 where the line carries the expected value, else how alike the two are, else 0."""
    folded, target = _folded(text), _folded(wanted)
    if not target:
        return 0.0
    if target in folded:
        return 1.0
    ratio = SequenceMatcher(None, folded, target).ratio()
    return ratio if ratio >= FUZZY_RATIO else 0.0


def _folded(text: str) -> str:
    return "".join(character for character in text.casefold() if character.isalnum())


def _candidate(
    line: TextLine,
    label: str | None,
    strategy: Strategy,
    raw_text: str,
    label_distance: float,
    match_ratio: float = 1.0,
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
        match_ratio=match_ratio,
    )
