"""Proving every box in a truth file by reading that box out of the PDF.

The renderer's claim is "this value is here". The proof runs the other way: open the
finished document, read the rectangle the truth names, and see whether it says what the
truth says it says. Nothing the renderer remembers is consulted.

Printed and normalised forms differ — "9.965,24 EUR" against "9965.24", a description
wrapped over two boxes against the whole sentence — so the comparison is on letters and
digits only, and a box has to hold text its value accounts for.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from invoice_forge.fields import LINE_ITEM_COLUMNS
from invoice_forge.render.pdf import text_in
from invoice_forge.truth.reading import Box, amount, block, box_at, boxes, rows, text

VAT_COMPONENTS = ("rate", "base", "vat")


class Match(Enum):
    """How a box's text and the value it stands for are allowed to differ.

    They are not always the same string. A field records what it printed, so its box says
    exactly that. A description wraps, so each of its boxes says PART of the value. A
    charge records the amount but prints it with a currency, so its box CONTAINS the
    value. Saying which relation applies is what keeps the check strict.
    """

    EXACT = "exact"
    PART = "part"
    CONTAINS = "contains"
    ANY = "any"


@dataclass(frozen=True, slots=True)
class Claim:
    """One box, what the truth says it holds, and how the two are allowed to differ."""

    where: str
    box: Box
    expected: str
    match: Match


def check_readback(truth: dict[str, object], pdf_path: Path) -> list[str]:
    """Read every claimed box out of the PDF and report the ones that say something else."""
    claims = tuple(_claims(truth))
    found = text_in(pdf_path, [(claim.box.page, claim.box.bbox) for claim in claims])
    return [
        _complaint(claim, actual)
        for claim, actual in zip(claims, found, strict=True)
        if not _holds(claim, actual)
    ]


def alnum(value: str) -> str:
    """Letters and digits, upper-cased: what survives every way of printing one value."""
    return "".join(character for character in value if character.isalnum()).upper()


def _holds(claim: Claim, actual: str) -> bool:
    read, expected = alnum(actual), alnum(claim.expected)
    if not read:
        return False
    if claim.match is Match.ANY:
        return True
    if claim.match is Match.EXACT:
        return read == expected
    return read in expected if claim.match is Match.PART else expected in read


def _complaint(claim: Claim, actual: str) -> str:
    wanted = "any text" if claim.match is Match.ANY else repr(claim.expected)
    said = f"says {actual!r}, not {wanted}"
    return f"{claim.where}: the box at {list(claim.box.bbox)} {said}"


def _claims(truth: dict[str, object]) -> Iterator[Claim]:
    yield from _field_claims(truth)
    yield from _cell_claims(truth)
    yield from _charge_claims(truth)
    yield from _vat_claims(truth)
    yield from _party_claims(truth)
    yield from _secondary_claims(truth)
    yield from _noise_claims(truth)


def _field_claims(truth: dict[str, object]) -> Iterator[Claim]:
    """A field records the exact string it printed, so its boxes are matched exactly."""
    for name, entry in block(truth, "fields").items():
        if not isinstance(entry, dict) or entry.get("printed") is None:
            continue
        where = f"fields.{name}"
        printed = text(entry, "printed", where)
        for box in boxes(entry, where):
            yield Claim(where, box, printed, Match.EXACT)


def _cell_claims(truth: dict[str, object]) -> Iterator[Claim]:
    """A cell records the value, not the printed form, and a description spans its lines."""
    for index, row in enumerate(rows(truth, "line_items")):
        cells = row.get("cells")
        if not isinstance(cells, dict):
            continue
        for column in LINE_ITEM_COLUMNS:
            if column not in cells:
                continue
            where = f"line_items[{index}].cells.{column}"
            expected = text(row, column, f"line_items[{index}]")
            for box in boxes(cells, where, key=column):
                yield Claim(where, box, expected, Match.PART)


def _charge_claims(truth: dict[str, object]) -> Iterator[Claim]:
    for index, charge in enumerate(rows(truth, "charges")):
        where = f"charges[{index}]"
        printed = str(amount(charge, "amount", where))
        for box in boxes(charge, where):
            yield Claim(where, box, printed, Match.CONTAINS)


def _vat_claims(truth: dict[str, object]) -> Iterator[Claim]:
    """The boxes of a summary row are its rate, base and VAT, in the order they were drawn."""
    for index, line in enumerate(rows(truth, "vat_summary")):
        where = f"vat_summary[{index}]"
        printed = [str(amount(line, key, where)) for key in VAT_COMPONENTS]
        paired = zip(VAT_COMPONENTS, printed, boxes(line, where), strict=False)
        for component, value, box in paired:
            yield Claim(f"{where}.{component}", box, value, Match.CONTAINS)


def _party_claims(truth: dict[str, object]) -> Iterator[Claim]:
    """A party's boxes are its name and its address lines, in the order they were drawn."""
    for kind, party in block(truth, "parties").items():
        if not isinstance(party, dict):
            continue
        where = f"parties.{kind}"
        printed = [text(party, "name", where), *_address_lines(party)]
        for value, box in zip(printed, boxes(party, where), strict=False):
            yield Claim(where, box, value, Match.EXACT)


def _secondary_claims(truth: dict[str, object]) -> Iterator[Claim]:
    echo = truth.get("secondary_amounts")
    if not isinstance(echo, dict):
        return
    printed = str(amount(echo, "total_amount", "secondary_amounts"))
    for box in boxes(echo, "secondary_amounts"):
        yield Claim("secondary_amounts", box, printed, Match.CONTAINS)


def _noise_claims(truth: dict[str, object]) -> Iterator[Claim]:
    """Noise records no string, so the only claim is that something is printed there."""
    for index, entry in enumerate(rows(truth, "noise")):
        where = f"noise[{index}]"
        yield Claim(where, box_at(entry, where), "", Match.ANY)


def _address_lines(party: dict[str, object]) -> list[str]:
    value = party.get("lines")
    if not isinstance(value, list):
        return []
    return [line for line in value if isinstance(line, str)]
