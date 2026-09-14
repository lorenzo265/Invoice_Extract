"""One generic runner for every field spec.

`run` finds candidates, normalizes and validates each, orders them by the spec's rankers
and reports the winner with the evidence it came from. It never opens a file and never
raises for a document it cannot understand: an unreadable field is a `FieldResult` with
`valid=False`, which is ADR-0005 applied per field.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from invoice_extractor.document.reader import TextLine, Zone
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.extraction.spec import Candidate, Evaluated, FieldSpec, OnAllInvalid
from invoice_extractor.extraction.strategies import STRATEGIES
from invoice_extractor.layout.schema import FieldLayout, Layout


@dataclass(frozen=True, slots=True)
class Extraction:
    """A field result plus what `validation/confidence.py` needs to score it."""

    field: FieldResult
    candidate_count: int
    zone: Zone | None


def run(spec: FieldSpec, lines: Sequence[TextLine], layout: Layout) -> Extraction:
    """Run one spec against a document's lines and report a single result for the field."""
    field_layout = layout.fields[spec.name]
    candidates = _candidates(spec, lines, field_layout)
    evaluated = [_evaluate(spec, candidate, layout, field_layout) for candidate in candidates]
    winner = _winner(_ranked(evaluated, spec, field_layout), spec)
    if winner is None:
        return Extraction(_not_found(spec.name), len(candidates), None)
    return Extraction(_result(spec.name, winner), len(candidates), winner.candidate.zone)


def _candidates(
    spec: FieldSpec, lines: Sequence[TextLine], field_layout: FieldLayout
) -> list[Candidate]:
    """Every way the field may be printed, pooled — the rankers decide which one won."""
    return [
        candidate
        for strategy in spec.strategies
        for candidate in STRATEGIES[strategy](lines, field_layout)
    ]


def _evaluate(
    spec: FieldSpec, candidate: Candidate, layout: Layout, field_layout: FieldLayout
) -> Evaluated:
    value = spec.normalizer(candidate, layout)
    valid = value is not None and spec.validator(value, field_layout)
    return Evaluated(candidate=candidate, value=value, valid=valid)


def _ranked(
    evaluated: Sequence[Evaluated], spec: FieldSpec, field_layout: FieldLayout
) -> list[Evaluated]:
    """Sorted by every ranker in the spec's order — the first one that differs decides."""

    def key(item: Evaluated) -> tuple[float, ...]:
        return tuple(rank(item, field_layout) for rank in spec.rankers)

    return sorted(evaluated, key=key)


def _winner(ordered: Sequence[Evaluated], spec: FieldSpec) -> Evaluated | None:
    """The best valid candidate, or the best invalid one when the spec asks for it."""
    valid = next((item for item in ordered if item.valid), None)
    if valid is not None:
        return valid
    if spec.on_all_invalid is OnAllInvalid.BEST and ordered:
        return ordered[0]
    return None


def _result(name: str, evaluated: Evaluated) -> FieldResult:
    candidate = evaluated.candidate
    return FieldResult(
        name=name,
        value=evaluated.value,
        raw_text=candidate.raw_text,
        evidence=candidate.evidence,
        valid=evaluated.valid,
    )


def _not_found(name: str) -> FieldResult:
    return FieldResult(name=name, value=None, raw_text=None, evidence=None, valid=False)
