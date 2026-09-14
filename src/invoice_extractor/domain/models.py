"""What a run of the pipeline produces, and the JSON shape it round-trips through.

Every scalar value here arrives with the `Evidence` that produced it — a page, a box, a
matched label and a strategy — so any number in the output can be traced back to the
line it was read from. `docs/SAMPLES_SPEC.md` fixes the JSON shape `to_dict` writes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum, auto
from typing import cast

from invoice_extractor.document.reader import BBox
from invoice_extractor.domain.findings import Finding

FieldValue = str | date | Decimal

# How a field's value is typed, by name. `extraction/specs.py` picks the normalizer that
# produces each of these, and `from_dict` reads them back the same way.
VALUE_TYPES: Mapping[str, type] = {
    "invoice_number": str,
    "invoice_date": date,
    "due_date": date,
    "supplier_vat_id": str,
    "customer_vat_id": str,
    "currency": str,
    "vat_rate": Decimal,
    "subtotal": Decimal,
    "vat_amount": Decimal,
    "total_amount": Decimal,
}


class Strategy(Enum):
    """How a candidate was found. It lives here, beside the `Evidence` that records it.

    `LABEL_RIGHT` and `LABEL_BESIDE` are the same reading of a page — the value follows
    its label along the line — found two ways, because a PDF has no idea what a line is.
    A vendor that writes `Invoice Number: INV-42` in one run gives the reader one line;
    a vendor that sets the label at one tab stop and the number flush right at another
    gives it two, and the text between them is white space that was never drawn.
    """

    LABEL_RIGHT = auto()
    LABEL_BESIDE = auto()
    LABEL_BELOW = auto()
    REGEX_ANCHOR = auto()


@dataclass(frozen=True, slots=True)
class Evidence:
    """Where a value came from: the page and box, the label matched, the text before parsing."""

    page: int
    bbox: BBox
    matched_label: str | None
    strategy: Strategy
    raw_text: str


@dataclass(frozen=True, slots=True)
class FieldResult:
    """One scalar field, its evidence, and how much the pipeline trusts it."""

    name: str
    value: FieldValue | None
    raw_text: str | None
    evidence: Evidence | None
    valid: bool
    confidence: float = 0.0
    confidence_breakdown: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LineItem:
    """One row of the invoice's table. Found as a table, so it carries no `Evidence`."""

    sku: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    net_amount: Decimal


@dataclass(frozen=True, slots=True)
class InvoiceResult:
    """Everything one invoice extracted to. `fields` always holds all ten names, in order."""

    fields: Mapping[str, FieldResult]
    line_items: tuple[LineItem, ...]
    findings: tuple[Finding, ...]
    layout_id: str
    source_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fields": {name: _field_to_dict(result) for name, result in self.fields.items()},
            "line_items": [_line_item_to_dict(item) for item in self.line_items],
            "findings": [finding.to_dict() for finding in self.findings],
            "layout_id": self.layout_id,
            "source_path": self.source_path,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> InvoiceResult:
        fields = cast(Mapping[str, Mapping[str, object]], data["fields"])
        items = cast(Sequence[Mapping[str, str]], data["line_items"])
        findings = cast(Sequence[Mapping[str, object]], data["findings"])
        return cls(
            fields={name: _field_from_dict(name, entry) for name, entry in fields.items()},
            line_items=tuple(_line_item_from_dict(item) for item in items),
            findings=tuple(Finding.from_dict(entry) for entry in findings),
            layout_id=str(data["layout_id"]),
            source_path=str(data["source_path"]),
        )


def _field_to_dict(result: FieldResult) -> dict[str, object]:
    evidence = result.evidence
    return {
        "value": _value_to_json(result.value),
        "raw_text": result.raw_text,
        "valid": result.valid,
        "evidence": None if evidence is None else _evidence_to_dict(evidence),
        "confidence": result.confidence,
        "confidence_breakdown": dict(result.confidence_breakdown),
    }


def _field_from_dict(name: str, data: Mapping[str, object]) -> FieldResult:
    raw_text = data["raw_text"]
    breakdown = cast(Mapping[str, float], data.get("confidence_breakdown", {}))
    return FieldResult(
        name=name,
        value=_value_from_json(name, data["value"]),
        raw_text=None if raw_text is None else str(raw_text),
        evidence=_optional_evidence(data["evidence"]),
        valid=bool(data["valid"]),
        confidence=cast(float, data.get("confidence", 0.0)),
        confidence_breakdown=dict(breakdown),
    )


def _optional_evidence(raw: object) -> Evidence | None:
    return None if raw is None else _evidence_from_dict(cast(Mapping[str, object], raw))


def _evidence_to_dict(evidence: Evidence) -> dict[str, object]:
    box = evidence.bbox
    return {
        "page": evidence.page,
        "bbox": {"x0": box.x0, "y0": box.y0, "x1": box.x1, "y1": box.y1},
        "matched_label": evidence.matched_label,
        "strategy": evidence.strategy.name,
        "raw_text": evidence.raw_text,
    }


def _evidence_from_dict(data: Mapping[str, object]) -> Evidence:
    box = cast(Mapping[str, float], data["bbox"])
    label = data["matched_label"]
    return Evidence(
        page=cast(int, data["page"]),
        bbox=BBox(x0=box["x0"], y0=box["y0"], x1=box["x1"], y1=box["y1"]),
        matched_label=None if label is None else str(label),
        strategy=Strategy[str(data["strategy"])],
        raw_text=str(data["raw_text"]),
    )


def _line_item_to_dict(item: LineItem) -> dict[str, object]:
    return {
        "sku": item.sku,
        "description": item.description,
        "quantity": str(item.quantity),
        "unit_price": str(item.unit_price),
        "net_amount": str(item.net_amount),
    }


def _line_item_from_dict(data: Mapping[str, str]) -> LineItem:
    return LineItem(
        sku=data["sku"],
        description=data["description"],
        quantity=Decimal(data["quantity"]),
        unit_price=Decimal(data["unit_price"]),
        net_amount=Decimal(data["net_amount"]),
    )


def _value_to_json(value: FieldValue | None) -> str | None:
    """A `Decimal` becomes its own digits, never a JSON number; a `date`, ISO-8601."""
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def _value_from_json(name: str, raw: object) -> FieldValue | None:
    """The inverse, typed by field name — the one place that mapping is consulted."""
    if raw is None:
        return None
    text = str(raw)
    expected = VALUE_TYPES.get(name, str)
    if expected is date:
        return date.fromisoformat(text)
    return Decimal(text) if expected is Decimal else text
