"""Building `forge-truth/1`: what the document contains, and where every value is.

Values come from the model, printed strings and labels from the renderer's placement log,
and boxes from reading the produced PDF back. The three never disagree, because none of
them is derived from either of the others.

`docs/GROUND_TRUTH_SCHEMA.md` is the contract this file keeps.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from invoice_forge import __version__
from invoice_forge.fields import LABELLED_FIELDS
from invoice_forge.model import Document, DocumentType, Party
from invoice_forge.render.placement import Placement, Slot
from invoice_forge.render.renderer import RenderRequest, RenderResult
from invoice_forge.render.totals import headline_rate
from invoice_forge.render.wording import Wording
from invoice_forge.truth.locate import Evidence, locate
from invoice_forge.truth.values import field_values, item_row

TRUTH_SCHEMA = "forge-truth/1"
PARTY_KINDS: tuple[str, ...] = ("supplier", "bill_to", "ship_to", "mail_to")


def build_truth(request: RenderRequest, result: RenderResult, pdf_path: Path) -> dict[str, object]:
    """The complete truth for one rendered document, ready to be written as JSON."""
    placements = result.placements
    evidence = locate(pdf_path, placements)
    located = tuple(zip(placements, evidence, strict=True))
    document = request.document
    return {
        "schema": TRUTH_SCHEMA,
        "generator": _generator(request),
        "document": _document(document, result.pages),
        "fields": _fields(document, result.context.wording, located),
        "line_items": _line_items(document, located),
        "charges": _charges(document, result.context.wording, located),
        "vat_summary": _vat_summary(document, located),
        "secondary_amounts": _secondary(document, located),
        "parties": _parties(document, located),
        "noise": _noise(located),
    }


Located = tuple[tuple[Placement, Evidence], ...]


def _generator(request: RenderRequest) -> dict[str, object]:
    return {
        "version": __version__,
        "seed": request.seed,
        "profile": request.profile.id,
        "template": request.family.value,
        "knobs": [knob.value for knob in request.knobs],
    }


def _document(document: Document, pages: int) -> dict[str, object]:
    kind = "credit_note" if document.type is DocumentType.CREDIT_NOTE else "invoice"
    return {
        "type": kind,
        "pages": pages,
        "language": document.language,
        "currency": document.currency,
        "secondary_currency": document.secondary_currency,
        "rounding": document.rounding.value,
    }


def _fields(document: Document, wording: Wording, located: Located) -> dict[str, object]:
    """Every canonical name, with `null`s where the document does not carry the value."""
    values = field_values(document, headline_rate(document.totals))
    printed = _by_slot(located, Slot.FIELD)
    return {name: _field_entry(values.get(name), printed.get(name, ())) for name in LABELLED_FIELDS}


def _field_entry(value: str | None, printed: Sequence[tuple[Placement, Evidence]]) -> object:
    if value is None or not printed:
        return {"value": value, "printed": None, "label": None, "evidence": []}
    first = printed[0][0]
    return {
        "value": value,
        "printed": first.text,
        "label": first.mark.label,
        "evidence": [found.to_dict() for _, found in printed],
    }


def _line_items(document: Document, located: Located) -> list[dict[str, object]]:
    cells = _cells_by_row(located)
    return [item_row(item, cells.get(item.pos, {})) for item in document.items]


def _cells_by_row(located: Located) -> dict[int, dict[str, list[dict[str, object]]]]:
    rows: dict[int, dict[str, list[dict[str, object]]]] = defaultdict(lambda: defaultdict(list))
    for placement, found in located:
        if placement.mark.slot is Slot.CELL:
            rows[placement.mark.index][placement.mark.name].append(found.to_dict())
    return rows


def _charges(document: Document, wording: Wording, located: Located) -> list[dict[str, object]]:
    """A declared charge carries evidence; an undeclared one is in the total and nowhere else."""
    printed = _by_index(located, Slot.CHARGE)
    return [
        {
            "type": charge.type.value,
            "amount": str(charge.amount),
            "vat_rate": str(charge.vat_rate),
            "declared": charge.declared,
            "label": wording.charges[charge.type.value] if charge.declared else None,
            "evidence": [found.to_dict() for _, found in printed.get(index, ())],
        }
        for index, charge in enumerate(document.charges)
    ]


def _vat_summary(document: Document, located: Located) -> list[dict[str, object]]:
    printed = _by_index(located, Slot.VAT_LINE)
    return [
        {
            "rate": str(line.rate),
            "base": str(line.base),
            "vat": str(line.vat),
            "evidence": [found.to_dict() for _, found in printed.get(index, ())],
        }
        for index, line in enumerate(document.totals.vat_lines)
    ]


def _secondary(document: Document, located: Located) -> dict[str, object] | None:
    rate = document.exchange_rate
    printed = [found for placement, found in located if placement.mark.slot is Slot.SECONDARY]
    if rate is None or document.secondary_currency is None or not printed:
        return None
    converted = (document.totals.total_amount * rate).quantize(Decimal("0.01"))
    return {
        "currency": document.secondary_currency,
        "total_amount": str(converted),
        "exchange_rate": str(rate),
        "evidence": [found.to_dict() for found in printed],
    }


def _parties(document: Document, located: Located) -> dict[str, object]:
    printed: dict[str, list[Evidence]] = defaultdict(list)
    for placement, found in located:
        if placement.mark.slot is Slot.PARTY and placement.mark.label is not None:
            printed[placement.mark.label].append(found)
    named = {
        "supplier": document.supplier,
        "bill_to": document.bill_to,
        "ship_to": document.ship_to,
        "mail_to": document.mail_to,
    }
    return {kind: _party(named[kind], printed.get(kind, ())) for kind in PARTY_KINDS}


def _party(party: Party | None, printed: Sequence[Evidence]) -> dict[str, object] | None:
    if party is None:
        return None
    return {
        "name": party.name,
        "lines": list(party.lines),
        "vat_id": party.vat_id,
        "evidence": [found.to_dict() for found in printed],
    }


def _noise(located: Located) -> list[dict[str, object]]:
    """What was printed to mislead, so a benchmark can say which trap caused which miss."""
    return [
        {
            "kind": placement.mark.name,
            "label": placement.mark.label,
            "page": found.page,
            "bbox": list(found.bbox),
        }
        for placement, found in located
        if placement.mark.slot is Slot.NOISE
    ]


def _by_slot(located: Located, slot: Slot) -> dict[str, list[tuple[Placement, Evidence]]]:
    grouped: dict[str, list[tuple[Placement, Evidence]]] = defaultdict(list)
    for placement, found in located:
        if placement.mark.slot is slot:
            grouped[placement.mark.name].append((placement, found))
    return grouped


def _by_index(located: Located, slot: Slot) -> dict[int, list[tuple[Placement, Evidence]]]:
    grouped: dict[int, list[tuple[Placement, Evidence]]] = defaultdict(list)
    for placement, found in located:
        if placement.mark.slot is slot:
            grouped[placement.mark.index].append((placement, found))
    return grouped
