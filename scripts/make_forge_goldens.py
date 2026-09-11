"""Regenerate the committed fixtures under `tests/forge/fixtures/`.

Two kinds, both golden:

- One PNG per profile, the first page of the document that profile renders at the golden
  seed. `tests/forge/integration/test_goldens.py` compares the bytes exactly.
- A one-document corpus under `fixtures/corpus/`, so `forge verify tests/forge/fixtures/`
  has something to verify and the plan's own gate can be run by hand.

A change to the renderer that moves a single glyph fails the suite, and this script is how
the change is accepted — deliberately, in a commit that shows the new files.

Run: python scripts/make_forge_goldens.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from invoice_forge.corpus.plan import cell_name
from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.profiles.loader import bundled_profile_ids
from invoice_forge.render.pdf import page_image

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "forge" / "fixtures"
CORPUS = FIXTURES / "corpus"
GOLDEN_SEED = 7
GOLDEN_DPI = 72
GOLDEN_PAGE = 1
# The fixture corpus: one plain document, and one with every structural knob turned on, so
# `forge verify tests/forge/fixtures/` proves both a bare page and a difficult one.
STRUCTURAL_KNOBS = (
    Knob.MULTI_PAGE,
    Knob.CARRY_FORWARD,
    Knob.PAGE_NUMBERING,
    Knob.WRAPPED_DESCRIPTION,
    Knob.SUB_ITEMS,
    Knob.SECTION_SUBTOTALS,
    Knob.DISCOUNT,
    Knob.PARTY_BLOCKS,
    Knob.PLACEHOLDER_ADDRESSES,
    Knob.TRAP_LABELS,
    Knob.CUSTOMER_VAT_POSITION,
    Knob.REPEAT_LETTERHEAD,
)
FIXTURE_CELLS = (
    DocumentSpec(profile_id="fr-FR", family=Family.CLASSIC, seed=GOLDEN_SEED),
    DocumentSpec("de-DE", Family.CLASSIC, GOLDEN_SEED, STRUCTURAL_KNOBS),
)
FIXTURE_CELL = FIXTURE_CELLS[0]


def golden_path(profile_id: str) -> Path:
    return FIXTURES / f"{profile_id}_classic_p{GOLDEN_PAGE}.png"


def fixture_pdf() -> Path:
    return CORPUS / f"{cell_name(0, FIXTURE_CELL)}.pdf"


def golden_image(profile_id: str, directory: Path) -> bytes:
    """Render the profile at the golden seed and return its first page as PNG bytes."""
    spec = DocumentSpec(profile_id, Family.CLASSIC, GOLDEN_SEED)
    produced = produce(spec, directory / f"{profile_id}.pdf")
    return page_image(produced.pdf, GOLDEN_PAGE, GOLDEN_DPI)


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        for profile_id in bundled_profile_ids():
            image = golden_image(profile_id, Path(scratch))
            path = golden_path(profile_id)
            path.write_bytes(image)
            sys.stdout.write(f"{path.relative_to(REPO_ROOT)} ({len(image)} bytes)\n")
    for index, cell in enumerate(FIXTURE_CELLS):
        produced = produce(cell, CORPUS / f"{cell_name(index, cell)}.pdf")
        for path in (produced.pdf, produced.truth):
            sys.stdout.write(f"{path.relative_to(REPO_ROOT)} ({path.stat().st_size} bytes)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
