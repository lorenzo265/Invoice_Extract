"""What a field is: five named behaviours composed as data, never a subclass (ADR-0001).

`Strategy` is re-exported from `domain.models`, where it lives beside the `Evidence`
that records it, so a caller assembling a `FieldSpec` needs only this module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from invoice_extractor.document.reader import Zone
from invoice_extractor.domain.models import Evidence, FieldValue, Strategy
from invoice_extractor.layout.schema import FieldLayout, Layout


class OnAllInvalid(Enum):
    """What to report when every candidate failed its validator."""

    BEST = auto()
    NOT_FOUND = auto()


@dataclass(frozen=True, slots=True)
class Candidate:
    """One piece of text a strategy thinks could be the field, and where it came from."""

    raw_text: str
    evidence: Evidence
    zone: Zone
    label_distance: float


@dataclass(frozen=True, slots=True)
class Evaluated:
    """A candidate after its normalizer and validator have had their say."""

    candidate: Candidate
    value: FieldValue | None
    valid: bool


Normalizer = Callable[[Candidate, Layout], FieldValue | None]
Validator = Callable[[FieldValue, FieldLayout], bool]
Ranker = Callable[[Evaluated, FieldLayout], float]  # lower sorts first


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """One field, declared. The layout says where to look; this says how to read it."""

    name: str
    strategy: Strategy
    normalizer: Normalizer
    validator: Validator
    rankers: tuple[Ranker, ...]
    on_all_invalid: OnAllInvalid
