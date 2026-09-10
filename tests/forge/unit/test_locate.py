"""Resolving what the renderer drew to the boxes the finished PDF actually holds."""

from __future__ import annotations

from pathlib import Path

import pytest

from invoice_forge.layout.classic import A4
from invoice_forge.profiles.schema import FontFamily
from invoice_forge.render.placement import Placement, field
from invoice_forge.render.sheet import Sheet
from invoice_forge.truth.locate import LocateError, locate

REPEATED = "AB-1234"
LEFT_X = 60.0
RIGHT_X = 300.0
BASELINE = 100.0
SIZE = 9.0


def written(tmp_path: Path) -> tuple[Path, Sheet]:
    """One page with the same string printed twice, and a third printed once."""
    sheet = Sheet(A4, FontFamily.SANS)
    sheet.new_page()
    sheet.draw(LEFT_X, BASELINE, REPEATED, SIZE, mark=field("invoice_number"))
    sheet.draw(RIGHT_X, BASELINE, REPEATED, SIZE, mark=field("order_number"))
    sheet.draw(LEFT_X, BASELINE + 20.0, "Only once", SIZE, mark=field("customer_number"))
    path = tmp_path / "written.pdf"
    sheet.save(path, "written")
    return path, sheet


def test_every_placement_gets_the_box_it_was_drawn_at(tmp_path: Path) -> None:
    path, sheet = written(tmp_path)
    found = locate(path, sheet.placements)
    assert len(found) == len(sheet.placements)
    for placement, evidence in zip(sheet.placements, found, strict=True):
        assert evidence.page == 1
        assert abs(evidence.bbox[0] - placement.x) < 1.0
        assert abs(evidence.bbox[3] - placement.y) < 3.0


def test_a_string_printed_twice_gives_each_placement_its_own_box(tmp_path: Path) -> None:
    path, sheet = written(tmp_path)
    found = locate(path, sheet.placements)
    assert found[0].bbox != found[1].bbox
    assert found[0].bbox[0] < found[1].bbox[0]


def test_two_readings_of_one_printed_string_share_its_box(tmp_path: Path) -> None:
    """A rate in the VAT summary that is also the headline rate is recorded twice."""
    path, sheet = written(tmp_path)
    extra = Placement(field("vat_rate"), REPEATED, 1, LEFT_X, BASELINE)
    found = locate(path, (*sheet.placements, extra))
    assert found[-1].bbox == found[0].bbox


def test_a_string_the_pdf_does_not_hold_is_a_generator_fault(tmp_path: Path) -> None:
    path, sheet = written(tmp_path)
    invented = Placement(field("invoice_number"), "NEVER PRINTED", 1, LEFT_X, BASELINE)
    with pytest.raises(LocateError, match="printed strings not found"):
        locate(path, (*sheet.placements, invented))


def test_the_fault_names_the_page_and_the_string(tmp_path: Path) -> None:
    path, _ = written(tmp_path)
    invented = Placement(field("invoice_number"), "NEVER PRINTED", 1, LEFT_X, BASELINE)
    with pytest.raises(LocateError, match="page 1: 'NEVER PRINTED'"):
        locate(path, (invented,))


def test_more_placements_than_printings_is_a_fault_too(tmp_path: Path) -> None:
    """Three readings of a string printed twice: the third has no occurrence to claim."""
    path, sheet = written(tmp_path)
    third = Placement(field("contract_number"), REPEATED, 1, 450.0, BASELINE)
    with pytest.raises(LocateError, match="printed strings not found"):
        locate(path, (*sheet.placements, third))


def test_nothing_recorded_locates_nothing(tmp_path: Path) -> None:
    path, _ = written(tmp_path)
    assert locate(path, ()) == ()
