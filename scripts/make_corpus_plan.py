"""Write `corpus/plan.json`: the ~250 document base corpus `make corpus` runs.

The plan is committed and the documents are not, so this script is how the plan changes
— add a profile, add a knob, run it again, review the diff. It writes cells in three
passes over `every_pair()`, which is what makes the file readable as well as correct:

1. Every profile against every family it declares, with no knob on at all. The plain
   document a vendor prints, and the corpus's first coverage target.
2. Every pair again, each carrying one themed bundle of knobs. Six bundles, rotating, so
   every knob in `docs/VARIATION_CATALOG.md` lands on thirteen or fourteen documents.
3. The documents the targets ask for and the first two passes do not supply: credit
   notes, spelled totals, and the long documents that run to three pages.

Every cell states how many pages and how many rows it is *for*, and its seed is searched
rather than chosen: the sampler is asked for a document until one comes back the right
shape. That is why a target like "at least twenty documents of a single line" is met by
construction here rather than hoped for and checked afterwards by `forge catalog`.

Run: python scripts/make_corpus_plan.py
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path

from invoice_forge.corpus.generate import write_plan
from invoice_forge.corpus.plan import Plan, every_pair
from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.profiles.loader import load_profile
from invoice_forge.sample.catalogue import load_catalogue
from invoice_forge.sample.sampler import SampleRequest, sample_document

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = REPO_ROOT / "corpus" / "plan.json"

# One bundle per section of the variation catalog, which is also how they were written:
# a document that numbers its pages is a document that carries its subtotal across them,
# and a document that names a charge is a document that rounds the total it lands on.
STRUCTURE = (
    Knob.MULTI_PAGE,
    Knob.CARRY_FORWARD,
    Knob.PAGE_NUMBERING,
    Knob.REPEAT_LETTERHEAD,
    Knob.STAMP_COPY,
)
PARTIES = (
    Knob.PARTY_BLOCKS,
    Knob.PLACEHOLDER_ADDRESSES,
    Knob.CUSTOMER_VAT_POSITION,
    Knob.TRAP_LABELS,
    Knob.EXTRA_REFERENCES,
    Knob.SUPPLY_DATE,
)
TABLE = (
    Knob.WRAPPED_DESCRIPTION,
    Knob.SUB_ITEMS,
    Knob.SECTION_SUBTOTALS,
    Knob.DISCOUNT,
    Knob.COLUMN_SET,
)
TAX = (
    Knob.MULTI_RATE,
    Knob.VAT_SUMMARY_TABLE,
    Knob.EXEMPTION_VERBIAGE,
    Knob.ROUNDING_PER_LINE,
)
CHARGES = (
    Knob.CHARGES,
    Knob.DECLARED_CHARGE,
    Knob.UNDECLARED_CHARGE,
    Knob.ROUNDING_TOTAL,
    Knob.THOUSANDS_VARIANT,
    Knob.DUAL_CURRENCY_ECHO,
)
FOOTER = (Knob.BANK_FOOTER, Knob.NOISE_FOOTER, Knob.PAYMENT_TERMS_BLOCK)
BUNDLES: tuple[tuple[Knob, ...], ...] = (STRUCTURE, PARTIES, TABLE, TAX, CHARGES, FOOTER)

# Two knobs are not rotated with the rest: a credit note is a document type rather than a
# variation of one, and a total is only spelled in a language whose lexicon spells numbers.
# `LONG` is not a bundle either — it is the shortest way to ask for a document of three
# pages, since thirty rows alone fill two and it takes wrapped rows with parts to fill a third.
LONG = (Knob.MULTI_PAGE, Knob.SUB_ITEMS, Knob.WRAPPED_DESCRIPTION)

# How many of each the third pass adds, on top of what the first two already cover.
CREDIT_NOTES = 40
SPELLED = 14
LONG_DOCUMENTS = 34
SINGLE_LINE = 22
# And how many of the second pass are printed on one page rather than two.
SHORT_BUNDLES = 24

# Page counts, low and high inclusive. `saas` sets nine columns in a smaller face and runs
# to six pages where `classic` runs to three, so "long" is a range rather than a number.
ONE_PAGE = (1, 1)
TWO_PAGES = (2, 2)
LONG_PAGES = (3, 8)
TWO_OR_MORE = (2, 8)
# A search that runs this far without a document of the wanted shape is a wanted shape
# that no seed produces, which is a plan to change rather than a search to widen.
MOST_SEEDS = 400
FIRST_SEED = 1000

Measure = Callable[["Wanted", int], int]


@dataclass(frozen=True, slots=True)
class Wanted:
    """One cell of the corpus, before a seed that produces it has been found."""

    profile_id: str
    family: Family
    knobs: tuple[Knob, ...]
    pages: tuple[int, int]
    items: tuple[int, int] | None = None


@dataclass
class Search:
    """Seeds already spent, so no two cells of the corpus are the same document."""

    scratch: Path
    taken: set[tuple[str, str, int]] = field(default_factory=set)

    def seed_for(self, wanted: Wanted) -> int:
        """The first seed at or after `FIRST_SEED` that renders the document wanted."""
        for seed in count(FIRST_SEED):
            if seed - FIRST_SEED > MOST_SEEDS:
                raise SystemExit(f"no seed in {MOST_SEEDS} renders {wanted}")
            if (wanted.profile_id, wanted.family.value, seed) in self.taken:
                continue
            if not _within(wanted.items, _rows, wanted, seed):
                continue
            if not _within(wanted.pages, self._drawn, wanted, seed):
                continue
            self.taken.add((wanted.profile_id, wanted.family.value, seed))
            return seed
        raise AssertionError("count() does not end")

    def _drawn(self, wanted: Wanted, seed: int) -> int:
        spec = DocumentSpec(wanted.profile_id, wanted.family, seed, wanted.knobs)
        return produce(spec, self.scratch / "probe.pdf").pages


def _within(band: tuple[int, int] | None, measure: Measure, wanted: Wanted, seed: int) -> bool:
    """Rows are checked before pages, because sampling is free and drawing a page is not."""
    if band is None:
        return True
    low, high = band
    return low <= measure(wanted, seed) <= high


def wanted_cells() -> tuple[Wanted, ...]:
    """The whole corpus as intents, in the order the three passes write them."""
    return (*_plain(), *_bundled(), *_targets())


def _plain() -> tuple[Wanted, ...]:
    """Every pair once, no knob on. The first `SINGLE_LINE` of them bill one line only."""
    return tuple(
        Wanted(profile_id, family, (), ONE_PAGE, (1, 1))
        if index < SINGLE_LINE
        else Wanted(profile_id, family, (), TWO_PAGES)
        for index, (profile_id, family) in enumerate(every_pair())
    )


def _bundled() -> tuple[Wanted, ...]:
    """Every pair again, rotating through the six bundles a document at a time."""
    return tuple(
        Wanted(
            profile_id=profile_id,
            family=family,
            knobs=BUNDLES[index % len(BUNDLES)],
            pages=_bundle_pages(index),
        )
        for index, (profile_id, family) in enumerate(every_pair())
    )


def _bundle_pages(index: int) -> tuple[int, int]:
    """A bundle that asks for more rows than a page holds cannot be a one-page document."""
    if BUNDLES[index % len(BUNDLES)] is STRUCTURE:
        return TWO_OR_MORE
    return ONE_PAGE if index < SHORT_BUNDLES else TWO_PAGES


def _targets() -> tuple[Wanted, ...]:
    """What the catalog asks for that the first two passes leave short."""
    pairs = every_pair()
    spelling = tuple(pair for pair in pairs if _spells(pair[0]))
    return (
        *_over(pairs, CREDIT_NOTES, (Knob.CREDIT_NOTE,), TWO_PAGES),
        *_over(spelling, SPELLED, (Knob.AMOUNT_IN_WORDS,), TWO_PAGES),
        *_over(pairs, LONG_DOCUMENTS, LONG, LONG_PAGES),
    )


def _over(
    pairs: Sequence[tuple[str, Family]],
    wanted: int,
    knobs: tuple[Knob, ...],
    pages: tuple[int, int],
) -> Iterator[Wanted]:
    """`wanted` documents of one kind, spread over the pairs rather than piled on one."""
    stride = max(1, len(pairs) // wanted)
    for index in range(wanted):
        profile_id, family = pairs[(index * stride) % len(pairs)]
        yield Wanted(profile_id, family, knobs, pages)


def _spells(profile_id: str) -> bool:
    """Half of Europe declines its numerals, and those lexicons spell no total at all."""
    return load_lexicon(load_profile(profile_id).lexicon).amount_in_words is not None


def _rows(wanted: Wanted, seed: int) -> int:
    """How many line items the cell would bill, sampled without drawing a page."""
    profile = load_profile(wanted.profile_id)
    lexicon = load_lexicon(profile.lexicon)
    catalogue = load_catalogue(profile.lexicon)
    request = SampleRequest(profile, lexicon, catalogue, wanted.family, seed, wanted.knobs)
    return len(sample_document(request).items)


def main() -> int:
    cells = wanted_cells()
    with tempfile.TemporaryDirectory() as scratch:
        search = Search(Path(scratch))
        found = []
        for index, wanted in enumerate(cells):
            seed = search.seed_for(wanted)
            found.append(DocumentSpec(wanted.profile_id, wanted.family, seed, wanted.knobs))
            sys.stdout.write(f"\r{index + 1}/{len(cells)} cells")
            sys.stdout.flush()
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_plan(Plan(tuple(found)), PLAN_PATH)
    sys.stdout.write(f"\n{PLAN_PATH.relative_to(REPO_ROOT)} ({len(found)} cells)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
