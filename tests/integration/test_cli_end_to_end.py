"""The CLI against a real document: what it writes, what it prints, what `make demo` shows.

The document is one of the corpus fixtures committed under `tests/forge/fixtures/corpus/`
— the only invoices in the repository that are not regenerated, which is what lets the
report in `README.md` be compared against a run rather than trusted.
"""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from invoice_extractor.cli import main

README = Path("README.md")
DEMO_PDF = "tests/forge/fixtures/corpus/0001_fr-FR_classic_s7.pdf"
CORPUS = Path("tests/forge/fixtures/corpus")
DEMO_PROFILE = "fr-FR"


def readme_report() -> str:
    """The report block README.md promises, taken from between its fences."""
    lines = README.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line == "Invoice Extraction Report")
    end = next(index for index in range(start, len(lines)) if lines[index].startswith("```"))
    return "\n".join(lines[start:end]) + "\n"


def test_cli_prints_report_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["extract", DEMO_PDF]) == 0
    assert capsys.readouterr().out.startswith("Invoice Extraction Report")


def test_cli_writes_json_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "result.json"
    assert main(["extract", DEMO_PDF, "--json", str(target)]) == 0
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["profile_id"] == DEMO_PROFILE
    assert written["valid"] is True
    assert written["fields"]["total_amount"]["value"] is not None
    assert capsys.readouterr().out == ""


def test_cli_prints_the_report_alongside_json_when_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "result.json"
    assert main(["extract", DEMO_PDF, "--json", str(target), "--report"]) == 0
    assert capsys.readouterr().out.startswith("Invoice Extraction Report")
    assert target.exists()


def test_demo_command_output_matches_readme(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["extract", DEMO_PDF, "--report"]) == 0
    assert capsys.readouterr().out == readme_report()


def test_module_entry_point_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["invoice_extractor", "extract", DEMO_PDF])
    with pytest.raises(SystemExit) as exit_code:
        runpy.run_module("invoice_extractor", run_name="__main__")
    assert exit_code.value.code == 0
    assert capsys.readouterr().out.startswith("Invoice Extraction Report")


def test_calibrate_fits_a_corpus_and_says_how_far_off_it_is(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The one command that writes something other than a result (ENGINE_SPEC §9)."""
    assert main(["calibrate", "--corpus", str(CORPUS), "--out", str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert "documents fitted into" in printed
    assert "expected calibration error" in printed
    assert {path.name for path in tmp_path.glob("*.json")} == {
        "weights.json",
        "calibration_maps.json",
        "reliability_report.json",
    }
