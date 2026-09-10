"""`forge`'s argument surface, and what it says about the commands not built yet."""

from __future__ import annotations

import pytest

from invoice_forge.cli import BUILT_BY, main

RENDER_ONE = [
    "render-one",
    "--profile",
    "de-DE",
    "--family",
    "classic",
    "--seed",
    "7",
    "--out",
    "x.pdf",
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
        RENDER_ONE,
    ],
)
def test_every_command_names_the_pull_request_that_builds_it(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 1
    message = capsys.readouterr().err
    assert f"PR {BUILT_BY[argv[0]]}" in message
    assert "docs/FORGE_PLAN.md" in message


def test_generate_requires_a_plan_or_profiles() -> None:
    with pytest.raises(SystemExit) as exit_code:
        main(["generate", "--out", "corpus/"])
    assert exit_code.value.code == 2


def test_an_unknown_knob_is_named_and_refused(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([*RENDER_ONE, "--knobs", "multi_page,multipage"]) == 1
    assert "unknown knob: multipage" in capsys.readouterr().err


def test_known_knobs_are_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([*RENDER_ONE, "--knobs", "multi_page,credit_note"]) == 1
    assert "unknown knob" not in capsys.readouterr().err
