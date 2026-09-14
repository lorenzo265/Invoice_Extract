"""The CLI's argument handling and the two inputs it refuses to start on.

The paths that need a real PDF live in `tests/integration/test_cli_end_to_end.py`: a unit
test that opens a PDF is testing PyMuPDF, not this codebase.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from invoice_extractor.cli import main

KNOWN_PROFILE = "en-GB"


def test_cli_returns_one_for_missing_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "absent.pdf"
    assert main([str(missing), "--profile", KNOWN_PROFILE]) == 1
    assert "absent.pdf" in capsys.readouterr().err


def test_cli_returns_one_for_unknown_profile_with_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path / "any.pdf"), "--profile", "no_such_vendor"]) == 1
    assert capsys.readouterr().err == "no profile at profiles/no_such_vendor.json\n"


def test_cli_requires_a_profile(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_code:
        main([str(tmp_path / "any.pdf")])
    assert exit_code.value.code == 2
    assert "--profile" in capsys.readouterr().err
