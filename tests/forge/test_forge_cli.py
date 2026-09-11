"""`forge`'s argument surface: what it does, and what it says about what it will not do."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from invoice_forge.cli import BUILT_BY, main
from invoice_forge.families import FAMILY_NAMES


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


def test_every_command_the_specification_names_is_built() -> None:
    """`BUILT_BY` is empty: nothing is left claiming a pull request will bring it."""
    assert BUILT_BY == {}


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


@pytest.mark.parametrize("family", FAMILY_NAMES)
def test_every_family_the_vocabulary_names_renders_from_the_command_line(
    family: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["render-one", "--profile", "de-DE", "--family", family]
    argv += ["--seed", "7", "--out", str(tmp_path / f"{family}.pdf")]
    assert main(argv) == 0
    assert str(tmp_path / f"{family}.pdf") in capsys.readouterr().out


def test_two_knobs_that_are_one_axis_are_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A cell cannot ask for both roundings: a document is rounded one way or the other."""
    argv = ["render-one", "--profile", "de-DE", "--family", "classic"]
    argv += ["--knobs", "rounding_per_line,rounding_total"]
    argv += ["--seed", "7", "--out", str(tmp_path / "x.pdf")]
    assert main(argv) == 1
    complaint = capsys.readouterr().err
    assert "rounding_per_line" in complaint
    assert "rounding_total" in complaint


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


def test_generate_verify_and_catalog_run_through_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = str(tmp_path / "corpus")
    argv = ["generate", "--profiles", "en-GB", "--count", "1", "--seed", "3", "--out", out]
    assert main(argv) == 0
    assert "1 documents" in capsys.readouterr().out
    assert main(["verify", out]) == 0
    assert "verified" in capsys.readouterr().out
    assert main(["catalog", out]) == 1
    assert "rows not met" in capsys.readouterr().out


def test_generate_reads_a_plan_file_when_given_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema": "forge-plan/1",
                "cells": [{"profile": "en-GB", "family": "classic", "seed": 5}],
            }
        ),
        encoding="utf-8",
    )
    out = str(tmp_path / "corpus")
    assert main(["generate", "--plan", str(plan), "--out", out]) == 0
    assert "0001_en-GB_classic_s5.pdf" in capsys.readouterr().out


def test_generate_names_the_key_a_broken_plan_gets_wrong(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"schema": "forge-plan/1", "cells": []}), encoding="utf-8")
    assert main(["generate", "--plan", str(plan), "--out", str(tmp_path / "c")]) == 1
    assert "cells must be a non-empty list" in capsys.readouterr().err


def test_generate_defaults_to_the_maximal_family(tmp_path: Path) -> None:
    out = str(tmp_path / "corpus")
    assert main(["generate", "--profiles", "en-GB", "--seed", "3", "--out", out]) == 0
    assert (tmp_path / "corpus" / "0001_en-GB_classic_s3.pdf").is_file()


def test_verify_says_which_corpus_it_cannot_find(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["verify", str(tmp_path / "absent")]) == 1
    assert "corpus directory not found" in capsys.readouterr().err


def test_catalog_says_which_corpus_it_cannot_find(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["catalog", str(tmp_path / "absent")]) == 1
    assert "corpus directory not found" in capsys.readouterr().err


def test_verify_reports_a_corpus_that_does_not_hold_up(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "corpus"
    assert main(["generate", "--profiles", "en-GB", "--seed", "3", "--out", str(out)]) == 0
    truth = next(out.glob("*.truth.json"))
    broken = json.loads(truth.read_text(encoding="utf-8"))
    broken["fields"]["total_amount"]["value"] = "1.00"
    truth.write_text(json.dumps(broken), encoding="utf-8")
    capsys.readouterr()
    assert main(["verify", str(out)]) == 1
    printed = capsys.readouterr().out
    assert "arithmetic" in printed
    assert "determinism" in printed
    assert "1 documents: 2 failures" in printed
