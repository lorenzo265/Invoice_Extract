"""What each `forge` subcommand does, once its arguments have been parsed.

Kept apart from `cli.py` so the argument surface stays readable as one page, and so a
caller that wants a corpus from Python does not have to build an argv to get one.
"""

from __future__ import annotations

import sys
from pathlib import Path

from invoice_forge.corpus.catalog import catalog, met_all, render_table
from invoice_forge.corpus.generate import generate
from invoice_forge.corpus.plan import Plan, load_plan, plan_from_arguments
from invoice_forge.corpus.survey import survey_corpus
from invoice_forge.families import FAMILY_NAMES, Family
from invoice_forge.jsonspec import SpecError
from invoice_forge.knobs import Knob
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.truth.locate import LocateError
from invoice_forge.truth.reading import TruthError
from invoice_forge.truth.verify import verify_corpus

FAILED, PASSED = 1, 0
SEPARATOR = ","


def render_one(profile: str, family_name: str, seed: int, knobs: tuple[Knob, ...], out: str) -> int:
    """Render one document and its truth, and say where both went."""
    spec = DocumentSpec(profile, family(family_name), seed, knobs)
    produced = produce(spec, Path(out))
    sys.stdout.write(f"{produced.pdf} ({produced.pages} pages)\n{produced.truth}\n")
    return PASSED


def generate_corpus(
    plan_path: str | None,
    profiles: str | None,
    families: str | None,
    count: int,
    seed: int,
    out: str,
) -> int:
    """Run a plan, or the cross product named on the command line, into a directory."""
    plan = load_plan(plan_path) if plan_path else _planned(profiles, families, count, seed)
    written = generate(plan, Path(out), progress=_announce)
    sys.stdout.write(f"{len(written.documents)} documents, {written.pages} pages, in {out}\n")
    return PASSED


def verify(corpus: str) -> int:
    """Check every document in a corpus and report what does not hold up."""
    report = verify_corpus(Path(corpus))
    for failure in report.failures:
        sys.stdout.write(f"{failure}\n")
    checked = f"{len(report.documents)} documents"
    if report.ok:
        sys.stdout.write(f"{checked}: verified\n")
        return PASSED
    sys.stdout.write(f"{checked}: {len(report.failures)} failures\n")
    return FAILED


def report_catalog(corpus: str) -> int:
    """Report coverage against `docs/VARIATION_CATALOG.md`, and fail when a row is unmet."""
    directory = Path(corpus)
    rows = catalog(directory)
    sys.stdout.write(render_table(rows, survey_corpus(directory).documents))
    return PASSED if met_all(rows) else FAILED


def family(name: str) -> Family:
    if name not in FAMILY_NAMES:
        raise SpecError(f"unknown family {name}; known: {', '.join(FAMILY_NAMES)}")
    return Family(name)


def split(argument: str | None) -> tuple[str, ...]:
    """A comma-separated argument, with the empty pieces a trailing comma leaves dropped."""
    if not argument:
        return ()
    return tuple(piece.strip() for piece in argument.split(SEPARATOR) if piece.strip())


def failures() -> tuple[type[Exception], ...]:
    """What a command may raise for a reason the user can fix, and see a message about."""
    return (SpecError, TruthError, LocateError, ValueError, OSError)


def _planned(profiles: str | None, families: str | None, count: int, seed: int) -> Plan:
    named = split(families) or (Family.CLASSIC.value,)
    return plan_from_arguments(split(profiles), [family(name) for name in named], count, seed)


def _announce(done: int, total: int, path: Path) -> None:
    sys.stdout.write(f"[{done}/{total}] {path.name}\n")
