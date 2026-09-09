"""The two bundled layouts load, and describe the invoices they ship with."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from invoice_extractor.layout.loader import load_layout
from invoice_extractor.layout.schema import FIELD_NAMES, LINE_ITEM_COLUMNS

BUNDLED = ("acme", "nordic")
SAMPLES = Path("samples")


def golden(layout_id: str) -> dict[str, Any]:
    text = (SAMPLES / f"{layout_id}_invoice.expected.json").read_text(encoding="utf-8")
    return json.loads(text)


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_bundled_layouts_load(layout_id: str) -> None:
    layout = load_layout(layout_id)
    assert layout.id == layout_id
    assert tuple(layout.fields) == FIELD_NAMES
    assert tuple(layout.line_items.header_labels) == LINE_ITEM_COLUMNS


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_bundled_layout_labels_match_samples_spec(layout_id: str) -> None:
    layout = load_layout(layout_id)
    fields = golden(layout_id)["fields"]
    for name in FIELD_NAMES:
        label = layout.fields[name].labels[0]
        assert fields[name]["raw_text"].startswith(f"{label}:"), f"{layout_id}.{name}"


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_bundled_stop_label_is_the_subtotal_label(layout_id: str) -> None:
    layout = load_layout(layout_id)
    # A stop word taken from the table's own vocabulary would end the table at row one.
    assert layout.line_items.stop_labels == layout.fields["subtotal"].labels
