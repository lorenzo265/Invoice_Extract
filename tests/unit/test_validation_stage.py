"""Stage 6: every rule, recorded whether it held, failed or did not apply."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from conftest import make_profile
from invoice_extractor.domain.findings import Severity
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.profile.schema import Exemption, Invariants
from invoice_extractor.validation.cross_field import CHECK_NAMES
from invoice_extractor.validation.facts import Facts
from invoice_extractor.validation.invariants import INVARIANT_NAMES
from invoice_extractor.validation.stage import EXEMPT, RULE_NAMES, validate

AMOUNTS = {"subtotal": "490.00", "vat_amount": "98.00", "total_amount": "588.00"}


def fields(**overrides: str) -> dict[str, FieldResult]:
    amounts = {**AMOUNTS, **overrides}
    return {
        name: FieldResult(name, Decimal(text), text, None, valid=True)
        for name, text in amounts.items()
    }


def facts(**changes: object) -> Facts:
    made: dict[str, object] = {"profile": make_profile(), "fields": fields()}
    return Facts(**{**made, **changes})  # type: ignore[arg-type]  # a test names its own


def test_every_rule_of_both_families_is_run_and_recorded() -> None:
    _, checks = validate(facts())
    assert tuple(check.code for check in checks) == RULE_NAMES
    assert (*INVARIANT_NAMES, *CHECK_NAMES) == RULE_NAMES


def test_a_rule_that_held_is_a_check_and_not_a_finding() -> None:
    findings, checks = validate(facts())
    held = next(check for check in checks if check.code == "subtotal_plus_vat_equals_total")
    assert held.passed
    assert held.fields == ("subtotal", "vat_amount", "total_amount")
    assert not [finding for finding in findings if finding.code == held.code]


def test_a_rule_that_failed_is_both_a_check_and_a_finding_about_one_field() -> None:
    findings, checks = validate(facts(fields=fields(total_amount="1.00")))
    failed = next(check for check in checks if check.code == "subtotal_plus_vat_equals_total")
    assert failed.passed is False
    finding = next(finding for finding in findings if finding.code == failed.code)
    assert (finding.severity, finding.field) == (Severity.ERROR, "total_amount")
    assert finding.message == failed.detail


def test_a_rule_this_document_cannot_be_asked_is_recorded_as_neither() -> None:
    findings, checks = validate(facts())
    skipped = next(check for check in checks if check.code == "per_rate_vat_consistency")
    assert skipped.passed is None
    assert not [finding for finding in findings if finding.code == skipped.code]


def test_a_vendor_may_be_excused_a_rule_and_the_exemption_is_said_out_loud() -> None:
    """A reverse-charge invoice states no tax and is right not to (ENGINE_SPEC §6)."""
    excused = dataclasses.replace(
        make_profile(),
        invariants=Invariants(
            exempt=(Exemption(code="vat_equals_subtotal_times_rate", reason="reverse charge"),)
        ),
    )
    findings, checks = validate(facts(profile=excused, fields=fields(vat_amount="1.00")))
    check = next(check for check in checks if check.code == "vat_equals_subtotal_times_rate")
    assert check.passed is None
    assert check.detail == "exempt: reverse charge"
    finding = next(finding for finding in findings if finding.code == EXEMPT)
    assert finding.severity is Severity.INFO
    assert "reverse charge" in finding.message


def test_an_exemption_does_not_excuse_the_rules_it_does_not_name() -> None:
    excused = dataclasses.replace(
        make_profile(),
        invariants=Invariants(exempt=(Exemption(code="dates_in_order", reason="undated"),)),
    )
    findings, _ = validate(facts(profile=excused, fields=fields(total_amount="1.00")))
    assert [finding.code for finding in findings if finding.severity is Severity.ERROR] == [
        "subtotal_plus_vat_equals_total"
    ]
