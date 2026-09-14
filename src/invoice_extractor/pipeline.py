"""The only orchestration in the project: a PDF and a profile in, an `InvoiceResult` out.

Every other module minds one concern; this one wires them together and does nothing
itself — it does not parse a date, match a label, or compute a confidence.
"""

from __future__ import annotations

from pathlib import Path

from invoice_extractor.document.pymupdf_reader import PyMuPDFReader
from invoice_extractor.document.reader import DocumentReader, TextLine
from invoice_extractor.domain.models import InvoiceResult
from invoice_extractor.extraction.engine import run
from invoice_extractor.extraction.line_items import extract_line_items
from invoice_extractor.extraction.specs import FIELD_SPECS
from invoice_extractor.profile.schema import Profile
from invoice_extractor.validation.confidence import score
from invoice_extractor.validation.invariants import check_all


def extract(pdf_path: Path, profile: Profile) -> InvoiceResult:
    """Extract one invoice. Raises only for input the pipeline cannot start on (ADR-0005)."""
    with PyMuPDFReader(pdf_path) as reader:
        lines = _all_lines(reader)
    extractions = {spec.name: run(spec, lines, profile) for spec in FIELD_SPECS}
    table = extract_line_items(lines, profile)
    found = {name: extraction.field for name, extraction in extractions.items()}
    findings = (*table.findings, *check_all(found, table.items))
    return InvoiceResult(
        fields={
            name: score(extraction, profile.fields[name], findings)
            for name, extraction in extractions.items()
        },
        line_items=table.items,
        findings=findings,
        profile_id=profile.id,
        source_path=pdf_path.as_posix(),
    )


def _all_lines(reader: DocumentReader) -> list[TextLine]:
    """Every page's lines, in page order — a label may sit on any page."""
    return [line for page in range(1, reader.page_count + 1) for line in reader.lines(page)]
