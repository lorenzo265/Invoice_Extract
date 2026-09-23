"""What a candidate has to survive before it is ranked."""

from __future__ import annotations

import dataclasses

from conftest import line, make_field_profile, make_profile
from invoice_extractor.document.model import Zone
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.extraction.specs import SPECS
from invoice_extractor.extraction.units.filters import (
    not_a_label,
    not_a_trap,
    not_the_suppliers_own,
)
from invoice_extractor.profile.schema import (
    CustomFieldProfile,
    FieldProfile,
    Noise,
    Profile,
    SectionProfile,
)

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


def with_supplier(vat_id: str, prefix: str = "GB") -> Profile:
    profile = make_profile()
    return dataclasses.replace(
        profile,
        supplier=dataclasses.replace(profile.supplier, vat_id=vat_id),
        vat=dataclasses.replace(profile.vat, id_prefix=prefix),
    )


def customer_vat_field() -> FieldProfile:
    return make_field_profile(labels=("VAT Reg. No.",))


def test_the_vendors_own_tax_id_is_never_the_customers() -> None:
    found = [candidate("GB123456789", label="VAT Reg. No.")]

    assert not_the_suppliers_own(found, customer_vat_field(), with_supplier("GB123456789")) == []


def test_the_same_id_printed_with_punctuation_is_the_same_id() -> None:
    found = [candidate("GB 123-456-789", label="VAT Reg. No.")]

    assert not_the_suppliers_own(found, customer_vat_field(), with_supplier("GB123456789")) == []


def test_the_same_id_printed_without_the_country_prefix_is_the_same_id() -> None:
    found = [candidate("123456789", label="VAT Reg. No.")]

    assert not_the_suppliers_own(found, customer_vat_field(), with_supplier("GB123456789")) == []


def test_the_vendors_own_tax_id_on_its_labels_line_is_dropped() -> None:
    """`label_right` hands over the whole line, the label included."""
    found = [candidate("VAT Reg. No.: GB123456789", label="VAT Reg. No.")]

    assert not_the_suppliers_own(found, customer_vat_field(), with_supplier("GB123456789")) == []


def test_the_customers_own_id_on_its_labels_line_survives() -> None:
    found = [candidate("VAT Reg. No.: GB987654321", label="VAT Reg. No.")]

    assert not_the_suppliers_own(found, customer_vat_field(), with_supplier("GB123456789")) == found


def test_the_customers_own_id_under_the_same_label_survives() -> None:
    found = [candidate("GB987654321", label="VAT Reg. No.")]

    assert not_the_suppliers_own(found, customer_vat_field(), with_supplier("GB123456789")) == found


def test_a_vendor_that_states_no_tax_id_of_its_own_filters_nothing() -> None:
    found = [candidate("GB123456789", label="VAT Reg. No.")]

    assert not_the_suppliers_own(found, customer_vat_field(), with_supplier("")) == found


def test_the_customers_vat_id_asks_for_the_filter() -> None:
    spec = next(one for one in SPECS if one.name == "customer_vat_id")

    assert "not_the_suppliers_own" in spec.filters
