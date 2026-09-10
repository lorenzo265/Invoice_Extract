"""`forge verify`: proving a corpus, one document at a time.

Four claims are checked, and a corpus is only usable if all four hold for every document:

- **Schema.** The file is `forge-truth/1` and describes the PDF that is beside it.
- **Readback.** Every box the truth names holds the text the truth says it holds, read
  out of the PDF rather than remembered from the render.
- **Arithmetic.** The rows add to the subtotal, the rates apply to their bases, and the
  blocks add to the total, under the rounding policy the document declares.
- **Determinism.** Generating the document again from its own recorded seed, profile,
  family and knobs produces the same bytes.

A benchmark measured against an unverified corpus measures two things at once. This is
what keeps it measuring one.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from invoice_forge.families import Family
from invoice_forge.knobs import parse_knobs
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.render.pdf import pages_in
from invoice_forge.truth.checks import check_arithmetic, check_evidence_rule, check_schema
from invoice_forge.truth.readback import check_readback
from invoice_forge.truth.reading import TruthError, block, read_truth, text, whole

TRUTH_SUFFIX = ".truth.json"
CHECKS: tuple[str, ...] = ("schema", "readback", "arithmetic", "evidence", "determinism")


@dataclass(frozen=True, slots=True)
class Failure:
    """One thing wrong with one document, named so it can be found and fixed."""

    document: str
    check: str
    detail: str

    def __str__(self) -> str:
        return f"{self.document}: {self.check}: {self.detail}"


@dataclass(frozen=True, slots=True)
class Report:
    """What `forge verify` found. A corpus passes only when nothing failed."""

    documents: tuple[str, ...]
    failures: tuple[Failure, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def truth_files(directory: Path) -> tuple[Path, ...]:
    """Every truth file in a corpus, in a stable order."""
    return tuple(sorted(directory.rglob(f"*{TRUTH_SUFFIX}")))


def verify_corpus(directory: Path, regenerate: bool = True) -> Report:
    """Check every document in a directory. Regeneration is the slow half; it can be off."""
    if not directory.is_dir():
        raise TruthError(f"corpus directory not found: {directory}")
    found = truth_files(directory)
    failures = tuple(
        failure for path in found for failure in verify_document(path, regenerate=regenerate)
    )
    return Report(documents=tuple(path.name for path in found), failures=failures)


def verify_document(truth_path: Path, regenerate: bool = True) -> tuple[Failure, ...]:
    """Every failure of one document, or an empty tuple when it holds up."""
    name = truth_path.name
    try:
        truth = read_truth(truth_path)
        pdf_path = _pdf_for(truth_path)
        return tuple(_failures(name, truth, pdf_path, regenerate))
    except TruthError as error:
        return (Failure(name, "schema", str(error)),)


def _failures(
    name: str, truth: dict[str, object], pdf_path: Path, regenerate: bool
) -> list[Failure]:
    if not pdf_path.is_file():
        return [Failure(name, "schema", f"no PDF beside it at {pdf_path.name}")]
    found = [
        *_named(name, "schema", check_schema(truth, pages_in(pdf_path))),
        *_named(name, "readback", check_readback(truth, pdf_path)),
        *_named(name, "arithmetic", check_arithmetic(truth)),
        *_named(name, "evidence", check_evidence_rule(truth)),
    ]
    if regenerate:
        found += _named(name, "determinism", check_determinism(truth, pdf_path))
    return found


def check_determinism(truth: dict[str, object], pdf_path: Path) -> list[str]:
    """Generate the document again from what it says made it, and compare every byte."""
    spec = document_spec(truth)
    with tempfile.TemporaryDirectory(prefix="forge-verify-") as scratch:
        again = produce(spec, Path(scratch) / pdf_path.name)
        complaints = []
        if again.pdf.read_bytes() != pdf_path.read_bytes():
            complaints.append("the PDF differs from a regeneration of its own seed")
        if _loaded(again.truth) != truth:
            complaints.append("the truth differs from a regeneration of its own seed")
        return complaints


def document_spec(truth: dict[str, object]) -> DocumentSpec:
    """The cell that made this document, read back out of what it recorded."""
    generator = block(truth, "generator")
    family = text(generator, "template", "generator")
    knobs = generator.get("knobs")
    names = [knob for knob in knobs if isinstance(knob, str)] if isinstance(knobs, list) else []
    try:
        return DocumentSpec(
            profile_id=text(generator, "profile", "generator"),
            family=Family(family),
            seed=whole(generator, "seed", "generator"),
            knobs=parse_knobs(names),
        )
    except ValueError as error:
        raise TruthError(f"generator names something unknown: {error}") from error


def _pdf_for(truth_path: Path) -> Path:
    stem = truth_path.name[: -len(TRUTH_SUFFIX)]
    return truth_path.with_name(f"{stem}.pdf")


def _loaded(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return dict(loaded) if isinstance(loaded, dict) else {}


def _named(document: str, check: str, complaints: list[str]) -> list[Failure]:
    return [Failure(document, check, detail) for detail in complaints]
