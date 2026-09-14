"""Which kind of document this is: an invoice, or the credit note that reverses one.

Stage 3 of `docs/ENGINE_SPEC.md` §2. The profile names the titles a vendor prints for
each kind and the labels a credit note cites its original invoice with; a page that says
neither is an invoice, because that is what a vendor sends unless it says otherwise.
"""

from __future__ import annotations

from enum import Enum

from invoice_extractor.document.model import Document
from invoice_extractor.profile.schema import Profile


class DocumentType(Enum):
    """What the document says it is."""

    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"


def classify_document(document: Document, profile: Profile) -> DocumentType:
    """A credit note where the page carries one of its titles or cites an invoice."""
    titles = profile.document_types
    printed = [line.text.strip().casefold() for line in document.lines]
    if _carries(printed, titles.credit_note_titles) or _carries(
        printed, titles.credit_reference_labels
    ):
        return DocumentType.CREDIT_NOTE
    return DocumentType.INVOICE


def _carries(printed: list[str], wanted: tuple[str, ...]) -> bool:
    """A title is a line of its own; a reference label introduces the number it cites."""
    folded = [word.casefold() for word in wanted if word]
    return any(text == word or text.startswith(word) for text in printed for word in folded)
