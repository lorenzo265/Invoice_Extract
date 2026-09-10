"""`forge`'s argument surface: what it does, and what it says about what it cannot yet do."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from invoice_forge.cli import BUILT_BY, main


def render_one(out: Path, *extra: str) -> list[str]:
    return [
        "render-one",
        "--profile",
        "de-DE",
        "--family",
        "classic",
        "--seed",
        "7",
        "--out",
        str(out),
        *extra,
    ]


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_code:
        main(["--help"])
    assert exit_code.value.code == 0
    assert "forge" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["generate", "--plan", "corpus/plan.json", "--out", "corpus/"],
        ["generate", "--profiles", "de-DE", "--out", "corpus/"],
        ["catalog", "corpus/"],
        ["verify", "corpus/"],
    ],
)
def test_a_command_not_built_yet_names_the_pull_request_that_builds_it(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 1
    message = capsys.readouterr().err
    assert f"PR {BUILT_BY[argv[0]]}" in message
    assert "docs/FORGE_PLAN.md" in message


def test_render_one_is_built_and_no_longer_claims_otherwise() -> None:
    assert "render-one" not in BUILT_BY


def test_generate_requires_a_plan_or_profiles() -> None:
    with pytest.raises(SystemExit) as exit_code:
        main(["generate", "--out", "corpus/"])
    assert exit_code.value.code == 2


def test_render_one_writes_a_pdf_and_its_truth(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "one.pdf"
    assert main(render_one(out)) == 0
    truth = tmp_path / "one.truth.json"
    assert out.is_file()
    assert truth.is_file()
    printed = capsys.readouterr().out
    assert str(out) in printed
    assert str(truth) in printed


def test_render_one_makes_the_directory_it_is_pointed_at(tmp_path: Path) -> None:
    out = tmp_path / "deep" / "down" / "one.pdf"
    assert main(render_one(out)) == 0
    assert out.is_file()


def test_the_truth_it_writes_records_the_knobs_it_was_given(tmp_path: Path) -> None:
    out = tmp_path / "one.pdf"
    assert main(render_one(out, "--knobs", "multi_page,credit_note")) == 0
    truth = json.loads((tmp_path / "one.truth.json").read_text(encoding="utf-8"))
    assert truth["generator"]["knobs"] == ["multi_page", "credit_note"]
    assert truth["generator"]["seed"] == 7
    assert truth["generator"]["profile"] == "de-DE"


def test_an_unknown_knob_is_named_and_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(render_one(tmp_path / "x.pdf", "--knobs", "multi_page,multipage")) == 1
    assert "unknown knob: multipage" in capsys.readouterr().err
    assert not (tmp_path / "x.pdf").exists()


def test_an_unknown_family_is_named_and_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["render-one", "--profile", "de-DE", "--family", "baroque"]
    argv += ["--seed", "7", "--out", str(tmp_path / "x.pdf")]
    assert main(argv) == 1
    assert "unknown family baroque" in capsys.readouterr().err


def test_a_family_that_is_declared_but_not_built_says_which_are(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["render-one", "--profile", "de-DE", "--family", "saas"]
    argv += ["--seed", "7", "--out", str(tmp_path / "x.pdf")]
    assert main(argv) == 1
    assert "not built yet" in capsys.readouterr().err


def test_an_unknown_profile_names_the_file_it_looked_for(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["render-one", "--profile", "zz-ZZ", "--family", "classic"]
    argv += ["--seed", "7", "--out", str(tmp_path / "x.pdf")]
    assert main(argv) == 1
    assert "profile file not found" in capsys.readouterr().err


def test_the_module_entry_point_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["invoice_forge", *render_one(tmp_path / "one.pdf")])
    with pytest.raises(SystemExit) as exit_code:
        runpy.run_module("invoice_forge", run_name="__main__")
    assert exit_code.value.code == 0
    assert "one.pdf" in capsys.readouterr().out
