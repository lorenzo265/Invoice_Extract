"""The human-readable report shown in README.md's "See it run".

Pure rendering: it reads an already-built `InvoiceResult` and never re-runs an invariant,
recomputes a confidence, or looks at the document again. Money is printed as the plain
decimal it was read as: a currency symbol is a vendor's decoration, not a value.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from enum import Enum, auto

from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import FieldResult, FieldValue, InvoiceResult, LineItem
from invoice_extractor.profile.schema import Profile
from invoice_extractor.validation.invariants import INVARIANT_NAMES

RULE_WIDTH = 80
PADDING = 2
LABEL_WIDTH = 9
MISSING = "-"
TITLE = "Invoice Extraction Report"
OK = "[ok]"
MARKERS: Mapping[Severity, str] = {
    Severity.INFO: "[..]",
    Severity.WARNING: "[??]",
    Severity.ERROR: "[!!]",
}


class Align(Enum):
    """Which edge a column's cells line up on."""

    LEFT = auto()
    RIGHT = auto()


FIELD_HEADERS = ("FIELD", "VALUE", "CONF", "EVIDENCE")
FIELD_ALIGN = (Align.LEFT, Align.LEFT, Align.LEFT, Align.LEFT)
ITEM_HEADERS = ("PART NUMBER", "DESCRIPTION", "QTY", "UNIT PRICE", "NET AMOUNT")
ITEM_ALIGN = (Align.LEFT, Align.LEFT, Align.RIGHT, Align.RIGHT, Align.RIGHT)


def render(result: InvoiceResult, profile: Profile) -> str:
    """The whole report as one string, without a trailing newline."""
    lines = [
        TITLE,
        "=" * RULE_WIDTH,
        f"{'source':<{LABEL_WIDTH}}{result.source_path}",
        f"{'profile':<{LABEL_WIDTH}}{result.profile_id}",
        "",
        *_field_table(result.fields),
        "",
        *_item_table(result.line_items),
        "",
        *_invariant_block(result),
        "",
        _counts(result.findings),
        "=" * RULE_WIDTH,
    ]
    return "\n".join(lines)


def _field_table(fields: Mapping[str, FieldResult]) -> list[str]:
    rows = [
        (name, _value(field.value), f"{field.confidence:.2f}", _evidence(field))
        for name, field in fields.items()
    ]
    return _table(FIELD_HEADERS, rows, FIELD_ALIGN)


def _item_table(items: Sequence[LineItem]) -> list[str]:
    rows = [
        (
            item.part_number,
            item.description,
            str(item.quantity),
            str(item.unit_price),
            str(item.net_amount),
        )
        for item in items
    ]
    return [f"Line items ({len(items)})", *_table(ITEM_HEADERS, rows, ITEM_ALIGN)]


def _invariant_block(result: InvoiceResult) -> list[str]:
    width = max(len(name) for name in INVARIANT_NAMES) + PADDING
    marker_width = len(OK) + PADDING
    lines = ["Invariants"]
    for name in INVARIANT_NAMES:
        finding = _finding_for(result.findings, name)
        marker = OK if finding is None else MARKERS[finding.severity]
        detail = ARITHMETIC[name](result) if finding is None else finding.message
        lines.append(f"{marker:<{marker_width}}{name:<{width}}{detail}".rstrip())
    return lines


def _table(
    headers: Sequence[str], rows: Sequence[Sequence[str]], alignments: Sequence[Align]
) -> list[str]:
    """Every column as wide as its widest cell plus two, so the columns never touch."""
    widths = [
        max([len(header), *(len(row[index]) for row in rows)]) + PADDING
        for index, header in enumerate(headers)
    ]
    body = [_row(row, widths, alignments) for row in rows]
    return [_row(headers, widths, alignments), "-" * RULE_WIDTH, *body]


def _row(cells: Sequence[str], widths: Sequence[int], alignments: Sequence[Align]) -> str:
    padded = [
        cell.rjust(width) if align is Align.RIGHT else cell.ljust(width)
        for cell, width, align in zip(cells, widths, alignments, strict=True)
    ]
    return "".join(padded).rstrip()


def _value(value: FieldValue | None) -> str:
    if value is None:
        return MISSING
    return value.isoformat() if isinstance(value, date) else str(value)


def _evidence(field: FieldResult) -> str:
    evidence = field.evidence
    if evidence is None:
        return MISSING
    label = MISSING if evidence.matched_label is None else f'"{evidence.matched_label}"'
    return f"p{evidence.page}  {evidence.strategy.name}  {label}"


def _amount(result: InvoiceResult, name: str) -> str:
    field = result.fields.get(name)
    return MISSING if field is None else _value(field.value)


def _totals_expression(result: InvoiceResult) -> str:
    left = f"{_amount(result, 'subtotal')} + {_amount(result, 'vat_amount')}"
    return f"{left} = {_amount(result, 'total_amount')}"


def _line_items_expression(result: InvoiceResult) -> str:
    added = " + ".join(str(item.net_amount) for item in result.line_items)
    return f"{added} = {_amount(result, 'subtotal')}"


def _vat_rate_expression(result: InvoiceResult) -> str:
    left = f"{_amount(result, 'vat_rate')}% x {_amount(result, 'subtotal')}"
    return f"{left} = {_amount(result, 'vat_amount')}"


ARITHMETIC: Mapping[str, Callable[[InvoiceResult], str]] = {
    "totals_reconcile": _totals_expression,
    "line_items_sum": _line_items_expression,
    "vat_rate_consistent": _vat_rate_expression,
}


def _finding_for(findings: Sequence[Finding], code: str) -> Finding | None:
    return next((finding for finding in findings if finding.code == code), None)


def _counts(findings: Sequence[Finding]) -> str:
    tally = dict.fromkeys(Severity, 0)
    for finding in findings:
        tally[finding.severity] += 1
    errors, warnings, infos = tally[Severity.ERROR], tally[Severity.WARNING], tally[Severity.INFO]
    return f"{errors} error, {warnings} warning, {infos} info findings"
