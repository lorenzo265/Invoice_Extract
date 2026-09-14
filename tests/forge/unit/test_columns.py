"""No heading ever runs into the column beside it, in any language, in either face.

A column set is hand-placed numbers, and the longest word a lexicon heads a column with
is not a number anyone can hold in their head — `Artikelbezeichnung`, `Kvarvarande`,
`Faktureringsintervall`. So the anchors are measured rather than trusted: every heading
every lexicon offers, wrapped the way the renderer wraps it, drawn in the face the profile
would draw it, and checked against its neighbours.

This is the test that says a rendered table is a table a vendor would have printed, rather
than one whose German heading sits on top of its Swedish neighbour.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

import pytest

from invoice_forge.layout import columns
from invoice_forge.layout.classic import A4, family_spec
from invoice_forge.layout.columns import ColumnSet
from invoice_forge.layout.spec import Alignment, ItemsSpec, Weight
from invoice_forge.lexicon.loader import bundled_lexicon_ids, load_lexicon
from invoice_forge.profiles.schema import FontFamily
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.table import COLUMN_GUTTER, heading_lines
from invoice_forge.render.text import NumberFormat, quantity
from invoice_forge.sample.sampler import FRACTIONAL_QUANTITIES, QUANTITIES

# The two faces and every language the corpus speaks: each set has to survive all of them.
FACES = tuple(FontFamily)
LANGUAGES = bundled_lexicon_ids()
# The header sizes the families set their tables in: the standard sets, and `saas`.
STANDARD_SIZE = 8.0
SAAS_SIZE = 6.5
# The face size a row is set in, which is what a quantity beside a description is measured at.
ROW_SIZE = 9.0
# No heading the corpus offers wraps to more than this many lines.
MOST_LINES = 4
# What the header costs when every heading fits on one line.
SHORTEST_HEADER = 28.0
SETS: tuple[tuple[str, ColumnSet, float], ...] = (
    ("classic", columns.CLASSIC, STANDARD_SIZE),
    ("classic_discount", columns.CLASSIC_DISCOUNT, STANDARD_SIZE),
    ("compact", columns.COMPACT, STANDARD_SIZE),
    ("compact_discount", columns.COMPACT_DISCOUNT, STANDARD_SIZE),
    ("saas", columns.SAAS, SAAS_SIZE),
)
for_each_set = pytest.mark.parametrize(
    ("name", "declared", "size"), SETS, ids=[name for name, _, _ in SETS]
)


@dataclass(frozen=True, slots=True)
class Headings:
    """The one thing `heading_lines` reads out of a wording: a heading per column."""

    columns: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Span:
    """Where one drawn heading line starts and ends, and what it says."""

    left: float
    right: float
    column: str
    text: str


def spec_for(declared: ColumnSet, size: float) -> ItemsSpec:
    """An items spec that differs from `classic`'s only in the set it prints."""
    return ItemsSpec(
        columns=declared.columns,
        ruled=True,
        description_width=declared.description_width,
        header_size=size,
        row_size=ROW_SIZE,
        row_leading=11.0,
        row_gap=6.0,
    )


def spans(sheet: Sheet, declared: ColumnSet, size: float, language: str) -> list[list[Span]]:
    """Every heading line of every column, as it would be drawn, one list per line."""
    spec = spec_for(declared, size)
    offered = load_lexicon(language).column_headers
    most = max(len(offered[column.name]) for column in declared.columns)
    by_line: list[list[Span]] = [[] for _ in range(MOST_LINES)]
    for choice in range(most):
        wording = _headings(declared, language, choice)
        for column, lines in heading_lines(sheet, spec, wording):
            for index, text in enumerate(lines):
                width = sheet.width(text, size, Weight.BOLD)
                left = column.anchor if column.align is Alignment.LEFT else column.anchor - width
                by_line[index].append(Span(left, left + width, column.name, text))
    return by_line


@for_each_set
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("fonts", FACES, ids=[face.value for face in FACES])
def test_no_heading_runs_into_the_column_beside_it(
    name: str, declared: ColumnSet, size: float, language: str, fonts: FontFamily
) -> None:
    sheet = _sheet(fonts)
    for line in spans(sheet, declared, size, language):
        placed = sorted(line, key=lambda span: span.left)
        for before, after in pairwise(placed):
            if before.column == after.column:
                continue
            assert before.right <= after.left, (
                f"{name}/{language}/{fonts.value}: {before.column} {before.text!r} "
                f"ends at {before.right:.1f}, {after.column} {after.text!r} starts "
                f"at {after.left:.1f}"
            )


@for_each_set
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("fonts", FACES, ids=[face.value for face in FACES])
def test_no_heading_runs_off_the_page(
    name: str, declared: ColumnSet, size: float, language: str, fonts: FontFamily
) -> None:
    sheet = _sheet(fonts)
    for line in spans(sheet, declared, size, language):
        for span in line:
            assert span.left >= A4.left, f"{name}/{language}: {span.text!r} starts off the page"
            assert span.right <= A4.right, f"{name}/{language}: {span.text!r} runs off the page"


@for_each_set
def test_a_column_set_is_anchored_left_to_right_inside_the_text_column(
    name: str, declared: ColumnSet, size: float
) -> None:
    anchors = [column.anchor for column in declared.columns]
    assert anchors == sorted(anchors), name
    assert min(anchors) >= A4.left
    assert max(anchors) <= A4.right


@for_each_set
def test_a_set_starts_on_a_left_edge_and_ends_on_a_right_one(
    name: str, declared: ColumnSet, size: float
) -> None:
    """Which is what lets a heading's room be the distance to the anchor beside it."""
    assert declared.columns[0].align is Alignment.LEFT, name
    assert declared.columns[-1].align is Alignment.RIGHT, name


@for_each_set
def test_a_description_never_claims_more_width_than_its_column_has(
    name: str, declared: ColumnSet, size: float
) -> None:
    anchors = [column.anchor for column in declared.columns]
    description = next(column for column in declared.columns if column.name == "description")
    after = min(anchor for anchor in anchors if anchor > description.anchor)
    assert declared.description_width <= after - description.anchor, name


@for_each_set
@pytest.mark.parametrize("fonts", FACES, ids=[face.value for face in FACES])
def test_a_description_stops_short_of_the_value_printed_beside_it(
    name: str, declared: ColumnSet, size: float, fonts: FontFamily
) -> None:
    """A right-aligned neighbour reaches back from its anchor, so the anchor is not the edge.

    The widest quantity the sampler can draw, set in the face the profile would set it in,
    is what the description has to stop one gutter short of — not the anchor it hangs from.
    """
    sheet = _sheet(fonts)
    description = next(column for column in declared.columns if column.name == "description")
    after = min(
        (column for column in declared.columns if column.anchor > description.anchor),
        key=lambda column: column.anchor,
    )
    reach = _widest_quantity(sheet) if after.name == "quantity" else 0.0
    room = after.anchor - reach - COLUMN_GUTTER - description.anchor
    assert declared.description_width <= room, f"{name}/{fonts.value}: room is {room:.1f}"


def _widest_quantity(sheet: Sheet) -> float:
    """Every quantity the sampler draws from, printed both ways round the decimal mark."""
    drawn = (*QUANTITIES, *FRACTIONAL_QUANTITIES)
    formats = (NumberFormat(".", ","), NumberFormat(",", "."))
    return max(
        sheet.width(quantity(Decimal(str(value)), number_format), ROW_SIZE, Weight.REGULAR)
        for value in drawn
        for number_format in formats
    )


def test_every_family_prints_one_of_the_sets_that_was_measured() -> None:
    """A set no test measures is a set whose headings nothing checks."""
    from invoice_forge.families import Family

    measured = {declared.columns for _, declared, _ in SETS}
    for family in Family:
        assert family_spec(family).items.columns in measured, family


def test_the_header_is_taller_where_a_heading_takes_two_lines() -> None:
    """Nine columns cannot hold a long heading on one line, and the budget has to know."""
    from invoice_forge.render.table import header_height

    sheet = _sheet(FontFamily.SANS)
    wide = spec_for(columns.CLASSIC, STANDARD_SIZE)
    narrow = spec_for(columns.SAAS, SAAS_SIZE)
    assert header_height(sheet, wide, _headings(columns.CLASSIC, "sv", 0)) == SHORTEST_HEADER
    assert header_height(sheet, narrow, _headings(columns.SAAS, "sv", 0)) > SHORTEST_HEADER


def _sheet(fonts: FontFamily) -> Sheet:
    sheet = Sheet(A4, fonts)
    sheet.new_page()
    return sheet


def _headings(declared: ColumnSet, language: str, choice: int) -> Headings:
    """The nth synonym of every column this set prints, or the last one it offers."""
    offered = load_lexicon(language).column_headers
    return Headings(
        {
            column.name: offered[column.name][min(choice, len(offered[column.name]) - 1)]
            for column in declared.columns
        }
    )
