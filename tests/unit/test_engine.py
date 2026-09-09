"""The generic runner: evaluate, rank, pick a winner, report what the scorer needs."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from conftest import line, make_field_layout, make_layout
from invoice_extractor.document.reader import TextLine, Zone
from invoice_extractor.domain.models import Strategy
from invoice_extractor.extraction.engine import run
from invoice_extractor.extraction.normalizers import parse_money
from invoice_extractor.extraction.rankers import top_most, valid_first, zone_priority
from invoice_extractor.extraction.spec import FieldSpec, OnAllInvalid, Ranker
from invoice_extractor.extraction.validators import is_positive_money
from invoice_extractor.layout.schema import Layout

BOTH_ZONES = (Zone.BOTTOM_RIGHT, Zone.TOP_RIGHT)


def subtotal_spec(
    rankers: Sequence[Ranker] = (valid_first, zone_priority, top_most),
    on_all_invalid: OnAllInvalid = OnAllInvalid.NOT_FOUND,
) -> FieldSpec:
    return FieldSpec(
        name="subtotal",
        strategy=Strategy.LABEL_RIGHT,
        normalizer=parse_money,
        validator=is_positive_money,
        rankers=tuple(rankers),
        on_all_invalid=on_all_invalid,
    )


def subtotal_layout(zones: Sequence[Zone] = BOTH_ZONES) -> Layout:
    return make_layout(fields={"subtotal": make_field_layout(labels=("Subtotal",), zones=zones)})


def two_valid_lines() -> list[TextLine]:
    return [line("Subtotal: 100.00", 400, 620), line("Subtotal: 200.00", 400, 76)]


def test_run_returns_not_found_when_no_candidates() -> None:
    extraction = run(subtotal_spec(), [line("Nothing here", 400, 620)], subtotal_layout())
    assert extraction.field.value is None
    assert extraction.field.raw_text is None
    assert extraction.field.evidence is None
    assert extraction.field.valid is False
    assert extraction.candidate_count == 0
    assert extraction.zone is None


def test_run_not_found_wins_over_best_when_nothing_was_found_at_all() -> None:
    spec = subtotal_spec(on_all_invalid=OnAllInvalid.BEST)
    extraction = run(spec, [line("Nothing here", 400, 620)], subtotal_layout())
    assert extraction.field.evidence is None


def test_run_best_keeps_invalid_top_candidate() -> None:
    spec = subtotal_spec(on_all_invalid=OnAllInvalid.BEST)
    extraction = run(spec, [line("Subtotal: -5.00", 400, 620)], subtotal_layout())
    assert extraction.field.value == Decimal("-5.00")
    assert extraction.field.valid is False
    assert extraction.field.evidence is not None


def test_run_not_found_discards_an_invalid_candidate() -> None:
    extraction = run(subtotal_spec(), [line("Subtotal: -5.00", 400, 620)], subtotal_layout())
    assert extraction.field.value is None
    assert extraction.candidate_count == 1


def test_run_orders_by_rankers_in_sequence() -> None:
    by_zone = run(
        subtotal_spec(rankers=(zone_priority, top_most)), two_valid_lines(), subtotal_layout()
    )
    by_position = run(
        subtotal_spec(rankers=(top_most, zone_priority)), two_valid_lines(), subtotal_layout()
    )
    assert by_zone.field.value == Decimal("100.00")
    assert by_position.field.value == Decimal("200.00")


def test_run_reports_candidate_count() -> None:
    extraction = run(subtotal_spec(), two_valid_lines(), subtotal_layout())
    assert extraction.candidate_count == 2


def test_run_reports_zone_of_winning_line() -> None:
    extraction = run(subtotal_spec(), two_valid_lines(), subtotal_layout())
    assert extraction.zone is Zone.BOTTOM_RIGHT
