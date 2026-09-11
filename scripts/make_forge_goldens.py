"""Regenerate the committed fixtures under `tests/forge/fixtures/`.

Two kinds, both golden:

- One PNG per profile and family the profile declares, the first page of the document
  that pair renders at the golden seed. `tests/forge/integration/test_goldens.py`
  compares the bytes exactly, which is `docs/FORGE_SPEC.md` §5.3.
- A small corpus under `fixtures/corpus/`, so `forge verify tests/forge/fixtures/` has
  something to verify and `forge catalog` has something to report on. Its cells are
  chosen so that every knob in `docs/VARIATION_CATALOG.md` is on in one document and off
  in another, and every family is rendered at least once.

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
from invoice_forge.profiles.loader import bundled_profile_ids, load_profile
from invoice_forge.render.pdf import page_image

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "forge" / "fixtures"
CORPUS = FIXTURES / "corpus"
GOLDEN_SEED = 7
GOLDEN_DPI = 72
GOLDEN_PAGE = 1

# The twelve structural axes, the ten money and tax ones, and everything else the catalog
# names. Together they are every knob exactly once, which a test asserts.
STRUCTURAL = (
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
MONEY = (
    Knob.MULTI_RATE,
    Knob.VAT_SUMMARY_TABLE,
    Knob.CHARGES,
    Knob.DECLARED_CHARGE,
    Knob.UNDECLARED_CHARGE,
    Knob.ROUNDING_TOTAL,
    Knob.DUAL_CURRENCY_ECHO,
    Knob.EXEMPTION_VERBIAGE,
    Knob.AMOUNT_IN_WORDS,
    Knob.THOUSANDS_VARIANT,
)
REST = (
    Knob.CREDIT_NOTE,
    Knob.STAMP_COPY,
    Knob.SUPPLY_DATE,
    Knob.EXTRA_REFERENCES,
    Knob.COLUMN_SET,
    Knob.ROUNDING_PER_LINE,
    Knob.BANK_FOOTER,
    Knob.NOISE_FOOTER,
    Knob.PAYMENT_TERMS_BLOCK,
)

FIXTURE_CELLS: tuple[DocumentSpec, ...] = (
    DocumentSpec(profile_id="fr-FR", family=Family.CLASSIC, seed=GOLDEN_SEED),
    DocumentSpec("de-DE", Family.CLASSIC, GOLDEN_SEED, STRUCTURAL),
    DocumentSpec("de-DE", Family.TABULAR, GOLDEN_SEED, MONEY),
    DocumentSpec("en-GB", Family.STACKED, GOLDEN_SEED, REST),
    DocumentSpec("en-GB", Family.SAAS, GOLDEN_SEED),
    DocumentSpec("sv-SE", Family.MINIMAL, GOLDEN_SEED),
)
FIXTURE_CELL = FIXTURE_CELLS[0]


def golden_pairs() -> tuple[tuple[str, Family], ...]:
    """Every profile against every family it declares, in a stable order."""
    return tuple(
        (profile_id, family)
        for profile_id in bundled_profile_ids()
        for family in load_profile(profile_id).families
    )


def golden_path(profile_id: str, family: Family) -> Path:
    return FIXTURES / f"{profile_id}_{family.value}_p{GOLDEN_PAGE}.png"


def fixture_pdf() -> Path:
    return CORPUS / f"{cell_name(0, FIXTURE_CELL)}.pdf"


def golden_image(profile_id: str, family: Family, directory: Path) -> bytes:
    """Render the pair at the golden seed and return its first page as PNG bytes."""
    spec = DocumentSpec(profile_id, family, GOLDEN_SEED)
    produced = produce(spec, directory / f"{profile_id}_{family.value}.pdf")
    return page_image(produced.pdf, GOLDEN_PAGE, GOLDEN_DPI)


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        for profile_id, family in golden_pairs():
            image = golden_image(profile_id, family, Path(scratch))
            path = golden_path(profile_id, family)
            path.write_bytes(image)
            sys.stdout.write(f"{path.relative_to(REPO_ROOT)} ({len(image)} bytes)\n")
    for index, cell in enumerate(FIXTURE_CELLS):
        produced = produce(cell, CORPUS / f"{cell_name(index, cell)}.pdf")
        for path in (produced.pdf, produced.truth):
            sys.stdout.write(f"{path.relative_to(REPO_ROOT)} ({path.stat().st_size} bytes)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
