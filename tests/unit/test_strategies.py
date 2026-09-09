"""What each strategy accepts as a candidate, on pages built in memory."""

from __future__ import annotations

from conftest import line, make_field_layout
from invoice_extractor.document.reader import Zone
from invoice_extractor.domain.models import Strategy
from invoice_extractor.extraction.strategies import label_below, label_right, regex_anchor


def test_label_right_reads_value_after_colon() -> None:
    lines = [line("Invoice Number: INV-2024-0042", 400, 76)]
    (candidate,) = label_right(lines, make_field_layout(labels=("Invoice Number",)))
    assert candidate.raw_text == "Invoice Number: INV-2024-0042"
    assert candidate.evidence.matched_label == "Invoice Number"
    assert candidate.evidence.strategy is Strategy.LABEL_RIGHT
    assert candidate.label_distance == 0.0


def test_label_right_is_case_insensitive() -> None:
    lines = [line("INVOICE NUMBER: INV-2024-0042", 400, 76)]
    assert label_right(lines, make_field_layout(labels=("Invoice Number",)))


def test_label_right_ignores_line_where_label_is_the_whole_text() -> None:
    lines = [line("Bill To", 56, 340)]
    assert label_right(lines, make_field_layout(labels=("Bill To",))) == []


def test_label_right_ignores_a_colon_with_nothing_after_it() -> None:
    lines = [line("Invoice Number:   ", 400, 76)]
    assert label_right(lines, make_field_layout(labels=("Invoice Number",))) == []


def test_label_right_ignores_a_longer_label_that_starts_the_same() -> None:
    lines = [line("Momsbelopp: 804,00", 400, 656)]
    assert label_right(lines, make_field_layout(labels=("Moms",))) == []


def test_label_right_prefers_expected_zone_then_falls_back() -> None:
    inside = line("Currency: SEK", 400, 76)
    outside = line("Currency: GBP", 56, 700)
    field_layout = make_field_layout(labels=("Currency",), zones=(Zone.TOP_RIGHT,))

    (preferred,) = label_right([inside, outside], field_layout)
    assert preferred.raw_text == "Currency: SEK"

    (fallback,) = label_right([outside], field_layout)
    assert fallback.raw_text == "Currency: GBP"


def test_label_below_picks_nearest_line_under_anchor() -> None:
    anchor = line("Bill To", 56, 340)
    near = line("Nordwind Logistik GmbH", 56, 356)
    far = line("Friedrichstrasse 88", 56, 372)
    field_layout = make_field_layout(labels=("Bill To",), zones=(Zone.MIDDLE_LEFT,))
    (candidate,) = label_below([anchor, far, near], field_layout)
    assert candidate.raw_text == "Nordwind Logistik GmbH"


def test_label_below_records_distance() -> None:
    anchor = line("Bill To", 56, 340)
    below = line("Nordwind Logistik GmbH", 56, 356)
    field_layout = make_field_layout(labels=("Bill To",), zones=(Zone.MIDDLE_LEFT,))
    (candidate,) = label_below([anchor, below], field_layout)
    assert candidate.label_distance == below.bbox.y0 - anchor.bbox.y0


def test_label_below_ignores_a_line_that_does_not_overlap_horizontally() -> None:
    anchor = line("Bill To", 56, 340)
    elsewhere = line("Total Due: 588.00", 400, 356)
    field_layout = make_field_layout(labels=("Bill To",), zones=(Zone.MIDDLE_LEFT,))
    assert label_below([anchor, elsewhere], field_layout) == []


def test_label_below_ignores_an_anchor_with_nothing_under_it() -> None:
    field_layout = make_field_layout(labels=("Bill To",), zones=(Zone.MIDDLE_LEFT,))
    assert label_below([line("Bill To", 56, 340)], field_layout) == []


def test_regex_anchor_returns_match_text_without_label() -> None:
    lines = [line("VAT Number: GB123456789", 56, 124)]
    field_layout = make_field_layout(zones=(Zone.TOP_LEFT,), regex=r"GB\d{9}")
    (candidate,) = regex_anchor(lines, field_layout)
    assert candidate.raw_text == "GB123456789"
    assert candidate.evidence.matched_label is None
    assert candidate.evidence.strategy is Strategy.REGEX_ANCHOR


def test_regex_anchor_yields_nothing_without_regex() -> None:
    lines = [line("VAT Number: GB123456789", 56, 124)]
    assert regex_anchor(lines, make_field_layout(zones=(Zone.TOP_LEFT,))) == []
