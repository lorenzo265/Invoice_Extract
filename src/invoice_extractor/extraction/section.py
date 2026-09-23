"""`SectionSpec`: a party block, read from the heading that opens it down the column it sits in.

A block is not a field and not a table. It is a heading, a name, the address under it and
sometimes a VAT id — and what ends it is the page's own drawing: the column runs out, or
the next thing down is too far away to belong, or the vendor's word for another block
begins. `max_lines` is the last guard, not the first.

Three things a block may say are told apart here: a placeholder (`same as billing
address`) is a block that defers rather than one that failed, a VAT id is a value and not
a line of the address, and the name is the first line and never one of them.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import takewhile

from invoice_extractor.document.model import Document, TextPart
from invoice_extractor.document.rows import CellRow, cell_rows_of
from invoice_extractor.domain.evidence import Evidence, Strategy
from invoice_extractor.domain.parties import Party
from invoice_extractor.extraction.spec import SectionSpec
from invoice_extractor.profile.schema import Profile, SectionProfile

# The one party no heading opens: the vendor prints itself as the letterhead.
SUPPLIER = "supplier"
# How far from the heading's own left edge a line still belongs to its column, in points.
COLUMN_TOLERANCE = 2.0
# How much of a line's height may stand between it and the line above before the block ends.
BLOCK_GAP = 1.5
# How much of the heading's height may stand between it and the block's first line. A
# vendor leaves room under `Bill To:` before the name it sets there; the room opens the
# block, and it is the gap between the block's own lines that ends it.
HEADING_GAP = 3.0


@dataclass(frozen=True, slots=True)
class Block:
    """A heading and the lines under it, as they were drawn."""

    page: int
    heading: TextPart
    lines: tuple[TextPart, ...]


def read_section(spec: SectionSpec, document: Document, profile: Profile) -> Party | None:
    """The party this spec names, read the way its own block is drawn."""
    if spec.source == SUPPLIER:
        return read_supplier(document, profile)
    section = profile.parties.get(spec.source)
    return None if section is None else read_party(document, section, profile)


def read_party(document: Document, section: SectionProfile, profile: Profile) -> Party | None:
    """The party this section describes, or nothing where the document prints no such block."""
    block = _block(document, section)
    if block is None:
        return None
    return _party(block, section, _registration(profile))


def read_supplier(document: Document, profile: Profile) -> Party | None:
    """The vendor's own block, which no heading opens: it starts at the name it prints itself.

    Everything under that name belongs to the address, because the name is the heading
    here rather than the first line of the block.
    """
    section = SectionProfile(
        labels=(profile.supplier.name, *profile.supplier.aliases),
        stop_labels=(),
        max_lines=_SUPPLIER_LINES,
        placeholders=(),
        zones=(),
    )
    block = _block(document, section)
    if block is None:
        return None
    registration = _registration(profile)
    lines = [line for line in block.lines if not registration.search(_squeezed(line))]
    return Party(
        name=block.heading.text.strip(),
        lines=tuple(line.text.strip() for line in lines),
        vat_id=_first_vat_id(block, registration),
        placeholder=False,
        evidence=(_evidence(block.page, block.heading), *_all(block)),
    )


# A letterhead is a name, an address and a registration line; nothing else belongs to it.
_SUPPLIER_LINES = 6


def _block(document: Document, section: SectionProfile) -> Block | None:
    for page in document.pages:
        rows = cell_rows_of(page.lines)
        for row in rows:
            heading = _heading(row, section.labels)
            if heading is not None:
                return Block(page.number, heading, _under(rows, heading, section))
    return None


def _heading(row: CellRow, labels: Sequence[str]) -> TextPart | None:
    folded = [label.strip().casefold() for label in labels if label.strip()]
    for cell in row.cells:
        text = cell.text.strip().casefold()
        if any(text == label or text.startswith(label) for label in folded):
            return cell
    return None


def _under(
    rows: Sequence[CellRow], heading: TextPart, section: SectionProfile
) -> tuple[TextPart, ...]:
    """The lines drawn under the heading, in its own column, while they keep coming.

    Only that column is walked: a page sets a metadata block beside a letterhead, and its
    lines are interleaved with these by height while belonging to something else entirely.
    """
    found: list[TextPart] = []
    last = heading
    for cell in _column(rows, heading):
        allowed = HEADING_GAP if last is heading else BLOCK_GAP
        if _too_far(last, cell, allowed) or _is_one_of(cell, section.stop_labels):
            break
        found.append(cell)
        last = cell
        if len(found) >= section.max_lines:
            break
    return tuple(found)


def _column(rows: Sequence[CellRow], heading: TextPart) -> list[TextPart]:
    """Every cell drawn under the heading at its own left edge, top to bottom."""
    edge = heading.bbox.x0
    return [
        cell
        for row in rows
        for cell in row.cells
        if cell.bbox.y0 > heading.bbox.y0 and abs(cell.bbox.x0 - edge) <= COLUMN_TOLERANCE
    ]


def _too_far(last: TextPart, cell: TextPart, allowed: float) -> bool:
    """Whether more than `allowed` heights of the last line stand between it and this one."""
    return cell.bbox.y0 - last.bbox.y1 > (last.bbox.y1 - last.bbox.y0) * allowed


def _party(block: Block, section: SectionProfile, registration: re.Pattern[str]) -> Party:
    """What the block says: a name, an address, a VAT id — or that it defers to another."""
    lines = [line for line in block.lines if not registration.search(_squeezed(line))]
    named = _name_lines(lines)
    rest = lines[len(named) :]
    name = " ".join(line.text.strip() for line in named) or None
    if _defers(rest, section.placeholders):
        return Party(name=name, placeholder=True, evidence=_all(block))
    return Party(
        name=name,
        lines=tuple(line.text.strip() for line in rest),
        vat_id=_first_vat_id(block, registration),
        placeholder=False,
        evidence=_all(block),
    )


def _name_lines(lines: Sequence[TextPart]) -> list[TextPart]:
    """The name, which a block sets in its own weight and may run over two lines.

    A name too wide for its column is set over two, and both are bold where the address
    under them is not. Weight says which lines are the name only where the block has two
    weights in it: a vendor that sets no weight at all, or the whole block in one, leaves
    the first line, which is the name in every block this reader has seen.
    """
    bold = list(takewhile(lambda line: line.bold, lines))
    if bold and len(bold) < len(lines):
        return bold
    return list(lines[:1])


def _defers(rest: Sequence[TextPart], placeholders: Sequence[str]) -> bool:
    """`same as billing address`, however many lines the block needed to say it."""
    said = " ".join(line.text.strip() for line in rest).casefold()
    folded = [label.strip().casefold() for label in placeholders if label.strip()]
    return bool(said) and any(said.startswith(label) or label.startswith(said) for label in folded)


def _registration(profile: Profile) -> re.Pattern[str]:
    """How a VAT id is printed here: the country's prefix, then the country's own shape."""
    prefix = re.escape(profile.vat.id_prefix)
    return re.compile(f"{prefix}{profile.vat.id_pattern.pattern}")


def _first_vat_id(block: Block, registration: re.Pattern[str]) -> str | None:
    for line in block.lines:
        found = registration.search(_squeezed(line))
        if found is not None:
            return found.group(0)
    return None


def _squeezed(line: TextPart) -> str:
    """A registration number may be set with spaces in it; the number is what it says."""
    return line.text.replace(" ", "")


def _is_one_of(line: TextPart, labels: Sequence[str]) -> bool:
    text = line.text.strip().casefold()
    return any(text.startswith(label.strip().casefold()) for label in labels if label.strip())


def _all(block: Block) -> tuple[Evidence, ...]:
    return tuple(_evidence(block.page, line) for line in block.lines)


def _evidence(page: int, line: TextPart) -> Evidence:
    return Evidence(
        page=page,
        bbox=line.bbox,
        matched_label=None,
        strategy=Strategy.SECTION_LINE,
        raw_text=line.text.strip(),
    )
