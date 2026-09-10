"""Counting what a corpus actually contains, from the truth files rather than the plan.

A plan says what was asked for. The truths say what came out — how many pages each
document took, how many rows it has, whether it is a credit note. Coverage is reported
against the documents, so a plan that asked for a three-page document and got a one-page
one is a gap the catalog shows.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from invoice_forge.truth.reading import TruthError, block, read_truth, rows, text, whole
from invoice_forge.truth.verify import truth_files

CREDIT_NOTE = "credit_note"


@dataclass(frozen=True, slots=True)
class Survey:
    """What a corpus holds, counted once so every coverage row reads the same numbers."""

    documents: int
    # Counters, so a pair or a knob no document used answers 0 rather than raising.
    pairs: Counter[tuple[str, str]]
    knobs: Counter[str]
    item_counts: tuple[int, ...]
    page_counts: tuple[int, ...]
    credit_notes: int


def survey_corpus(directory: Path) -> Survey:
    """Read every truth in a corpus and tally the axes the catalog reports on."""
    if not directory.is_dir():
        raise TruthError(f"corpus directory not found: {directory}")
    pairs: Counter[tuple[str, str]] = Counter()
    knobs: Counter[str] = Counter()
    items: list[int] = []
    pages: list[int] = []
    credit_notes = 0
    found = truth_files(directory)
    for path in found:
        truth = read_truth(path)
        generator, document = block(truth, "generator"), block(truth, "document")
        profile = text(generator, "profile", "generator")
        family = text(generator, "template", "generator")
        pairs[profile, family] += 1
        knobs.update(_knob_names(generator))
        items.append(len(rows(truth, "line_items")))
        pages.append(whole(document, "pages", "document"))
        if text(document, "type", "document") == CREDIT_NOTE:
            credit_notes += 1
    return Survey(
        documents=len(found),
        pairs=pairs,
        knobs=knobs,
        item_counts=tuple(items),
        page_counts=tuple(pages),
        credit_notes=credit_notes,
    )


def _knob_names(generator: Mapping[str, object]) -> list[str]:
    declared = generator.get("knobs")
    if not isinstance(declared, list):
        raise TruthError("generator.knobs must be a list of strings")
    return [name for name in declared if isinstance(name, str)]
