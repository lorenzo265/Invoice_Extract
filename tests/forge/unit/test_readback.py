"""What a box has to say for a truth entry to be believed, and how strict each kind is."""

from __future__ import annotations

import pytest

from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.truth.readback import Claim, Match, _claims, _holds, alnum
from invoice_forge.truth.reading import Box, TruthError
from invoice_forge.truth.verify import document_spec

BOX = Box(page=1, bbox=(1.0, 2.0, 3.0, 4.0))


def claim(expected: str, match: Match) -> Claim:
    return Claim("fields.total_amount", BOX, expected, match)


def test_letters_and_digits_are_what_survive_a_printing() -> None:
    assert alnum("9.965,24 EUR") == "996524EUR"
    assert alnum("USt-IdNr.: DE811234567") == "USTIDNRDE811234567"
    assert alnum("   ") == ""


def test_an_exact_claim_is_the_whole_string_and_nothing_else() -> None:
    exact = claim("53.653,50 EUR", Match.EXACT)
    assert _holds(exact, "53.653,50 EUR")
    assert _holds(exact, "53653.50 eur")
    assert not _holds(exact, "53.653,50")
    assert not _holds(exact, "53.653,50 EUR and more")


def test_a_part_claim_is_a_piece_of_the_value() -> None:
    """A description wrapped over two lines gives each of its boxes part of the sentence."""
    part = claim("Temperatursensor PT100, 3-Leiter", Match.PART)
    assert _holds(part, "Temperatursensor PT100,")
    assert _holds(part, "3-Leiter")
    assert not _holds(part, "Koppelrelais")


def test_a_contains_claim_is_the_value_and_whatever_is_printed_with_it() -> None:
    """A charge records the amount but the page prints it with its currency."""
    contains = claim("120.00", Match.CONTAINS)
    assert _holds(contains, "120,00 EUR")
    assert _holds(contains, "120.00")
    assert not _holds(contains, "12,00 EUR")


def test_an_any_claim_only_asks_that_something_is_there() -> None:
    anything = claim("", Match.ANY)
    assert _holds(anything, "a legal line about retention of title")
    assert not _holds(anything, "")


@pytest.mark.parametrize("match", list(Match))
def test_an_empty_box_never_holds_a_claim(match: Match) -> None:
    assert not _holds(claim("anything", match), "   ")


def test_a_truth_with_nothing_in_it_makes_no_claims() -> None:
    empty = {
        "fields": {},
        "line_items": [],
        "charges": [],
        "vat_summary": [],
        "parties": {},
        "noise": [],
        "secondary_amounts": None,
    }
    assert tuple(_claims(empty)) == ()


def test_a_party_the_document_does_not_name_makes_no_claims() -> None:
    truth = {
        "fields": {},
        "line_items": [],
        "charges": [],
        "vat_summary": [],
        "parties": {"mail_to": None},
        "noise": [],
        "secondary_amounts": None,
    }
    assert tuple(_claims(truth)) == ()


def test_a_party_without_address_lines_still_claims_its_name() -> None:
    party = {
        "name": "A Vendor Ltd",
        "lines": None,
        "vat_id": None,
        "evidence": [{"page": 1, "bbox": [1, 2, 3, 4]}],
    }
    truth = {
        "fields": {},
        "line_items": [],
        "charges": [],
        "vat_summary": [],
        "parties": {"supplier": party},
        "noise": [],
        "secondary_amounts": None,
    }
    made = tuple(_claims(truth))
    assert [entry.expected for entry in made] == ["A Vendor Ltd"]


def test_a_row_without_cells_makes_no_cell_claims() -> None:
    truth = {
        "fields": {},
        "line_items": [{"pos": 1, "part_number": "SKU-1", "cells": None}],
        "charges": [],
        "vat_summary": [],
        "parties": {},
        "noise": [],
        "secondary_amounts": None,
    }
    assert tuple(_claims(truth)) == ()


def test_the_cell_of_a_column_a_family_does_not_print_is_skipped() -> None:
    row = {
        "pos": 1,
        "part_number": "SKU-1",
        "description": "A thing",
        "quantity": "1",
        "unit_price": "1.00",
        "net_amount": "1.00",
        "cells": {"part_number": [{"page": 1, "bbox": [1, 2, 3, 4]}]},
    }
    truth = {
        "fields": {},
        "line_items": [row],
        "charges": [],
        "vat_summary": [],
        "parties": {},
        "noise": [],
        "secondary_amounts": None,
    }
    made = tuple(_claims(truth))
    assert [entry.expected for entry in made] == ["SKU-1"]


def test_the_cell_that_made_a_document_reads_back_out_of_its_generator_block() -> None:
    generator = {
        "version": "0.1.0",
        "seed": 7,
        "profile": "de-DE",
        "template": "classic",
        "knobs": ["multi_page"],
    }
    spec = document_spec({"generator": generator})
    assert spec.profile_id == "de-DE"
    assert spec.family is Family.CLASSIC
    assert spec.seed == 7
    assert spec.knobs == (Knob.MULTI_PAGE,)


@pytest.mark.parametrize(
    "generator",
    [
        {"version": "0.1.0", "seed": 7, "profile": "de-DE", "template": "baroque", "knobs": []},
        {
            "version": "0.1.0",
            "seed": 7,
            "profile": "de-DE",
            "template": "classic",
            "knobs": ["wobble"],
        },
    ],
)
def test_a_generator_block_naming_something_unknown_is_refused(
    generator: dict[str, object],
) -> None:
    with pytest.raises(TruthError, match=r"generator names something unknown"):
        document_spec({"generator": generator})
