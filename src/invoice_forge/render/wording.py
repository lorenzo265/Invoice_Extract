"""Which of a language's words this particular document uses.

A lexicon offers up to five ways of saying "invoice number"; one document says it one
way, on every page, and the truth records which. Drawing the choice once, here, is what
keeps the page and the truth from disagreeing — and what makes a corpus measure a label
matcher against a real vocabulary rather than a dictionary of size one.

This is the third place a knob lands, after the family's declaration and the sampler's
content: `docs/FORGE_SPEC.md` §3.8 calls it "the renderer (how)". A knob that changes
neither what the document says nor where it sits — which thousands separator it writes,
which of the exemption sentences it gives — changes the wording it commits to, and the
blocks still read a record rather than a `Knob`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

from invoice_forge.knobs import Knob
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
    traps: Mapping[str, str]
    vat_summary: Mapping[str, str]
    carry: Mapping[str, str]
    page_numbering: str
    legal_lines: tuple[str, ...]
    copy_stamp: str
    exemption: str
    date_format: DateFormat
    number_format: NumberFormat


def choose_wording(
    document: Document,
    profile: VendorProfile,
    lexicon: Lexicon,
    rng: Random,
    knobs: Sequence[Knob] = (),
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
        traps=_picked(lexicon.trap_labels, rng),
        vat_summary=_picked(lexicon.vat_summary_headers, rng),
        carry=_picked(lexicon.carry_forward, rng),
        page_numbering=rng.choice(lexicon.page_numbering),
        legal_lines=tuple(rng.sample(lexicon.legal_lines, lines)),
        copy_stamp=rng.choice(lexicon.copy_stamps),
        exemption=_exemption(lexicon, rng),
        date_format=rng.choice(profile.date_formats),
        number_format=_number_format(profile, knobs, rng),
    )


def _exemption(lexicon: Lexicon, rng: Random) -> str:
    """One of the three reasons a rate is zero, drawn whether or not it is printed."""
    kind = rng.choice(sorted(lexicon.exemption_sentences))
    return rng.choice(lexicon.exemption_sentences[kind])


def page_line(wording: Wording, page: int, pages: int) -> str:
    """The "page x of y" line, in whichever of the language's two shapes was drawn."""
    return wording.page_numbering.format(page=page, pages=pages)


def _picked(synonyms: Mapping[str, tuple[str, ...]], rng: Random) -> Mapping[str, str]:
    return {name: rng.choice(options) for name, options in synonyms.items()}


def _number_format(profile: VendorProfile, knobs: Sequence[Knob], rng: Random) -> NumberFormat:
    """The vendor's usual separator, or one of the others it also writes numbers with."""
    separators = profile.thousands_separators
    drawn = rng.choice(separators[1:]) if len(separators) > 1 else separators[0]
    return NumberFormat(
        decimal=profile.decimal_separator,
        thousands=drawn if Knob.THOUSANDS_VARIANT in knobs else separators[0],
    )
