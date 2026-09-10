"""`forge` — generate a corpus, check it, and report what it covers.

The four subcommands and their arguments are fixed by `docs/FORGE_SPEC.md` §4 and are
declared here in full, so `forge --help` describes the finished tool from the first
commit. Each one names the pull request of `docs/FORGE_PLAN.md` that builds it until it
is built.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from invoice_forge.families import FAMILY_NAMES, Family
from invoice_forge.jsonspec import SpecError
from invoice_forge.knobs import KNOB_NAMES, Knob, split_knobs
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.truth.locate import LocateError

PROGRAM = "forge"
DESCRIPTION = "Generate synthetic invoice PDFs with exact ground truth."
BUILT_BY = {"generate": "F3", "catalog": "F3", "verify": "F3"}


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse(argv)
    knobs: tuple[Knob, ...] = ()
    if arguments.knobs is not None:
        try:
            knobs = split_knobs(arguments.knobs)
        except ValueError as error:
            return _failed(error)
    if arguments.command == "render-one":
        return _render_one(arguments, knobs)
    command = arguments.command
    sys.stderr.write(f"forge {command} arrives in PR {BUILT_BY[command]} of docs/FORGE_PLAN.md\n")
    return 1


def _render_one(arguments: argparse.Namespace, knobs: tuple[Knob, ...]) -> int:
    """Render one document and its truth, and say where both went."""
    try:
        family = _family(arguments.family)
        spec = DocumentSpec(arguments.profile, family, arguments.seed, knobs)
        produced = produce(spec, Path(arguments.out))
    except (SpecError, LocateError, ValueError) as error:
        return _failed(error)
    sys.stdout.write(f"{produced.pdf} ({produced.pages} pages)\n{produced.truth}\n")
    return 0


def _family(name: str) -> Family:
    try:
        return Family(name)
    except ValueError as error:
        raise ValueError(f"unknown family {name}; known: {', '.join(FAMILY_NAMES)}") from error


def _failed(error: Exception) -> int:
    sys.stderr.write(f"{error}\n")
    return 1


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=DESCRIPTION)
    parser.set_defaults(knobs=None)
    subcommands = parser.add_subparsers(dest="command", required=True)
    _add_generate(subcommands)
    _add_corpus_command(subcommands, "catalog", "report coverage against docs/VARIATION_CATALOG.md")
    _add_corpus_command(subcommands, "verify", "check readback, arithmetic and determinism")
    _add_render_one(subcommands)
    return parser.parse_args(argv)


def _add_generate(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subcommands.add_parser("generate", help="generate a corpus of documents")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--plan", metavar="PATH", help="a plan naming every cell to generate")
    source.add_argument("--profiles", help="comma-separated profile ids")
    parser.add_argument("--families", help="comma-separated template family names")
    parser.add_argument("--count", type=int, default=1, help="documents per profile and family")
    parser.add_argument("--seed", type=int, default=0, help="the seed the corpus derives from")
    parser.add_argument("--out", metavar="PATH", required=True, help="directory to write into")


def _add_corpus_command(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser], name: str, help_text: str
) -> None:
    parser = subcommands.add_parser(name, help=help_text)
    parser.add_argument("corpus", help="directory holding the generated documents")


def _add_render_one(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subcommands.add_parser("render-one", help="render a single document")
    parser.add_argument("--profile", required=True, help="the profile id to render")
    parser.add_argument("--family", required=True, help="the template family to render")
    parser.add_argument(
        "--knobs", default="", help=f"comma-separated, from: {', '.join(KNOB_NAMES)}"
    )
    parser.add_argument("--seed", type=int, required=True, help="the seed to render from")
    parser.add_argument("--out", metavar="PATH", required=True, help="the PDF to write")
