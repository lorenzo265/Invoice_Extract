"""Does the invoice's own arithmetic add up? The ten rules of `docs/ENGINE_SPEC.md` §6.

Each is a question with three answers: it held, it did not, or this document cannot be
asked it — a rate no single-rate document has, a summary this vendor does not print, a
row whose amount nobody could read. None of them raises: a supplier's rounding mistake
describes the document, it is not a defect in this program (ADR-0005).

They are written in the vendor's own units. The tolerance is the profile's, the rates
are percentages because that is how a page prints them, and what is taxed is the net
plus whatever the block declared on top of it.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from invoice_extractor.domain.findings import Severity
from invoice_extractor.domain.money import quantize_cents
from invoice_extractor.validation.facts import (
    PERCENT,
    ZERO,
    Facts,
    Verdict,
    agree,
    fails,
    holds,
    missing,
    rates,
    summed,
)

Invariant = Callable[[Facts], Verdict]
CREDIT_NOTE = "credit_note"


def subtotal_plus_vat_equals_total(facts: Facts) -> Verdict:
    """The net, what was added to it and the tax should be what the invoice asks for."""
    names = ("subtotal", "vat_amount", "total_amount")
    net, tax, total = (facts.amount(name) for name in names)
    if net is None or tax is None or total is None:
        return missing(names, _first_missing(facts, names))
    terms = [str(part) for part in (net, *_charges(facts), tax)]
    return agree(names, " + ".join(terms), net + facts.added + tax, total, facts.tolerance)


def line_items_sum_equals_subtotal(facts: Facts) -> Verdict:
    """The rows of the table should add up to the net printed under them."""
    names = ("line_items", "subtotal")
    net = facts.amount("subtotal")
    rows = summed([item.net_amount for item in facts.items])
    if net is None:
        return missing(names, "subtotal")
    if rows is None:
        return missing(names, "line_items")
    return agree(names, f"{rows} (rows)", rows, net, facts.tolerance)


def line_items_sum_equals_total_when_no_vat(facts: Facts) -> Verdict:
    """Where nothing was taxed, what was sold and what is owed are the same amount."""
    names = ("line_items", "total_amount")
    tax, total = facts.amount("vat_amount"), facts.amount("total_amount")
    rows = summed([item.net_amount for item in facts.items])
    if tax is None:
        return missing(names, "vat_amount")
    if tax != ZERO:
        return Verdict(None, names, "the document charges tax")
    if total is None or rows is None:
        return missing(names, "total_amount" if total is None else "line_items")
    expression = f"{rows} (rows) + {facts.added}"
    return agree(names, expression, rows + facts.added, total, facts.tolerance)


def vat_equals_subtotal_times_rate(facts: Facts) -> Verdict:
    """The tax should be the printed rate applied to what was taxed, to the cent.

    Only a document at one rate has one rate to multiply by; a summary with several lines
    says this one is not that document.
    """
    names = ("vat_rate", "vat_amount")
    if len(rates(facts.summary)) > 1:
        return Verdict(None, names, "the document is charged at more than one rate")
    rate, tax = facts.amount("vat_rate"), facts.amount("vat_amount")
    net = facts.amount("subtotal")
    if rate is None or tax is None or net is None:
        return missing(names, _first_missing(facts, ("vat_rate", "vat_amount", "subtotal")))
    taxed = net + facts.declared
    expected = quantize_cents(taxed * rate / PERCENT)
    return agree(names, f"{rate}% x {taxed}", expected, tax, facts.tolerance)


def per_rate_vat_consistency(facts: Facts) -> Verdict:
    """Every line of the summary should tax its own base at its own rate."""
    names = ("vat_summary",)
    lines = [row for row in facts.summary if _complete(row.rate, row.base, row.vat)]
    if not lines:
        return Verdict(None, names, "no line of a summary states a rate, a base and a tax")
    wrong = [row for row in lines if not _taxes_its_base(row.rate, row.base, row.vat, facts)]
    if not wrong:
        return holds(names, f"{len(lines)} line(s) tax their base at their rate")
    first = wrong[0]
    return fails(names, f"{first.rate}% x {first.base} is not {first.vat}")


def summary_base_sums_equal_subtotal(facts: Facts) -> Verdict:
    """What the summary says was taxed should be the net plus what the block declared."""
    names = ("vat_summary", "subtotal")
    net = facts.amount("subtotal")
    bases = summed([row.base for row in facts.summary])
    if net is None or bases is None:
        return missing(names, "subtotal" if net is None else "vat_summary")
    return agree(names, f"{bases} (bases)", bases, net + facts.declared, facts.tolerance)


def summary_vat_sums_equal_vat_total(facts: Facts) -> Verdict:
    """What the summary charges per rate should come to the tax the block states."""
    names = ("vat_summary", "vat_amount")
    tax = facts.amount("vat_amount")
    taxed = summed([row.vat for row in facts.summary])
    if tax is None or taxed is None:
        return missing(names, "vat_amount" if tax is None else "vat_summary")
    return agree(names, f"{taxed} (summary)", taxed, tax, facts.tolerance)


def line_totals_plus_charges_equal_grand_total(facts: Facts) -> Verdict:
    """The rows, the charges and the tax together should be what is owed."""
    names = ("line_items", "total_amount")
    tax, total = facts.amount("vat_amount"), facts.amount("total_amount")
    rows = summed([item.net_amount for item in facts.items])
    if rows is None or tax is None or total is None:
        return missing(names, "line_items" if rows is None else _first_missing(facts, names[1:]))
    expression = " + ".join(str(part) for part in (rows, *_charges(facts), tax))
    return agree(names, expression, rows + facts.added + tax, total, facts.tolerance)


def line_items_vat_sum_equals_vat_total(facts: Facts) -> Verdict:
    """Each row taxed at its own rate should come to the tax the document states."""
    names = ("line_items", "vat_amount")
    tax = facts.amount("vat_amount")
    rows = summed([_taxed(item.net_amount, item.vat_rate) for item in facts.items])
    if tax is None or rows is None:
        return missing(names, "vat_amount" if tax is None else "line_items")
    on_charges = _taxed(facts.declared, facts.amount("vat_rate"))
    charged = quantize_cents(rows + (ZERO if on_charges is None else on_charges))
    return agree(names, f"{charged} (rows)", charged, tax, facts.tolerance)


def document_type_matches_total_sign(facts: Facts) -> Verdict:
    """A credit note gives money back, and an invoice asks for it. Advisory, not an error."""
    names = ("total_amount",)
    total = facts.amount("total_amount")
    if total is None or total == ZERO:
        return missing(names, "total_amount")
    credit = facts.document_type == CREDIT_NOTE
    if credit == (total < ZERO):
        return holds(names, f"{facts.document_type} with a total of {total}")
    detail = f"{facts.document_type} with a total of {total}"
    return fails(names, detail, Severity.WARNING)


INVARIANTS: tuple[Invariant, ...] = (
    subtotal_plus_vat_equals_total,
    line_items_sum_equals_subtotal,
    line_items_sum_equals_total_when_no_vat,
    vat_equals_subtotal_times_rate,
    per_rate_vat_consistency,
    summary_base_sums_equal_subtotal,
    summary_vat_sums_equal_vat_total,
    line_totals_plus_charges_equal_grand_total,
    line_items_vat_sum_equals_vat_total,
    document_type_matches_total_sign,
)
INVARIANT_NAMES: tuple[str, ...] = tuple(rule.__name__ for rule in INVARIANTS)


def _charges(facts: Facts) -> tuple[Decimal, ...]:
    """The charges as terms of a sum; a document with none has no term for them."""
    return tuple(charge.amount for charge in facts.charges)


def _first_missing(facts: Facts, names: tuple[str, ...]) -> str:
    return next(name for name in names if facts.amount(name) is None)


def _complete(*values: Decimal | None) -> bool:
    return all(value is not None for value in values)


def _taxes_its_base(
    rate: Decimal | None, base: Decimal | None, vat: Decimal | None, facts: Facts
) -> bool:
    expected = _taxed(base, rate)
    return expected is not None and vat is not None and abs(expected - vat) <= facts.tolerance


def _taxed(net: Decimal | None, rate: Decimal | None) -> Decimal | None:
    if net is None or rate is None:
        return None
    return quantize_cents(net * rate / PERCENT)
