"""Every document's score, added up the four ways the benchmark reports it.

Field by field over the whole corpus; then field by profile, field by family, and each
knob on against the same knob off. The last one is the point of the corpus: a knob whose
"on" rate is well under its "off" rate names the variation that breaks the extractor,
and a knob whose two rates match names one it survives.

Confidence is tallied beside the outcomes, in bands, so the report can say whether the
number the extractor prints beside a value predicts whether the value is right.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from benchmarks.compare import DocumentScore, Outcome, Scored
from invoice_extractor.domain.models import LINE_ITEM_COLUMNS
from invoice_forge.knobs import KNOB_NAMES

BANDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0001),
)


@dataclass
class Tally:
    """One cell of any of the matrices: four outcome counts and the boxes that agreed."""

    hit: int = 0
    miss: int = 0
    absent: int = 0
    not_covered: int = 0
    evidence_agreed: int = 0
    found_nothing: int = 0

    def add(self, scored: Scored) -> None:
        setattr(self, scored.outcome.value, getattr(self, scored.outcome.value) + 1)
        self.evidence_agreed += bool(scored.evidence_agreed)
        self.found_nothing += scored.found_nothing

    @property
    def scored(self) -> int:
        return self.hit + self.miss

    @property
    def hit_rate(self) -> float | None:
        """`None` where nothing was scored, which a report prints as a dash, not a zero."""
        return None if not self.scored else self.hit / self.scored

    def to_dict(self) -> dict[str, object]:
        return {
            "hit": self.hit,
            "miss": self.miss,
            "absent": self.absent,
            "not_covered": self.not_covered,
            "evidence_agreed": self.evidence_agreed,
            "found_nothing": self.found_nothing,
            "hit_rate": self.hit_rate,
        }


@dataclass
class Matrix:
    """The whole benchmark, accumulated one document at a time."""

    documents: int = 0
    fields: dict[str, Tally] = field(default_factory=dict)
    by_profile: dict[str, dict[str, Tally]] = field(default_factory=dict)
    by_family: dict[str, dict[str, Tally]] = field(default_factory=dict)
    knob_on: dict[str, Tally] = field(default_factory=dict)
    knob_off: dict[str, Tally] = field(default_factory=dict)
    columns: dict[str, Tally] = field(default_factory=dict)
    rows_agreed: int = 0
    detected: int = 0
    calibration: list[Tally] = field(default_factory=lambda: [Tally() for _ in BANDS])

    def add(self, score: DocumentScore) -> None:
        self.documents += 1
        self.detected += score.detected
        self.rows_agreed += score.rows_expected == score.rows_found
        for scored in score.fields:
            self._add_field(score, scored)
        for column, (hit, miss) in score.columns.items():
            cell = self.columns.setdefault(column, Tally())
            cell.hit += hit
            cell.miss += miss

    def _add_field(self, score: DocumentScore, scored: Scored) -> None:
        self.fields.setdefault(scored.field, Tally()).add(scored)
        self.by_profile.setdefault(score.profile, {}).setdefault(scored.field, Tally()).add(scored)
        self.by_family.setdefault(score.family, {}).setdefault(scored.field, Tally()).add(scored)
        turned = set(score.knobs)
        for knob in KNOB_NAMES:
            side = self.knob_on if knob in turned else self.knob_off
            side.setdefault(knob, Tally()).add(scored)
        if scored.outcome in (Outcome.HIT, Outcome.MISS):
            self.calibration[_band(scored.confidence)].add(scored)

    def to_dict(self) -> dict[str, object]:
        return {
            "documents": self.documents,
            "detected": self.detected,
            "fields": _tallies(self.fields),
            "by_profile": {name: _tallies(row) for name, row in sorted(self.by_profile.items())},
            "by_family": {name: _tallies(row) for name, row in sorted(self.by_family.items())},
            "by_knob": _knobs(self.knob_on, self.knob_off),
            "line_items": {
                "rows_agreed": self.rows_agreed,
                "columns": _tallies(self.columns, LINE_ITEM_COLUMNS),
            },
            "calibration": _calibration(self.calibration),
        }


def build(scores: Iterable[DocumentScore]) -> Matrix:
    matrix = Matrix()
    for score in scores:
        matrix.add(score)
    return matrix


def _band(confidence: float) -> int:
    return next(index for index, (low, high) in enumerate(BANDS) if low <= confidence < high)


def _tallies(cells: Mapping[str, Tally], order: Sequence[str] = ()) -> dict[str, object]:
    names = [name for name in order if name in cells] or sorted(cells)
    return {name: cells[name].to_dict() for name in names}


def _knobs(on: Mapping[str, Tally], off: Mapping[str, Tally]) -> dict[str, object]:
    return {
        knob: {"on": on[knob].to_dict(), "off": off[knob].to_dict()}
        for knob in KNOB_NAMES
        if knob in on and knob in off
    }


def _calibration(bands: Sequence[Tally]) -> list[dict[str, object]]:
    return [
        {"band": f"{low:.1f}-{min(high, 1.0):.1f}", **cell.to_dict()}
        for (low, high), cell in zip(BANDS, bands, strict=True)
    ]
