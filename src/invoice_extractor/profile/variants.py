"""Stage 2: the variant this document matches, laid over the profile it belongs to.

A profile says what a vendor's invoices usually are. A variant says what one run of them
is instead — the document type that is worded differently, the branch that prints an
extra line — as a partial profile plus the fingerprint (`when`) that says when it
applies. The first variant whose fingerprint matches wins; a document matching none is
read with the profile as it stands, which is the ordinary case and costs nothing.

The overlay goes through the one merge function and the one loader every other layer goes
through (`docs/PROFILE_FORMAT.md`), so a variant naming a key no profile has is a
`ProfileError` like any other rather than a field that silently never resolves. That is
also why the layers are re-read here rather than patched onto the record: a `Profile` is
the *validated* form, and there is no second way to build one.

`document_type` is answered by stage 3's own classifier run against the base profile,
which is the only vocabulary available before a variant is chosen. A variant that changes
the titles therefore changes what stage 3 concludes, not what chose it.
"""

from __future__ import annotations

from pathlib import Path

from invoice_extractor.document.model import Document
from invoice_extractor.extraction.classify import classify_document
from invoice_extractor.profile.loader import (
    DEFAULTS_ID,
    PROFILES_ROOT,
    lexicons_beside,
    parse,
    read_profile_json,
)
from invoice_extractor.profile.merge import PROFILE_RULES, merge
from invoice_extractor.profile.schema import Profile, Variant

DOCUMENT_TYPE = "document_type"


def select_variant(document: Document, profile: Profile, root: Path = PROFILES_ROOT) -> Profile:
    """The profile this document is read with: the vendor's, or its matching variant's."""
    matched = next(
        (variant for variant in profile.variants if _matches(variant, document, profile)),
        None,
    )
    return profile if matched is None else _applied(matched, profile, root)


def _matches(variant: Variant, document: Document, profile: Profile) -> bool:
    """Every condition the fingerprint names, not just one: conditions narrow, never widen."""
    return all(_condition(key, wanted, document, profile) for key, wanted in variant.when.items())


def _condition(key: str, wanted: str, document: Document, profile: Profile) -> bool:
    if key == DOCUMENT_TYPE:
        return classify_document(document, profile).value == wanted
    return any(wanted.casefold() in line.text.casefold() for line in document.lines)


def _applied(variant: Variant, profile: Profile, root: Path) -> Profile:
    """The three layers again, with a fourth on top, validated as strictly as the first."""
    defaults = read_profile_json(root / f"{DEFAULTS_ID}.json")
    declared = read_profile_json(root / f"{profile.id}.json")
    layered = merge(defaults, declared, PROFILE_RULES)
    return parse(merge(layered, variant.overlay, PROFILE_RULES), lexicons_beside(root))
