"""What a candidate has to survive before it is ranked."""

from __future__ import annotations

import dataclasses

from conftest import line, make_field_profile, make_profile
from invoice_extractor.document.model import Zone
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.extraction.units.filters import not_a_trap
from invoice_extractor.profile.schema import Noise

TRAPS = Noise(ignore_labels=("Order Date", "Print Date"))


def candidate(text: str, label: str | None = "Invoice Date") -> Candidate:
    drawn = line(text, 400, 76)
    evidence = Evidence(1, drawn.bbox, label, Strategy.LABEL_BESIDE, text)
    return Candidate(raw_text=text, evidence=evidence, zone=Zone(1, 3), label_distance=0.0)


def with_traps() -> object:
    return dataclasses.replace(make_profile(), noise=TRAPS)


def test_a_candidate_a_trap_label_introduced_is_dropped() -> None:
    field = make_field_profile(labels=("Invoice Date",))
    found = [candidate("01.02.2024", label="Order Date")]
    assert not_a_trap(found, field, with_traps()) == []


def test_a_candidate_this_fields_own_label_introduced_is_kept() -> None:
    field = make_field_profile(labels=("Invoice Date",))
    found = [candidate("01.02.2024")]
    assert not_a_trap(found, field, with_traps()) == found


def test_a_label_another_field_calls_a_trap_is_not_a_trap_for_the_field_that_wants_it() -> None:
    """`Lieferdatum` is a trap beside the invoice date and the supply date's own label."""
    field = make_field_profile(labels=("Order Date",))
    found = [candidate("01.02.2024", label="Order Date")]
    assert not_a_trap(found, field, with_traps()) == found


def test_a_line_that_starts_with_a_trap_label_is_dropped() -> None:
    field = make_field_profile(labels=("Invoice Date",))
    found = [candidate("Print Date: 02.02.2024", label=None)]
    assert not_a_trap(found, field, with_traps()) == []


def test_nothing_is_dropped_when_the_vendor_names_no_traps() -> None:
    field = make_field_profile(labels=("Invoice Date",))
    found = [candidate("01.02.2024", label="Order Date")]
    assert not_a_trap(found, field, make_profile()) == found
