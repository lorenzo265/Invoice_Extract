"""What each strategy accepts as a candidate, on pages built in memory."""

from __future__ import annotations

from conftest import line
from invoice_extractor.domain.models import Strategy
from invoice_extractor.extraction.units.strategies import (
    anchor_value,
    label_below,
    label_beside,
    label_pattern,
    label_right,
)

NUMBER = ("Invoice Number",)


def test_label_right_reads_a_label_and_its_value_in_one_run() -> None:
    lines = [line("Invoice Number: INV-2024-0042", 400, 76)]
    (candidate,) = label_right(lines, NUMBER)
    assert candidate.raw_text == "Invoice Number: INV-2024-0042"
    assert candidate.evidence.matched_label == "Invoice Number"
    assert candidate.evidence.strategy is Strategy.LABEL_RIGHT
    assert candidate.label_distance == 0.0


def test_label_right_is_case_insensitive() -> None:
    assert label_right([line("INVOICE NUMBER: INV-42", 400, 76)], NUMBER)


def test_label_right_ignores_a_line_that_is_only_the_label() -> None:
    assert label_right([line("Bill To", 56, 340)], ("Bill To",)) == []


def test_label_right_ignores_a_colon_with_nothing_after_it() -> None:
    assert label_right([line("Invoice Number:   ", 400, 76)], NUMBER) == []


def test_label_right_ignores_a_longer_label_that_starts_the_same() -> None:
    assert label_right([line("Invoice Number Suffix: X", 400, 76)], NUMBER) == []


def test_label_beside_reads_the_nearest_thing_to_the_right_of_the_label() -> None:
    lines = [line("Invoice Number:", 400, 76), line("INV-2024-0042", 500, 76)]
    (candidate,) = label_beside(lines, NUMBER)
    assert candidate.raw_text == "INV-2024-0042"
    assert candidate.evidence.strategy is Strategy.LABEL_BESIDE
    assert candidate.label_distance > 0


def test_label_beside_ignores_what_is_drawn_on_another_line() -> None:
    lines = [line("Invoice Number:", 400, 76), line("INV-2024-0042", 500, 200)]
    assert label_beside(lines, NUMBER) == []


def test_label_beside_takes_the_first_thing_along_the_line_and_no_further() -> None:
    lines = [
        line("Invoice Number:", 400, 76),
        line("INV-2024-0042", 500, 76),
        line("something else", 580, 76),
    ]
    (candidate,) = label_beside(lines, NUMBER)
    assert candidate.raw_text == "INV-2024-0042"


def test_label_below_reads_the_nearest_thing_under_the_label() -> None:
    lines = [line("Invoice Number", 400, 76), line("INV-2024-0042", 400, 90)]
    (candidate,) = label_below(lines, NUMBER)
    assert candidate.raw_text == "INV-2024-0042"
    assert candidate.evidence.strategy is Strategy.LABEL_BELOW
    assert candidate.label_distance > 0


def test_label_below_ignores_what_does_not_sit_under_the_label() -> None:
    lines = [line("Invoice Number", 400, 76), line("INV-2024-0042", 60, 90)]
    assert label_below(lines, NUMBER) == []


def test_label_below_ignores_an_anchor_with_nothing_under_it() -> None:
    assert label_below([line("Invoice Number", 400, 76)], NUMBER) == []


def test_a_label_with_the_tab_stop_colon_left_on_it_is_still_the_label() -> None:
    lines = [line("Invoice Number:", 400, 76), line("INV-42", 400, 90)]
    assert label_below(lines, NUMBER)


def test_label_pattern_reads_what_the_pattern_matches_and_nothing_else() -> None:
    lines = [line("VAT Number: GB123456789", 56, 124)]
    (candidate,) = label_pattern(lines, (r"GB\d{9}",))
    assert candidate.raw_text == "GB123456789"
    assert candidate.evidence.matched_label is None
    assert candidate.evidence.strategy is Strategy.LABEL_PATTERN


def test_label_pattern_with_nothing_to_match_finds_nothing() -> None:
    assert label_pattern([line("VAT Number: GB123456789", 56, 124)], ()) == []


def test_an_anchor_publishes_the_value_it_expected_not_the_line_it_sat_on() -> None:
    lines = [line("USt-IdNr.: DE811234567", 56, 124)]
    (candidate,) = anchor_value(lines, ("DE811234567",))
    assert candidate.raw_text == "DE811234567"
    assert candidate.evidence.raw_text == "DE811234567"
    assert candidate.evidence.strategy is Strategy.ANCHOR
    assert candidate.match_ratio == 1.0


def test_an_anchor_finds_a_value_however_it_was_punctuated() -> None:
    lines = [line("VAT no. G B 1 2 3 4 5 6 7 8 9", 56, 124)]
    (candidate,) = anchor_value(lines, ("GB123456789",))
    assert candidate.match_ratio == 1.0


def test_an_anchor_finds_a_name_that_is_nearly_right_and_says_how_nearly() -> None:
    lines = [line("Rheinwerk Industriebedarf GmbM", 56, 50)]
    (candidate,) = anchor_value(lines, ("Rheinwerk Industriebedarf GmbH",))
    assert 0.85 <= candidate.match_ratio < 1.0


def test_an_anchor_ignores_a_line_that_is_nothing_like_the_value() -> None:
    assert anchor_value([line("Nordwind Logistik GmbH", 56, 50)], ("Rheinwerk GmbH",)) == []


def test_an_anchor_asked_for_nothing_finds_nothing() -> None:
    assert anchor_value([line("Rheinwerk GmbH", 56, 50)], ("",)) == []
