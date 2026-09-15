"""What a fit on a corpus of known answers learned, read back at run time.

Two files, both written by `invoice-extractor calibrate` and both reviewed like code
before they are committed (ENGINE_SPEC §9): what each signal is worth per field, and what
a score of a given size has actually been worth. A run with neither file scores every
field with the uniform mean and says so — there is no half-fitted state.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

CALIBRATION_ROOT = Path("calibration")
WEIGHTS_FILE = "weights.json"
MAPS_FILE = "calibration_maps.json"
REPORT_FILE = "reliability_report.json"
SCHEMA = "invoice-extractor-calibration/1"
# A point of a calibration map: a score, and what a score that size proved to be worth.
Curve = tuple[tuple[float, float], ...]
_A_POINT = 2


@dataclass(frozen=True, slots=True)
class Calibration:
    """Per field: what its signals are worth, and what its scores have been worth."""

    weights: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    curves: Mapping[str, Curve] = field(default_factory=dict)

    def weights_for(self, name: str) -> Mapping[str, float] | None:
        return self.weights.get(name)

    def curve_for(self, name: str) -> Curve | None:
        return self.curves.get(name)


@cache
def load(root: Path = CALIBRATION_ROOT) -> Calibration:
    """The committed fit, or an empty one where none is committed. Never raises."""
    return Calibration(
        weights={name: _weights(entry) for name, entry in _fields(root / WEIGHTS_FILE).items()},
        curves={name: _curve(entry) for name, entry in _fields(root / MAPS_FILE).items()},
    )


def write(calibration: Calibration, root: Path) -> None:
    """The two fitted files, byte for byte the same for the same fit."""
    root.mkdir(parents=True, exist_ok=True)
    weighted = {
        name: dict(sorted(entry.items())) for name, entry in sorted(calibration.weights.items())
    }
    curved = {
        name: [list(point) for point in curve] for name, curve in sorted(calibration.curves.items())
    }
    _write(root / WEIGHTS_FILE, weighted)
    _write(root / MAPS_FILE, curved)


def _write(path: Path, fields: Mapping[str, object]) -> None:
    body = {"schema": SCHEMA, "fields": fields}
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def _fields(path: Path) -> Mapping[str, object]:
    """The `fields` object of one fitted file; an absent file is an absent fit."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    found = data.get("fields") if isinstance(data, dict) else None
    return {str(name): entry for name, entry in found.items()} if isinstance(found, dict) else {}


def _weights(entry: object) -> Mapping[str, float]:
    found = entry if isinstance(entry, dict) else {}
    return {str(name): float(value) for name, value in found.items()}


def _curve(entry: object) -> Curve:
    points = entry if isinstance(entry, list) else []
    return tuple(
        (float(point[0]), float(point[1]))
        for point in points
        if isinstance(point, Sequence) and len(point) == _A_POINT
    )
