"""How much the pipeline trusts a field, as a weighted sum of named signals.

Nothing here re-reads the document. Every signal is a question about what extraction
already recorded — the evidence, the winning line's zone, how many candidates there were
— so a reader can see why a number scored what it did without re-running anything.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence

from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.extraction.engine import Extraction
from invoice_extractor.profile.schema import FieldProfile

SIGNAL_WEIGHTS: Mapping[str, float] = {
    "label_exact_match": 0.25,
    "in_expected_zone": 0.15,
    "validator_passed": 0.30,
    "single_candidate": 0.10,
    "invariants_agree": 0.20,
}
PRECISION = 2
# What a field is worth when nothing caps it: everything its signals came to.
NO_CAP = 1.0


def score(
    extraction: Extraction,
    field_profile: FieldProfile | None,
    findings: Sequence[Finding],
    cap: float = NO_CAP,
) -> FieldResult:
    """The field again, with its confidence and what each signal contributed to it.

    `cap` is what stage 5 found the document disagreeing with itself about, applied here
    and nowhere else (`docs/ENGINE_SPEC.md` §2): a value the VAT summary contradicts is
    still the value the block printed, and the signals that lit are still the signals
    that lit — what changes is how far any of that is worth trusting.
    """
    field = extraction.field
    if field.value is None:
        return dataclasses.replace(field, confidence=0.0, confidence_breakdown=_nothing_lit())
    lit = _signals(extraction, field_profile, findings)
    breakdown = {
        signal: weight if lit[signal] else 0.0 for signal, weight in SIGNAL_WEIGHTS.items()
    }
    total = round(min(sum(breakdown.values()), cap), PRECISION)
    return dataclasses.replace(field, confidence=total, confidence_breakdown=breakdown)


def _signals(
    extraction: Extraction, field_profile: FieldProfile | None, findings: Sequence[Finding]
) -> Mapping[str, bool]:
    field = extraction.field
    evidence = field.evidence
    return {
        "label_exact_match": evidence is not None and evidence.matched_label is not None,
        # The engine already stored the winning line's zone; never recompute one here.
        "in_expected_zone": field_profile is not None and extraction.zone in field_profile.zones,
        "validator_passed": field.valid,
        "single_candidate": extraction.candidate_count == 1,
        "invariants_agree": not _contradicted(findings, field.name),
    }


def _contradicted(findings: Sequence[Finding], name: str) -> bool:
    return any(finding.severity is Severity.ERROR and finding.field == name for finding in findings)


def _nothing_lit() -> dict[str, float]:
    return dict.fromkeys(SIGNAL_WEIGHTS, 0.0)
