"""A corpus is its plan. The PDFs are not committed, because the plan regenerates them.

`forge-plan/1` names every cell exactly once — a profile, a family, a seed and the knobs
that are on — so a corpus is a list of documents rather than a recipe with a random
element. Two people running the same plan get the same bytes, and a plan is small enough
to read in a review.

`forge generate --profiles ... --families ... --count N --seed S` writes no file; it
builds the same plan in memory from the cross product, so both routes into `generate`
are the one route.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from invoice_forge.families import FAMILY_NAMES, Family
from invoice_forge.jsonspec import SpecError, read_object, reject_unknown, require_choices
from invoice_forge.knobs import KNOB_NAMES, Knob, parse_knobs
from invoice_forge.produce import DocumentSpec
from invoice_forge.profiles.loader import load_profile, profile_ids

PLAN_SCHEMA = "forge-plan/1"
TOP_LEVEL_KEYS = ("schema", "cells")
CELL_KEYS = ("profile", "family", "seed", "knobs")
NAME_DIGITS = 4


@dataclass(frozen=True, slots=True)
class Plan:
    """Every document a corpus holds, in the order they are generated."""

    cells: tuple[DocumentSpec, ...]

    def to_dict(self) -> dict[str, object]:
        return {"schema": PLAN_SCHEMA, "cells": [_cell_to_dict(cell) for cell in self.cells]}


def load_plan(path: str | Path) -> Plan:
    """Read a plan file, or raise `SpecError` naming the key that is wrong."""
    data = read_object(Path(path), "plan")
    reject_unknown(data, TOP_LEVEL_KEYS, "", "plan key")
    declared = data.get("schema")
    if declared != PLAN_SCHEMA:
        raise SpecError(f"schema must be {PLAN_SCHEMA!r}, not {declared!r}")
    cells = data.get("cells")
    if not isinstance(cells, list) or not cells:
        raise SpecError("cells must be a non-empty list of documents")
    return Plan(tuple(_cell(entry, index) for index, entry in enumerate(cells)))


def plan_from_arguments(
    profiles: Sequence[str], families: Sequence[Family], count: int, seed: int
) -> Plan:
    """The cross product of profiles and families, `count` documents deep from `seed`.

    The same offset gives the same seed in every profile, so a cell can be compared
    across vendors: document 3 of `de-DE` and document 3 of `en-GB` were drawn alike.
    """
    if count < 1:
        raise SpecError(f"count must be at least 1, not {count}")
    if not profiles or not families:
        raise SpecError("at least one profile and one family are needed")
    return Plan(
        tuple(
            DocumentSpec(profile_id=profile, family=family, seed=seed + offset)
            for profile in profiles
            for family in families
            for offset in range(count)
        )
    )


def every_pair() -> tuple[tuple[str, Family], ...]:
    """Every profile against every family it declares, in a stable order.

    The corpus's first coverage target, and the order both the plan and the golden images
    are built in, so the two never disagree about what a bundled profile can render.
    """
    return tuple(
        (profile_id, family)
        for profile_id in profile_ids()
        for family in load_profile(profile_id).families
    )


def cell_name(index: int, cell: DocumentSpec) -> str:
    """The file stem for one cell: ordered, and readable enough to find by eye."""
    return f"{index + 1:0{NAME_DIGITS}d}_{cell.profile_id}_{cell.family.value}_s{cell.seed}"


def _cell(entry: object, index: int) -> DocumentSpec:
    where = f"cells[{index}]"
    if not isinstance(entry, dict):
        raise SpecError(f"{where} must be an object")
    reject_unknown(entry, CELL_KEYS, f"{where}.", "cell key")
    return DocumentSpec(
        profile_id=_required_text(entry, "profile", where),
        family=_family(entry, where),
        seed=_seed(entry, where),
        knobs=_knobs(entry, where),
    )


def _required_text(entry: dict[str, object], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise SpecError(f"{where}.{key} must be a non-empty string")
    return value


def _family(entry: dict[str, object], where: str) -> Family:
    name = _required_text(entry, "family", where)
    if name not in FAMILY_NAMES:
        raise SpecError(f"{where}.family must be one of: {', '.join(FAMILY_NAMES)}")
    return Family(name)


def _seed(entry: dict[str, object], where: str) -> int:
    value = entry.get("seed")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SpecError(f"{where}.seed must be a whole number, zero or more")
    return value


def _knobs(entry: dict[str, object], where: str) -> tuple[Knob, ...]:
    """Absent and empty both mean "every knob off", which most cells of a corpus are."""
    if entry.get("knobs", []) == []:
        return ()
    names = require_choices(entry, "knobs", f"{where}.knobs", KNOB_NAMES)
    return parse_knobs(names)


def _cell_to_dict(cell: DocumentSpec) -> dict[str, object]:
    return {
        "profile": cell.profile_id,
        "family": cell.family.value,
        "seed": cell.seed,
        "knobs": [knob.value for knob in cell.knobs],
    }
