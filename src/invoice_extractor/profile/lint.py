"""How ready a profile is, measured against the profiles already shipping.

A new vendor is onboarded by writing a profile, and the question a reviewer has is
whether it is finished. "Finished" is not an opinion here: a profile is compared with the
median of every other profile in the registry, field by field, and reported as one of
three tiers.

| Tier | What it means |
|---|---|
| T0 | a required field declares no label at all — the profile cannot work |
| T1 | every required field has labels, but some have no zone or fewer labels than the median |
| T2 | at or above the median everywhere |

The benchmark is the other half of T2 and is not computed here: this module reads a
profile, not a corpus. `make bench` is what says whether the profile's documents come
back right.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.profile.schema import Profile

TIERS = ("T0", "T1", "T2")


@dataclass(frozen=True, slots=True)
class FieldRow:
    """One field of one profile, against what the other profiles declare for it."""

    name: str
    labels: int
    zones: int
    required: bool
    median_labels: float

    @property
    def below_median(self) -> bool:
        return self.labels < self.median_labels

    @property
    def unusable(self) -> bool:
        return self.required and self.labels == 0

    @property
    def incomplete(self) -> bool:
        return self.zones == 0 or self.below_median


@dataclass(frozen=True, slots=True)
class LintReport:
    """A profile's readiness tier, and the field rows the tier was read off."""

    profile_id: str
    tier: str
    rows: tuple[FieldRow, ...]

    @property
    def unusable(self) -> tuple[FieldRow, ...]:
        return tuple(row for row in self.rows if row.unusable)

    @property
    def incomplete(self) -> tuple[FieldRow, ...]:
        return tuple(row for row in self.rows if row.incomplete and not row.unusable)


def lint(profile: Profile, registry: ProfileRegistry) -> LintReport:
    """Measure one profile against every other profile the registry holds."""
    others = [held for held in registry.all() if held.id != profile.id]
    rows = tuple(_row(profile, name, others) for name in sorted(profile.fields))
    return LintReport(profile_id=profile.id, tier=_tier(rows), rows=rows)


def _row(profile: Profile, name: str, others: Sequence[Profile]) -> FieldRow:
    field = profile.fields[name]
    return FieldRow(
        name=name,
        labels=len(field.labels),
        zones=len(field.zones),
        required=field.required,
        median_labels=_median_labels(name, others),
    )


def _median_labels(name: str, others: Sequence[Profile]) -> float:
    """What the rest of the registry declares for this field. No others, no expectation."""
    counts = [len(held.fields[name].labels) for held in others if name in held.fields]
    return median(counts) if counts else 0.0


def _tier(rows: Sequence[FieldRow]) -> str:
    if any(row.unusable for row in rows):
        return TIERS[0]
    if any(row.incomplete for row in rows):
        return TIERS[1]
    return TIERS[2]


def render(report: LintReport) -> str:
    """The report as the CLI prints it: the tier, then a line per field that falls short."""
    lines = [f"{report.profile_id}: {report.tier}"]
    for row in (*report.unusable, *report.incomplete):
        lines.append(f"  {row.name}: {row.labels} labels, {row.zones} zones{_why(row)}")
    if len(lines) == 1:
        lines.append("  every field at or above the median of the other profiles")
    return "\n".join(lines)


def _why(row: FieldRow) -> str:
    if row.unusable:
        return " — required, and no label declared"
    if row.zones == 0:
        return " — no zone declared"
    return f" — fewer labels than the median of {row.median_labels:g}"
