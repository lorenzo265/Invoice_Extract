"""What a candidate has to survive before it is ranked.

A strategy reads the whole page, which is what makes it able to find a value wherever a
vendor drew it. A filter is where that generosity is paid for: a candidate introduced by
a label this field is not is dropped before the rankers are asked to choose between it
and a real one.

Only what is *wrong* is filtered. Where a field usually sits is a preference, not a
fence, so it is a ranker (`zone_priority`) rather than a filter: a vendor that moved a
block has not printed a different invoice, and a filter would throw the value away.
"""

from __future__ import annotations

from collections.abc import Sequence

from invoice_extractor.extraction.candidate import Candidate
from invoice_extractor.extraction.units.normalizers import NOT_ALNUM, strip_label
from invoice_extractor.profile.schema import FieldProfile, Profile


def not_a_trap(
    found: Sequence[Candidate], field: FieldProfile, profile: Profile
) -> list[Candidate]:
    """Drop what a trap label introduced: an order date is not the invoice date.

    A trap is a label the vendor prints beside the one this field wants, and the profile
    names them twice over — per field in `exclude_labels`, and once for the whole vendor
    in `noise.ignore_labels`. A label the field itself declares is never a trap for it,
    however many other fields call it one.
    """
    traps = _traps(field, profile)
    if not traps:
        return list(found)
    return [candidate for candidate in found if not _introduced_by(candidate, traps)]


def _traps(field: FieldProfile, profile: Profile) -> frozenset[str]:
    own = {label.casefold() for label in field.labels}
    named = (*field.exclude_labels, *profile.noise.ignore_labels)
    return frozenset(label.casefold() for label in named if label.casefold() not in own)


def _introduced_by(candidate: Candidate, traps: frozenset[str]) -> bool:
    matched = candidate.evidence.matched_label
    if matched is not None and matched.casefold() in traps:
        return True
    text = candidate.evidence.raw_text.strip().casefold()
    return any(text.startswith(trap) for trap in traps)


def not_a_label(
    found: Sequence[Candidate], field: FieldProfile, profile: Profile
) -> list[Candidate]:
    """Drop a candidate that is nothing but a label the vendor introduces something else with.

    `label_below` reads the line under a label, and a vendor that sets its values at a tab
    stop to the right leaves the next label there instead: under `Payment Terms:` it
    prints `Payment Date:`, which introduces the next value and is not this one. Every
    label the profile declares — for a field, for an extra the vendor prints, for a party
    block — is such a word, and so is that word with its own value after it. A label the
    field itself declares is not, for the reason `not_a_trap` gives.
    """
    labels = _declared(profile) - {_bare(label) for label in field.labels}
    return [candidate for candidate in found if not _is_a_label(candidate, labels)]


def _declared(profile: Profile) -> frozenset[str]:
    """Every label this vendor introduces a value with, as the page prints it."""
    described = (*profile.fields.values(), *(custom.field for custom in profile.custom_fields))
    headings = [label for section in profile.parties.values() for label in section.labels]
    groups = (*(one.labels for one in described), headings)
    return frozenset(_bare(label) for group in groups for label in group if label.strip())


def _is_a_label(candidate: Candidate, labels: frozenset[str]) -> bool:
    text = _bare(candidate.raw_text)
    return any(text == label or text.startswith(f"{label}:") for label in labels)


def _bare(text: str) -> str:
    """A label as the page prints it, without the colon after it or the space around it."""
    return text.strip().rstrip(":").strip().casefold()


def not_the_suppliers_own(
    found: Sequence[Candidate], field: FieldProfile, profile: Profile
) -> list[Candidate]:
    """Drop the vendor's own tax id, whichever label introduced it.

    A vendor prints its own registration under the same words the customer's sits under —
    the Czech `DIC:` heads both, and an English letterhead sets `VAT Reg. No.:` beside the
    vendor's number at the top of the page and the customer's further down — so a label
    reads both and the closer one usually wins. The candidate whose value is the profile's
    own `supplier.vat_id` is never the customer's, so it is dropped before the rankers are
    asked to choose. Compared as the field will read it — the text after the label where
    the label shares its line, as `strip_label` gives it — and bare: without punctuation,
    and without the country prefix that one side may print and the other leave out.
    """
    own = _bare_id(profile.supplier.vat_id, profile.vat.id_prefix)
    if not own:
        return list(found)
    return [
        candidate
        for candidate in found
        if _bare_id(strip_label(candidate, profile), profile.vat.id_prefix) != own
    ]


def _bare_id(text: str, prefix: str) -> str:
    """An identifier as either side may print it: alphanumerics, upper case, and without the
    country prefix this vendor's profile declares."""
    bare = NOT_ALNUM.sub("", text).upper()
    head = prefix.upper()
    return bare[len(head) :] if head and bare.startswith(head) else bare
