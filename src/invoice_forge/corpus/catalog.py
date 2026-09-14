"""`forge catalog`: what a corpus covers, against the rows `docs/VARIATION_CATALOG.md` names.

The catalog is the coverage contract, and this reports the corpus against it rather than
against what the corpus happens to contain. Every knob gets a row whether or not any
document turns it on, and every coverage target gets a row with the number it asks for —
so a gap shows up as an unmet row, not as an absence nobody notices.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from invoice_forge.corpus.survey import Survey, survey_corpus
from invoice_forge.knobs import KNOB_NAMES
from invoice_forge.profiles.loader import load_profile, profile_ids

KNOB_ON = 10
KNOB_OFF = 10
SINGLE_ITEM = 20
TEN_ITEMS = 20
THIRTY_ITEMS = 5
ONE_PAGE_SHARE = 0.15
TWO_PAGE_SHARE = 0.60
LONG_SHARE = 0.10
CREDIT_NOTE_SHARE = 0.15
LONG_DOCUMENT = 3
COLUMNS = ("Row", "In the corpus", "Target", "")
MET, UNMET = "yes", "NO"


@dataclass(frozen=True, slots=True)
class Row:
    """One row of the coverage report: what was asked for, and what is there."""

    section: str
    axis: str
    seen: str
    target: str
    met: bool


def catalog(directory: Path) -> tuple[Row, ...]:
    """Every coverage row for a corpus, in the catalog's own order."""
    survey = survey_corpus(directory)
    return (*_family_rows(survey), *_knob_rows(survey), *_target_rows(survey))


def met_all(rows: tuple[Row, ...]) -> bool:
    return all(row.met for row in rows)


def render_table(rows: tuple[Row, ...], documents: int) -> str:
    """The report as a plain table, one section at a time."""
    lines = [f"{documents} documents", ""]
    for section in _sections(rows):
        lines.append(section)
        shown = [row for row in rows if row.section == section]
        widths = _widths(shown)
        lines += [f"  {_line(row, widths)}" for row in shown]
        lines.append("")
    unmet = sum(1 for row in rows if not row.met)
    lines.append("every row met" if not unmet else f"{unmet} of {len(rows)} rows not met")
    return "\n".join(lines) + "\n"


def _sections(rows: tuple[Row, ...]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        if row.section not in seen:
            seen.append(row.section)
    return seen


def _widths(rows: list[Row]) -> tuple[int, int, int]:
    return (
        max(len(COLUMNS[0]), *(len(row.axis) for row in rows)),
        max(len(COLUMNS[1]), *(len(row.seen) for row in rows)),
        max(len(COLUMNS[2]), *(len(row.target) for row in rows)),
    )


def _line(row: Row, widths: tuple[int, int, int]) -> str:
    axis, seen, target = widths
    mark = MET if row.met else UNMET
    return f"{row.axis:<{axis}}  {row.seen:>{seen}}  {row.target:>{target}}  {mark}"


def _family_rows(survey: Survey) -> tuple[Row, ...]:
    """Every profile against every family that profile declares."""
    return tuple(
        Row(
            section="Profile x family",
            axis=f"{profile_id} x {family}",
            seen=str(survey.pairs[profile_id, family]),
            target=">= 1",
            met=survey.pairs[profile_id, family] >= 1,
        )
        for profile_id in profile_ids()
        for family in _families_of(profile_id)
    )


def _families_of(profile_id: str) -> tuple[str, ...]:
    return tuple(family.value for family in load_profile(profile_id).families)


def _knob_rows(survey: Survey) -> tuple[Row, ...]:
    """Every knob the catalog names, on and off, whether or not the corpus uses it."""
    return tuple(
        Row(
            section="Knobs",
            axis=name,
            seen=f"{survey.knobs[name]} on / {survey.documents - survey.knobs[name]} off",
            target=f">= {KNOB_ON} on / >= {KNOB_OFF} off",
            met=survey.knobs[name] >= KNOB_ON and survey.documents - survey.knobs[name] >= KNOB_OFF,
        )
        for name in KNOB_NAMES
    )


def _target_rows(survey: Survey) -> tuple[Row, ...]:
    counts = survey.item_counts
    single = sum(1 for count in counts if count == 1)
    ten = sum(1 for count in counts if count >= 10)
    thirty = sum(1 for count in counts if count >= 30)
    return (
        _count_row("1 item", single, SINGLE_ITEM),
        _count_row("10 items or more", ten, TEN_ITEMS),
        _count_row("30 items or more", thirty, THIRTY_ITEMS),
        *_page_rows(survey),
        _share_row("credit notes", survey.credit_notes, survey.documents, CREDIT_NOTE_SHARE),
    )


def _page_rows(survey: Survey) -> tuple[Row, ...]:
    pages = Counter(survey.page_counts)
    total = survey.documents
    long_documents = sum(count for size, count in pages.items() if size >= LONG_DOCUMENT)
    return (
        _share_row("one page", pages[1], total, ONE_PAGE_SHARE),
        _share_row("two pages", pages[2], total, TWO_PAGE_SHARE),
        _share_row("three pages or more", long_documents, total, LONG_SHARE),
    )


def _count_row(axis: str, seen: int, target: int) -> Row:
    return Row("Coverage targets", axis, str(seen), f">= {target}", seen >= target)


def _share_row(axis: str, seen: int, total: int, share: float) -> Row:
    """A share of the corpus, reported as the catalog states it rather than as a count."""
    return Row(
        section="Coverage targets",
        axis=axis,
        seen=f"{seen} ({_percent(seen, total)})",
        target=f">= {round(share * 100)}%",
        met=total > 0 and seen >= int(total * share),
    )


def _percent(part: int, whole: int) -> str:
    return "0%" if not whole else f"{round(100 * part / whole)}%"
