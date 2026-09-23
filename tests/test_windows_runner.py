"""`make.ps1` checked by PowerShell rather than by reading it.

A PowerShell parse error is total: the script defines nothing and runs nothing, so the
message names whichever line the parser gave up on rather than anything that ran. Every
other check in this repository reads the runner as text and cannot see that at all.

GitHub's Ubuntu runners ship `pwsh`, so this runs in CI. A machine without it skips,
because the alternative is making a Windows convenience a dependency of the test suite.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parent.parent / "make.ps1"
MAKEFILE = Path(__file__).resolve().parent.parent / "Makefile"

# Every executable pip writes into `Scripts\`, matched where a command can begin: the
# start of a line, or straight after the brace that opens a script block. `python -m`
# puts the interpreter in that position instead, which is the whole point.
SHIM = re.compile(r"(?:^|\{)\s*(pip|pytest|mypy|ruff|pre-commit|forge|invoice-extractor)\b")

# A double quote inside a single-quoted PowerShell string survives right up to the moment
# the argument reaches a native executable: Windows PowerShell 5.1 re-quotes the command
# line without escaping it, so python reads `print(..join(...))` and dies on a SyntaxError.
# The other way round - double quotes outside, single inside - the argument arrives whole.
SINGLE_QUOTED = re.compile(r"'[^']*'")

# `ParseFile` reports what is wrong with a script without running a line of it.
PARSE = """
$errors = $null
$tokens = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    '{path}', [ref] $tokens, [ref] $errors) | Out-Null
if ($errors) {{
    $errors | ForEach-Object {{ "line $($_.Extent.StartLineNumber): $($_.Message)" }}
    exit 1
}}
"""


def powershell() -> str:
    found = shutil.which("pwsh") or shutil.which("powershell")
    if found is None:
        pytest.skip("no PowerShell on this machine")
    return found


def test_the_windows_runner_parses() -> None:
    done = subprocess.run(
        [powershell(), "-NoProfile", "-Command", PARSE.format(path=RUNNER.as_posix())],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"make.ps1 does not parse:\n{done.stdout}{done.stderr}"


def test_the_runner_offers_every_target_the_makefile_does() -> None:
    """Two files, one set of names: a target in one and not the other is a trap."""
    declared = set(MAKEFILE.read_text(encoding="utf-8").partition("\n")[0].split()[1:])
    offered = {
        line.split("'")[1]
        for line in RUNNER.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("'") and line.rstrip().endswith("{")
    }
    assert declared == offered, (
        f"only the Makefile has {declared - offered}, only make.ps1 has {offered - declared}"
    )


def test_the_runner_reaches_its_tools_as_modules() -> None:
    """Not through the Scripts shims, which Application Control blocks (see the header).

    A command in this script starts a line or follows the brace that opens a script
    block, so those are the two positions worth reading. A tool name anywhere else is
    prose — `'lint (ruff check)'` is a label, not a call.
    """
    offenders = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(RUNNER.read_text(encoding="utf-8").splitlines(), 1)
        if SHIM.search(line)
    ]
    assert not offenders, f"tools called through the Scripts shims: {offenders}"


def runner_code_lines() -> list[tuple[int, str]]:
    """The runner's numbered lines, with the comment-based help and the comments dropped.

    An apostrophe in prose is not a PowerShell string, and reading one as if it were would
    make the quoting check below fail on a sentence rather than on a command.
    """
    lines: list[tuple[int, str]] = []
    in_help = False
    for number, line in enumerate(RUNNER.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        in_help = in_help or stripped.startswith("<#")
        if in_help:
            in_help = not stripped.endswith("#>")
        elif not stripped.startswith("#"):
            lines.append((number, stripped))
    return lines


def test_the_runner_never_hides_a_double_quote_inside_a_single_quoted_argument() -> None:
    """Windows PowerShell 5.1 eats those before the native executable ever sees them."""
    offenders = [
        f"{number}: {line}"
        for number, line in runner_code_lines()
        for quoted in SINGLE_QUOTED.findall(line)
        if '"' in quoted
    ]
    assert not offenders, f"quotes Windows PowerShell 5.1 will eat on the way out: {offenders}"
