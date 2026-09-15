"""`invoice-extractor calibrate`: fit the confidence on a corpus whose answers are known.

The synthetic corpus is the only place a confidence can be checked, because it is the
only place the right answer is written down — and it carries negatives by construction,
since the difficulty knobs are there to make documents this reader gets wrong.

The run is offline, deterministic and reviewed: same corpus, same files, byte for byte.
Nothing here promotes what it fits; writing the files and committing them are two
different acts, and the second one is a pull request (ENGINE_SPEC §9).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from invoice_extractor.domain.models import FieldResult, InvoiceResult
from invoice_extractor.pipeline import extract
from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.scoring.compute import compute
from invoice_extractor.scoring.fit import (
    Band,
    Sample,
    bands,
    curve_for,
    expected_calibration_error,
    weights_for,
)
from invoice_extractor.scoring.weights import REPORT_FILE, SCHEMA, Calibration, write

TRUTH_SUFFIX = ".truth.json"
# The fields whose values are numbers, compared as numbers. The same rule the benchmark
# scores by (`docs/GROUND_TRUTH_SCHEMA.md`): money and rates are decimals, not strings.
NUMERIC = frozenset({"vat_rate", "subtotal", "vat_amount", "total_amount"})
PRECISION = 6


@dataclass(frozen=True, slots=True)
class FieldReliability:
    """One field over the corpus: how often it was right, and how well it said so."""

    name: str
    count: int
    hit_rate: float
    fitted: bool
    bands: tuple[Band, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "hit_rate": round(self.hit_rate, PRECISION),
            "fitted": self.fitted,
            "bands": [band.to_dict() for band in self.bands],
        }


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """What the fit saw and how far off the confidences it produces are."""

    documents: int
    fields: tuple[FieldReliability, ...]
    expected_calibration_error: float
    calibration: Calibration

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "corpus": {
                "documents": self.documents,
                "values_scored": sum(entry.count for entry in self.fields),
            },
            "expected_calibration_error": self.expected_calibration_error,
            "fields": {entry.name: entry.to_dict() for entry in sorted(self.fields, key=_by_name)},
        }


def calibrate(
    corpus: Path, out: Path, registry: ProfileRegistry | None = None
) -> CalibrationReport:
    """Read the corpus, fit what its answers say, write the three files, report."""
    documents = sorted(corpus.glob(f"*{TRUTH_SUFFIX}"))
    samples = _samples(documents, registry or ProfileRegistry())
    calibration = fitted(samples)
    report = _report(len(documents), samples, calibration)
    write(calibration, out)
    (out / REPORT_FILE).write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return report


def _samples(documents: Sequence[Path], registry: ProfileRegistry) -> Mapping[str, list[Sample]]:
    """Every field of every document: what its signals said, and whether it was right."""
    collected: dict[str, list[Sample]] = {}
    for truth_path in documents:
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        pdf = truth_path.with_name(truth_path.name.removesuffix(TRUTH_SUFFIX) + ".pdf")
        result = extract(pdf, registry)
        for name, sample in _of_document(result, truth).items():
            collected.setdefault(name, []).append(sample)
    return collected


def _of_document(result: InvoiceResult, truth: Mapping[str, object]) -> Mapping[str, Sample]:
    """One document's fields: every value that was read, and whether it was the right one.

    A value read off a page that carries none is wrong, the same way the benchmark counts
    it wrong — those are most of the negatives a fit has to learn from, and skipping them
    would be fitting on a corpus this reader never gets anything wrong on.
    """
    wanted = truth.get("fields")
    entries = wanted if isinstance(wanted, dict) else {}
    found: dict[str, Sample] = {}
    for name, result_field in result.fields.items():
        if result_field.value is None:
            continue
        expected = _expected(entries.get(name))
        right = expected is not None and _agrees(name, expected, result_field)
        found[name] = Sample(result_field.confidence_breakdown, right)
    return found


def fitted(samples: Mapping[str, Sequence[Sample]]) -> Calibration:
    """Weights where a field was ever wrong, and a curve where there is enough to fit one."""
    weights = {name: found for name in samples if (found := weights_for(samples[name]))}
    curves = {}
    for name, observed in samples.items():
        scored = _scored(observed, weights.get(name))
        curve = curve_for(scored)
        if curve is not None:
            curves[name] = curve
    return Calibration(weights=weights, curves=curves)


def _report(
    documents: int, samples: Mapping[str, Sequence[Sample]], calibration: Calibration
) -> CalibrationReport:
    fields: list[FieldReliability] = []
    everything: list[tuple[float, bool]] = []
    for name, observed in sorted(samples.items()):
        scored = _scored(observed, calibration.weights_for(name), calibration.curve_for(name))
        everything.extend(scored)
        fields.append(
            FieldReliability(
                name=name,
                count=len(scored),
                hit_rate=sum(1 for _, correct in scored if correct) / len(scored),
                fitted=calibration.weights_for(name) is not None,
                bands=bands(scored),
            )
        )
    return CalibrationReport(
        documents=documents,
        fields=tuple(fields),
        expected_calibration_error=expected_calibration_error(bands(everything)),
        calibration=calibration,
    )


def _scored(
    samples: Sequence[Sample],
    weights: Mapping[str, float] | None,
    curve: Sequence[tuple[float, float]] | None = None,
) -> list[tuple[float, bool]]:
    return [
        (compute(sample.signals, weights, curve=curve).confidence, sample.correct)
        for sample in samples
    ]


def _expected(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None
    value = entry.get("value")
    return None if value is None else str(value)


def _agrees(name: str, expected: str, found: FieldResult) -> bool:
    if name in NUMERIC:
        return _decimal(expected) == _decimal(str(found.value))
    return expected == str(found.value)


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _by_name(entry: FieldReliability) -> str:
    return entry.name
