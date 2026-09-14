"""Which vendor printed this document — or nobody, which is an answer (ADR-0008).

Every registered profile is scored on four measurable things the document either carries
or does not: the supplier's own name, its VAT id, a currency it trades in, and how much
of its language's label vocabulary appears on the page. The best score above
`PROFILE_THRESHOLD` wins; below it the answer is `None`, and the pipeline reports
`profile_not_detected` rather than extracting with the wrong vocabulary.

A file-path hint may add score. It can promote a profile that was already close — a
deployment that files invoices per vendor knows something — but it cannot carry one over
the threshold on its own, because a file name is not evidence about a document.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from invoice_extractor.document.model import Document
from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.profile.schema import Profile

PROFILE_THRESHOLD = 0.5

# What each part of a score is worth. The two that identify a vendor outright are worth
# more together than everything a document shares with its neighbours in the same
# language, so a German invoice is never mistaken for an Austrian one.
WEIGHTS: Mapping[str, float] = {
    "supplier": 0.30,
    "vat_id": 0.30,
    "labels": 0.30,
    "currency": 0.10,
    "path_hint": 0.05,
}
# The hint's weight is not part of the sum the rest is normalised over: it is a bonus on
# top, and `PROFILE_THRESHOLD` sits above what a hint alone can reach.
SCORED = tuple(name for name in WEIGHTS if name != "path_hint")


@dataclass(frozen=True, slots=True)
class ProfileScore:
    """One profile's score against one document, and what each part of it contributed."""

    profile_id: str
    score: float
    parts: Mapping[str, float]


def detect_profile(
    document: Document, registry: ProfileRegistry, path_hint: str | None = None
) -> tuple[Profile | None, tuple[ProfileScore, ...]]:
    """The best profile above the threshold, or `None`, and every score that was computed."""
    text = _searchable(document)
    hint = _searchable_text(path_hint or "")
    scored = sorted(
        (score_profile(profile, text, hint) for profile in registry.all()),
        key=lambda entry: (-entry.score, entry.profile_id),
    )
    if not scored or scored[0].score < PROFILE_THRESHOLD:
        return None, tuple(scored)
    return registry.get(scored[0].profile_id), tuple(scored)


def score_profile(profile: Profile, text: str, hint: str) -> ProfileScore:
    """How much of this profile the document carries, part by part."""
    parts = {
        "supplier": _supplier(profile, text),
        "vat_id": _contains(text, profile.supplier.vat_id),
        "labels": _labels(profile, text),
        "currency": max(_contains(text, code) for code in profile.currencies),
        "path_hint": _contains(hint, profile.id),
    }
    total = sum(WEIGHTS[name] * parts[name] for name in SCORED)
    return ProfileScore(
        profile_id=profile.id,
        score=round(total + WEIGHTS["path_hint"] * parts["path_hint"], 4),
        parts=parts,
    )


def _supplier(profile: Profile, text: str) -> float:
    """The vendor's own name, or one of the shorter names it also goes by."""
    names = (profile.supplier.name, *profile.supplier.aliases)
    return max(_contains(text, name) for name in names)


def _labels(profile: Profile, text: str) -> float:
    """The share of the fields this profile declares whose label the document prints."""
    declared = tuple(profile.fields.values())
    if not declared:
        return 0.0
    found = sum(1 for field in declared if _any_label(text, field.labels))
    return found / len(declared)


def _any_label(text: str, labels: Sequence[str]) -> bool:
    return any(_contains(text, label) for label in labels)


def _contains(text: str, wanted: str) -> float:
    searched = _searchable_text(wanted)
    return 1.0 if searched and searched in text else 0.0


def _searchable(document: Document) -> str:
    return _searchable_text(" ".join(document.text()))


def _searchable_text(text: str) -> str:
    """Case-folded letters and digits, in any script.

    A label has to match whatever spacing, punctuation and casing it met on the page, and
    the corpus is printed in sixteen languages: `str.isalnum` keeps a Greek alpha and a
    Turkish dotless i, where an ASCII character class would drop a whole page of text and
    score its vendor at zero.
    """
    return "".join(character for character in text.casefold() if character.isalnum())
