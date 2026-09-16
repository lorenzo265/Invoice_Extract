"""Values no line carries, computed from lines that do.

A `DerivedSpec` names one of these. Each is a pure function of the document and the
fields that have already resolved, so it can be read, tested and re-run without opening
the PDF again; each returns `None` rather than a guess when the document does not say.

A derivation reports the line it read as well as the value it computed, because a
derived value is still a value read off a document and has to point at one (ADR-0002).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from invoice_extractor.document.model import Document, TextLine
from invoice_extractor.domain.models import FieldResult, FieldValue
from invoice_extractor.profile.schema import Profile


@dataclass(frozen=True, slots=True)
class Derived:
    """What was computed, and the line the text it was computed from was printed on."""

    value: FieldValue
    line: TextLine


@dataclass(frozen=True, slots=True)
class Seen:
    """How often a word appears on a page, and the line it first appeared on."""

    count: int
    line: TextLine


def currency(
    document: Document, profile: Profile, resolved: Mapping[str, FieldResult]
) -> Derived | None:
    """The currency this document is in: the vendor's code that the page prints most.

    A profile lists the codes a vendor trades in. Counting which of them the document
    actually carries is what separates the invoice's own currency from the one it echoes
    a converted total in, without reading a label for either.
    """
    counted = _counts(document, profile)
    if not counted:
        return None
    code = max(counted, key=lambda seen: (counted[seen].count, -profile.currencies.index(seen)))
    return Derived(code, counted[code].line)


Derivation = Callable[[Document, Profile, Mapping[str, FieldResult]], Derived | None]

DERIVATIONS: Mapping[str, Derivation] = {"currency": currency}


def _counts(document: Document, profile: Profile) -> dict[str, Seen]:
    """How often each code the vendor trades in appears, and where it first appeared."""
    counted: dict[str, Seen] = {}
    for line in document.lines:
        printed = line.text.upper()
        for code in profile.currencies:
            times = printed.count(code)
            if times:
                counted[code] = _plus(counted.get(code), times, line)
    return counted


def _plus(seen: Seen | None, times: int, line: TextLine) -> Seen:
    """The first line a code was seen on stays the first, however often it is seen again."""
    return Seen(times, line) if seen is None else Seen(seen.count + times, seen.line)
