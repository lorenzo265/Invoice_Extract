"""The sixteen signals: what each of them measures, and when a field is not asked it."""

from __future__ import annotations

import dataclasses
import re
from decimal import Decimal

from conftest import line, make_field_profile, make_profile
from invoice_extractor.document.model import Zone
from invoice_extractor.domain.checks import Check
from invoice_extractor.domain.evidence import Evidence, Strategy
from invoice_extractor.domain.models import FieldResult, LineItem
from invoice_extractor.domain.parties import Party
from invoice_extractor.domain.rows import VatSummaryRow
from invoice_extractor.extraction.engine import Extraction
from invoice_extractor.scoring.signals import SIGNAL_NAMES, ScoringContext, extract_signals

DRAWN = line("Invoice Number: INV-42", 400, 76)
TOP_RIGHT = Zone(1, 3)


def extraction(
    value: object = "INV-42",
    raw: str | None = "Invoice Number: INV-42",
    label: str | None = "Invoice Number",
    zone: Zone | None = TOP_RIGHT,
    candidates: int = 1,
    gap: float | None = 0.5,
    valid: bool = True,
    name: str = "invoice_number",
) -> Extraction:
    evidence = None if raw is None else Evidence(1, DRAWN.bbox, label, Strategy.LABEL_RIGHT, raw)
    found = FieldResult(name, value, raw, evidence, valid=valid)  # type: ignore[arg-type]
    return Extraction(found, candidates, zone, gap)


def context(**changes: object) -> ScoringContext:
    made: dict[str, object] = {
        "profile": make_profile(
            fields={"invoice_number": make_field_profile(labels=("Invoice Number",))}
        ),
        "resolved": {},
        "profile_score": 0.8,
        "items": (LineItem(description="A thing", net_amount=Decimal("1.00")),),
        "summary": (),
        "parties": {},
    }
    return ScoringContext(**{**made, **changes})  # type: ignore[arg-type]  # a test names its own


def test_a_field_with_no_value_emits_no_signal_at_all() -> None:
    assert extract_signals(extraction(value=None, raw=None), context()) == {}


def test_every_signal_a_field_emits_is_one_of_the_sixteen() -> None:
    signals = extract_signals(extraction(), context())
    assert set(signals) <= set(SIGNAL_NAMES)
    assert signals["label_found"] == 1.0


def test_a_value_no_label_introduced_says_so_and_is_asked_no_more_about_labels() -> None:
    signals = extract_signals(extraction(label=None), context())
    assert signals["label_found"] == 0.0
    assert "label_similarity" not in signals


def test_a_label_the_profile_declares_word_for_word_is_worth_the_most() -> None:
    signals = extract_signals(extraction(), context())
    assert signals["label_similarity"] == 1.0
    near = extract_signals(extraction(label="Invoice No"), context())
    assert 0.0 < near["label_similarity"] < 1.0


def test_a_validator_that_refused_the_value_says_so() -> None:
    assert extract_signals(extraction(valid=False), context())["value_format_match"] == 0.0


def test_a_pattern_is_only_asked_of_a_field_whose_profile_declares_one() -> None:
    assert "format_pattern_match" not in extract_signals(extraction(), context())
    shaped = make_field_profile(labels=("Invoice Number",), pattern=r"INV-\d+")
    described = context(profile=make_profile(fields={"invoice_number": shaped}))
    assert extract_signals(extraction(), described)["format_pattern_match"] == 1.0
    assert extract_signals(extraction(value="X"), described)["format_pattern_match"] == 0.0


def test_how_near_what_was_read_is_to_what_it_was_read_from() -> None:
    whole = extract_signals(extraction(raw="INV-42"), context())
    assert whole["format_canonical_distance"] == 1.0
    assert whole["length_plausible"] == 1.0
    part = extract_signals(extraction(), context())
    assert part["length_plausible"] < 1.0


def test_text_that_is_all_punctuation_is_not_a_value_to_measure_against() -> None:
    signals = extract_signals(extraction(raw="---"), context())
    assert "format_canonical_distance" not in signals
    assert "length_plausible" not in signals


def test_a_value_read_from_nothing_is_asked_nothing_about_the_text() -> None:
    signals = extract_signals(extraction(raw=None), context())
    assert "format_canonical_distance" not in signals
    assert "length_plausible" not in signals


def test_a_zone_is_only_asked_where_the_profile_expects_one() -> None:
    assert extract_signals(extraction(), context())["zone_match"] == 1.0
    assert extract_signals(extraction(zone=Zone(3, 1)), context())["zone_match"] == 0.0
    assert "zone_match" not in extract_signals(extraction(zone=None), context())


def test_one_candidate_is_certainty_about_where_the_value_came_from() -> None:
    assert extract_signals(extraction(), context())["competing_candidates"] == 1.0
    assert extract_signals(extraction(candidates=4), context())["competing_candidates"] == 0.25
    assert "competing_candidates" not in extract_signals(extraction(candidates=0), context())


def test_nothing_else_in_the_running_is_not_a_close_contest() -> None:
    assert extract_signals(extraction(gap=None), context()).get("runner_up_gap") is None
    assert extract_signals(extraction(gap=0.25), context())["runner_up_gap"] == 0.25


def test_the_rules_that_named_this_field_are_what_corroborates_it() -> None:
    checks = (
        Check("subtotal_plus_vat_equals_total", True, ("invoice_number",), ""),
        Check("dates_in_order", True, ("invoice_number",), ""),
    )
    signals = extract_signals(extraction(), context(checks=checks))
    assert signals["arithmetic_consistency"] == 1.0
    assert signals["cross_field_consistency"] == 1.0
    assert signals["invariant_corroboration"] == 0.5


def test_a_rule_that_failed_about_this_field_is_what_contradicts_it() -> None:
    checks = (Check("subtotal_plus_vat_equals_total", False, ("invoice_number",), ""),)
    assert extract_signals(extraction(), context(checks=checks))["arithmetic_consistency"] == 0.0


def test_a_rule_that_did_not_apply_says_nothing_either_way() -> None:
    checks = (Check("subtotal_plus_vat_equals_total", None, ("invoice_number",), ""),)
    signals = extract_signals(extraction(), context(checks=checks))
    assert "arithmetic_consistency" not in signals
    assert "invariant_corroboration" not in signals


def test_a_rule_about_another_field_says_nothing_about_this_one() -> None:
    checks = (Check("subtotal_plus_vat_equals_total", False, ("subtotal",), ""),)
    assert "arithmetic_consistency" not in extract_signals(extraction(), context(checks=checks))


def test_how_well_the_vendor_was_recognised_is_a_signal_about_every_field() -> None:
    assert extract_signals(extraction(), context())["profile_match"] == 0.8


def test_how_much_of_what_the_vendor_prints_was_read() -> None:
    required = make_field_profile(labels=("Invoice Number",))
    profile = make_profile(fields={"invoice_number": required, "due_date": required})
    read = {"invoice_number": FieldResult("invoice_number", "INV-42", "x", None, valid=True)}
    signals = extract_signals(extraction(), context(profile=profile, resolved=read))
    assert signals["structural_completeness"] == 0.5


def test_a_vendor_that_requires_nothing_is_complete_by_definition() -> None:
    optional = dataclasses.replace(make_field_profile(), required=False)
    profile = make_profile(fields={"invoice_number": optional})
    assert extract_signals(extraction(), context(profile=profile))["structural_completeness"] == 1.0


def test_the_structures_a_document_should_carry_are_counted() -> None:
    assert extract_signals(extraction(), context())["count_plausibility"] == 1.0
    assert extract_signals(extraction(), context(items=()))["count_plausibility"] == 0.0


def test_a_structure_the_vendor_does_not_print_is_not_counted_against_it() -> None:
    profile = make_profile(
        fields={"invoice_number": make_field_profile(labels=("Invoice Number",))},
        vat_summary=make_profile().line_items,
    )
    summarised = context(profile=profile, summary=(VatSummaryRow(rate=Decimal("20")),))
    assert extract_signals(extraction(), summarised)["count_plausibility"] == 1.0


def test_a_party_block_the_profile_describes_is_counted_with_the_rest() -> None:
    profile = make_profile(
        fields={"invoice_number": make_field_profile(labels=("Invoice Number",))},
        parties={"bill_to": _section()},
    )
    read = context(profile=profile, parties={"bill_to": Party(name="Ashgrove Ltd")})
    assert extract_signals(extraction(), read)["count_plausibility"] == 1.0
    assert extract_signals(extraction(), context(profile=profile))["count_plausibility"] == 0.5


def test_a_field_is_only_as_strong_as_the_weakest_thing_said_about_it() -> None:
    signals = extract_signals(extraction(zone=Zone(3, 1)), context())
    assert signals["min_component_strength"] == 0.0


def test_a_custom_field_is_described_by_the_profile_that_declares_it() -> None:
    """A vendor's own extra is a field like any other, and is asked the same questions."""
    profile = dataclasses.replace(
        make_profile(),
        fields={},
        custom_fields=(_custom("contract_number", "Contract"),),
    )
    found = extraction(label="Contract", name="contract_number")
    assert extract_signals(found, context(profile=profile))["label_similarity"] == 1.0


def _section() -> object:
    from invoice_extractor.profile.schema import SectionProfile

    return SectionProfile(
        labels=("Bill to",), stop_labels=(), max_lines=6, placeholders=(), zones=()
    )


def _custom(name: str, label: str) -> object:
    from invoice_extractor.profile.schema import CustomFieldProfile

    return CustomFieldProfile(
        name=name,
        field=dataclasses.replace(
            make_field_profile(labels=(label,)), pattern=re.compile(r"[A-Z0-9-]+")
        ),
    )
