"""`python -m invoice_extractor` — read one PDF, inspect one, or lint one profile.

The exit code is a one-line rule (ADR-0005): `0` whenever the command ran, however many
findings or shortfalls it reported; non-zero only for input it never started on — a PDF
that is not there, a profile that does not load.

`extract` is not given a vendor. It detects one (ADR-0008), and a document no profile
matches comes back with `profile_not_detected` and nothing read, which is the result a
reviewer needs rather than a plausible-looking wrong one.

`inspect` is the command for the moment before a vendor has a profile at all: it
prints the page as the engine reads it — every line with its zone and its box — and
how each known vendor scored against it. Writing a profile means naming labels and
zones, and this is where both are read off rather than guessed at.

`profile draft` is the inverse of `inspect`: it writes the profile a page suggests, with
the evidence for every key beside it, for a person to correct. A drafting tool only — the
engine never runs it, and a document no profile matches still comes back
`profile_not_detected` (ADR-0008).

`calibrate` is the one command that writes something other than a result: it fits the
confidence on a corpus whose answers are known and writes the three files of
`calibration/`. Promoting what it wrote is a reviewed commit, not a side effect of
running it (ENGINE_SPEC §9).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from invoice_extractor.document.pymupdf_reader import read
from invoice_extractor.drafting import summary, writer
from invoice_extractor.drafting.draft import draft
from invoice_extractor.output import inspection
from invoice_extractor.output.json_writer import emit
from invoice_extractor.output.text_report import render
from invoice_extractor.pipeline import extract
from invoice_extractor.profile import lint as linting
from invoice_extractor.profile.detect import detect_profile
from invoice_extractor.profile.loader import PROFILES_ROOT
from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.profile.schema import ProfileError
from invoice_extractor.scoring.calibrate import calibrate
from invoice_extractor.scoring.weights import CALIBRATION_ROOT

PROGRAM = "invoice-extractor"
DESCRIPTION = "Extract structured, evidence-backed data from a PDF invoice."
ROOT_HELP = "directory of vendor profiles (default: the ones this package ships with)"


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse(argv)
    try:
        registry = ProfileRegistry(Path(arguments.profiles))
        if arguments.command == "extract":
            return _extract(arguments, registry)
        if arguments.command == "inspect":
            return _inspect(arguments, registry)
        if arguments.command == "calibrate":
            return _calibrate(arguments, registry)
        if arguments.action == "draft":
            return _draft(arguments, registry)
        return _lint(arguments, registry)
    except (FileNotFoundError, FileExistsError, ProfileError) as error:
        sys.stderr.write(f"{error}\n")
        return 1


def _extract(arguments: argparse.Namespace, registry: ProfileRegistry) -> int:
    result = extract(Path(arguments.pdf), registry)
    if arguments.json is not None:
        written, mirror = emit(result, Path(arguments.json))
        sys.stderr.write(f"wrote {written} and {mirror}\n")
    if arguments.report or arguments.json is None:
        sys.stdout.write(f"{render(result)}\n")
    return 0


def _inspect(arguments: argparse.Namespace, registry: ProfileRegistry) -> int:
    """Read the page and weigh the vendors, and report both. Nothing is extracted."""
    document = read(Path(arguments.pdf))
    _, scores = detect_profile(document, registry, Path(arguments.pdf).name)
    sys.stdout.write(f"{inspection.render(document, scores)}\n")
    return 0


def _calibrate(arguments: argparse.Namespace, registry: ProfileRegistry) -> int:
    report = calibrate(Path(arguments.corpus), Path(arguments.out), registry)
    written = ", ".join(sorted(path.name for path in Path(arguments.out).glob("*.json")))
    sys.stdout.write(
        f"{report.documents} documents fitted into {arguments.out}: {written}\n"
        f"expected calibration error {report.expected_calibration_error:.4f}\n"
    )
    return 0


def _draft(arguments: argparse.Namespace, registry: ProfileRegistry) -> int:
    """Read the page, write the profile it suggests and the evidence beside it, report both."""
    drafted = draft(read(Path(arguments.pdf)), registry, arguments.id, arguments.language)
    written = writer.write(
        drafted.profile, drafted.evidence, Path(arguments.out), registry.root, drafted.vocabulary
    )
    sys.stdout.write(f"{summary.render(drafted.evidence, written)}\n")
    return 0


def _lint(arguments: argparse.Namespace, registry: ProfileRegistry) -> int:
    report = linting.lint(registry.get(arguments.profile_id), registry)
    sys.stdout.write(f"{linting.render(report)}\n")
    return 0


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=DESCRIPTION)
    commands = parser.add_subparsers(dest="command", required=True)
    _extract_parser(commands.add_parser("extract", help="extract one invoice"))
    _inspect_parser(commands.add_parser("inspect", help="show what the engine sees"))
    _profile_parser(commands.add_parser("profile", help="work with vendor profiles"))
    _calibrate_parser(commands.add_parser("calibrate", help="fit the confidence on a corpus"))
    return parser.parse_args(argv)


def _extract_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pdf", help="path to the invoice PDF")
    parser.add_argument("--profiles", default=str(PROFILES_ROOT), help=ROOT_HELP)
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="write the full result to PATH, and its findings beside it",
    )
    parser.add_argument("--report", action="store_true", help="print the human-readable report")


def _inspect_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pdf", help="path to the invoice PDF")
    parser.add_argument("--profiles", default=str(PROFILES_ROOT), help=ROOT_HELP)


def _calibrate_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--corpus", default="corpus", help="directory of PDFs and truth files")
    parser.add_argument("--out", default=str(CALIBRATION_ROOT), help="where to write the fit")
    parser.add_argument("--profiles", default=str(PROFILES_ROOT), help=ROOT_HELP)


def _profile_parser(parser: argparse.ArgumentParser) -> None:
    actions = parser.add_subparsers(dest="action", required=True)
    lint = actions.add_parser("lint", help="report how ready a profile is")
    lint.add_argument("profile_id", help="the profile to measure against the others")
    lint.add_argument("--profiles", default=str(PROFILES_ROOT), help=ROOT_HELP)
    drafting = actions.add_parser("draft", help="write the profile one document suggests")
    drafting.add_argument("pdf", help="path to the invoice PDF to draft from")
    drafting.add_argument(
        "--out", required=True, metavar="DIR", help="profile directory to write into"
    )
    drafting.add_argument("--id", help="profile id (default: <language>-<COUNTRY>, else draft)")
    drafting.add_argument("--language", help="ISO 639-1 code, where the page's language is known")
    drafting.add_argument("--profiles", default=str(PROFILES_ROOT), help=ROOT_HELP)
