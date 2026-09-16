"""Who printed the page: the supplier block, its VAT id, and the country the id says.

The supplier is what `detect_profile` weighs most, so a draft that gets it wrong is a
profile that never matches. The page says it in two places a draft can read without a
language: the letterhead — the block at the left margin above the first gap, which the
reader already finds as `logo_bottom` — and the VAT id, whose prefix names a country a
shipped profile describes. Where neither is there, the draft says so with a placeholder.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from invoice_extractor.document.anchors import COLUMN_TOLERANCE
from invoice_extractor.document.model import Document, TextLine
from invoice_extractor.drafting.pairs import SEPARATOR, could_be_a_label
from invoice_extractor.drafting.seen import Seen
from invoice_extractor.drafting.shapes import KnownId, Shape
from invoice_extractor.drafting.trace import PLACEHOLDER, Trace, missing, traced

SUPPLIER_ID = "header_labels.supplier_vat_id"
CUSTOMER_ID = "header_labels.customer_vat_id"
# How many lines a letterhead is read for where the reader found no gap under it.
LETTERHEAD_LINES = 4
UNKNOWN_COUNTRY = "??"


@dataclass(frozen=True, slots=True)
class Identity:
    """The `supplier`, `vat.id_*` and `country` keys as the draft writes them, traced."""

    supplier: dict[str, object]
    country: str
    id_prefix: str
    id_pattern: str
    traces: tuple[Trace, ...]


def identity(document: Document, seen: Sequence[Seen], known_ids: Sequence[KnownId]) -> Identity:
    name, address, block_traces = _letterhead(document)
    vat = _supplier_id(seen)
    country, prefix, pattern, id_traces = _id_shape(vat, known_ids)
    supplier: dict[str, object] = {
        "name": name,
        "aliases": [],
        "address_lines": address,
        "vat_id": PLACEHOLDER if vat is None else _compact(vat.pair.value),
    }
    vat_trace = (
        missing("supplier.vat_id", "the supplier's VAT id")
        if vat is None
        else traced("supplier.vat_id", _compact(vat.pair.value), _why(vat), vat.pair)
    )
    return Identity(
        supplier=supplier,
        country=country,
        id_prefix=prefix,
        id_pattern=pattern,
        traces=(*block_traces, vat_trace, *id_traces),
    )


def _letterhead(document: Document) -> tuple[str, list[str], tuple[Trace, ...]]:
    """The first line at the left margin is the name; the ones under it, the address."""
    lines = _block(document)
    if not lines:
        return (
            PLACEHOLDER,
            [],
            (
                missing("supplier.name", "the supplier's name"),
                missing("supplier.address_lines", "its address"),
            ),
        )
    name, *rest = lines
    address = [line.text.strip() for line in rest]
    return (
        name.text.strip(),
        address,
        (
            Trace(
                "supplier.name",
                name.text.strip(),
                "first line of the letterhead",
                name.page,
                name.zone.name,
                name.bbox,
            ),
            Trace(
                "supplier.address_lines", " / ".join(address), "the letterhead lines under the name"
            ),
        ),
    )


def _block(document: Document) -> list[TextLine]:
    """The letterhead: left-margin lines above `logo_bottom`, labelled lines left out."""
    if not document.pages:
        return []
    page = document.page(1)
    if not page.lines:
        return []
    margin = min(line.bbox.x0 for line in page.lines)
    column = sorted(
        (line for line in page.lines if abs(line.bbox.x0 - margin) <= COLUMN_TOLERANCE),
        key=lambda line: line.bbox.y0,
    )
    floor = page.anchors.logo_bottom
    if floor is not None:
        column = [line for line in column if line.bbox.y1 <= floor + COLUMN_TOLERANCE]
    else:
        column = column[:LETTERHEAD_LINES]
    return [line for line in column if not _labelled(line.text)]


def _labelled(text: str) -> bool:
    label, colon, _ = text.strip().partition(SEPARATOR)
    return bool(colon) and could_be_a_label(label.strip())


def _supplier_id(seen: Sequence[Seen]) -> Seen | None:
    """The value labelled as the supplier's id, else the first known id not the customer's."""
    for one in seen:
        if SUPPLIER_ID in {term.name for term in one.terms} and one.pair.value:
            return one
    for one in seen:
        names = {term.name for term in one.terms}
        if one.reading.shape is Shape.VAT_ID and CUSTOMER_ID not in names:
            return one
    return None


def _why(vat: Seen) -> str:
    if SUPPLIER_ID in {term.name for term in vat.terms}:
        return f"labelled '{vat.pair.label}', which the lexicon names as the supplier's VAT id"
    return f"shaped like a {vat.reading.details[0]} VAT id, labelled '{vat.pair.label}'"


def _id_shape(
    vat: Seen | None, known_ids: Sequence[KnownId]
) -> tuple[str, str, str, tuple[Trace, ...]]:
    """Country, prefix and pattern: a known country's own, or read off the id itself."""
    if vat is None:
        return (
            UNKNOWN_COUNTRY,
            "",
            PLACEHOLDER,
            (missing("country", "ISO 3166-1 alpha-2"), missing("vat.id_pattern", "a regex")),
        )
    if vat.reading.shape is Shape.VAT_ID:
        country = vat.reading.details[0]
        known = next(one for one in known_ids if one.country == country)
        reason = f"the shape of a {country} VAT id, as the {country} profile declares it"
        return (
            country,
            known.prefix,
            known.pattern.pattern,
            (
                Trace("country", country, reason),
                Trace("vat.id_pattern", known.pattern.pattern, reason),
            ),
        )
    compact = _compact(vat.pair.value)
    prefix = _prefix_of(compact)
    pattern = pattern_of(compact[len(prefix) :])
    reason = f"read off the id '{compact}' — no shipped profile knows this country"
    return (
        prefix or UNKNOWN_COUNTRY,
        prefix,
        pattern,
        (
            Trace("country", prefix or UNKNOWN_COUNTRY, reason),
            Trace("vat.id_pattern", pattern, reason),
        ),
    )


def _compact(value: str) -> str:
    return value.replace(" ", "")


def _prefix_of(compact: str) -> str:
    match = re.match(r"[A-Z]{2}", compact)
    return match.group(0) if match else ""


def pattern_of(text: str) -> str:
    """A regex that reads exactly this text's shape: `\\d{8}` for eight digits, and so on."""
    parts: list[str] = []
    for run in re.finditer(r"\d+|[A-Z]+|[a-z]+|.", text):
        piece = run.group(0)
        if piece.isdigit():
            parts.append(_counted(r"\d", len(piece)))
        elif piece.isalpha():
            parts.append(_counted("[A-Z]" if piece.isupper() else "[a-z]", len(piece)))
        else:
            parts.append(re.escape(piece))
    return "".join(parts)


def _counted(atom: str, count: int) -> str:
    return atom if count == 1 else f"{atom}{{{count}}}"
