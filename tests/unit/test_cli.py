"""The CLI's two commands, and the inputs they refuse to start on.

The paths that need a real PDF live in `tests/integration/test_cli_end_to_end.py`: a unit
test that opens a PDF is testing PyMuPDF, not this codebase.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from invoice_extractor.cli import main


def test_extract_returns_one_for_missing_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "absent.pdf"
    assert main(["extract", str(missing)]) == 1
    assert "absent.pdf" in capsys.readouterr().err


def test_extract_returns_one_when_the_profiles_are_not_where_it_looked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["extract", str(tmp_path / "any.pdf"), "--profiles", str(tmp_path)]) == 1
    assert capsys.readouterr().err.endswith("any.pdf\n")


def test_a_command_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_code:
        main([])
    assert exit_code.value.code == 2
    assert "extract" in capsys.readouterr().err


def test_profile_lint_names_the_tier_it_measured(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["profile", "lint", "de-DE"]) == 0
    assert capsys.readouterr().out.startswith("de-DE: T")


def test_profile_lint_returns_one_for_a_vendor_that_is_not_there(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["profile", "lint", "no_such_vendor"]) == 1
    assert capsys.readouterr().err == "no profile at profiles/no_such_vendor.json\n"


def test_profile_needs_an_action(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_code:
        main(["profile"])
    assert exit_code.value.code == 2
    assert "lint" in capsys.readouterr().err
