"""What every check reads, and the verdict every one of them returns.

A check is one question about one document: its values, its rows, the charges its block
declared, the party blocks it printed. Bundling those is what lets the ten invariants of
`docs/ENGINE_SPEC.md` §6 and the seven cross-field checks of §7 share one signature, so
stage 6 runs them in one loop and records a `Check` for every one.

A rule answers with a `Verdict` rather than with a finding, because the two are made from
it together: what failed becomes a `Finding`, and what was asked at all becomes a
`Check` — including the questions this document could not be asked.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from invoice_extractor.domain.checks import Check
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.parties import Party
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge
from invoice_extractor.profile.schema import Profile

ZERO = Decimal(0)
PERCENT = Decimal(100)


@dataclass(frozen=True, slots=True)
class Facts:
    """One document as the checks see it: what was read, and the vendor that printed it."""

    profile: Profile
    fields: Mapping[str, FieldResult]
    items: tuple[LineItem, ...] = ()
    summary: tuple[VatSummaryRow, ...] = ()
    charges: tuple[Charge, ...] = ()
    parties: Mapping[str, Party] = field(default_factory=dict)
    document_type: str | None = None
    source_path: str = ""
    # What stage 5 found the amounts adding up in, where they added up at all.
    currency_basis: str | None = None

    @property
    def tolerance(self) -> Decimal:
        return self.profile.totals.tolerance.absolute

    def amount(self, name: str) -> Decimal | None:
        """One of the document's amounts, where it was read and read as a number."""
        found = self.fields.get(name)
        value = None if found is None else found.value
        return value if isinstance(value, Decimal) else None

    def text(self, name: str) -> str | None:
        found = self.fields.get(name)
        return None if found is None or found.value is None else str(found.value)

    @property
    def declared(self) -> Decimal:
        """What the block charged on top of the net and said so."""
        return sum((charge.amount for charge in self.charges if charge.declared), ZERO)

    @property
    def added(self) -> Decimal:
        """Every charge the document carries, whether a line declared it or not."""
        return sum((charge.amount for charge in self.charges), ZERO)


@dataclass(frozen=True, slots=True)
class Verdict:
    """What one rule found: yes, no, or not a question this document can be asked."""

    passed: bool | None
    fields: tuple[str, ...]
    detail: str
    severity: Severity = Severity.ERROR


Checked = tuple[Finding | None, Check]


def agree(
    names: tuple[str, ...],
    expression: str,
    expected: Decimal,
    found: Decimal,
    tolerance: Decimal,
    severity: Severity = Severity.ERROR,
) -> Verdict:
    """Two sides of one identity, to the tolerance the vendor's own rounding needs."""
    held = abs(expected - found) <= tolerance
    detail = f"{expression} = {expected}"
    if held:
        return Verdict(True, names, detail)
    return Verdict(False, names, f"{detail} but {names[-1]} is {found}", severity)


def missing(names: tuple[str, ...], operand: str) -> Verdict:
    """A question this document cannot be asked, because it does not carry the operand."""
    return Verdict(None, names, f"{operand} was not read")


def holds(names: tuple[str, ...], detail: str) -> Verdict:
    return Verdict(True, names, detail)


def fails(names: tuple[str, ...], detail: str, severity: Severity = Severity.ERROR) -> Verdict:
    return Verdict(False, names, detail, severity)


def rates(summary: Sequence[VatSummaryRow]) -> frozenset[Decimal]:
    """The rates a document's summary says it is charged at."""
    return frozenset(row.rate for row in summary if row.rate is not None)


def summed(values: Sequence[Decimal | None]) -> Decimal | None:
    """What a column comes to, or nothing where a row of it could not be read."""
    if not values or any(value is None for value in values):
        return None
    return sum((value for value in values if value is not None), ZERO)
