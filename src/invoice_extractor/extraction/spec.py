"""What a field is: a declaration naming registered units, never values (ADR-0001, 0007).

Six kinds, one engine behind all of them:

| Kind | Where the value comes from |
|---|---|
| `LabelSpec` | the text beside, under or matching a label the profile declares |
| `AnchorSpec` | a value the profile already expects, found on the page |
| `DerivedSpec` | a pure function over fields that are already resolved |
| `SectionSpec` | the block a heading opens, down the column it was set in |
| `TableSpec` | the rows under a header, cell by cell |
| `BlockSpec` | the column of rows a document adds up in, read as one block |

A spec holds names, not functions: `units/registry.py` is the vocabulary, and `validate`
refuses a spec that names a unit, a source or a dependency that does not exist. That
check runs when `extraction/specs.py` is imported, so a typo is an import error rather
than a field that silently never resolves.
"""

from __future__ import annotations

from collections.abc import Container, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto

from invoice_extractor.domain.parties import PARTY_NAMES
from invoice_extractor.domain.rows import LINE_ITEM_COLUMNS, VAT_SUMMARY_COLUMNS
from invoice_extractor.extraction.units.registry import (
    FILTERS,
    LABEL_STRATEGIES,
    NORMALIZERS,
    RANKERS,
    VALIDATORS,
)
from invoice_extractor.profile.schema import REQUIRED_COMPONENTS

# What a profile may be asked for by name: the values it already knows about its vendor.
EXPECTED_VALUES: tuple[str, ...] = ("supplier.name", "supplier.vat_id")
# Where a `LabelSpec` finds the field profile it reads: the catalog's fields, or the
# vendor's own declared extras.
SOURCES: tuple[str, ...] = ("fields", "custom_fields")
# The tables a profile describes, and the party blocks. A `TableSpec` or a `SectionSpec`
# names one of these, and `validate` refuses a spec that names anything else.
TABLE_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "line_items": LINE_ITEM_COLUMNS,
    "vat_summary": VAT_SUMMARY_COLUMNS,
}
SECTION_SOURCES: tuple[str, ...] = PARTY_NAMES
# What a totals block may publish as a field of its own. Everything else it names is a
# charge, and a charge is a row of the block rather than a field of the catalog.
BLOCK_COMPONENTS: tuple[str, ...] = (*REQUIRED_COMPONENTS, "vat_rate")


class SpecKind(Enum):
    """The ways a value is collected: by label, by expectation, by derivation, or by
    reading a part of the document — a party block, a table, the totals block."""

    LABEL = auto()
    ANCHOR = auto()
    DERIVED = auto()
    SECTION = auto()
    TABLE = auto()
    BLOCK = auto()


class OnFailure(Enum):
    """What to report when no candidate survived, or every one of them failed."""

    NOT_FOUND = auto()
    BEST_INVALID = auto()


@dataclass(frozen=True, slots=True)
class LabelSpec:
    """One labelled field: what its text means, how it is judged, how a tie is broken."""

    name: str
    normalizer: str
    validator: str
    rankers: tuple[str, ...]
    filters: tuple[str, ...] = ("not_a_trap",)
    on_failure: OnFailure = OnFailure.NOT_FOUND
    source: str = "fields"
    depends_on: tuple[str, ...] = ()
    kind: SpecKind = field(default=SpecKind.LABEL, init=False)


@dataclass(frozen=True, slots=True)
class AnchorSpec:
    """A value the profile already knows, looked for on the page rather than searched for."""

    name: str
    expected: str
    normalizer: str
    validator: str
    rankers: tuple[str, ...] = ("valid_first", "best_match", "top_most")
    filters: tuple[str, ...] = ()
    on_failure: OnFailure = OnFailure.NOT_FOUND
    depends_on: tuple[str, ...] = ()
    kind: SpecKind = field(default=SpecKind.ANCHOR, init=False)


@dataclass(frozen=True, slots=True)
class DerivedSpec:
    """A value no line carries, computed from fields that have already resolved."""

    name: str
    derive: str
    depends_on: tuple[str, ...] = ()
    on_failure: OnFailure = OnFailure.NOT_FOUND
    kind: SpecKind = field(default=SpecKind.DERIVED, init=False)


@dataclass(frozen=True, slots=True)
class SectionSpec:
    """One party block: which of the profile's sections describes it."""

    name: str
    source: str
    kind: SpecKind = field(default=SpecKind.SECTION, init=False)


@dataclass(frozen=True, slots=True)
class TableSpec:
    """One table: which of the profile's tables describes it, and what a row must carry.

    `required_columns` is what makes a printed row a row of this table rather than a
    heading, a section subtotal or the line a page break carried: a row of line items has
    something charged and what it was charged for, a VAT line has a rate and a tax.
    """

    name: str
    source: str
    required_columns: tuple[str, ...]
    columns: tuple[str, ...]
    kind: SpecKind = field(default=SpecKind.TABLE, init=False)


@dataclass(frozen=True, slots=True)
class BlockSpec:
    """The totals block: which of the components a profile names are fields of their own.

    A block publishes more than fields — the charges it declares and the currency it
    echoes the total in — but only these have a name in the catalog, and only these are
    scored like any other field.
    """

    name: str
    fields: tuple[str, ...]
    kind: SpecKind = field(default=SpecKind.BLOCK, init=False)


# A spec whose value is collected off the page, as against one computed from others.
Collected = LabelSpec | AnchorSpec
Spec = LabelSpec | AnchorSpec | DerivedSpec
# A spec that publishes a part of a document rather than one value.
Structure = SectionSpec | TableSpec | BlockSpec


class SpecError(ValueError):
    """A spec that names something that does not exist. Raised while specs are imported."""


def validate(specs: Sequence[Spec], derivations: Mapping[str, object]) -> None:
    """Every name every spec uses is a name something registered. Raises `SpecError`."""
    for spec in specs:
        _validate_one(spec, derivations)
    _names_are_unique(specs)
    _dependencies_resolve(specs)


def validate_structures(structures: Sequence[Structure]) -> None:
    """Every block and table names a part of a profile, and a table names real columns."""
    for structure in structures:
        if isinstance(structure, SectionSpec):
            _known(structure.name, "section", structure.source, SECTION_SOURCES)
        elif isinstance(structure, BlockSpec):
            for component in structure.fields:
                _known(structure.name, "component", component, BLOCK_COMPONENTS)
        else:
            _table(structure)


def _table(structure: TableSpec) -> None:
    _known(structure.name, "table", structure.source, TABLE_COLUMNS)
    known = TABLE_COLUMNS[structure.source]
    for column in (*structure.columns, *structure.required_columns):
        _known(structure.name, "column", column, known)


def strategies_for(spec: Collected, declares_a_pattern: bool) -> tuple[str, ...]:
    """The collect units this spec's kind runs, in the order their candidates are pooled.

    `label_pattern` runs only for a field whose profile declares one: a label is not a
    regular expression, and compiling one as if it were finds the label itself.
    """
    if isinstance(spec, AnchorSpec):
        return ("anchor_value",)
    return (*LABEL_STRATEGIES, *(("label_pattern",) if declares_a_pattern else ()))


def _validate_one(spec: Spec, derivations: Mapping[str, object]) -> None:
    if isinstance(spec, DerivedSpec):
        _known(spec.name, "derivation", spec.derive, derivations)
        return
    _known(spec.name, "normalizer", spec.normalizer, NORMALIZERS)
    _known(spec.name, "validator", spec.validator, VALIDATORS)
    for ranker in spec.rankers:
        _known(spec.name, "ranker", ranker, RANKERS)
    for unit in spec.filters:
        _known(spec.name, "filter", unit, FILTERS)
    if isinstance(spec, AnchorSpec):
        _known(spec.name, "expected value", spec.expected, EXPECTED_VALUES)
    else:
        _known(spec.name, "source", spec.source, SOURCES)


def _known(spec_name: str, what: str, named: str, registered: Container[str]) -> None:
    """A registry is asked by name, whether it is a mapping of units or a tuple of values."""
    if named not in registered:
        raise SpecError(f"{spec_name} names {what} {named!r}, which is not registered")


def _names_are_unique(specs: Sequence[Spec]) -> None:
    seen: set[str] = set()
    for spec in specs:
        if spec.name in seen:
            raise SpecError(f"{spec.name} is declared twice")
        seen.add(spec.name)


def _dependencies_resolve(specs: Sequence[Spec]) -> None:
    declared = {spec.name for spec in specs}
    for spec in specs:
        for wanted in spec.depends_on:
            if wanted not in declared:
                raise SpecError(f"{spec.name} depends on {wanted!r}, which no spec resolves")
