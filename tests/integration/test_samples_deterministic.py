"""The committed samples are reproducible: same bytes, same arithmetic, every run."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from make_samples import SAMPLES, draw, write_expected

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMITTED = REPO_ROOT / "samples"


def generate(directory: Path) -> list[Path]:
    """Write both samples into `directory`, returning every file produced, sorted by name."""
    written: list[Path] = []
    for sample in SAMPLES.values():
        pdf_path = directory / f"{sample.layout_id}_invoice.pdf"
        json_path = pdf_path.with_suffix(".expected.json")
        draw(sample, pdf_path)
        write_expected(sample, pdf_path, json_path)
        written += [pdf_path, json_path]
    return sorted(written)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def golden(layout_id: str) -> dict[str, Any]:
    text = (COMMITTED / f"{layout_id}_invoice.expected.json").read_text(encoding="utf-8")
    return json.loads(text)


def field_value(data: dict[str, Any], name: str) -> Decimal:
    return Decimal(data["fields"][name]["value"])


def test_make_samples_is_byte_deterministic(tmp_path: Path) -> None:
    first = generate(tmp_path / "first")
    second = generate(tmp_path / "second")
    assert [digest(path) for path in first] == [digest(path) for path in second]


def test_committed_samples_match_generator(tmp_path: Path) -> None:
    for regenerated in generate(tmp_path):
        committed = COMMITTED / regenerated.name
        assert regenerated.read_bytes() == committed.read_bytes(), regenerated.name


@pytest.mark.parametrize("layout_id", sorted(SAMPLES))
def test_expected_json_arithmetic_is_consistent(layout_id: str) -> None:
    data = golden(layout_id)
    subtotal = field_value(data, "subtotal")
    vat_amount = field_value(data, "vat_amount")
    line_items = data["line_items"]
    net_total = sum((Decimal(item["net_amount"]) for item in line_items), Decimal(0))
    assert net_total == subtotal
    assert subtotal + vat_amount == field_value(data, "total_amount")
    assert subtotal * field_value(data, "vat_rate") / Decimal(100) == vat_amount
