"""What a run of the pipeline produces, and the JSON shape it round-trips through.

Every value here arrives with the `Evidence` that produced it — a page, a box, a matched
label and a strategy — so any number in the output can be traced back to the line it was
read from. `docs/FIELD_CATALOG.md` names every field this shape carries; the rows and the
parties have records of their own in `domain/rows.py` and `domain/parties.py`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import cast

from invoice_extractor.domain.checks import Check
from invoice_extractor.domain.evidence import Evidence, Strategy, optional
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.parties import Party
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge, SecondaryAmounts

FieldValue = str | date | Decimal

# Where a confidence's weights came from: a fit on a corpus whose answers were known, or
# the uniform mean of whatever signals the field emitted (ENGINE_SPEC §8).
FITTED = "fitted"
UNIFORM = "uniform"

# How a field's value is typed, by name. `extraction/specs.py` picks the normalizer that
# produces each of these, and `from_dict` reads them back the same way.
VALUE_TYPES: Mapping[str, type] = {
    "invoice_number": str,
    "order_number": str,
    "customer_number": str,
    "invoice_date": date,
    "supply_date": date,
    "due_date": date,
    "supplier_vat_id": str,
    "customer_vat_id": str,
    "currency": str,
    "vat_rate": Decimal,
    "subtotal": Decimal,
    "vat_amount": Decimal,
    "total_amount": Decimal,
    "contract_number": str,
    "our_reference": str,
    "your_reference": str,
    "credit_reference": str,
}

__all__ = [
    "FITTED",
    "UNIFORM",
    "VALUE_TYPES",
    "Charge",
    "Check",
    "Evidence",
    "FieldResult",
    "FieldValue",
    "InvoiceResult",
    "LineItem",
    "Party",
    "SecondaryAmounts",
    "Strategy",
    "VatSummaryRow",
]


@dataclass(frozen=True, slots=True)
class FieldResult:
    """One scalar field, its evidence, and how much the pipeline trusts it."""

    name: str
    value: FieldValue | None
    raw_text: str | None
    evidence: Evidence | None
    valid: bool
    confidence: float = 0.0
    # The signals the confidence was made of, by name (ENGINE_SPEC §8): what each of them
    # is worth is the fitted `calibration/weights.json`, not this record.
    confidence_breakdown: Mapping[str, float] = field(default_factory=dict)
    # `fitted` where weights were fitted for this field, `uniform` where the signals were
    # simply averaged, so a number that came from a guess does not look like one that did not.
    confidence_source: str = UNIFORM


@dataclass(frozen=True, slots=True)
class InvoiceResult:
    """Everything one invoice extracted to.

    `profile_id` is `None` for a document no profile matched: there is no default
    vocabulary to fall back on (ADR-0008), so `fields` is empty and the findings say why.
    `document_type` is `None` for the same document, because which kind it is is read
    with the vendor's own words for each kind.
    """

    fields: Mapping[str, FieldResult]
    line_items: tuple[LineItem, ...]
    findings: tuple[Finding, ...]
    profile_id: str | None
    document_type: str | None
    source_path: str
    parties: Mapping[str, Party] = field(default_factory=dict)
    vat_summary: tuple[VatSummaryRow, ...] = ()
    charges: tuple[Charge, ...] = ()
    secondary_amounts: SecondaryAmounts | None = None
    checks: tuple[Check, ...] = ()

    @property
    def valid(self) -> bool:
        """Derived from the findings, never set beside them (ADR-0010)."""
        return not any(finding.severity is Severity.ERROR for finding in self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "fields": {name: _field_to_dict(result) for name, result in self.fields.items()},
            "parties": {name: party.to_dict() for name, party in self.parties.items()},
            "line_items": [item.to_dict() for item in self.line_items],
            "vat_summary": [row.to_dict() for row in self.vat_summary],
            "charges": [charge.to_dict() for charge in self.charges],
            "secondary_amounts": _secondary_to_dict(self.secondary_amounts),
            "findings": [finding.to_dict() for finding in self.findings],
            "checks": [check.to_dict() for check in self.checks],
            "profile_id": self.profile_id,
            "document_type": self.document_type,
            "valid": self.valid,
            "source_path": self.source_path,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> InvoiceResult:
        fields = cast(Mapping[str, Mapping[str, object]], data["fields"])
        findings = cast(Sequence[Mapping[str, object]], data["findings"])
        return cls(
            fields={name: _field_from_dict(name, entry) for name, entry in fields.items()},
            line_items=tuple(LineItem.from_dict(item) for item in _rows(data, "line_items")),
            findings=tuple(Finding.from_dict(entry) for entry in findings),
            profile_id=_optional_text(data["profile_id"]),
            document_type=_optional_text(data["document_type"]),
            source_path=str(data["source_path"]),
            parties=_parties(data),
            vat_summary=tuple(VatSummaryRow.from_dict(row) for row in _rows(data, "vat_summary")),
            charges=tuple(Charge.from_dict(charge) for charge in _rows(data, "charges")),
            checks=tuple(Check.from_dict(check) for check in _rows(data, "checks")),
            secondary_amounts=_secondary(data.get("secondary_amounts")),
        )


def _secondary_to_dict(amounts: SecondaryAmounts | None) -> dict[str, object] | None:
    return None if amounts is None else amounts.to_dict()


def _secondary(raw: object) -> SecondaryAmounts | None:
    """The echo in another currency, which most documents do not print at all."""
    return None if raw is None else SecondaryAmounts.from_dict(cast(Mapping[str, object], raw))


def _parties(data: Mapping[str, object]) -> dict[str, Party]:
    found = data.get("parties")
    entries = cast(Mapping[str, Mapping[str, object]], found if isinstance(found, dict) else {})
    return {name: Party.from_dict(entry) for name, entry in entries.items()}


def _rows(data: Mapping[str, object], key: str) -> Sequence[Mapping[str, object]]:
    found = data.get(key)
    return cast(Sequence[Mapping[str, object]], found if isinstance(found, list) else ())


def _optional_text(raw: object) -> str | None:
    return None if raw is None else str(raw)


def _field_to_dict(result: FieldResult) -> dict[str, object]:
    evidence = result.evidence
    return {
        "value": _value_to_json(result.value),
        "raw_text": result.raw_text,
        "valid": result.valid,
        "evidence": None if evidence is None else evidence.to_dict(),
        "confidence": result.confidence,
        "confidence_breakdown": dict(result.confidence_breakdown),
        "confidence_source": result.confidence_source,
    }


def _field_from_dict(name: str, data: Mapping[str, object]) -> FieldResult:
    raw_text = data["raw_text"]
    breakdown = cast(Mapping[str, float], data.get("confidence_breakdown", {}))
    return FieldResult(
        name=name,
        value=_value_from_json(name, data["value"]),
        raw_text=None if raw_text is None else str(raw_text),
        evidence=optional(data["evidence"]),
        valid=bool(data["valid"]),
        confidence=cast(float, data.get("confidence", 0.0)),
        confidence_breakdown=dict(breakdown),
        confidence_source=str(data.get("confidence_source", UNIFORM)),
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
