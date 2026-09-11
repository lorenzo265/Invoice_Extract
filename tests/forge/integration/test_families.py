"""The four families that are `classic` with blocks restyled or switched off.

`docs/FORGE_SPEC.md` §3.3 defines each by what it declares, and these hold the rendered
document to that definition — read out of the PDF and the truth, not out of the spec.
Every one of them goes through the same renderer, which is the claim being tested.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from rendering import Rendered, for_each_pair, rendered

from invoice_forge.families import Family
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.profiles.loader import bundled_profile_ids, load_profile
from invoice_forge.render.pdf import locate_all
from invoice_forge.truth.verify import verify_document

# The right-hand column of the reference block; a stacked value starts left of it.
VALUE_EDGE = 400.0


def truth_path(document: Rendered) -> Path:
    return document.pdf.with_name(f"{document.pdf.stem}.truth.json")


def field_box(document: Rendered, name: str) -> list[float]:
    entry = document.truth["fields"][name]
    assert entry["evidence"], f"{name} carries no evidence"
    return list(entry["evidence"][0]["bbox"])


def page_holds(document: Rendered, needle: str, page: int = 1) -> bool:
    return bool(locate_all(document.pdf, [(page, needle)])[0])


@for_each_pair
def test_every_pair_renders_and_verifies(profile_id: str, family: Family) -> None:
    assert verify_document(truth_path(rendered(profile_id, family)), regenerate=False) == ()


@for_each_pair
def test_the_truth_records_the_family_that_made_the_document(
    profile_id: str, family: Family
) -> None:
    assert rendered(profile_id, family).truth["generator"]["template"] == family.value


@for_each_pair
def test_every_pair_prints_the_fields_an_invoice_cannot_do_without(
    profile_id: str, family: Family
) -> None:
    """However much a family switches off, these are on the page and located."""
    document = rendered(profile_id, family)
    for name in ("invoice_number", "invoice_date", "total_amount", "supplier_vat_id"):
        assert document.truth["fields"][name]["value"] is not None, name
        assert document.truth["fields"][name]["evidence"], name


@pytest.mark.parametrize("profile_id", bundled_profile_ids())
def test_a_family_changes_the_page_without_changing_what_is_billed(profile_id: str) -> None:
    """Two families, one seed: the same rows and the same total, a different page."""
    classic = rendered(profile_id, Family.CLASSIC)
    tabular = rendered(profile_id, Family.TABULAR)
    assert classic.pdf.read_bytes() != tabular.pdf.read_bytes()
    assert _row_values(classic) == _row_values(tabular)
    assert _total(classic) == _total(tabular)


def test_tabular_sets_its_references_further_apart_to_leave_room_for_the_rules() -> None:
    """The first row starts where a list starts; every row after it is a rule lower."""
    listed = rendered("de-DE", Family.CLASSIC)
    boxed = rendered("de-DE", Family.TABULAR)
    assert field_box(listed, "invoice_number") == field_box(boxed, "invoice_number")
    assert field_box(boxed, "due_date")[1] > field_box(listed, "due_date")[1]


def test_tabular_prints_a_code_beside_every_rate() -> None:
    """The summary is on the last page, and a coded one carries a heading a list has not."""
    coded = rendered("de-DE", Family.TABULAR)
    headings = load_lexicon(load_profile("de-DE").lexicon).vat_summary_headers["code"]
    assert coded.truth["vat_summary"]
    assert any(page_holds(coded, heading, coded.pages) for heading in headings)


def test_stacked_puts_no_value_to_the_right_of_its_label() -> None:
    """The layout that defeats "the value is to the right of the label"."""
    listed = rendered("de-DE", Family.CLASSIC)
    above = rendered("de-DE", Family.STACKED)
    assert field_box(listed, "invoice_number")[0] > VALUE_EDGE
    assert field_box(above, "invoice_number")[0] < VALUE_EDGE


def test_stacked_draws_an_unruled_table_that_still_carries_every_cell() -> None:
    above = rendered("de-DE", Family.STACKED)
    for row in above.truth["line_items"]:
        assert row["cells"]["description"]
        assert row["cells"]["net_amount"]


def test_saas_bills_subscriptions_and_prints_their_periods() -> None:
    subscribed = rendered("de-DE", Family.SAAS)
    first = subscribed.truth["line_items"][0]
    page = first["cells"]["description"][0]["page"]
    assert page_holds(subscribed, "SUB-", page)


def test_saas_groups_its_rows_into_sections_with_their_own_subtotals() -> None:
    """The family implies the content, so no knob has to be named for it."""
    subscribed = rendered("de-DE", Family.SAAS)
    assert subscribed.truth["generator"]["knobs"] == []
    assert {row["section"] for row in subscribed.truth["line_items"]} != {None}
    assert "section_subtotal" in {entry["kind"] for entry in subscribed.truth["noise"]}


def test_minimal_prints_one_party_no_summary_no_bank_block_and_no_footer() -> None:
    bare = rendered("sv-SE", Family.MINIMAL)
    assert bare.truth["parties"]["bill_to"] is not None
    assert not bare.truth["parties"]["ship_to"]["evidence"]
    assert bare.truth["vat_summary"], "the document is still taxed; it just prints no summary"
    assert all(not line["evidence"] for line in bare.truth["vat_summary"])
    assert bare.truth["noise"] == []
    assert not page_holds(bare, "IBAN", bare.pages)


def test_minimal_still_adds_up_and_still_says_what_is_owed() -> None:
    bare = rendered("sv-SE", Family.MINIMAL)
    fields = bare.truth["fields"]
    parts = (Decimal(str(fields["subtotal"]["value"])), Decimal(str(fields["vat_amount"]["value"])))
    assert Decimal(str(fields["total_amount"]["value"])) == sum(parts)
    assert fields["total_amount"]["evidence"]


def test_a_family_a_profile_does_not_declare_is_a_pair_nothing_renders() -> None:
    """`forge catalog` reports profile against family, so the two lists have to agree."""
    for profile_id in bundled_profile_ids():
        declared = set(load_profile(profile_id).families)
        assert declared <= set(Family)
        assert Family.CLASSIC in declared, profile_id


def _row_values(document: Rendered) -> list[tuple[str, str]]:
    return [(row["sku"], row["net_amount"]) for row in document.truth["line_items"]]


def _total(document: Rendered) -> Decimal:
    return Decimal(str(document.truth["fields"]["total_amount"]["value"]))
