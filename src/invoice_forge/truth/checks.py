"""What has to be true of a truth file, checked from the file's own numbers.

Nothing here calls the generator. The arithmetic is re-derived from the rows the truth
records, under the rounding policy the truth declares, because a verifier that asked
`compute_totals` whether `compute_totals` was right would prove nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal

from invoice_forge.truth.reading import TruthError, amount, block, boxes, flag, rows, text, whole

CENT = Decimal("0.01")
PERCENT = Decimal(100)
PER_LINE = "per_line"
TOTAL = "total"
ROUNDING_POLICIES = (PER_LINE, TOTAL)
TRUTH_SCHEMA = "forge-truth/1"


def check_schema(truth: dict[str, object], pages: int) -> list[str]:
    """The file says what it is, and describes the PDF that is actually there."""
    complaints: list[str] = []
    declared = truth.get("schema")
    if declared != TRUTH_SCHEMA:
        complaints.append(f"schema is {declared!r}, not {TRUTH_SCHEMA!r}")
    document = block(truth, "document")
    stated = whole(document, "pages", "document")
    if stated != pages:
        complaints.append(f"document.pages says {stated}, the PDF has {pages}")
    policy = text(document, "rounding", "document")
    if policy not in ROUNDING_POLICIES:
        complaints.append(f"document.rounding is {policy!r}, not one of {ROUNDING_POLICIES}")
    complaints += _check_generator(truth)
    return complaints


def check_arithmetic(truth: dict[str, object]) -> list[str]:
    """Every number the document prints follows from the rows above it."""
    policy = text(block(truth, "document"), "rounding", "document")
    fields = block(truth, "fields")
    items = rows(truth, "line_items")
    complaints = _check_rows(items)
    subtotal = _field_amount(fields, "subtotal")
    if subtotal is not None:
        complaints += _check_subtotal(items, subtotal, policy)
    complaints += _check_vat_lines(truth)
    complaints += _check_total(truth, fields)
    return complaints


def check_evidence_rule(truth: dict[str, object]) -> list[str]:
    """A declared charge is on the page; an undeclared one is in the total and nowhere else."""
    complaints: list[str] = []
    for index, charge in enumerate(rows(truth, "charges")):
        where = f"charges[{index}]"
        declared = flag(charge, "declared", where)
        found = boxes(charge, where)
        if declared and not found:
            complaints.append(f"{where} is declared but carries no evidence")
        if not declared and found:
            complaints.append(f"{where} is undeclared but carries evidence")
    return complaints


def _check_generator(truth: dict[str, object]) -> list[str]:
    generator = block(truth, "generator")
    for key in ("version", "profile", "template"):
        text(generator, key, "generator")
    whole(generator, "seed", "generator")
    knobs = generator.get("knobs")
    if not isinstance(knobs, list) or not all(isinstance(knob, str) for knob in knobs):
        raise TruthError("generator.knobs must be a list of strings")
    return []


def _check_rows(items: Sequence[dict[str, object]]) -> list[str]:
    complaints: list[str] = []
    for index, row in enumerate(items):
        where = f"line_items[{index}]"
        expected = _cents(_exact_net(row, where))
        printed = amount(row, "net_amount", where)
        if expected != printed:
            complaints.append(f"{where}: {expected} was expected, the truth says {printed}")
    return complaints


def _exact_net(row: dict[str, object], where: str) -> Decimal:
    """Quantity times price, less the discount the row declares, before anyone rounds."""
    gross = amount(row, "quantity", where) * amount(row, "unit_price", where)
    if row.get("discount_percent") is None:
        return gross
    return gross - gross * amount(row, "discount_percent", where) / PERCENT


def _check_subtotal(
    items: Sequence[dict[str, object]], subtotal: Decimal, policy: str
) -> list[str]:
    """The two policies differ only in where the cents are decided; both are re-derived."""
    exact = [_exact_net(row, "line_items") for row in items]
    expected = _summed(exact, policy)
    if expected == subtotal:
        return []
    return [f"subtotal: {expected} follows from the rows under {policy}, the truth says {subtotal}"]


def _check_vat_lines(truth: dict[str, object]) -> list[str]:
    complaints: list[str] = []
    charged = Decimal(0)
    for index, line in enumerate(rows(truth, "vat_summary")):
        where = f"vat_summary[{index}]"
        base, rate, vat = (amount(line, key, where) for key in ("base", "rate", "vat"))
        expected = _cents(base * rate / PERCENT)
        if expected != vat:
            complaints.append(f"{where}: {rate}% of {base} is {expected}, the truth says {vat}")
        charged += vat
    stated = _field_amount(block(truth, "fields"), "vat_amount")
    if stated is not None and charged != stated:
        complaints.append(f"vat_amount: the summary adds to {charged}, the truth says {stated}")
    return complaints


def _check_total(truth: dict[str, object], fields: dict[str, object]) -> list[str]:
    parts = [_field_amount(fields, name) for name in ("subtotal", "vat_amount", "total_amount")]
    subtotal, vat_amount, total = parts
    if subtotal is None or vat_amount is None or total is None:
        return []
    charges = sum(
        (amount(charge, "amount", "charges") for charge in rows(truth, "charges")), Decimal(0)
    )
    expected = _cents(subtotal + charges + vat_amount)
    if expected == total:
        return []
    return [f"total_amount: {expected} follows from the blocks above it, the truth says {total}"]


def _field_amount(fields: dict[str, object], name: str) -> Decimal | None:
    entry = fields.get(name)
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    return amount(entry, "value", f"fields.{name}")


def _summed(values: Iterable[Decimal], policy: str) -> Decimal:
    if policy == PER_LINE:
        return sum((_cents(value) for value in values), Decimal(0))
    return _cents(sum(values, Decimal(0)))


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
