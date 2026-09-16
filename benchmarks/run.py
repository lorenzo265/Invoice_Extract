"""`make bench`: the extractor over every document in `corpus/`, scored against its truth.

Writes three files, all of them generated:

- `benchmarks/latest.json` — the matrix, the calibration table and what is not covered.
- `benchmarks/README.md` — the same numbers as markdown.
- the block between the two markers in the repository `README.md`.

Nothing is typed by hand, so a published figure cannot outlive the run that produced it.
`tests/test_benchmark.py` fails when a marker block and `latest.json` disagree.

Run: python -m benchmarks.run [corpus directory]
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

import invoice_extractor
import invoice_forge
from benchmarks import matrix as matrices
from benchmarks import report as reports
from benchmarks.compare import NOT_COVERED, DocumentScore, compare
from invoice_extractor import ProfileRegistry, extract
from invoice_forge.produce import TRUTH_SUFFIX

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS = REPO_ROOT / "benchmarks"
LATEST = BENCHMARKS / "latest.json"
REPORT = BENCHMARKS / "README.md"
README = REPO_ROOT / "README.md"
DEFAULT_CORPUS = REPO_ROOT / "corpus"
SCHEMA = "forge-bench/1"
JSON_INDENT = 2


def score_corpus(directory: Path) -> Iterator[DocumentScore]:
    """Every document in a corpus, read the way a deployment would read it, and compared.

    No profile is handed over: the extractor is given the registry and detects the vendor
    itself (ADR-0008), so what is measured includes finding the right vocabulary.
    """
    registry = ProfileRegistry()
    for truth_path in sorted(directory.glob(f"*{TRUTH_SUFFIX}")):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        pdf = truth_path.with_name(truth_path.name.removesuffix(TRUTH_SUFFIX) + ".pdf")
        yield compare(pdf.stem, truth, extract(pdf, registry))


def build_report(directory: Path) -> dict[str, object]:
    """The whole benchmark as the JSON both markdown outputs are rendered from."""
    return _report(directory, matrices.build(score_corpus(directory)))


def _report(directory: Path, built: matrices.Matrix) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "run": {
            "corpus": directory.name,
            "extractor_version": invoice_extractor.__version__,
            "generator_version": invoice_forge.__version__,
        },
        "matrix": built.to_dict(),
        "not_covered": list(NOT_COVERED),
    }


def write_readme_block(report: dict[str, object], path: Path) -> None:
    """Replace what stands between the two markers. The markers themselves are hand-written."""
    text = path.read_text(encoding="utf-8")
    before, begin, rest = text.partition(reports.BEGIN)
    _, end, after = rest.partition(reports.END)
    if not begin or not end:
        raise SystemExit(f"{path.name} has no {reports.BEGIN} / {reports.END} block")
    path.write_text(before + reports.render_readme_block(report) + after, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    directory = Path(arguments[0]) if arguments else DEFAULT_CORPUS
    if not sorted(directory.glob(f"*{TRUTH_SUFFIX}")):
        sys.stderr.write(f"no documents in {directory}/; run `make corpus` first\n")
        return 1
    built = matrices.build(score_corpus(directory))
    report = _report(directory, built)
    LATEST.write_text(json.dumps(report, indent=JSON_INDENT) + "\n", encoding="utf-8")
    REPORT.write_text(reports.render_report(report), encoding="utf-8")
    write_readme_block(report, README)
    written = ", ".join(str(path.relative_to(REPO_ROOT)) for path in (LATEST, REPORT, README))
    sys.stdout.write(f"{built.documents} documents scored into {written}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
