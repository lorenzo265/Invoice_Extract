"""The only orchestration in the project: a PDF and a registry in, an `InvoiceResult` out.

Every other module minds one concern; this one wires them together and does nothing
itself — it does not parse a date, match a label, check an identity or compute a
confidence. The stages it wires are `docs/ENGINE_SPEC.md` §2, in that order: read, detect
the profile, classify the document, run every spec, read the blocks and the tables,
reconcile what was left out, check what was read, and score how much to trust it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from invoice_extractor.document.model import Document
from invoice_extractor.document.pymupdf_reader import read
from invoice_extractor.domain.checks import Check
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import FieldResult, InvoiceResult, VatSummaryRow
from invoice_extractor.domain.parties import Party
from invoice_extractor.extraction.block import read_totals
from invoice_extractor.extraction.classify import classify_document
from invoice_extractor.extraction.engine import Extraction, order, run
from invoice_extractor.extraction.line_items import TableExtraction, extract_line_items
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
from invoice_extractor.scoring.compute import compute
from invoice_extractor.scoring.signals import ScoringContext, extract_signals
from invoice_extractor.scoring.weights import Calibration, load
from invoice_extractor.validation.facts import Facts
from invoice_extractor.validation.stage import validate

NOT_DETECTED = "profile_not_detected"


def extract(pdf_path: Path, registry: ProfileRegistry) -> InvoiceResult:
    """Extract one invoice. Raises only for input the pipeline cannot start on (ADR-0005)."""
    document = read(pdf_path)
    profile, scores = detect_profile(document, registry, pdf_path.name)
    if profile is None:
        return _undetected(document, scores)
    return _extracted(document, profile, scores[0].score if scores else 0.0)


def _extracted(document: Document, profile: Profile, matched: float) -> InvoiceResult:
    kind = classify_document(document, profile)
    table = extract_line_items(document, profile, LINE_ITEMS)
    summary = extract_vat_summary(document, profile, VAT_SUMMARY)
    totals = read_totals(TOTALS, document, profile)
    parties = _parties(document, profile)
    extractions = {**_resolve(document, profile), **totals.extractions}
    found = {name: extraction.field for name, extraction in extractions.items()}
    reconciled = reconcile(found, totals.charges, table.items, summary, profile)
    facts = _facts(document, profile, kind.value, reconciled, table, summary, parties)
    findings, checks = validate(facts)
    return InvoiceResult(
        fields=_scored(extractions, reconciled, _context(facts, checks, matched)),
        line_items=table.items,
        findings=(*table.findings, *reconciled.findings, *findings),
        checks=checks,
        profile_id=profile.id,
        document_type=kind.value,
        source_path=document.source_path,
        parties=parties,
        vat_summary=summary,
        charges=reconciled.charges,
        secondary_amounts=totals.secondary,
    )


def _facts(
    document: Document,
    profile: Profile,
    kind: str,
    reconciled: Reconciliation,
    table: TableExtraction,
    summary: tuple[VatSummaryRow, ...],
    parties: Mapping[str, Party],
) -> Facts:
    """What stage 6 asks its questions about: everything the earlier stages published."""
    return Facts(
        profile=profile,
        fields=reconciled.fields,
        items=table.items,
        summary=summary,
        charges=reconciled.charges,
        parties=parties,
        document_type=kind,
        source_path=document.source_path,
        currency_basis=reconciled.currency,
    )


def _context(facts: Facts, checks: tuple[Check, ...], matched: float) -> ScoringContext:
    return ScoringContext(
        profile=facts.profile,
        resolved=facts.fields,
        checks=checks,
        profile_score=matched,
        items=facts.items,
        summary=facts.summary,
        parties=facts.parties,
    )


def _scored(
    extractions: Mapping[str, Extraction],
    reconciled: Reconciliation,
    context: ScoringContext,
) -> dict[str, FieldResult]:
    """Every field, with the value stage 5 settled on and the confidence stage 7 gives it."""
    calibration = load()
    return {
        name: _confidence(
            replace(extractions[name], field=reconciled.fields[name]),
            context,
            calibration,
            reconciled.caps.get(name),
        )
        for name in FIELD_ORDER
    }


def _confidence(
    extraction: Extraction,
    context: ScoringContext,
    calibration: Calibration,
    cap: float | None,
) -> FieldResult:
    name = extraction.field.name
    signals = extract_signals(extraction, context)
    scored = compute(signals, calibration.weights_for(name), cap, calibration.curve_for(name))
    return replace(
        extraction.field,
        confidence=scored.confidence,
        confidence_breakdown=scored.breakdown,
        confidence_source=scored.source,
    )


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
