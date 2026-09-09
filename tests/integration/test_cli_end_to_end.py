"""The CLI against a real sample: what it writes, what it prints, what `make demo` shows."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from invoice_extractor.cli import main

README = Path("README.md")
ACME = "samples/acme_invoice.pdf"


def readme_report() -> str:
    """The report block README.md promises, taken from between its fences."""
    lines = README.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line == "Invoice Extraction Report")
    end = next(index for index in range(start, len(lines)) if lines[index].startswith("```"))
    return "\n".join(lines[start:end]) + "\n"


def test_cli_prints_report_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([ACME, "--layout", "acme"]) == 0
    assert capsys.readouterr().out.startswith("Invoice Extraction Report")


def test_cli_writes_json_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "result.json"
    assert main([ACME, "--layout", "acme", "--json", str(target)]) == 0
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["fields"]["total_amount"]["value"] == "588.00"
    assert written["fields"]["total_amount"]["confidence"] == 1.0
    assert capsys.readouterr().out == ""


def test_cli_prints_the_report_alongside_json_when_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "result.json"
    assert main([ACME, "--layout", "acme", "--json", str(target), "--report"]) == 0
    assert capsys.readouterr().out.startswith("Invoice Extraction Report")
    assert target.exists()


def test_demo_command_output_matches_readme(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([ACME, "--layout", "acme", "--report"]) == 0
    assert capsys.readouterr().out == readme_report()


def test_module_entry_point_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["invoice_extractor", ACME, "--layout", "acme"])
    with pytest.raises(SystemExit) as exit_code:
        runpy.run_module("invoice_extractor", run_name="__main__")
    assert exit_code.value.code == 0
    assert capsys.readouterr().out.startswith("Invoice Extraction Report")
