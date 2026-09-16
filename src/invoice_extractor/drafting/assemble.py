"""The profile JSON a draft writes: what this vendor does differently from the defaults.

A shipped profile is an overlay over `_defaults.json` (`profile/merge.py`), and so is a
draft — it says what the page showed and nothing the defaults already say. The keys it
writes are the ones a person cannot get from a language: who the supplier is, how it
writes numbers and dates, what it trades in, and *where on the page* each field's label
was actually found. The defaults guess zones for a generic vendor; a draft replaces the
guess with the zone the label sat in, which is the one correction every hand-written
profile so far has needed.

The zone written is the value's, not the label's: it is the zone a candidate for the
field carries once the engine reads the page (`extraction/units/strategies.py`).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from invoice_extractor.drafting.conventions import Convention
from invoice_extractor.drafting.identity import Identity
from invoice_extractor.drafting.seen import Seen

FIELD_GROUPS = ("header_labels", "totals_labels")
PARTY_GROUP = "party_headings"


@dataclass(frozen=True, slots=True)
class Settings:
    """The conventions and identity a profile is assembled from, already read."""

    identity: Identity
    number_format: Convention
    date_formats: Convention
    currencies: Convention
    rates: Convention


def assemble(
    profile_id: str,
    language: str,
    settings: Settings,
    seen: Sequence[Seen],
    default_fields: Collection[str],
) -> dict[str, object]:
    """The overlay, in the key order `docs/PROFILE_FORMAT.md` lists them."""
    return {
        "id": profile_id,
        "language": language,
        "country": settings.identity.country,
        "lexicon": language,
        "number_format": settings.number_format.value,
        "date_formats": settings.date_formats.value,
        "currencies": settings.currencies.value,
        "vat": {
            "rates": settings.rates.value,
            "id_prefix": settings.identity.id_prefix,
            "id_pattern": settings.identity.id_pattern,
        },
        "supplier": settings.identity.supplier,
        "fields": fields(seen, language, default_fields),
        "parties": parties(seen, language),
    }


def fields(
    seen: Sequence[Seen], language: str, default_fields: Collection[str]
) -> dict[str, dict[str, list[str]]]:
    """Per field the defaults declare and the page labelled: its zones, and any foreign label.

    A label spelled by another language's lexicon — an English line on a German page —
    is added to the field as a label of this vendor's own, so the profile reads it; one
    the page's own lexicon spells is already there through the defaults.
    """
    drafted: dict[str, dict[str, list[str]]] = {}
    for one in seen:
        for name in _field_names(one, language, default_fields):
            entry = drafted.setdefault(name, {"zones": []})
            _add(entry["zones"], one.pair.zone.name)
            if not any(term.language == language for term in one.terms):
                _add(entry.setdefault("labels", []), one.pair.label)
    return drafted


def parties(seen: Sequence[Seen], language: str) -> dict[str, dict[str, list[str]]]:
    """Per party block whose heading the page printed: the zone the heading sat in."""
    drafted: dict[str, dict[str, list[str]]] = {}
    for one in seen:
        for entry in one.names(language):
            group, _, name = entry.partition(".")
            if group == PARTY_GROUP:
                _add(drafted.setdefault(name, {"zones": []})["zones"], one.pair.label_zone.name)
    return drafted


def _field_names(one: Seen, language: str, default_fields: Collection[str]) -> list[str]:
    names: list[str] = []
    for entry in one.names(language):
        group, _, name = entry.partition(".")
        if group in FIELD_GROUPS and name in default_fields and name not in names:
            names.append(name)
    return names


def _add(into: list[str], value: str) -> None:
    if value not in into:
        into.append(value)


def default_field_names(defaults: Mapping[str, object]) -> tuple[str, ...]:
    """The fields `_defaults.json` declares — the ones a draft may place on the page."""
    declared = defaults.get("fields")
    return tuple(declared) if isinstance(declared, dict) else ()
