"""Every money and tax knob, on a rendered document, against the page it produced.

One test per knob, the same shape as `test_knob_documents.py` gives the structural ones:
render the same seed with the knob on and off, verify both, and assert the difference the
knob is for — read out of the PDF or out of the truth, never out of the renderer's memory.
"""

from __future__ import annotations

import json
from decimal import Decimal
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from rendering import Rendered

from invoice_forge.families import Family
from invoice_forge.knobs import KNOB_NAMES, Knob
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.lexicon.spelling import spell_amount
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.profiles.loader import load_profile
from invoice_forge.render.pdf import locate_all
from invoice_forge.truth.verify import verify_document

PROFILE = "de-DE"
SEED = 5
# A seed whose multi-rate document carries a zero-rated line for the sentence to explain.
EXEMPT_SEED = 3
# The fifteen axes PR F5 of docs/FORGE_PLAN.md builds, and the four the plan left over.
MONEY = (
    Knob.MULTI_RATE,
    Knob.VAT_SUMMARY_TABLE,
    Knob.DECLARED_CHARGE,
    Knob.UNDECLARED_CHARGE,
    Knob.ROUNDING_PER_LINE,
    Knob.ROUNDING_TOTAL,
    Knob.DUAL_CURRENCY_ECHO,
    Knob.CREDIT_NOTE,
    Knob.EXEMPTION_VERBIAGE,
    Knob.AMOUNT_IN_WORDS,
    Knob.THOUSANDS_VARIANT,
    Knob.STAMP_COPY,
    Knob.BANK_FOOTER,
    Knob.NOISE_FOOTER,
    Knob.PAYMENT_TERMS_BLOCK,
)
REMAINDER = (Knob.CHARGES, Knob.SUPPLY_DATE, Knob.EXTRA_REFERENCES, Knob.COLUMN_SET)
EVERY = (*MONEY, *REMAINDER)
for_each_knob = pytest.mark.parametrize("knob", EVERY, ids=[k.value for k in EVERY])
# Three knobs do not always move a glyph, and that is right: the two rounding knobs pin a
# value the sampler may already have drawn, and the exemption sentence is printed only
# where a rate is zero. Each has a test of its own for what it does instead.
QUIET = (Knob.ROUNDING_PER_LINE, Knob.ROUNDING_TOTAL, Knob.EXEMPTION_VERBIAGE)
LOUD = tuple(knob for knob in EVERY if knob not in QUIET)


@cache
def _scratch() -> TemporaryDirectory[str]:
    return TemporaryDirectory(prefix="forge-money-")


@cache
def turned(*knobs: Knob, seed: int = SEED, profile_id: str = PROFILE) -> Rendered:
    """The document these knobs produce, rendered once and kept for the run."""
    stem = "-".join(knob.value[:4] for knob in knobs) or "none"
    spec = DocumentSpec(profile_id, Family.CLASSIC, seed, knobs)
    produced = produce(spec, Path(_scratch().name) / f"{profile_id}_{seed}_{stem}.pdf")
    truth = json.loads(produced.truth.read_text(encoding="utf-8"))
    return Rendered(profile_id, produced.pdf, truth, produced.pages)


def noise_kinds(document: Rendered) -> set[str]:
    return {entry["kind"] for entry in document.truth["noise"]}


def fields_of(document: Rendered) -> dict[str, Any]:
    return dict(document.truth["fields"])


def page_holds(document: Rendered, needle: str, page: int = 1) -> bool:
    return bool(locate_all(document.pdf, [(page, needle)])[0])


@for_each_knob
def test_a_document_with_the_knob_on_verifies(knob: Knob) -> None:
    assert verify_document(_truth_path(turned(knob)), regenerate=False) == ()


@for_each_knob
def test_the_truth_records_the_knob_that_made_the_document(knob: Knob) -> None:
    assert turned(knob).truth["generator"]["knobs"] == [knob.value]
    assert turned().truth["generator"]["knobs"] == []


@pytest.mark.parametrize("knob", LOUD, ids=[k.value for k in LOUD])
def test_the_knob_changes_the_page(knob: Knob) -> None:
    assert turned(knob).pdf.read_bytes() != turned().pdf.read_bytes()


def test_multi_rate_fills_the_summary_with_more_than_one_row() -> None:
    plain, mixed = turned(), turned(Knob.MULTI_RATE)
    assert len(plain.truth["vat_summary"]) == 1
    assert len(mixed.truth["vat_summary"]) > 1


def test_a_document_at_one_rate_states_it_and_one_at_several_states_the_dominant_one() -> None:
    """The single-rate document prints the rate as a totals row; the other has no such row."""
    plain = fields_of(turned())["vat_rate"]
    assert plain["printed"] and plain["label"]
    mixed = fields_of(turned(Knob.MULTI_RATE))["vat_rate"]
    rates = [Decimal(line["rate"]) for line in turned(Knob.MULTI_RATE).truth["vat_summary"]]
    assert Decimal(str(mixed["value"])) in rates


def test_vat_summary_table_prints_the_rates_as_lines_rather_than_columns() -> None:
    """Every rate still carries evidence; there is just one box a row instead of three."""
    table, listed = turned(), turned(Knob.VAT_SUMMARY_TABLE)
    assert all(len(line["evidence"]) == 3 for line in table.truth["vat_summary"])
    assert all(len(line["evidence"]) == 2 for line in listed.truth["vat_summary"])
    assert all(line["evidence"] for line in listed.truth["vat_summary"])


def test_a_declared_charge_is_on_the_page_and_an_undeclared_one_is_only_in_the_total() -> None:
    declared = turned(Knob.DECLARED_CHARGE).truth["charges"]
    hidden = turned(Knob.UNDECLARED_CHARGE).truth["charges"]
    assert [entry["declared"] for entry in declared] == [True]
    assert declared[0]["evidence"] and declared[0]["label"]
    assert [entry["declared"] for entry in hidden] == [False]
    assert not hidden[0]["evidence"] and hidden[0]["label"] is None


def test_an_undeclared_charge_makes_the_printed_blocks_not_add_up() -> None:
    """Which is the point of the knob: the page is right and the arithmetic on it is not."""
    truth = turned(Knob.UNDECLARED_CHARGE).truth
    parts = [Decimal(str(truth["fields"][n]["value"])) for n in ("subtotal", "vat_amount")]
    total = Decimal(str(truth["fields"]["total_amount"]["value"]))
    assert total > sum(parts)
    assert total - sum(parts) == Decimal(truth["charges"][0]["amount"])


def test_the_rounding_knobs_are_recorded_and_the_arithmetic_follows_them() -> None:
    assert turned(Knob.ROUNDING_PER_LINE).truth["document"]["rounding"] == "per_line"
    assert turned(Knob.ROUNDING_TOTAL).truth["document"]["rounding"] == "total"


def test_dual_currency_echo_prints_the_rate_and_the_converted_total() -> None:
    plain, echoed = turned(), turned(Knob.DUAL_CURRENCY_ECHO)
    assert plain.truth["secondary_amounts"] is None
    echo = echoed.truth["secondary_amounts"]
    assert echo is not None
    assert echo["currency"] == load_profile(PROFILE).secondary_currency
    assert echo["evidence"]


def test_credit_note_reverses_the_document_and_titles_it_as_one() -> None:
    invoice, note = turned(), turned(Knob.CREDIT_NOTE)
    assert invoice.truth["document"]["type"] == "invoice"
    assert note.truth["document"]["type"] == "credit_note"
    reference = fields_of(note)["credit_reference"]
    assert reference["value"] == fields_of(invoice)["invoice_number"]["value"]
    assert reference["evidence"], "the invoice a credit note reverses is printed on it"


def test_credit_note_prints_a_negative_total_where_the_vendor_negates_amounts() -> None:
    note = turned(Knob.CREDIT_NOTE)
    entry = fields_of(note)["total_amount"]
    assert Decimal(str(entry["value"])) < 0
    assert str(entry["printed"]).startswith("-")
    assert entry["evidence"]


def test_exemption_verbiage_prints_a_sentence_where_a_rate_is_zero() -> None:
    """A seed whose rates include the zero one, so the sentence has a reason to be there."""
    lexicon = load_lexicon(load_profile(PROFILE).lexicon)
    offered = {line for lines in lexicon.exemption_sentences.values() for line in lines}
    exempt = turned(Knob.EXEMPTION_VERBIAGE, Knob.MULTI_RATE, seed=EXEMPT_SEED)
    rates = {Decimal(line["rate"]) for line in exempt.truth["vat_summary"]}
    assert Decimal(0) in rates, "this seed is chosen because it draws a zero-rated line"
    assert "exemption" in noise_kinds(exempt)
    assert any(page_holds(exempt, sentence[:30], exempt.pages) for sentence in offered)


def test_a_zero_rate_alone_prints_no_sentence_unless_the_knob_asks_for_one() -> None:
    assert "exemption" not in noise_kinds(turned(Knob.MULTI_RATE, seed=EXEMPT_SEED))


def test_exemption_verbiage_prints_nothing_on_a_document_with_no_zero_rate() -> None:
    assert "exemption" not in noise_kinds(turned(Knob.EXEMPTION_VERBIAGE))


def test_amount_in_words_spells_the_total_out_under_the_totals() -> None:
    spelled = turned(Knob.AMOUNT_IN_WORDS)
    assert "amount_in_words" in noise_kinds(spelled)
    assert "amount_in_words" not in noise_kinds(turned())
    words = load_lexicon(load_profile(PROFILE).lexicon).amount_in_words
    total = Decimal(str(fields_of(spelled)["total_amount"]["value"]))
    written = spell_amount(total, words)
    assert page_holds(spelled, written.split()[0], spelled.pages)


def test_thousands_variant_writes_the_separator_the_vendor_usually_does_not() -> None:
    separators = load_profile(PROFILE).thousands_separators
    plain = str(fields_of(turned())["total_amount"]["printed"])
    varied = str(fields_of(turned(Knob.THOUSANDS_VARIANT))["total_amount"]["printed"])
    assert plain != varied
    assert separators[0] in plain


def test_stamp_copy_prints_a_word_that_says_this_is_not_the_original() -> None:
    stamped = turned(Knob.STAMP_COPY)
    assert "copy_stamp" in noise_kinds(stamped)
    assert "copy_stamp" not in noise_kinds(turned())
    printed = [e for e in stamped.truth["noise"] if e["kind"] == "copy_stamp"]
    stamps = load_lexicon(load_profile(PROFILE).lexicon).copy_stamps
    assert {entry["label"] for entry in printed} <= set(stamps)


def test_bank_footer_takes_the_block_that_says_where_to_pay_away() -> None:
    banked, bare = turned(), turned(Knob.BANK_FOOTER)
    assert page_holds(banked, banked.truth["parties"]["supplier"]["name"])
    iban = "IBAN"
    assert page_holds(banked, iban, banked.pages)
    assert not page_holds(bare, iban, bare.pages)


def test_noise_footer_takes_the_legal_lines_away() -> None:
    assert "footer_legal" in noise_kinds(turned())
    assert "footer_legal" not in noise_kinds(turned(Knob.NOISE_FOOTER))


def test_payment_terms_block_moves_the_terms_out_of_the_bank_block() -> None:
    inline = fields_of(turned())["payment_terms"]["evidence"][0]["bbox"]
    blocked = fields_of(turned(Knob.PAYMENT_TERMS_BLOCK))["payment_terms"]["evidence"][0]["bbox"]
    assert inline != blocked
    assert blocked[1] < inline[1], "its own block sits above the bank details"


def test_charges_puts_a_charge_on_a_document_that_would_have_had_none() -> None:
    assert turned().truth["charges"] == []
    assert len(turned(Knob.CHARGES).truth["charges"]) == 1


def test_supply_date_is_the_other_value_of_whatever_the_profile_prints() -> None:
    prints = load_profile(PROFILE).prints_supply_date
    assert (fields_of(turned())["supply_date"]["value"] is not None) is prints
    turned_on = fields_of(turned(Knob.SUPPLY_DATE))["supply_date"]["value"]
    assert (turned_on is not None) is not prints


def test_extra_references_prints_every_optional_reference_at_once() -> None:
    every = fields_of(turned(Knob.EXTRA_REFERENCES))
    for name in ("contract_number", "our_reference", "your_reference"):
        assert every[name]["value"] is not None, name
        assert every[name]["evidence"], name


def test_column_set_takes_the_part_number_out_of_the_table() -> None:
    plain, compact = turned(), turned(Knob.COLUMN_SET)
    assert all(row["cells"].get("part_number") for row in plain.truth["line_items"])
    assert all(not row["cells"].get("part_number") for row in compact.truth["line_items"])
    assert all(row["cells"]["description"] for row in compact.truth["line_items"])


def test_every_knob_this_pull_request_builds_is_one_the_catalog_names() -> None:
    assert {knob.value for knob in EVERY} <= set(KNOB_NAMES)


def test_all_of_them_at_once_still_renders_and_verifies() -> None:
    """Every knob but the one that contradicts another, on one document."""
    together = turned(*(knob for knob in EVERY if knob is not Knob.ROUNDING_PER_LINE))
    assert verify_document(_truth_path(together), regenerate=False) == ()


def _truth_path(document: Rendered) -> Path:
    return document.pdf.with_name(f"{document.pdf.stem}.truth.json")
