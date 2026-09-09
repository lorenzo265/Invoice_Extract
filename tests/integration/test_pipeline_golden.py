"""The pipeline against the committed golden results, on both real sample PDFs.

The comparison is a projection: `confidence` and `confidence_breakdown` are removed from
every field before comparing, because those are the output of an algorithm the golden
files deliberately do not pin (docs/SAMPLES_SPEC.md). Everything else — value, raw text,
validity and the full evidence, bounding box included — is compared exactly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from invoice_extractor import extract, load_layout

SAMPLES = Path("samples")
BUNDLED = ("acme", "nordic")
UNPINNED = ("confidence", "confidence_breakdown")


def golden(layout_id: str) -> dict[str, Any]:
    text = (SAMPLES / f"{layout_id}_invoice.expected.json").read_text(encoding="utf-8")
    return json.loads(text)


def extracted(layout_id: str) -> dict[str, Any]:
    result = extract(SAMPLES / f"{layout_id}_invoice.pdf", load_layout(layout_id))
    return result.to_dict()


def projected_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {
        name: {key: value for key, value in field.items() if key not in UNPINNED}
        for name, field in data["fields"].items()
    }


def projected(data: dict[str, Any]) -> dict[str, Any]:
    return {**data, "fields": projected_fields(data)}


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_scalar_fields_match_expected_json(layout_id: str) -> None:
    assert projected_fields(extracted(layout_id)) == projected_fields(golden(layout_id))


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_line_items_match_expected_json(layout_id: str) -> None:
    assert extracted(layout_id)["line_items"] == golden(layout_id)["line_items"]


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_clean_samples_report_no_table_findings(layout_id: str) -> None:
    assert extracted(layout_id)["findings"] == golden(layout_id)["findings"]


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_full_result_matches_expected_json(layout_id: str) -> None:
    assert projected(extracted(layout_id)) == projected(golden(layout_id))


@pytest.mark.parametrize("layout_id", BUNDLED)
def test_result_names_its_layout_and_source(layout_id: str) -> None:
    data = extracted(layout_id)
    assert data["layout_id"] == golden(layout_id)["layout_id"]
    assert data["source_path"] == golden(layout_id)["source_path"]
