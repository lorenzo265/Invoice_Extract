"""The sixteen named measurements a field's confidence is made of (ENGINE_SPEC §8).

Nothing here re-reads the document. Every signal is a question about what extraction,
reconciliation and validation already recorded — the evidence, the zone the winning line
sat in, how many candidates there were, which rules named this field and whether they
held — so a reader can see why a number scored what it did without re-running anything.

A signal a field cannot be asked is *absent* rather than zero, and an absent signal is
excluded from the weighting rather than counted against the value: a block row has no
label to match, and holding that against it would score every totals field down for a
question the page never asked.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from invoice_extractor.domain.checks import Check
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.parties import Party
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.extraction.engine import Extraction
from invoice_extractor.profile.schema import FieldProfile, Profile
from invoice_extractor.validation.cross_field import CHECK_NAMES
from invoice_extractor.validation.invariants import INVARIANT_NAMES

# The sixteen, in the order a report prints them.
SIGNAL_NAMES: tuple[str, ...] = (
    "label_found",
    "label_similarity",
    "value_format_match",
    "format_pattern_match",
    "format_canonical_distance",
    "zone_match",
    "arithmetic_consistency",
    "invariant_corroboration",
    "competing_candidates",
    "runner_up_gap",
    "cross_field_consistency",
    "profile_match",
    "length_plausible",
    "structural_completeness",
    "count_plausibility",
    "min_component_strength",
)
NOT_ALNUM = re.compile(r"[^A-Za-z0-9]")
YES, NO = 1.0, 0.0


@dataclass(frozen=True, slots=True)
class ScoringContext:
    """One document, as the signals ask about it, gathered once and read many times."""

    profile: Profile
    resolved: Mapping[str, FieldResult]
    checks: tuple[Check, ...] = ()
    profile_score: float = 0.0
    items: tuple[LineItem, ...] = ()
    summary: tuple[VatSummaryRow, ...] = ()
    parties: Mapping[str, Party] = field(default_factory=dict)

    def described(self, name: str) -> FieldProfile | None:
        declared = {custom.name: custom.field for custom in self.profile.custom_fields}
        return self.profile.fields.get(name) or declared.get(name)


def extract_signals(extraction: Extraction, context: ScoringContext) -> dict[str, float]:
    """Every signal this field can be asked, by name. A field with no value has none."""
    found = extraction.field
    if found.value is None:
        return {}
    signals = {
        **_from_the_page(extraction, context),
        **_from_the_rules(found.name, context),
        **_from_the_document(context),
    }
    return {**signals, "min_component_strength": min(signals.values(), default=NO)}


def _from_the_page(extraction: Extraction, context: ScoringContext) -> dict[str, float]:
    """What reading it was like: the label, the shape, the zone, the competition."""
    found = extraction.field
    described = context.described(found.name)
    evidence = found.evidence
    label = None if evidence is None else evidence.matched_label
    signals: dict[str, float] = {
        "label_found": YES if label is not None else NO,
        "value_format_match": YES if found.valid else NO,
    }
    _put(signals, "label_similarity", _similarity(label, described))
    _put(signals, "format_pattern_match", _pattern(found, described))
    _put(signals, "format_canonical_distance", _canonical_distance(found))
    _put(signals, "zone_match", _zone(extraction, described))
    _put(signals, "competing_candidates", _competing(extraction))
    _put(signals, "runner_up_gap", extraction.runner_up_gap)
    _put(signals, "length_plausible", _length(found))
    return signals


def _from_the_rules(name: str, context: ScoringContext) -> dict[str, float]:
    """What the document's own rules said about this field, where any of them named it."""
    applied = [check for check in context.checks if check.applied and name in check.fields]
    arithmetic = [check for check in applied if check.code in INVARIANT_NAMES]
    across = [check for check in applied if check.code in CHECK_NAMES]
    signals: dict[str, float] = {}
    _put(signals, "arithmetic_consistency", _all_passed(arithmetic))
    _put(signals, "cross_field_consistency", _all_passed(across))
    _put(signals, "invariant_corroboration", _corroboration(arithmetic))
    return signals


def _from_the_document(context: ScoringContext) -> dict[str, float]:
    """What kind of read this was at all: the vendor, the fields, the structures."""
    return {
        "profile_match": _clamped(context.profile_score),
        "structural_completeness": _completeness(context),
        "count_plausibility": _counts(context),
    }


def _put(signals: dict[str, float], name: str, value: float | None) -> None:
    """A signal this field cannot be asked is left out, not written down as a zero."""
    if value is not None:
        signals[name] = _clamped(value)


def _similarity(label: str | None, described: FieldProfile | None) -> float | None:
    """How much of the label the page printed is the label the profile declares."""
    if label is None or described is None or not described.labels:
        return None
    folded = label.casefold()
    return max(SequenceMatcher(None, folded, one.casefold()).ratio() for one in described.labels)


def _pattern(found: FieldResult, described: FieldProfile | None) -> float | None:
    if described is None or described.pattern is None:
        return None
    return YES if described.pattern.fullmatch(str(found.value)) else NO


def _canonical_distance(found: FieldResult) -> float | None:
    """How near what was read is to what it was read from, letters and digits only."""
    if found.raw_text is None:
        return None
    read, printed = _canonical(str(found.value)), _canonical(found.raw_text)
    if not printed:
        return None
    return SequenceMatcher(None, read, printed).ratio()


def _zone(extraction: Extraction, described: FieldProfile | None) -> float | None:
    if described is None or not described.zones or extraction.zone is None:
        return None
    return YES if extraction.zone in described.zones else NO


def _competing(extraction: Extraction) -> float | None:
    """One candidate is certainty about where it came from; ten is a choice between ten."""
    if extraction.candidate_count < 1:
        return None
    return 1.0 / extraction.candidate_count


def _length(found: FieldResult) -> float | None:
    """A value is most of what was read; one read out of a sentence is a small part of it."""
    if found.raw_text is None:
        return None
    read, printed = _canonical(str(found.value)), _canonical(found.raw_text)
    return None if not printed else min(len(read) / len(printed), 1.0)


def _all_passed(checks: Sequence[Check]) -> float | None:
    if not checks:
        return None
    return YES if all(check.passed for check in checks) else NO


def _corroboration(checks: Sequence[Check]) -> float | None:
    """A value three identities agree on is worth more than one nothing checks at all."""
    if not checks:
        return None
    return len(checks) / (len(checks) + 1)


def _completeness(context: ScoringContext) -> float:
    """How much of what this vendor says it prints was read off this document."""
    required = [name for name, described in context.profile.fields.items() if described.required]
    if not required:
        return YES
    read = [name for name in required if _has_value(context.resolved.get(name))]
    return len(read) / len(required)


def _counts(context: ScoringContext) -> float:
    """Whether the document's structures came back at all, as a share of the ones expected."""
    expected = [True, context.profile.vat_summary is not None, bool(context.profile.parties)]
    found = [bool(context.items), bool(context.summary), bool(context.parties)]
    wanted = [index for index, one in enumerate(expected) if one]
    return YES if not wanted else sum(found[index] for index in wanted) / len(wanted)


def _has_value(found: FieldResult | None) -> bool:
    return found is not None and found.value is not None


def _canonical(text: str) -> str:
    return NOT_ALNUM.sub("", text).upper()


def _clamped(value: float) -> float:
    return min(max(value, NO), YES)
