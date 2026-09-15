"""A rendered document says what its truth says it says, in the place the truth says.

This is what `forge verify` does over a whole corpus; here it holds the renderer and the
truth builder to each other on one `classic` document per profile, with no knob on.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from make_forge_goldens import GOLDEN_SEED
from rendering import for_each_profile, render_document, rendered

from invoice_forge.families import Family
from invoice_forge.fields import LINE_ITEM_COLUMNS, TRUTH_FIELDS
from invoice_forge.knobs import Knob
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.profiles.loader import load_profile
from invoice_forge.render.pdf import locate_all
from invoice_forge.truth.builder import TRUTH_SCHEMA

CENT = Decimal("0.01")
# A seed whose document is short enough that the echo has room under the totals.
ECHO_SEED = 5


def evidence_of(entry: dict[str, object]) -> list[dict[str, object]]:
    found = entry["evidence"]
    assert isinstance(found, list)
    return found


@for_each_profile
def test_the_truth_declares_the_schema_it_keeps(profile_id: str) -> None:
    document = rendered(profile_id)
    assert document.truth["schema"] == TRUTH_SCHEMA


@for_each_profile
def test_the_generator_block_names_the_cell_that_made_it(profile_id: str) -> None:
    document = rendered(profile_id)
    generator = document.truth["generator"]
    assert generator["profile"] == document.profile_id
    assert generator["template"] == "classic"
    assert generator["seed"] == GOLDEN_SEED
    assert generator["knobs"] == []


@for_each_profile
def test_the_document_block_agrees_with_the_pdf(profile_id: str) -> None:
    document = rendered(profile_id)
    profile = load_profile(document.profile_id)
    block = document.truth["document"]
    assert block["pages"] == document.pages
    assert block["language"] == profile.language
    assert block["currency"] == profile.currency
    assert block["type"] == "invoice"


@for_each_profile
def test_every_canonical_field_name_is_present(profile_id: str) -> None:
    document = rendered(profile_id)
    assert tuple(document.truth["fields"]) == TRUTH_FIELDS


@for_each_profile
def test_a_field_the_document_does_not_carry_says_so_in_every_way(profile_id: str) -> None:
    document = rendered(profile_id)
    for name, entry in document.truth["fields"].items():
        if entry["value"] is None:
            assert entry["printed"] is None, name
            assert entry["label"] is None, name
            assert evidence_of(entry) == [], name


@for_each_profile
def test_a_field_the_document_carries_was_printed_and_located(profile_id: str) -> None:
    document = rendered(profile_id)
    carried = {name: entry for name, entry in document.truth["fields"].items() if entry["value"]}
    assert len(carried) >= 10
    for name, entry in carried.items():
        assert entry["printed"], name
        assert evidence_of(entry), name


def alnum(text: str) -> str:
    """Letters and digits only, upper-cased — separators, labels and spacing removed."""
    return "".join(character for character in text if character.isalnum()).upper()


@for_each_profile
def test_the_printed_string_of_every_field_contains_its_value(profile_id: str) -> None:
    """The normalised value is what the extractor should reach; the page shows it.

    Dates are the one pair that cannot be compared this way: the truth is ISO-8601 and
    the page is whatever format the profile declared.
    """
    document = rendered(profile_id)
    for name, entry in document.truth["fields"].items():
        if entry["value"] is None or name.endswith("_date"):
            continue
        assert alnum(str(entry["value"])) in alnum(str(entry["printed"])), name


@for_each_profile
def test_every_evidence_box_really_holds_that_string(profile_id: str) -> None:
    """The strongest claim the truth makes: read the PDF back and find it there."""
    document = rendered(profile_id)
    queries = []
    boxes = []
    for entry in document.truth["fields"].values():
        for found in evidence_of(entry):
            queries.append((found["page"], str(entry["printed"])))
            boxes.append(tuple(found["bbox"]))
    located = locate_all(document.pdf, queries)
    for (page, text), box, hits in zip(queries, boxes, located, strict=True):
        assert box in hits, f"{text!r} is not at {box} on page {page}"


@for_each_profile
def test_every_row_is_in_the_truth_with_a_box_for_every_column(profile_id: str) -> None:
    document = rendered(profile_id)
    rows = document.truth["line_items"]
    assert rows
    for row in rows:
        for column in LINE_ITEM_COLUMNS:
            assert row["cells"][column], f"row {row['pos']} has no box for {column}"


@for_each_profile
def test_the_rows_are_numbered_from_one_in_order(profile_id: str) -> None:
    document = rendered(profile_id)
    assert [row["pos"] for row in document.truth["line_items"]] == list(
        range(1, len(document.truth["line_items"]) + 1)
    )


@for_each_profile
def test_every_row_net_is_its_quantity_times_its_price(profile_id: str) -> None:
    document = rendered(profile_id)
    for row in document.truth["line_items"]:
        exact = Decimal(row["quantity"]) * Decimal(row["unit_price"])
        assert abs(exact - Decimal(row["net_amount"])) <= CENT, row["pos"]


@for_each_profile
def test_the_totals_recompute_from_the_rows(profile_id: str) -> None:
    document = rendered(profile_id)
    fields = document.truth["fields"]
    rows = sum(Decimal(row["net_amount"]) for row in document.truth["line_items"])
    assert rows == Decimal(str(fields["subtotal"]["value"]))


@for_each_profile
def test_the_total_is_the_subtotal_the_charges_and_the_tax(profile_id: str) -> None:
    document = rendered(profile_id)
    fields = document.truth["fields"]
    charges = sum(Decimal(charge["amount"]) for charge in document.truth["charges"])
    expected = (
        Decimal(str(fields["subtotal"]["value"]))
        + charges
        + Decimal(str(fields["vat_amount"]["value"]))
    )
    assert expected == Decimal(str(fields["total_amount"]["value"]))


@for_each_profile
def test_every_vat_line_is_its_rate_applied_to_its_base(profile_id: str) -> None:
    document = rendered(profile_id)
    lines = document.truth["vat_summary"]
    assert lines
    for line in lines:
        expected = Decimal(line["base"]) * Decimal(line["rate"]) / Decimal(100)
        assert abs(expected - Decimal(line["vat"])) <= CENT, line["rate"]


@for_each_profile
def test_the_vat_lines_add_up_to_the_vat_amount(profile_id: str) -> None:
    document = rendered(profile_id)
    charged = sum(Decimal(line["vat"]) for line in document.truth["vat_summary"])
    assert charged == Decimal(str(document.truth["fields"]["vat_amount"]["value"]))


@for_each_profile
def test_an_unknobbed_document_carries_no_charge_at_all(profile_id: str) -> None:
    assert rendered(profile_id).truth["charges"] == []


@for_each_profile
def test_a_declared_charge_carries_evidence_and_an_undeclared_one_does_not(
    profile_id: str, tmp_path: Path
) -> None:
    """Both halves of the evidence rule, on the one document that asks for both charges."""
    knobs = (Knob.DECLARED_CHARGE, Knob.UNDECLARED_CHARGE)
    spec = DocumentSpec(profile_id, Family.CLASSIC, ECHO_SEED, knobs)
    produced = produce(spec, tmp_path / f"{profile_id}_charged.pdf")
    charges = json.loads(produced.truth.read_text(encoding="utf-8"))["charges"]
    assert [charge["declared"] for charge in charges] == [True, False]
    declared, undeclared = charges
    assert declared["evidence"] and declared["label"]
    assert not undeclared["evidence"] and undeclared["label"] is None


@for_each_profile
def test_the_parties_the_document_names_are_in_the_truth(profile_id: str) -> None:
    document = rendered(profile_id)
    parties = document.truth["parties"]
    for kind in ("supplier", "bill_to", "ship_to"):
        assert parties[kind] is not None, kind
        assert parties[kind]["name"]
        assert parties[kind]["lines"]
        assert parties[kind]["evidence"], kind
    assert parties["mail_to"] is None


@for_each_profile
def test_the_noise_a_classic_document_prints_is_recorded(profile_id: str) -> None:
    """Legal lines on every page, and a carried subtotal wherever the table breaks."""
    document = rendered(profile_id)
    kinds = {entry["kind"] for entry in document.truth["noise"]}
    assert kinds <= {"footer_legal", "carry_forward"}
    assert "footer_legal" in kinds
    assert ("carry_forward" in kinds) == (document.pages > 1)


@for_each_profile
def test_a_document_echoes_no_second_currency_unless_it_is_asked_to(profile_id: str) -> None:
    """The echo is an axis of its own, so an unknobbed document has none of it."""
    assert rendered(profile_id).truth["secondary_amounts"] is None


@for_each_profile
def test_a_secondary_currency_is_echoed_where_the_knob_asks_and_the_vendor_has_one(
    profile_id: str, tmp_path: Path
) -> None:
    spec = DocumentSpec(profile_id, Family.CLASSIC, ECHO_SEED, (Knob.DUAL_CURRENCY_ECHO,))
    produced = produce(spec, tmp_path / f"{profile_id}.pdf")
    truth = json.loads(produced.truth.read_text(encoding="utf-8"))
    profile = load_profile(profile_id)
    echo = truth["secondary_amounts"]
    if profile.secondary_currency is None:
        assert echo is None
        return
    assert echo["currency"] == profile.secondary_currency
    assert echo["evidence"]
    total = Decimal(str(truth["fields"]["total_amount"]["value"]))
    expected = total * Decimal(echo["exchange_rate"])
    assert abs(expected - Decimal(echo["total_amount"])) <= CENT


@for_each_profile
def test_the_same_seed_produces_the_same_bytes(profile_id: str, tmp_path: Path) -> None:
    """Determinism is the whole contract: a corpus is its plan, not its files."""
    first = render_document(profile_id, tmp_path / "first")
    second = render_document(profile_id, tmp_path / "second")
    assert first.pdf.read_bytes() == second.pdf.read_bytes()
    assert first.truth == second.truth


@for_each_profile
def test_a_different_seed_produces_a_different_document(profile_id: str, tmp_path: Path) -> None:
    first = render_document(profile_id, tmp_path / "first", seed=1)
    second = render_document(profile_id, tmp_path / "second", seed=2)
    assert first.pdf.read_bytes() != second.pdf.read_bytes()
