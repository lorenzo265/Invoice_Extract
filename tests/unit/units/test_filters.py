"""What a candidate has to survive before it is ranked."""

from __future__ import annotations

import dataclasses

from conftest import line, make_field_profile, make_profile
from invoice_extractor.document.model import Zone
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.extraction.units.filters import not_a_label, not_a_trap
from invoice_extractor.profile.schema import CustomFieldProfile, Noise, SectionProfile

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


def with_labels() -> object:
    """A vendor that prints its values at a tab stop, so the line under a label is a label."""
    fields = {"due_date": make_field_profile(labels=("Payment Date",))}
    terms = CustomFieldProfile("payment_terms", make_field_profile(labels=("Payment Terms",)))
    heading = SectionProfile(("Bill To",), (), 6, (), ())
    return dataclasses.replace(
        make_profile(fields=fields), custom_fields=(terms,), parties={"bill_to": heading}
    )


def test_a_candidate_that_is_only_another_fields_label_is_dropped() -> None:
    """Under `Payment Terms:` the vendor prints `Payment Date:`, which introduces the next
    value and is not this one."""
    field = make_field_profile(labels=("Payment Terms",))
    found = [candidate("Payment Date:", label="Payment Terms")]
    assert not_a_label(found, field, with_labels()) == []


def test_a_candidate_that_is_another_label_and_its_own_value_is_dropped() -> None:
    field = make_field_profile(labels=("Payment Terms",))
    found = [candidate("Payment Date: 30.07.2026", label="Payment Terms")]
    assert not_a_label(found, field, with_labels()) == []


def test_a_candidate_that_is_a_party_heading_is_dropped() -> None:
    field = make_field_profile(labels=("Payment Terms",))
    found = [candidate("Bill To:", label="Payment Terms")]
    assert not_a_label(found, field, with_labels()) == []


def test_a_candidate_this_fields_own_label_introduces_is_kept() -> None:
    """`Terms: 30 days` is the field's own label and its value, however it was found."""
    field = make_field_profile(labels=("Payment Terms", "Terms"))
    found = [candidate("Terms: 30 days", label=None)]
    assert not_a_label(found, field, with_labels()) == found


def test_a_value_is_kept_however_much_it_resembles_a_label() -> None:
    field = make_field_profile(labels=("Payment Terms",))
    found = [candidate("Payment within 30 days", label="Payment Terms")]
    assert not_a_label(found, field, with_labels()) == found
