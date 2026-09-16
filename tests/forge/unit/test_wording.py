"""One document says one thing one way, and says it the same way on every page."""

from __future__ import annotations

from random import Random

import pytest

from invoice_forge.families import Family
from invoice_forge.fields import LABELLED_FIELDS
from invoice_forge.knobs import Knob
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.model import CHARGE_TYPE_NAMES, CreditNoteStyle, as_credit_note
from invoice_forge.profiles.loader import load_profile, profile_ids
from invoice_forge.render.wording import Wording, choose_wording, page_line
from invoice_forge.sample.catalogue import load_catalogue
from invoice_forge.sample.sampler import SampleRequest, sample_document

SEEDS = range(5)


def wording_for(profile_id: str, seed: int, knobs: tuple[Knob, ...] = ()) -> Wording:
    profile = load_profile(profile_id)
    lexicon = load_lexicon(profile.lexicon)
    catalogue = load_catalogue(profile.lexicon)
    request = SampleRequest(profile, lexicon, catalogue, Family.CLASSIC, seed, knobs)
    document = sample_document(request)
    return choose_wording(document, profile, lexicon, Random(seed), knobs)


@pytest.mark.parametrize("profile_id", profile_ids())
def test_the_same_seed_chooses_the_same_words(profile_id: str) -> None:
    for seed in SEEDS:
        assert wording_for(profile_id, seed) == wording_for(profile_id, seed)


@pytest.mark.parametrize("profile_id", profile_ids())
def test_every_labelled_field_has_a_word_for_it(profile_id: str) -> None:
    labels = wording_for(profile_id, 1).labels
    assert set(labels) == set(LABELLED_FIELDS)
    assert all(labels[name] for name in LABELLED_FIELDS)


@pytest.mark.parametrize("profile_id", profile_ids())
def test_every_charge_and_party_the_profile_can_print_has_a_word(profile_id: str) -> None:
    wording = wording_for(profile_id, 2)
    assert set(wording.charges) == set(CHARGE_TYPE_NAMES)
    assert {"bill_to", "ship_to", "mail_to"} <= set(wording.parties)
    assert {"code", "rate", "base", "vat"} == set(wording.vat_summary)
    assert {"incoming", "outgoing"} == set(wording.carry)


@pytest.mark.parametrize("profile_id", profile_ids())
def test_the_words_chosen_are_words_the_lexicon_offers(profile_id: str) -> None:
    profile = load_profile(profile_id)
    lexicon = load_lexicon(profile.lexicon)
    wording = wording_for(profile_id, 3)
    for name, chosen in wording.labels.items():
        offered = {**lexicon.header_labels, **lexicon.totals_labels}[name]
        assert chosen in offered, name
    assert wording.title in lexicon.document_titles["invoice"]
    assert wording.page_numbering in lexicon.page_numbering
    assert set(wording.legal_lines) <= set(lexicon.legal_lines)


@pytest.mark.parametrize("profile_id", profile_ids())
def test_the_formats_chosen_are_formats_the_profile_declares(profile_id: str) -> None:
    profile = load_profile(profile_id)
    wording = wording_for(profile_id, 4)
    assert wording.date_format in profile.date_formats
    assert wording.number_format.decimal == profile.decimal_separator
    assert wording.number_format.thousands in profile.thousands_separators


@pytest.mark.parametrize("profile_id", profile_ids())
def test_no_legal_line_is_printed_twice(profile_id: str) -> None:
    lines = wording_for(profile_id, 0).legal_lines
    assert len(set(lines)) == len(lines)
    assert lines


def test_a_credit_note_is_titled_as_one() -> None:
    profile = load_profile("de-DE")
    lexicon = load_lexicon(profile.lexicon)
    catalogue = load_catalogue(profile.lexicon)
    request = SampleRequest(profile, lexicon, catalogue, Family.CLASSIC, 1)
    note = as_credit_note(sample_document(request), "CN-1", CreditNoteStyle.NEGATIVE_AMOUNTS)
    wording = choose_wording(note, profile, lexicon, Random(1))
    assert wording.title in lexicon.document_titles["credit_note"]


@pytest.mark.parametrize("profile_id", profile_ids())
def test_thousands_variant_writes_the_separator_the_vendor_usually_does_not(
    profile_id: str,
) -> None:
    """Off, the vendor's first separator; on, one of the others it also writes."""
    profile = load_profile(profile_id)
    separators = profile.thousands_separators
    assert wording_for(profile_id, 1).number_format.thousands == separators[0]
    turned = wording_for(profile_id, 1, (Knob.THOUSANDS_VARIANT,)).number_format.thousands
    assert turned in separators
    if len(separators) > 1:
        assert turned != separators[0]


@pytest.mark.parametrize("profile_id", profile_ids())
def test_a_copy_stamp_and_an_exemption_sentence_are_drawn_whether_or_not_they_print(
    profile_id: str,
) -> None:
    """Drawn always, so a knob that prints them shifts no other choice in the document."""
    profile = load_profile(profile_id)
    lexicon = load_lexicon(profile.lexicon)
    wording = wording_for(profile_id, 2)
    assert wording.copy_stamp in lexicon.copy_stamps
    offered = {line for lines in lexicon.exemption_sentences.values() for line in lines}
    assert wording.exemption in offered


def test_the_page_line_carries_both_numbers() -> None:
    wording = wording_for("en-GB", 1)
    printed = page_line(wording, 2, 5)
    assert "2" in printed
    assert "5" in printed
