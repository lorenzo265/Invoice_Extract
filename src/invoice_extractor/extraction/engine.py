"""One runner for every spec kind (ADR-0007).

`run` takes a declaration and a document and returns one `FieldResult`, through the same
internal pipeline whatever the kind is:

    guard -> collect -> filter -> normalize -> validate -> rank -> on_failure -> publish

What differs between kinds is only the collect step and what a published value carries.
Nothing here opens a file, and nothing raises for a document it cannot understand: an
unreadable field comes back with `valid=False`, which is ADR-0005 applied per field.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from invoice_extractor.document.model import Document, TextLine, Zone
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import Evidence, FieldResult, Strategy
from invoice_extractor.extraction.candidate import Candidate, Evaluated
from invoice_extractor.extraction.spec import (
    AnchorSpec,
    Collected,
    DerivedSpec,
    OnFailure,
    Spec,
    strategies_for,
)
from invoice_extractor.extraction.units.derivations import DERIVATIONS
from invoice_extractor.extraction.units.registry import (
    FILTERS,
    NORMALIZERS,
    RANKERS,
    STRATEGIES,
    VALIDATORS,
)
from invoice_extractor.profile.schema import FieldProfile, Profile

# How many points of distance from its label make one candidate a clear winner over the
# next: half an inch, which is wider than the gap between a label and its own value.
GAP_SCALE = 36.0
# What a required field that resolved nothing is reported as (ENGINE_SPEC §3).
FIELD_MISSING = "field_missing"


@dataclass(frozen=True, slots=True)
class Extraction:
    """A field result plus what `scoring/` needs to judge how much to trust it.

    `runner_up_gap` is how clearly the winner won, in points of distance from its label:
    `None` where nothing else was in the running, or where what came second said the same
    thing, because neither of those is a contest that was close.

    `findings` is what the spec's `on_failure` had to say — a required field the vendor
    prints and this document did not yield is a fact about the document, not a silence.
    """

    field: FieldResult
    candidate_count: int
    zone: Zone | None
    runner_up_gap: float | None = None
    findings: tuple[Finding, ...] = ()


def order(specs: Sequence[Spec]) -> tuple[Spec, ...]:
    """The specs in an order where every dependency resolves first. Stable, and a cycle raises."""
    remaining = list(specs)
    ordered: list[Spec] = []
    resolved: set[str] = set()
    while remaining:
        ready = [spec for spec in remaining if set(spec.depends_on) <= resolved]
        if not ready:
            names = ", ".join(sorted(spec.name for spec in remaining))
            raise ValueError(f"specs depend on each other and cannot be ordered: {names}")
        ordered.extend(ready)
        resolved.update(spec.name for spec in ready)
        remaining = [spec for spec in remaining if spec not in ready]
    return tuple(ordered)


def run(
    spec: Spec, document: Document, profile: Profile, resolved: Mapping[str, FieldResult]
) -> Extraction:
    """Run one spec against one document and report a single result for its field."""
    if isinstance(spec, DerivedSpec):
        return _derived(spec, document, profile, resolved)
    described = _field_profile(spec, profile)
    if described is None:
        return Extraction(_not_found(spec.name), 0, None)
    candidates = _filtered(_collect(spec, document, described, profile), spec, described, profile)
    evaluated = [_evaluate(spec, candidate, profile, described) for candidate in candidates]
    ordered = _ranked(evaluated, spec, described)
    winner = _winner(ordered, spec)
    if winner is None:
        return Extraction(
            _not_found(spec.name), len(candidates), None, findings=_missing(spec, described)
        )
    return Extraction(
        field=_result(spec.name, winner),
        candidate_count=len(candidates),
        zone=winner.candidate.zone,
        runner_up_gap=_gap(ordered, winner),
    )


def _gap(ordered: Sequence[Evaluated], winner: Evaluated) -> float | None:
    """How far behind the nearest candidate saying something else was, at most a full gap."""
    others = [item for item in ordered if item.value != winner.value]
    if not others:
        return None
    apart = others[0].candidate.label_distance - winner.candidate.label_distance
    return min(max(apart, 0.0) / GAP_SCALE, 1.0)


def _field_profile(spec: Collected, profile: Profile) -> FieldProfile | None:
    """What the vendor says about this field, or nothing where it does not print it."""
    if isinstance(spec, AnchorSpec):
        return _anchor_field(profile)
    if spec.source == "custom_fields":
        declared = {custom.name: custom.field for custom in profile.custom_fields}
        return declared.get(spec.name)
    return profile.fields.get(spec.name)


def _anchor_field(profile: Profile) -> FieldProfile:
    """An anchor has no labels; it borrows the supplier's zones so ranking has a preference."""
    return FieldProfile(
        labels=(),
        zones=profile.fields["supplier_vat_id"].zones,
        placement=profile.fields["supplier_vat_id"].placement,
        pattern=None,
        required=True,
        exclude_labels=(),
    )


def _collect(
    spec: Collected, document: Document, described: FieldProfile, profile: Profile
) -> list[Candidate]:
    """Every way the field may be printed, pooled — the rankers decide which one won."""
    return [
        candidate
        for name in strategies_for(spec, described)
        for candidate in STRATEGIES[name](document.lines, _terms(name, spec, described, profile))
    ]


def _terms(
    name: str, spec: Collected, described: FieldProfile, profile: Profile
) -> tuple[str, ...]:
    """What this strategy looks for: expected values, a declared pattern, or the labels."""
    if isinstance(spec, AnchorSpec):
        return _expected(spec.expected, profile)
    if name == "label_pattern" and described.pattern is not None:
        return (described.pattern.pattern,)
    return described.labels


def _expected(named: str, profile: Profile) -> tuple[str, ...]:
    """The values a profile already knows, by the name an `AnchorSpec` asked for.

    A vendor's name is asked for with the names it also trades under: a document that
    prints an alias is the same vendor printing itself differently.
    """
    supplier = profile.supplier
    if named == "supplier.name":
        return (supplier.name, *supplier.aliases)
    return (supplier.vat_id,)


def _filtered(
    found: Sequence[Candidate], spec: Collected, described: FieldProfile, profile: Profile
) -> list[Candidate]:
    kept = list(found)
    for name in spec.filters:
        kept = FILTERS[name](kept, described, profile)
    return kept


def _evaluate(
    spec: Collected, candidate: Candidate, profile: Profile, described: FieldProfile
) -> Evaluated:
    value = NORMALIZERS[spec.normalizer](candidate, profile)
    valid = value is not None and VALIDATORS[spec.validator](value, described)
    return Evaluated(candidate=candidate, value=value, valid=valid)


def _ranked(
    evaluated: Sequence[Evaluated], spec: Collected, described: FieldProfile
) -> list[Evaluated]:
    """Sorted by every ranker in the spec's order — the first one that differs decides."""

    def key(item: Evaluated) -> tuple[float, ...]:
        return tuple(RANKERS[name](item, described) for name in spec.rankers)

    return sorted(evaluated, key=key)


def _winner(ordered: Sequence[Evaluated], spec: Collected) -> Evaluated | None:
    """The best valid candidate, or the best invalid one when the spec asks for it."""
    valid = next((item for item in ordered if item.valid), None)
    if valid is not None:
        return valid
    if spec.on_failure is OnFailure.BEST_INVALID and ordered:
        return ordered[0]
    return None


def _missing(spec: Spec, described: FieldProfile) -> tuple[Finding, ...]:
    """`on_failure = not_found` on a field the vendor says it prints (ENGINE_SPEC §3).

    A field the profile marks optional is one this vendor prints only sometimes, and a
    document that leaves it out is not disagreeing with anything. A required one is the
    vendor's own claim that every invoice carries it, so a document without it is a fact
    worth reporting even though nothing about the arithmetic is wrong.
    """
    if spec.on_failure is not OnFailure.NOT_FOUND or not described.required:
        return ()
    return (
        Finding(
            severity=Severity.WARNING,
            code=FIELD_MISSING,
            message=f"{spec.name} is required by this profile and no value was read",
            field=spec.name,
        ),
    )


def _derived(
    spec: DerivedSpec, document: Document, profile: Profile, resolved: Mapping[str, FieldResult]
) -> Extraction:
    """A value computed rather than read, pointing at the line it was computed from."""
    derived = DERIVATIONS[spec.derive](document, profile, resolved)
    if derived is None:
        # A derivation that came to nothing is as much a missing required field as a
        # label nothing matched: a document priced in a currency its vendor's profile
        # does not list leaves `currency` unresolved, and saying so is the point.
        described = profile.fields.get(spec.name)
        missing = () if described is None else _missing(spec, described)
        return Extraction(_not_found(spec.name), 0, None, findings=missing)
    field = FieldResult(
        name=spec.name,
        value=derived.value,
        raw_text=str(derived.value),
        evidence=_derived_evidence(derived.line),
        valid=True,
    )
    return Extraction(field, 1, derived.line.zone)


def _derived_evidence(line: TextLine) -> Evidence:
    """A derived value is still a value read off a document (ADR-0002): this is where."""
    return Evidence(
        page=line.page,
        bbox=line.bbox,
        matched_label=None,
        strategy=Strategy.DERIVED,
        raw_text=line.text,
    )


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
