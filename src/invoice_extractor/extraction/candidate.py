"""What a strategy found, and what the rest of the engine does to it.

A `Candidate` is a piece of text the engine thinks could be the field, with the evidence
for where it came from. An `Evaluated` is the same candidate after its normalizer and
validator have had their say. Neither is ever published: what leaves the engine is a
`FieldResult`, and only after ranking has decided which candidate won.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from invoice_extractor.document.model import Zone
from invoice_extractor.domain.models import Evidence, FieldValue
from invoice_extractor.profile.schema import FieldProfile, Profile


@dataclass(frozen=True, slots=True)
class Candidate:
    """One piece of text a strategy thinks could be the field, and where it came from.

    `label_distance` is in points, whichever direction the value sits from its label: the
    gap to the right of a label on the same line, or the drop to the line under it. One
    unit for both is what lets a ranker prefer the value nearest its label without
    knowing which strategy found it.
    """

    raw_text: str
    evidence: Evidence
    zone: Zone
    label_distance: float
    match_ratio: float = 1.0


@dataclass(frozen=True, slots=True)
class Evaluated:
    """A candidate after its normalizer and validator have had their say."""

    candidate: Candidate
    value: FieldValue | None
    valid: bool


# What a spec may name, by signature. The vocabulary of names is `units/registry.py`.
Normalizer = Callable[[Candidate, Profile], FieldValue | None]
Validator = Callable[[FieldValue, FieldProfile], bool]
Ranker = Callable[["Evaluated", FieldProfile], float]  # lower sorts first
