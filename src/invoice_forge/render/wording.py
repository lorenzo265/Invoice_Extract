"""Which of a language's words this particular document uses.

A lexicon offers up to five ways of saying "invoice number"; one document says it one
way, on every page, and the truth records which. Drawing the choice once, here, is what
keeps the page and the truth from disagreeing — and what makes a corpus measure a label
matcher against a real vocabulary rather than a dictionary of size one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from random import Random

from invoice_forge.lexicon.schema import Lexicon
from invoice_forge.model import Document, DocumentType
from invoice_forge.profiles.schema import DateFormat, VendorProfile
from invoice_forge.render.text import NumberFormat

LEGAL_LINE_RANGE = (2, 3)


@dataclass(frozen=True, slots=True)
class Wording:
    """Every printed word and format this document commits to, drawn once from its seed."""

    title: str
    labels: Mapping[str, str]
    columns: Mapping[str, str]
    charges: Mapping[str, str]
    parties: Mapping[str, str]
    vat_summary: Mapping[str, str]
    carry: Mapping[str, str]
    page_numbering: str
    legal_lines: tuple[str, ...]
    date_format: DateFormat
    number_format: NumberFormat


def choose_wording(
    document: Document, profile: VendorProfile, lexicon: Lexicon, rng: Random
) -> Wording:
    """One synonym per idea, one date format, one thousands separator, for this document."""
    kind = "credit_note" if document.type is DocumentType.CREDIT_NOTE else "invoice"
    low, high = LEGAL_LINE_RANGE
    lines = min(rng.randint(low, high), len(lexicon.legal_lines))
    return Wording(
        title=rng.choice(lexicon.document_titles[kind]),
        labels=_picked({**lexicon.header_labels, **lexicon.totals_labels}, rng),
        columns=_picked(lexicon.column_headers, rng),
        charges=_picked(lexicon.charge_labels, rng),
        parties=_picked(lexicon.party_headings, rng),
        vat_summary=_picked(lexicon.vat_summary_headers, rng),
        carry=_picked(lexicon.carry_forward, rng),
        page_numbering=rng.choice(lexicon.page_numbering),
        legal_lines=tuple(rng.sample(lexicon.legal_lines, lines)),
        date_format=rng.choice(profile.date_formats),
        number_format=_number_format(profile, rng),
    )


def page_line(wording: Wording, page: int, pages: int) -> str:
    """The "page x of y" line, in whichever of the language's two shapes was drawn."""
    return wording.page_numbering.format(page=page, pages=pages)


def _picked(synonyms: Mapping[str, tuple[str, ...]], rng: Random) -> Mapping[str, str]:
    return {name: rng.choice(options) for name, options in synonyms.items()}


def _number_format(profile: VendorProfile, rng: Random) -> NumberFormat:
    return NumberFormat(
        decimal=profile.decimal_separator,
        thousands=rng.choice(profile.thousands_separators),
    )
