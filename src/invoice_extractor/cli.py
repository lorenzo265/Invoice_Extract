"""`python -m invoice_extractor` — one PDF, one profile, JSON and/or a report.

The exit code is a one-line rule (ADR-0005): `0` whenever extraction ran, however many
findings it returned; non-zero only for input the pipeline never started on.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from invoice_extractor.output.json_writer import write_json
from invoice_extractor.output.text_report import render
from invoice_extractor.pipeline import extract
from invoice_extractor.profile.loader import load_profile
from invoice_extractor.profile.schema import ProfileError

PROGRAM = "invoice-extractor"
DESCRIPTION = "Extract structured, evidence-backed data from a PDF invoice."


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse(argv)
    try:
        profile = load_profile(arguments.profile)
        result = extract(Path(arguments.pdf), profile)
    except (FileNotFoundError, ProfileError) as error:
        sys.stderr.write(f"{error}\n")
        return 1
    if arguments.json is not None:
        write_json(result, Path(arguments.json))
    if arguments.report or arguments.json is None:
        sys.stdout.write(f"{render(result, profile)}\n")
    return 0


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=DESCRIPTION)
    parser.add_argument("pdf", help="path to the invoice PDF")
    parser.add_argument(
        "--profile", required=True, help="profile id or path to a profile JSON file"
    )
    parser.add_argument("--json", metavar="PATH", help="write the full result as JSON to PATH")
    parser.add_argument("--report", action="store_true", help="print the human-readable report")
    return parser.parse_args(argv)
