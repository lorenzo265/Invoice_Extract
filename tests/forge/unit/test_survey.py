"""Counting a corpus from its truth files, without rendering one."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from invoice_forge.corpus.survey import survey_corpus
from invoice_forge.truth.reading import TruthError


def truth(kind: str = "invoice", knobs: list[str] | None = None, **changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema": "forge-truth/1",
        "generator": {
            "version": "0.1.0",
            "seed": 1,
            "profile": "en-GB",
            "template": "classic",
            "knobs": knobs or [],
        },
        "document": {
            "type": kind,
            "pages": 2,
            "language": "en",
            "currency": "GBP",
            "secondary_currency": None,
            "rounding": "per_line",
        },
        "line_items": [{"pos": 1}, {"pos": 2}],
    }
    return {**base, **changes}


def written(directory: Path, name: str, data: dict[str, Any]) -> Path:
    path = directory / f"{name}.truth.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_a_directory_that_is_not_there_says_so(tmp_path: Path) -> None:
    with pytest.raises(TruthError, match=r"corpus directory not found"):
        survey_corpus(tmp_path / "absent")


def test_an_empty_corpus_counts_nothing(tmp_path: Path) -> None:
    survey = survey_corpus(tmp_path)
    assert survey.documents == 0
    assert survey.item_counts == ()
    assert survey.credit_notes == 0
    assert survey.knobs["multi_page"] == 0
    assert survey.pairs["de-DE", "classic"] == 0


def test_documents_are_counted_by_profile_and_family(tmp_path: Path) -> None:
    written(tmp_path, "a", truth())
    written(tmp_path, "b", truth())
    survey = survey_corpus(tmp_path)
    assert survey.documents == 2
    assert survey.pairs["en-GB", "classic"] == 2


def test_a_credit_note_is_counted_as_one(tmp_path: Path) -> None:
    written(tmp_path, "a", truth(kind="credit_note"))
    written(tmp_path, "b", truth())
    survey = survey_corpus(tmp_path)
    assert survey.credit_notes == 1
    assert survey.documents == 2


def test_a_knob_is_counted_in_every_document_that_turns_it_on(tmp_path: Path) -> None:
    written(tmp_path, "a", truth(knobs=["multi_page", "credit_note"]))
    written(tmp_path, "b", truth(knobs=["multi_page"]))
    survey = survey_corpus(tmp_path)
    assert survey.knobs["multi_page"] == 2
    assert survey.knobs["credit_note"] == 1
    assert survey.knobs["discount"] == 0


def test_rows_and_pages_are_counted_per_document(tmp_path: Path) -> None:
    written(tmp_path, "a", truth())
    written(tmp_path, "b", truth(line_items=[{"pos": 1}]))
    survey = survey_corpus(tmp_path)
    assert sorted(survey.item_counts) == [1, 2]
    assert survey.page_counts == (2, 2)


def test_a_corpus_in_subdirectories_is_still_one_corpus(tmp_path: Path) -> None:
    nested = tmp_path / "deeper"
    nested.mkdir()
    written(tmp_path, "a", truth())
    written(nested, "b", truth())
    assert survey_corpus(tmp_path).documents == 2


def test_knobs_that_are_not_a_list_are_refused(tmp_path: Path) -> None:
    broken = truth()
    broken["generator"]["knobs"] = "multi_page"
    written(tmp_path, "a", broken)
    with pytest.raises(TruthError, match=r"generator.knobs must be a list of strings"):
        survey_corpus(tmp_path)
