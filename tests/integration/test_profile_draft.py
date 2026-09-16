"""`profile draft` against a real document: the profile it writes reads the page back.

The proof a draft is worth anything: drafted from one corpus fixture into an empty
directory, the profile loads, lints at T2, is the one `extract` detects for that same
document, and reads its header back with the confidence the shipped profile does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from invoice_extractor.cli import main

GERMAN_PDF = "tests/forge/fixtures/corpus/0002_de-DE_classic_s7.pdf"


def drafted(tmp_path: Path, *arguments: str) -> Path:
    out = tmp_path / "vendors" / "profiles"
    assert main(["profile", "draft", GERMAN_PDF, "--out", str(out), *arguments]) == 0
    return out


def test_the_draft_lands_with_its_evidence_defaults_and_lexicon(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = drafted(tmp_path, "--id", "draft-de")
    printed = capsys.readouterr().out
    assert (out / "draft-de.json").is_file()
    assert (out / "_defaults.json").is_file()
    assert (tmp_path / "vendors" / "lexicon" / "de.json").is_file()
    evidence = json.loads((tmp_path / "vendors" / "drafts" / "draft-de.json").read_text("utf-8"))
    assert evidence["language"]["chosen"] == "de"
    assert evidence["placeholders"] == []
    assert printed.startswith("Drafted draft-de from tests/forge/fixtures/corpus/0002_de-DE")
    assert "supplier.name" in printed


def test_the_drafted_profile_lints_at_t2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = drafted(tmp_path, "--id", "draft-de")
    capsys.readouterr()
    assert main(["profile", "lint", "draft-de", "--profiles", str(out)]) == 0
    assert capsys.readouterr().out.startswith("draft-de: T2")


def test_the_drafted_profile_reads_the_document_it_was_drafted_from(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = drafted(tmp_path, "--id", "draft-de")
    target = tmp_path / "result.json"
    assert main(["extract", GERMAN_PDF, "--profiles", str(out), "--json", str(target)]) == 0
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["profile_id"] == "draft-de"
    assert result["fields"]["invoice_number"]["value"] == "RG-2024-442182"
    assert result["fields"]["total_amount"]["value"] == "94553.88"
    assert result["fields"]["invoice_date"]["confidence"] >= 0.99
    shipped = tmp_path / "shipped.json"
    assert main(["extract", GERMAN_PDF, "--json", str(shipped)]) == 0
    expected = json.loads(shipped.read_text(encoding="utf-8"))
    assert result["findings"] == expected["findings"], "what the document says about itself"
    assert {name: field["value"] for name, field in result["fields"].items()} == {
        name: field["value"] for name, field in expected["fields"].items()
    }


def test_the_draft_is_named_after_its_language_and_country_by_default(tmp_path: Path) -> None:
    out = drafted(tmp_path)
    assert (out / "de-DE.json").is_file()


def test_a_language_no_lexicon_speaks_gets_a_skeleton_and_the_page_labels(
    tmp_path: Path,
) -> None:
    out = drafted(tmp_path, "--language", "xx")
    skeleton = json.loads((tmp_path / "vendors" / "lexicon" / "xx.json").read_text("utf-8"))
    assert skeleton["header_labels"]["invoice_number"] == ["?"]
    profile = json.loads((out / "xx-DE.json").read_text(encoding="utf-8"))
    assert profile["fields"]["invoice_number"]["labels"] == ["Rechnungs-Nr."]


def test_a_second_draft_over_the_first_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = drafted(tmp_path, "--id", "draft-de")
    capsys.readouterr()
    assert main(["profile", "draft", GERMAN_PDF, "--out", str(out), "--id", "draft-de"]) == 1
    assert (
        capsys.readouterr().err
        == f"{out / 'draft-de.json'} already exists; pass --id to name the draft differently\n"
    )
