"""Invariants and confidence, end to end on real documents.

The documents are the corpus fixtures: generated, arithmetically consistent by
construction, and committed, so what an invariant says here is what it says about an
invoice a vendor could have sent. Some of them turn every difficulty knob on at once,
which is why only the plain ones are held to reconciling: a document that hides a charge
in its total is a document this extractor does not yet read, and the benchmark is where
that is counted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from invoice_extractor import ProfileRegistry, extract
from invoice_extractor.domain.findings import Severity
from invoice_extractor.validation.invariants import INVARIANT_NAMES

FIXTURES = Path("tests/forge/fixtures/corpus")
TRUTH_SUFFIX = ".truth.json"


def documents() -> list[tuple[Path, str, tuple[str, ...]]]:
    """Every committed fixture: its PDF, its vendor's profile, and the knobs it turned on."""
    found = []
    for truth_path in sorted(FIXTURES.glob(f"*{TRUTH_SUFFIX}")):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        pdf = truth_path.with_name(truth_path.name.removesuffix(TRUTH_SUFFIX) + ".pdf")
        generator = truth["generator"]
        found.append((pdf, str(generator["profile"]), tuple(generator["knobs"])))
    return found


PLAIN = [(pdf, profile_id) for pdf, profile_id, knobs in documents() if not knobs]
EVERY = [(pdf, profile_id) for pdf, profile_id, _ in documents()]


@pytest.mark.parametrize(("pdf", "profile_id"), PLAIN)
def test_a_plain_document_reconciles(pdf: Path, profile_id: str) -> None:
    """Nothing the generator prints disagrees with itself, so no invariant may say it does."""
    result = extract(pdf, ProfileRegistry().get(profile_id))
    errors = [finding for finding in result.findings if finding.severity is Severity.ERROR]
    assert errors == [], f"{pdf.name}: {[finding.code for finding in errors]}"


@pytest.mark.parametrize(("pdf", "profile_id"), EVERY)
def test_a_document_the_extractor_cannot_read_is_reported_rather_than_raised(
    pdf: Path, profile_id: str
) -> None:
    """ADR-0005 end to end: every disagreement comes back as a finding with a known code."""
    result = extract(pdf, ProfileRegistry().get(profile_id))
    codes = {finding.code for finding in result.findings}
    known = {*INVARIANT_NAMES, "line_item_incomplete", "line_items_header_not_found"}
    assert codes <= known, sorted(codes - known)


@pytest.mark.parametrize(("pdf", "profile_id"), EVERY)
def test_a_result_names_the_profile_and_the_file_it_came_from(pdf: Path, profile_id: str) -> None:
    result = extract(pdf, ProfileRegistry().get(profile_id))
    assert result.profile_id == profile_id
    assert result.source_path == pdf.as_posix()


@pytest.mark.parametrize(("pdf", "profile_id"), EVERY)
def test_a_value_read_off_the_page_carries_the_evidence_for_it(pdf: Path, profile_id: str) -> None:
    result = extract(pdf, ProfileRegistry().get(profile_id))
    found = [field for field in result.fields.values() if field.value is not None]
    assert found, "a corpus document with no readable field would not be a corpus document"
    assert all(field.evidence is not None for field in found)


@pytest.mark.parametrize(("pdf", "profile_id"), PLAIN)
def test_a_field_no_finding_touched_is_reported_with_confidence(pdf: Path, profile_id: str) -> None:
    result = extract(pdf, ProfileRegistry().get(profile_id))
    touched = {finding.field for finding in result.findings}
    untouched = [
        field
        for name, field in result.fields.items()
        if name not in touched and field.valid and field.evidence is not None
    ]
    assert untouched
    assert all(field.confidence > 0.5 for field in untouched)
