"""Everything a block needs to know, gathered once so no block takes six arguments.

The context is the document and the three things that decide how it reads: the vendor's
profile, the language's lexicon, and the family's declaration — plus the wording drawn
for this one document.
"""

from __future__ import annotations

from dataclasses import dataclass

from invoice_forge.knobs import Knob
from invoice_forge.layout.spec import FamilySpec
from invoice_forge.lexicon.schema import Lexicon
from invoice_forge.model import Document
from invoice_forge.profiles.schema import VendorProfile
from invoice_forge.render.wording import Wording


@dataclass(frozen=True, slots=True)
class RenderContext:
    """One document, and every decision already made about how it will read."""

    document: Document
    profile: VendorProfile
    lexicon: Lexicon
    family: FamilySpec
    wording: Wording
    knobs: tuple[Knob, ...] = ()
