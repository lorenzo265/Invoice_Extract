"""What a candidate has to survive before it is ranked.

A strategy reads the whole page, which is what makes it able to find a value wherever a
vendor drew it. A filter is where that generosity is paid for: a candidate introduced by
a label this field is not is dropped before the rankers are asked to choose between it
and a real one.

Only what is *wrong* is filtered. Where a field usually sits is a preference, not a
fence, so it is a ranker (`zone_priority`) rather than a filter: a vendor that moved a
block has not printed a different invoice, and a filter would throw the value away.
"""

from __future__ import annotations

from collections.abc import Sequence

from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.profile.schema import FieldProfile, Profile


def not_a_trap(
    found: Sequence[Candidate], field: FieldProfile, profile: Profile
) -> list[Candidate]:
    """Drop what a trap label introduced: an order date is not the invoice date.

    A trap is a label the vendor prints beside the one this field wants, and the profile
    names them twice over — per field in `exclude_labels`, and once for the whole vendor
    in `noise.ignore_labels`. A label the field itself declares is never a trap for it,
    however many other fields call it one.
    """
    traps = _traps(field, profile)
    if not traps:
        return list(found)
    return [candidate for candidate in found if not _introduced_by(candidate, traps)]


def _traps(field: FieldProfile, profile: Profile) -> frozenset[str]:
    own = {label.casefold() for label in field.labels}
    named = (*field.exclude_labels, *profile.noise.ignore_labels)
    return frozenset(label.casefold() for label in named if label.casefold() not in own)


def _introduced_by(candidate: Candidate, traps: frozenset[str]) -> bool:
    matched = candidate.evidence.matched_label
    if matched is not None and matched.casefold() in traps:
        return True
    text = candidate.evidence.raw_text.strip().casefold()
    return any(text.startswith(trap) for trap in traps)
