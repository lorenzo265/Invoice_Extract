"""The arithmetic a truth file has to satisfy, re-derived from its own numbers.

These are built by hand rather than rendered, so a policy or a shape the four bundled
profiles do not produce yet — a document rounded on the total, a field the document does
not carry — is still checked.
"""

from __future__ import annotations

from typing import Any

import pytest

from invoice_forge.truth.checks import (
    TRUTH_SCHEMA,
    check_arithmetic,
    check_evidence_rule,
    check_schema,
)
from invoice_forge.truth.reading import TruthError

PAGES = 1


def row(quantity: str, price: str, net: str) -> dict[str, Any]:
    return {"quantity": quantity, "unit_price": price, "net_amount": net}


def field(value: str | None) -> dict[str, Any]:
    return {"value": value, "printed": None, "label": None, "evidence": []}


def truth(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema": TRUTH_SCHEMA,
        "generator": {
            "version": "0.1.0",
            "seed": 1,
            "profile": "en-GB",
            "template": "classic",
            "knobs": [],
        },
        "document": {
            "type": "invoice",
            "pages": PAGES,
            "language": "en",
            "currency": "GBP",
            "secondary_currency": None,
            "rounding": "per_line",
        },
        "fields": {
            "subtotal": field("20.00"),
            "vat_amount": field("3.80"),
            "total_amount": field("23.80"),
        },
        "line_items": [row("2", "10.00", "20.00")],
        "charges": [],
        "vat_summary": [{"rate": "19", "base": "20.00", "vat": "3.80", "evidence": []}],
        "secondary_amounts": None,
        "parties": {},
        "noise": [],
    }
    return {**base, **changes}


def test_a_truth_that_holds_up_has_nothing_to_report() -> None:
    assert check_schema(truth(), PAGES) == []
    assert check_arithmetic(truth()) == []
    assert check_evidence_rule(truth()) == []


def test_a_wrong_line_net_is_named_by_its_position() -> None:
    broken = truth(line_items=[row("2", "10.00", "20.00"), row("3", "5.00", "16.00")])
    complaints = check_arithmetic(broken)
    assert any("line_items[1]" in complaint for complaint in complaints)


def test_the_two_rounding_policies_are_both_re_derived() -> None:
    """Three rows of half a cent: rounded per row they are 0.03, rounded once 0.02."""
    rows = [row("1", "0.005", "0.01") for _ in range(3)]
    fields = {"subtotal": field("0.03"), "vat_amount": field("0.00"), "total_amount": field("0.03")}
    per_line = truth(line_items=rows, fields=fields, vat_summary=[])
    assert check_arithmetic(per_line) == []

    document = {**per_line["document"], "rounding": "total"}
    on_the_total = {**per_line, "document": document}
    assert any("under total" in complaint for complaint in check_arithmetic(on_the_total))


def test_a_document_rounded_on_the_total_adds_up_its_own_way() -> None:
    rows = [row("1", "0.005", "0.01") for _ in range(3)]
    fields = {"subtotal": field("0.02"), "vat_amount": field("0.00"), "total_amount": field("0.02")}
    document = {
        "type": "invoice",
        "pages": PAGES,
        "language": "en",
        "currency": "GBP",
        "secondary_currency": None,
        "rounding": "total",
    }
    assert (
        check_arithmetic(truth(line_items=rows, fields=fields, vat_summary=[], document=document))
        == []
    )


def test_a_declared_charge_joins_the_total() -> None:
    charge = {
        "type": "SHIPPING",
        "amount": "10.00",
        "vat_rate": "19",
        "declared": True,
        "label": "Shipping",
        "evidence": [{"page": 1, "bbox": [1, 2, 3, 4]}],
    }
    fields = {
        "subtotal": field("20.00"),
        "vat_amount": field("5.70"),
        "total_amount": field("35.70"),
    }
    summary = [{"rate": "19", "base": "30.00", "vat": "5.70", "evidence": []}]
    assert check_arithmetic(truth(charges=[charge], fields=fields, vat_summary=summary)) == []


def test_an_undeclared_charge_still_has_to_be_in_the_total() -> None:
    charge = {
        "type": "SHIPPING",
        "amount": "10.00",
        "vat_rate": "19",
        "declared": False,
        "label": None,
        "evidence": [],
    }
    assert any(
        "total_amount" in complaint for complaint in check_arithmetic(truth(charges=[charge]))
    )


def test_a_field_the_document_does_not_carry_is_not_checked() -> None:
    fields = {"subtotal": field(None), "vat_amount": field(None), "total_amount": field(None)}
    assert check_arithmetic(truth(fields=fields)) == []


def test_a_summary_that_does_not_add_to_the_vat_amount_is_reported() -> None:
    summary = [{"rate": "19", "base": "20.00", "vat": "3.00", "evidence": []}]
    complaints = check_arithmetic(truth(vat_summary=summary))
    assert any("vat_summary[0]" in complaint for complaint in complaints)
    assert any("vat_amount" in complaint for complaint in complaints)


def test_a_page_count_that_does_not_match_the_pdf_is_reported() -> None:
    assert any("document.pages" in complaint for complaint in check_schema(truth(), pages=3))


def test_a_generator_block_without_knobs_as_a_list_is_refused() -> None:
    generator = {
        "version": "0.1.0",
        "seed": 1,
        "profile": "en-GB",
        "template": "classic",
        "knobs": "multi_page",
    }
    with pytest.raises(TruthError, match=r"generator.knobs must be a list of strings"):
        check_schema(truth(generator=generator), PAGES)


@pytest.mark.parametrize("key", ["version", "profile", "template"])
def test_a_generator_block_missing_a_name_is_refused(key: str) -> None:
    generator = dict(truth()["generator"])
    del generator[key]
    with pytest.raises(TruthError, match=rf"generator.{key} must be a string"):
        check_schema(truth(generator=generator), PAGES)


def test_a_declared_charge_without_evidence_is_reported() -> None:
    charge = {
        "type": "SHIPPING",
        "amount": "10.00",
        "vat_rate": "19",
        "declared": True,
        "label": "Shipping",
        "evidence": [],
    }
    assert check_evidence_rule(truth(charges=[charge])) == [
        "charges[0] is declared but carries no evidence"
    ]


def test_an_undeclared_charge_with_evidence_is_reported() -> None:
    charge = {
        "type": "SHIPPING",
        "amount": "10.00",
        "vat_rate": "19",
        "declared": False,
        "label": None,
        "evidence": [{"page": 1, "bbox": [1, 2, 3, 4]}],
    }
    assert check_evidence_rule(truth(charges=[charge])) == [
        "charges[0] is undeclared but carries evidence"
    ]
