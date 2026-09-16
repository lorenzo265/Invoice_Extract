"""Reading a truth file back without trusting it: every refusal names what is wrong."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from invoice_forge.truth.reading import (
    TruthError,
    amount,
    block,
    box_at,
    boxes,
    flag,
    read_truth,
    rows,
    text,
    whole,
)

WHERE = "fields.total_amount"


def test_a_file_that_is_not_there_is_named(tmp_path: Path) -> None:
    with pytest.raises(TruthError, match=r"cannot be read"):
        read_truth(tmp_path / "absent.truth.json")


def test_a_file_that_is_not_json_is_named(tmp_path: Path) -> None:
    path = tmp_path / "broken.truth.json"
    path.write_text("{,}", encoding="utf-8")
    with pytest.raises(TruthError, match=r"invalid JSON"):
        read_truth(path)


def test_a_file_that_is_json_but_not_an_object_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "list.truth.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(TruthError, match=r"must be a JSON object"):
        read_truth(path)


def test_a_valid_file_reads_as_a_plain_object(tmp_path: Path) -> None:
    path = tmp_path / "one.truth.json"
    path.write_text('{"schema": "forge-truth/1"}', encoding="utf-8")
    assert read_truth(path) == {"schema": "forge-truth/1"}


def test_a_block_must_be_an_object() -> None:
    assert block({"document": {"pages": 2}}, "document") == {"pages": 2}
    with pytest.raises(TruthError, match=r"document must be an object"):
        block({"document": []}, "document")


def test_rows_must_be_a_list_of_objects() -> None:
    assert rows({"charges": [{"amount": "1.00"}]}, "charges") == [{"amount": "1.00"}]
    with pytest.raises(TruthError, match=r"charges must be a list of objects"):
        rows({"charges": ["1.00"]}, "charges")


def test_text_must_be_a_string() -> None:
    assert text({"printed": "x"}, "printed", WHERE) == "x"
    with pytest.raises(TruthError, match=rf"{WHERE}.printed must be a string"):
        text({"printed": 7}, "printed", WHERE)


def test_a_flag_must_be_a_boolean() -> None:
    assert flag({"declared": True}, "declared", WHERE) is True
    with pytest.raises(TruthError, match=r"must be true or false"):
        flag({"declared": "yes"}, "declared", WHERE)


@pytest.mark.parametrize("value", ["2", 2.5, True, None])
def test_a_whole_number_must_be_one(value: object) -> None:
    with pytest.raises(TruthError, match=r"must be a whole number"):
        whole({"pages": value}, "pages", WHERE)


def test_an_amount_is_a_decimal_written_as_a_string() -> None:
    assert amount({"value": "9.99"}, "value", WHERE) == Decimal("9.99")
    with pytest.raises(TruthError, match=r"must be a decimal written as a string"):
        amount({"value": "nine"}, "value", WHERE)


def test_an_amount_that_is_a_number_is_refused() -> None:
    """Money never passes through a float, so a JSON number is not an amount."""
    with pytest.raises(TruthError, match=r"must be a string"):
        amount({"value": 9.99}, "value", WHERE)


def test_evidence_must_be_a_list() -> None:
    assert boxes({"evidence": []}, WHERE) == ()
    with pytest.raises(TruthError, match=r"evidence must be a list"):
        boxes({"evidence": {}}, WHERE)


def test_an_evidence_entry_must_be_an_object() -> None:
    with pytest.raises(TruthError, match=r"evidence\[0\] must be an object"):
        boxes({"evidence": ["somewhere"]}, WHERE)


def test_a_box_reads_as_four_numbers() -> None:
    found = boxes({"evidence": [{"page": 2, "bbox": [1, 2.5, 3, 4]}]}, WHERE)
    assert found[0].page == 2
    assert found[0].bbox == (1.0, 2.5, 3.0, 4.0)


@pytest.mark.parametrize("bbox", [[1, 2, 3], "1,2,3,4", [1, 2, 3, "4"], [1, 2, 3, True], None])
def test_a_box_that_is_not_four_numbers_is_refused(bbox: object) -> None:
    with pytest.raises(TruthError, match=r"must be four numbers"):
        boxes({"evidence": [{"page": 1, "bbox": bbox}]}, WHERE)


@pytest.mark.parametrize("bbox", [[9, 2, 3, 4], [1, 9, 3, 4]])
def test_a_box_whose_corners_are_the_wrong_way_round_is_refused(bbox: list[float]) -> None:
    with pytest.raises(TruthError, match=r"is inside out"):
        boxes({"evidence": [{"page": 1, "bbox": bbox}]}, WHERE)


def test_a_box_may_be_flat_where_a_rule_or_an_empty_string_was_drawn() -> None:
    assert boxes({"evidence": [{"page": 1, "bbox": [1, 2, 1, 2]}]}, WHERE)[0].bbox == (1, 2, 1, 2)


def test_an_entry_that_carries_its_own_box_reads_directly() -> None:
    found = box_at({"page": 3, "bbox": [1, 2, 3, 4]}, "noise[0]")
    assert found.page == 3
    assert found.bbox == (1.0, 2.0, 3.0, 4.0)


def test_a_different_key_can_hold_the_boxes() -> None:
    cells = {"part_number": [{"page": 1, "bbox": [1, 2, 3, 4]}]}
    assert boxes(cells, "line_items[0].cells.part_number", key="part_number")[0].page == 1
