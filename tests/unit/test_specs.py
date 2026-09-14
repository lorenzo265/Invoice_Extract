"""The declared fields, and the checks that run when they are imported."""

from __future__ import annotations

import pytest

from invoice_extractor.domain.models import VALUE_TYPES
from invoice_extractor.extraction.spec import (
    AnchorSpec,
    DerivedSpec,
    LabelSpec,
    SpecError,
    SpecKind,
    validate,
)
from invoice_extractor.extraction.specs import FIELD_ORDER, SPECS
from invoice_extractor.extraction.units.derivations import DERIVATIONS

BY_LABEL = ("valid_first", "zone_priority", "closest_to_label", "top_most")


def a_spec(**changed: object) -> LabelSpec:
    declared = {
        "name": "invoice_number",
        "normalizer": "strip_label",
        "validator": "is_identifier",
        "rankers": BY_LABEL,
    }
    return LabelSpec(**{**declared, **changed})  # type: ignore[arg-type]


def test_every_declared_field_is_typed_by_the_result_model() -> None:
    assert set(FIELD_ORDER) <= set(VALUE_TYPES)


def test_no_field_is_declared_twice() -> None:
    assert len(set(FIELD_ORDER)) == len(FIELD_ORDER)


def test_every_spec_knows_which_kind_it_is() -> None:
    assert {spec.kind for spec in SPECS} == {SpecKind.LABEL, SpecKind.ANCHOR, SpecKind.DERIVED}


def test_the_shipped_specs_pass_the_check_that_runs_at_import() -> None:
    validate(SPECS, DERIVATIONS)


def test_a_spec_naming_a_normalizer_nobody_registered_is_refused() -> None:
    with pytest.raises(SpecError, match="names normalizer 'guess'"):
        validate((a_spec(normalizer="guess"),), DERIVATIONS)


def test_a_spec_naming_a_validator_nobody_registered_is_refused() -> None:
    with pytest.raises(SpecError, match="names validator 'looks_right'"):
        validate((a_spec(validator="looks_right"),), DERIVATIONS)


def test_a_spec_naming_a_ranker_nobody_registered_is_refused() -> None:
    with pytest.raises(SpecError, match="names ranker 'by_vibes'"):
        validate((a_spec(rankers=("by_vibes",)),), DERIVATIONS)


def test_a_spec_naming_a_filter_nobody_registered_is_refused() -> None:
    with pytest.raises(SpecError, match="names filter 'tidy'"):
        validate((a_spec(filters=("tidy",)),), DERIVATIONS)


def test_a_spec_reading_from_somewhere_that_is_not_a_source_is_refused() -> None:
    with pytest.raises(SpecError, match="names source 'guesswork'"):
        validate((a_spec(source="guesswork"),), DERIVATIONS)


def test_an_anchor_expecting_something_no_profile_holds_is_refused() -> None:
    spec = AnchorSpec(
        name="supplier_vat_id",
        expected="supplier.favourite_colour",
        normalizer="upper_alnum",
        validator="is_vat_id",
    )
    with pytest.raises(SpecError, match="names expected value"):
        validate((spec,), DERIVATIONS)


def test_a_derived_spec_naming_no_derivation_is_refused() -> None:
    with pytest.raises(SpecError, match="names derivation 'divination'"):
        validate((DerivedSpec(name="currency", derive="divination"),), DERIVATIONS)


def test_two_specs_with_one_name_are_refused() -> None:
    with pytest.raises(SpecError, match="is declared twice"):
        validate((a_spec(), a_spec()), DERIVATIONS)


def test_a_dependency_no_spec_resolves_is_refused() -> None:
    with pytest.raises(SpecError, match="depends on 'nothing'"):
        validate((a_spec(depends_on=("nothing",)),), DERIVATIONS)


def test_a_dependency_another_spec_resolves_is_accepted() -> None:
    validate((a_spec(name="first"), a_spec(name="second", depends_on=("first",))), DERIVATIONS)
