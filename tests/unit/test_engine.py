"""One runner, every spec kind: what it collects, how it judges, what it publishes."""

from __future__ import annotations

import dataclasses

import pytest

from conftest import make_document, make_field_profile, make_profile
from invoice_extractor.domain.models import Strategy
from invoice_extractor.extraction.engine import order, run
from invoice_extractor.extraction.spec import AnchorSpec, DerivedSpec, LabelSpec, OnFailure

BY_LABEL = ("valid_first", "zone_priority", "closest_to_label", "top_most")


def number_spec(**changed: object) -> LabelSpec:
    declared = {
        "name": "invoice_number",
        "normalizer": "strip_label",
        "validator": "is_identifier",
        "rankers": BY_LABEL,
    }
    return LabelSpec(**{**declared, **changed})  # type: ignore[arg-type]


def profile_with(labels: tuple[str, ...] = ("Invoice Number",)) -> object:
    fields = {"invoice_number": make_field_profile(labels=labels)}
    return dataclasses.replace(make_profile(), fields=fields)


def page(*texts: str) -> object:
    return make_document(
        [
            (1, text, 400.0, 60.0 + index * 20, 540.0, 74.0 + index * 20)
            for index, text in enumerate(texts)
        ]
    )


def test_a_label_spec_publishes_the_value_beside_its_label() -> None:
    found = run(number_spec(), page("Invoice Number: INV-2024-0042"), profile_with(), {})
    assert found.field.value == "INV-2024-0042"
    assert found.field.valid
    assert found.field.evidence is not None
    assert found.field.evidence.strategy is Strategy.LABEL_RIGHT


def test_a_field_the_vendor_does_not_declare_is_not_found() -> None:
    bare = dataclasses.replace(make_profile(), fields={})
    found = run(number_spec(), page("Invoice Number: INV-42"), bare, {})
    assert found.field.value is None
    assert found.candidate_count == 0


def test_nothing_found_is_reported_as_not_found() -> None:
    found = run(number_spec(), page("nothing here"), profile_with(), {})
    assert found.field.value is None
    assert not found.field.valid
    assert found.field.evidence is None


def test_a_spec_may_ask_for_the_best_invalid_candidate_instead() -> None:
    spec = number_spec(on_failure=OnFailure.BEST_INVALID)
    found = run(spec, page("Invoice Number: X"), profile_with(), {})
    assert found.field.raw_text == "Invoice Number: X"
    assert not found.field.valid


def test_a_valid_candidate_beats_an_invalid_one_wherever_it_sits() -> None:
    document = page("Invoice Number: X", "Invoice Number: INV-2024-0042")
    found = run(number_spec(), document, profile_with(), {})
    assert found.field.value == "INV-2024-0042"


def test_an_anchor_spec_finds_the_value_its_profile_already_expected() -> None:
    spec = AnchorSpec(
        name="supplier_vat_id",
        expected="supplier.vat_id",
        normalizer="upper_alnum",
        validator="is_vat_id",
    )
    profile = dataclasses.replace(
        make_profile(),
        supplier=dataclasses.replace(make_profile().supplier, vat_id="GB123456789"),
    )
    found = run(spec, page("VAT Number: GB123456789"), profile, {})
    assert found.field.value == "GB123456789"
    assert found.field.evidence is not None
    assert found.field.evidence.strategy is Strategy.ANCHOR


def test_an_anchor_spec_may_ask_for_the_vendors_name_and_finds_an_alias_of_it() -> None:
    """A document that prints a name the vendor also trades under prints the vendor."""
    spec = AnchorSpec(
        name="supplier_name",
        expected="supplier.name",
        normalizer="upper_alnum",
        validator="is_identifier",
    )
    supplier = dataclasses.replace(make_profile().supplier, name="Acme Ltd", aliases=("Acme",))
    profile = dataclasses.replace(make_profile(), supplier=supplier)
    found = run(spec, page("Acme"), profile, {})
    assert found.field.value == "ACME"
    assert found.field.valid


def test_a_field_the_vendor_prints_to_a_pattern_is_looked_for_by_that_pattern() -> None:
    """A label may be missing from a line the value is unmistakable on its own."""
    spec = number_spec()
    fields = {"invoice_number": make_field_profile(labels=("Rechnungsnummer",), pattern=r"R-\d{4}")}
    profile = dataclasses.replace(make_profile(), fields=fields)
    found = run(spec, page("R-2024"), profile, {})
    assert found.field.value == "R-2024"
    assert found.field.evidence is not None
    assert found.field.evidence.strategy is Strategy.LABEL_PATTERN


def test_a_derived_spec_publishes_what_it_computed_with_evidence_for_it() -> None:
    spec = DerivedSpec(name="currency", derive="currency")
    found = run(spec, page("Total 100.00 GBP"), make_profile(), {})
    assert found.field.value == "GBP"
    assert found.field.evidence is not None
    assert found.field.evidence.strategy is Strategy.DERIVED


def test_a_derivation_that_computes_nothing_is_not_found() -> None:
    spec = DerivedSpec(name="currency", derive="currency")
    found = run(spec, page("no money here"), make_profile(), {})
    assert found.field.value is None


def test_order_puts_a_field_before_the_ones_derived_from_it() -> None:
    first = number_spec()
    second = DerivedSpec(name="currency", derive="currency", depends_on=("invoice_number",))
    assert [spec.name for spec in order((second, first))] == ["invoice_number", "currency"]


def test_order_keeps_the_declared_order_between_independent_specs() -> None:
    specs = (number_spec(name="a"), number_spec(name="b"), number_spec(name="c"))
    assert [spec.name for spec in order(specs)] == ["a", "b", "c"]


def test_order_refuses_specs_that_depend_on_each_other() -> None:
    left = number_spec(name="a", depends_on=("b",))
    right = number_spec(name="b", depends_on=("a",))
    with pytest.raises(ValueError, match="depend on each other"):
        order((left, right))
