"""What a candidate has to survive before it is ranked."""

from __future__ import annotations

import dataclasses

from conftest import line, make_field_profile, make_profile
from invoice_extractor.document.model import Zone
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.extraction.units.filters import looks_numeric, not_a_trap
from invoice_extractor.profile.schema import Noise

TRAPS = Noise(ignore_labels=("Order Date", "Print Date"))


def candidate(text: str, label: str | None = "Invoice Date") -> Candidate:
    drawn = line(text, 400, 76)
    evidence = Evidence(1, drawn.bbox, label, Strategy.LABEL_BESIDE, text)
    return Candidate(raw_text=text, evidence=evidence, zone=Zone(1, 3), label_distance=0.0)


def with_traps() -> object:
    return dataclasses.replace(make_profile(), noise=TRAPS)


def test_a_candidate_a_trap_label_introduced_is_dropped() -> None:
    field = make_field_profile(labels=("Invoice Date",))
    found = [candidate("01.02.2024", label="Order Date")]
    assert not_a_trap(found, field, with_traps()) == []


def test_a_candidate_this_fields_own_label_introduced_is_kept() -> None:
    field = make_field_profile(labels=("Invoice Date",))
    found = [candidate("01.02.2024")]
    assert not_a_trap(found, field, with_traps()) == found


def test_a_label_another_field_calls_a_trap_is_not_a_trap_for_the_field_that_wants_it() -> None:
    """`Lieferdatum` is a trap beside the invoice date and the supply date's own label."""
    field = make_field_profile(labels=("Order Date",))
    found = [candidate("01.02.2024", label="Order Date")]
    assert not_a_trap(found, field, with_traps()) == found


def test_a_line_that_starts_with_a_trap_label_is_dropped() -> None:
    field = make_field_profile(labels=("Invoice Date",))
    found = [candidate("Print Date: 02.02.2024", label=None)]
    assert not_a_trap(found, field, with_traps()) == []


def test_nothing_is_dropped_when_the_vendor_names_no_traps() -> None:
    field = make_field_profile(labels=("Invoice Date",))
    found = [candidate("01.02.2024", label="Order Date")]
    assert not_a_trap(found, field, make_profile()) == found


def test_an_amount_is_kept_and_a_sentence_carrying_digits_is_not() -> None:
    field = make_field_profile(labels=("Total",))
    amount = candidate("1,234.56", label="Total")
    printed = "Bergslundbanken IBAN SE81 2663 9935 1456 5769 3224 BIC XUNJSEHQZ12"
    sentence = candidate(printed, label="Total")
    assert looks_numeric([amount, sentence], field, make_profile()) == [amount]


def test_an_empty_candidate_is_not_a_number() -> None:
    field = make_field_profile(labels=("Total",))
    assert looks_numeric([candidate("", label=None)], field, make_profile()) == []


def test_an_amount_printed_with_its_currency_code_is_still_a_number() -> None:
    """`19.25 GBP` is how a vendor prints an amount, and the code is not prose."""
    field = make_field_profile(labels=("Subtotal",))
    priced = candidate("19.25 GBP", label="Subtotal")
    assert looks_numeric([priced], field, make_profile()) == [priced]


def test_a_vendor_that_writes_its_thousands_with_a_space_still_reads_as_a_number() -> None:
    field = make_field_profile(labels=("Total",))
    spaced = candidate("2 670,00", label="Total")
    swedish = make_profile(decimal_separator=",", thousands_separators=(" ",))
    assert looks_numeric([spaced], field, swedish) == [spaced]
