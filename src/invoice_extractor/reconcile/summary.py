"""Stage 5, second half: does the block agree with the summary, and what taxes what.

A document states its tax twice — once in the totals block and once, per rate, in the VAT
summary — and an invoice that is right says the same thing both times. Where the two
disagree, nothing here picks a winner: it says so, and caps how much either is trusted
(`docs/ENGINE_SPEC.md` §5).

Linking is the other half: every line item and every declared charge is taxed by one line
of the summary, and knowing which is what lets validation check a rate per row rather
than per document. A row whose rate matches two summary lines is linked to neither.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge
from invoice_extractor.profile.schema import Profile

# What a field is worth once the document contradicts itself about it: half, at most.
DISAGREEMENT_CAP = 0.5
DISAGREE = "totals_summary_disagree"
AMBIGUOUS = "vat_line_ambiguous"
ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Crossed:
    """The three questions the summary answers about the block, and what they cost."""

    vat_agrees: bool
    base_agrees: bool
    closes: bool
    caps: Mapping[str, float]
    findings: tuple[Finding, ...] = ()

    @property
    def agrees(self) -> bool:
        return self.vat_agrees and self.base_agrees and self.closes


@dataclass(frozen=True, slots=True)
class Linked:
    """Which line of the VAT summary taxes each row, by position; `None` where unknown."""

    items: tuple[int | None, ...]
    charges: tuple[int | None, ...]
    findings: tuple[Finding, ...] = ()


def cross_check_totals_vs_summary(
    fields: Mapping[str, FieldResult],
    charges: Sequence[Charge],
    summary: Sequence[VatSummaryRow],
    profile: Profile,
) -> Crossed:
    """Three comparisons: the tax, what it was charged on, and whether the summary closes.

    What the summary is charged on is the net plus the charges the block declared, because
    a vendor that bills for delivery taxes the delivery: the base is what was taxed, not
    what was sold. A document that prints no summary is not disagreeing with one, so all
    three hold and nothing is capped; so does each comparison a vendor leaves the column
    out of.
    """
    tolerance = profile.totals.tolerance.absolute
    taxed = _taxable(fields, charges)
    vat = _agrees(_summed(summary, "vat"), _amount(fields, "vat_amount"), tolerance)
    base = _agrees(_summed(summary, "base"), taxed, tolerance)
    closes = _closes(summary, tolerance)
    disputed = _disputed(vat, base, closes)
    return Crossed(
        vat_agrees=vat,
        base_agrees=base,
        closes=closes,
        caps=dict.fromkeys(disputed, DISAGREEMENT_CAP),
        findings=_disagreements(vat, base, closes),
    )


def link_items_to_vat_lines(
    items: Sequence[LineItem], charges: Sequence[Charge], summary: Sequence[VatSummaryRow]
) -> Linked:
    """The summary line that taxes each item and each declared charge, where one does.

    A row says which by the rate it is charged at. Where it prints no rate and the
    document is at one, that one taxes everything; where it prints none and the document
    is at several, which one taxes this row is not written down and is not guessed at.
    """
    found = [_line_for(item.vat_rate, summary) for item in items]
    for_charges = [_line_for(charge.vat_rate, summary) for charge in charges]
    ambiguous = sum(1 for link in (*found, *for_charges) if link == _AMBIGUOUS)
    return Linked(
        items=tuple(_resolved(link) for link in found),
        charges=tuple(_resolved(link) for link in for_charges),
        findings=(_ambiguous(ambiguous),) if ambiguous else (),
    )


# A row that matches more than one summary line, told apart from one that matches none.
_AMBIGUOUS = -1


def _line_for(rate: Decimal | None, summary: Sequence[VatSummaryRow]) -> int | None:
    if not summary:
        return None
    if rate is None:
        return 0 if len(summary) == 1 else None
    matched = [index for index, row in enumerate(summary) if row.rate == rate]
    if len(matched) == 1:
        return matched[0]
    return _AMBIGUOUS if len(matched) > 1 else None


def _resolved(link: int | None) -> int | None:
    return None if link == _AMBIGUOUS else link


def _taxable(fields: Mapping[str, FieldResult], charges: Sequence[Charge]) -> Decimal | None:
    """What the summary is charged on: the net and every charge a line of the block named."""
    net = _amount(fields, "subtotal")
    if net is None:
        return None
    return net + sum((charge.amount for charge in charges if charge.declared), ZERO)


def _summed(summary: Sequence[VatSummaryRow], column: str) -> Decimal | None:
    """What the summary's column comes to, where any line of it prints that column."""
    printed = [getattr(row, column) for row in summary]
    found = [value for value in printed if isinstance(value, Decimal)]
    return sum(found, ZERO) if found else None


def _closes(summary: Sequence[VatSummaryRow], tolerance: Decimal) -> bool:
    """Every line of the summary taxes its own base at its own rate, or it does not close."""
    return all(_line_closes(row, tolerance) for row in summary)


def _line_closes(row: VatSummaryRow, tolerance: Decimal) -> bool:
    if row.rate is None or row.base is None or row.vat is None:
        return True
    expected = row.base * row.rate / _PER_CENT
    return abs(expected - row.vat) <= tolerance


# A summary prints its rates as percentages, the way the page does.
_PER_CENT = Decimal(100)


def _agrees(summed: Decimal | None, stated: Decimal | None, tolerance: Decimal) -> bool:
    """Two numbers agree when both were read and they are within tolerance, or one was not."""
    if summed is None or stated is None:
        return True
    return abs(summed - stated) <= tolerance


def _amount(fields: Mapping[str, FieldResult], name: str) -> Decimal | None:
    found = fields.get(name)
    return found.value if found is not None and isinstance(found.value, Decimal) else None


def _disputed(vat: bool, base: bool, closes: bool) -> tuple[str, ...]:
    """The fields a disagreement is about: the one that disagrees, and the summary's own."""
    disputed: list[str] = []
    if not vat:
        disputed.append("vat_amount")
    if not base:
        disputed.append("subtotal")
    if not closes:
        disputed.append("vat_rate")
    return tuple(disputed)


def _disagreements(vat: bool, base: bool, closes: bool) -> tuple[Finding, ...]:
    said = {
        "vat_amount": (vat, "the VAT summary does not add up to the tax the block states"),
        "subtotal": (base, "the VAT summary does not add up to what the block says was taxed"),
        "vat_rate": (closes, "a line of the VAT summary does not tax its base at its rate"),
    }
    return tuple(
        Finding(severity=Severity.WARNING, code=DISAGREE, message=message, field=name)
        for name, (held, message) in said.items()
        if not held
    )


def _ambiguous(count: int) -> Finding:
    return Finding(
        severity=Severity.WARNING,
        code=AMBIGUOUS,
        message=f"{count} row(s) match more than one line of the VAT summary; none is linked",
    )
