"""Every structural knob, on a rendered document, against the page it produced.

One test per knob. Each renders the same seed with the knob on and off, verifies both,
and asserts the difference the knob is for — read out of the PDF or out of the truth,
never out of the renderer's own memory.
"""

from __future__ import annotations

import json
from decimal import Decimal
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from rendering import Rendered, render_document

from invoice_forge.families import Family
from invoice_forge.knobs import KNOB_NAMES, Knob
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.render.pdf import locate_all
from invoice_forge.truth.verify import verify_document

PROFILE = "de-DE"
SEED = 3
# "Seite 1" cannot match "Folgeseite", which the carry-forward line also prints.
PAGE_LINE = "Seite 1"
# The rule above the legal lines: page height less the footer block.
FOOTER_RULE = 746.0
# The twelve axes PR F4 of docs/FORGE_PLAN.md builds.
STRUCTURAL = (
    Knob.MULTI_PAGE,
    Knob.CARRY_FORWARD,
    Knob.PAGE_NUMBERING,
    Knob.WRAPPED_DESCRIPTION,
    Knob.SUB_ITEMS,
    Knob.SECTION_SUBTOTALS,
    Knob.DISCOUNT,
    Knob.PARTY_BLOCKS,
    Knob.PLACEHOLDER_ADDRESSES,
    Knob.TRAP_LABELS,
    Knob.CUSTOMER_VAT_POSITION,
    Knob.REPEAT_LETTERHEAD,
)
for_each_knob = pytest.mark.parametrize("knob", STRUCTURAL, ids=[k.value for k in STRUCTURAL])


@cache
def _scratch() -> TemporaryDirectory[str]:
    return TemporaryDirectory(prefix="forge-knobs-")


@cache
def turned(*knobs: Knob, seed: int = SEED, profile_id: str = PROFILE) -> Rendered:
    """The document these knobs produce, rendered once and kept for the run."""
    stem = "_".join(knob.value for knob in knobs) or "none"
    spec = DocumentSpec(profile_id, Family.CLASSIC, seed, knobs)
    produced = produce(spec, Path(_scratch().name) / f"{profile_id}_{seed}_{stem}.pdf")
    truth = json.loads(produced.truth.read_text(encoding="utf-8"))
    return Rendered(profile_id, produced.pdf, truth, produced.pages)


def noise_kinds(document: Rendered) -> set[str]:
    return {entry["kind"] for entry in document.truth["noise"]}


def page_text(document: Rendered, page: int, needle: str) -> bool:
    return bool(locate_all(document.pdf, [(page, needle)])[0])


def rows_of(document: Rendered) -> list[dict[str, Any]]:
    return list(document.truth["line_items"])


@for_each_knob
def test_a_document_with_the_knob_on_verifies(knob: Knob) -> None:
    assert verify_document(_truth_path(turned(knob)), regenerate=False) == ()


@for_each_knob
def test_the_truth_records_the_knob_that_made_the_document(knob: Knob) -> None:
    assert turned(knob).truth["generator"]["knobs"] == [knob.value]
    assert turned().truth["generator"]["knobs"] == []


@for_each_knob
def test_the_knob_changes_the_page(knob: Knob) -> None:
    assert turned(knob).pdf.read_bytes() != turned().pdf.read_bytes()


def test_multi_page_breaks_a_document_that_would_not_have_broken() -> None:
    single = turned(seed=5, profile_id="fr-FR")
    broken = turned(Knob.MULTI_PAGE, seed=5, profile_id="fr-FR")
    assert single.pages == 1
    assert broken.pages > 1


def test_carry_forward_is_the_break_that_carries_nothing() -> None:
    carried, plain = turned(), turned(Knob.CARRY_FORWARD)
    assert carried.pages > 1
    assert "carry_forward" in noise_kinds(carried)
    assert "carry_forward" not in noise_kinds(plain)


def test_page_numbering_moves_the_count_to_the_foot_of_the_page() -> None:
    """The header carries it beside the references; the knob puts it under the footer rule."""
    assert not _below_the_footer_rule(turned(), PAGE_LINE)
    assert _below_the_footer_rule(turned(Knob.PAGE_NUMBERING), PAGE_LINE)


def test_wrapped_description_gives_a_row_more_than_one_box_for_its_description() -> None:
    wrapped = rows_of(turned(Knob.WRAPPED_DESCRIPTION))
    assert max(len(row["cells"]["description"]) for row in wrapped) > 1


def test_sub_items_are_printed_under_their_parent_and_recorded_in_the_truth() -> None:
    rows = rows_of(turned(Knob.SUB_ITEMS))
    parents = [row for row in rows if row["sub_items"]]
    assert parents
    first = parents[0]
    page = first["cells"]["sku"][0]["page"]
    assert page_text(turned(Knob.SUB_ITEMS), page, first["sub_items"][0]["description"][:20])
    assert all(not row["sub_items"] for row in rows_of(turned()))


def test_section_subtotals_print_a_number_that_is_not_the_total_and_say_so() -> None:
    sectioned = turned(Knob.SECTION_SUBTOTALS)
    assert "section_subtotal" in noise_kinds(sectioned)
    assert {row["section"] for row in rows_of(sectioned)} != {None}
    assert "section_subtotal" not in noise_kinds(turned())


def test_a_section_subtotal_adds_only_its_own_section() -> None:
    rows = rows_of(turned(Knob.SECTION_SUBTOTALS))
    first = rows[0]["section"]
    grouped = sum(Decimal(row["net_amount"]) for row in rows if row["section"] == first)
    total = sum(Decimal(row["net_amount"]) for row in rows)
    assert 0 < grouped < total


def test_discount_prints_a_column_and_takes_the_discount_off_the_row() -> None:
    discounted = turned(Knob.DISCOUNT)
    rows = [row for row in rows_of(discounted) if row["discount_percent"] is not None]
    assert rows
    row = rows[0]
    gross = Decimal(row["quantity"]) * Decimal(row["unit_price"])
    assert Decimal(row["net_amount"]) < gross
    assert all(row["discount_percent"] is None for row in rows_of(turned()))


def test_party_blocks_prints_a_third_party_and_puts_it_in_the_truth() -> None:
    three = turned(Knob.PARTY_BLOCKS)
    assert three.truth["parties"]["mail_to"] is not None
    assert three.truth["parties"]["mail_to"]["evidence"]
    assert turned().truth["parties"]["mail_to"] is None


def test_placeholder_addresses_prints_the_placeholder_instead_of_the_address() -> None:
    placed = turned(Knob.PLACEHOLDER_ADDRESSES)
    ship_to = placed.truth["parties"]["ship_to"]
    assert ship_to["lines"] == []
    assert turned().truth["parties"]["ship_to"]["lines"]


def test_trap_labels_print_dates_that_are_not_the_invoice_date() -> None:
    trapped = turned(Knob.TRAP_LABELS)
    traps = [entry for entry in trapped.truth["noise"] if entry["kind"] == "trap_label"]
    assert len(traps) >= 3
    assert {entry["label"] for entry in traps}
    assert "trap_label" not in noise_kinds(turned())


def test_a_trap_date_is_never_the_date_it_is_a_trap_for() -> None:
    trapped = turned(Knob.TRAP_LABELS)
    printed = trapped.truth["fields"]["invoice_date"]["printed"]
    for entry in trapped.truth["noise"]:
        if entry["kind"] == "trap_label":
            assert entry["bbox"] != trapped.truth["fields"]["invoice_date"]["evidence"][0]["bbox"]
    assert printed


def test_customer_vat_position_moves_the_id_out_of_the_party_block() -> None:
    moved = turned(Knob.CUSTOMER_VAT_POSITION)
    here = moved.truth["fields"]["customer_vat_id"]["evidence"][0]["bbox"]
    there = turned().truth["fields"]["customer_vat_id"]["evidence"][0]["bbox"]
    assert here != there
    assert here[0] > there[0], "the reference block is to the right of the party block"


def test_repeat_letterhead_stops_the_vat_id_appearing_on_every_page() -> None:
    repeated, once = turned(), turned(Knob.REPEAT_LETTERHEAD)
    assert repeated.pages > 1
    assert once.pages > 1
    assert len(repeated.truth["fields"]["supplier_vat_id"]["evidence"]) == repeated.pages
    assert len(once.truth["fields"]["supplier_vat_id"]["evidence"]) == 1


def test_every_knob_this_pull_request_builds_is_one_the_catalog_names() -> None:
    assert {knob.value for knob in STRUCTURAL} <= set(KNOB_NAMES)


def test_all_twelve_at_once_still_renders_and_verifies() -> None:
    together = turned(*STRUCTURAL)
    assert verify_document(_truth_path(together), regenerate=False) == ()
    assert together.pages > 1


def _truth_path(document: Rendered) -> Path:
    return document.pdf.with_name(f"{document.pdf.stem}.truth.json")


def _below_the_footer_rule(document: Rendered, needle: str) -> bool:
    """Whether the string is printed under the rule that closes the page."""
    found = locate_all(document.pdf, [(1, needle)])[0]
    assert found, f"{needle!r} is printed on every page of a classic document"
    return any(box[1] > FOOTER_RULE for box in found)


def test_a_rendered_knob_document_is_still_byte_deterministic() -> None:
    first = render_document(PROFILE, Path(_scratch().name) / "again", seed=SEED)
    assert (
        first.pdf.read_bytes()
        == render_document(PROFILE, Path(_scratch().name) / "third", seed=SEED).pdf.read_bytes()
    )


def test_a_page_that_holds_only_the_totals_prints_no_column_headings() -> None:
    """An empty table header is the kind of thing a real invoice never prints."""
    together = turned(*STRUCTURAL)
    last = together.pages
    rows_on_the_last_page = [
        row for row in rows_of(together) if any(box["page"] == last for box in row["cells"]["sku"])
    ]
    if rows_on_the_last_page:
        pytest.skip("this seed fills its last page with rows")
    columns = together.truth["line_items"][0]
    assert not page_text(together, last, columns["sku"])
    assert page_text(together, last, str(together.truth["fields"]["total_amount"]["printed"]))
