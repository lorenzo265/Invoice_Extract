"""The CLI's argument handling and the two inputs it refuses to start on.

The paths that need a real PDF live in `tests/integration/test_cli_end_to_end.py`: a unit
test that opens a PDF is testing PyMuPDF, not this codebase.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from invoice_extractor.cli import main


def test_cli_returns_one_for_missing_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "absent.pdf"
    assert main([str(missing), "--layout", "acme"]) == 1
    assert "absent.pdf" in capsys.readouterr().err


def test_cli_returns_one_for_bad_layout_with_message(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["samples/acme_invoice.pdf", "--layout", "no_such_vendor"]) == 1
    assert capsys.readouterr().err == "layout file not found: layouts/no_such_vendor.json\n"


def test_cli_requires_a_layout(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_code:
        main(["samples/acme_invoice.pdf"])
    assert exit_code.value.code == 2
    assert "--layout" in capsys.readouterr().err
