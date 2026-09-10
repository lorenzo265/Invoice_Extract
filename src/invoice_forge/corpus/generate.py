"""Running a plan into a directory: one PDF and one truth per cell, plus the plan itself.

The plan is written beside the documents whether it came from a file or from command-line
arguments, so a corpus always carries the thing that reproduces it. `forge verify` needs
none of it — every document already records the cell that made it — but a person picking
up a corpus should not have to reconstruct how it was asked for.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from invoice_forge.corpus.plan import Plan, cell_name
from invoice_forge.produce import Produced, produce

PLAN_NAME = "plan.json"
JSON_INDENT = 2
Progress = Callable[[int, int, Path], None]


@dataclass(frozen=True, slots=True)
class Generated:
    """What a run of a plan produced."""

    directory: Path
    documents: tuple[Produced, ...]

    @property
    def pages(self) -> int:
        return sum(document.pages for document in self.documents)


def generate(plan: Plan, directory: Path, progress: Progress | None = None) -> Generated:
    """Produce every cell of the plan into `directory`, and leave the plan there too."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Produced] = []
    for index, cell in enumerate(plan.cells):
        path = directory / f"{cell_name(index, cell)}.pdf"
        written.append(produce(cell, path))
        if progress is not None:
            progress(index + 1, len(plan.cells), path)
    write_plan(plan, directory / PLAN_NAME)
    return Generated(directory=directory, documents=tuple(written))


def write_plan(plan: Plan, path: Path) -> None:
    """The plan as JSON, formatted the way a committed `corpus/plan.json` is."""
    text = json.dumps(plan.to_dict(), ensure_ascii=False, indent=JSON_INDENT)
    path.write_text(f"{text}\n", encoding="utf-8")
