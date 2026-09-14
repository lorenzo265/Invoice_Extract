"""The only orchestration in the project: a PDF and a registry in, an `InvoiceResult` out.

Every other module minds one concern; this one wires them together and does nothing
itself — it does not parse a date, match a label, or compute a confidence. The stages it
wires are `docs/ENGINE_SPEC.md` §2, in that order: read, detect the profile, classify the
document, run every spec, read the blocks and the tables, check the arithmetic, score.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from invoice_extractor.document.model import Document
from invoice_extractor.document.pymupdf_reader import read
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import FieldResult, InvoiceResult
from invoice_extractor.domain.parties import Party
from invoice_extractor.extraction.block import read_totals
from invoice_extractor.extraction.classify import classify_document
from invoice_extractor.extraction.engine import Extraction, order, run
from invoice_extractor.extraction.line_items import extract_line_items
from invoice_extractor.extraction.section import read_section
from invoice_extractor.extraction.specs import (
    FIELD_ORDER,
    LINE_ITEMS,
    SECTIONS,
    SPECS,
    TOTALS,
    VAT_SUMMARY,
)
from invoice_extractor.extraction.vat_summary import extract_vat_summary
from invoice_extractor.profile.detect import ProfileScore, detect_profile
from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.profile.schema import Profile
from invoice_extractor.reconcile.stage import Reconciliation, reconcile
from invoice_extractor.validation.confidence import NO_CAP, score
from invoice_extractor.validation.invariants import check_all

NOT_DETECTED = "profile_not_detected"


def extract(pdf_path: Path, registry: ProfileRegistry) -> InvoiceResult:
    """Extract one invoice. Raises only for input the pipeline cannot start on (ADR-0005)."""
    document = read(pdf_path)
    profile, scores = detect_profile(document, registry, pdf_path.name)
    if profile is None:
        return _undetected(document, scores)
    return _extracted(document, profile)


def _extracted(document: Document, profile: Profile) -> InvoiceResult:
    kind = classify_document(document, profile)
    table = extract_line_items(document, profile, LINE_ITEMS)
    summary = extract_vat_summary(document, profile, VAT_SUMMARY)
    totals = read_totals(TOTALS, document, profile)
    extractions = {**_resolve(document, profile), **totals.extractions}
    found = {name: extraction.field for name, extraction in extractions.items()}
    reconciled = reconcile(found, totals.charges, table.items, summary, profile)
    findings = (
        *table.findings,
        *reconciled.findings,
        *check_all(reconciled.fields, table.items, reconciled.charges, summary),
    )
    return InvoiceResult(
        fields=_scored(extractions, reconciled, profile, findings),
        line_items=table.items,
        findings=findings,
        profile_id=profile.id,
        document_type=kind.value,
        source_path=document.source_path,
        parties=_parties(document, profile),
        vat_summary=summary,
        charges=reconciled.charges,
        secondary_amounts=totals.secondary,
    )


def _scored(
    extractions: Mapping[str, Extraction],
    reconciled: Reconciliation,
    profile: Profile,
    findings: Sequence[Finding],
) -> dict[str, FieldResult]:
    """Every field, with the value stage 5 settled on and the cap stage 5 asked for."""
    return {
        name: score(
            replace(extractions[name], field=reconciled.fields[name]),
            profile.fields.get(name),
            findings,
            reconciled.caps.get(name, NO_CAP),
        )
        for name in FIELD_ORDER
    }


def _parties(document: Document, profile: Profile) -> dict[str, Party]:
    """Every party block the document prints; one it does not print is absent, not empty."""
    read_blocks = ((spec.name, read_section(spec, document, profile)) for spec in SECTIONS)
    return {name: party for name, party in read_blocks if party is not None}


def _resolve(document: Document, profile: Profile) -> dict[str, Extraction]:
    """Every spec, in an order where what a field is derived from resolved first."""
    extractions: dict[str, Extraction] = {}
    resolved: dict[str, FieldResult] = {}
    for spec in order(SPECS):
        extraction = run(spec, document, profile, resolved)
        extractions[spec.name] = extraction
        resolved[spec.name] = extraction.field
    return extractions


def _undetected(document: Document, scores: tuple[ProfileScore, ...]) -> InvoiceResult:
    """No profile matched, so nothing is read: a wrong vocabulary is worse than none."""
    return InvoiceResult(
        fields={},
        line_items=(),
        findings=(_not_detected(scores),),
        profile_id=None,
        document_type=None,
        source_path=document.source_path,
    )


def _not_detected(scores: tuple[ProfileScore, ...]) -> Finding:
    best = f"best was {scores[0].profile_id} at {scores[0].score:.2f}" if scores else "none scored"
    return Finding(
        severity=Severity.ERROR,
        code=NOT_DETECTED,
        message=f"no profile matched this document; {best}",
    )
