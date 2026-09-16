"""The file beside the draft: every guess, its reason, and everything that was not one.

`profiles/<id>.json` is what the engine will read; `drafts/<id>.json` beside it is what
the person reads first. It carries the trace of each key written, the fields whose label
was found and where, the table headings and party headings the page printed, and — the
part that matters most on a page in a new language — every labelled value no lexicon
could name, with the shape of the value and the zone it sat in. That list is the
worksheet: each line of it is a label to assign, or to leave alone.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from invoice_extractor.drafting.assemble import FIELD_GROUPS, Settings
from invoice_extractor.drafting.pairs import Mark
from invoice_extractor.drafting.seen import Seen
from invoice_extractor.drafting.shapes import Shape
from invoice_extractor.drafting.trace import Trace

# The groups whose matches are reported as what the page printed, by kind.
REPORTED = {
    "column_headers": "line_items",
    "vat_summary_headers": "vat_summary",
    "party_headings": "parties",
    "charge_labels": "charges",
    "document_titles": "titles",
    "trap_labels": "traps",
    "carry_forward": "carry_forward",
}
# Shapes strong enough that a pair no lexicon names is worth a line of the worksheet even
# where the vendor set no colon after the label.
STRONG = frozenset(
    {Shape.DATE, Shape.AMOUNT, Shape.PERCENT, Shape.CURRENCY, Shape.VAT_ID, Shape.IBAN}
)


@dataclass(frozen=True, slots=True)
class Placed:
    """One field the page labelled, and the pair it was read from."""

    field: str
    seen: Seen

    def to_dict(self) -> dict[str, object]:
        return {
            "field": self.field,
            "label": self.seen.pair.label,
            "lexicon": [f"{term.language}: {term.name}" for term in self.seen.terms],
            **_where(self.seen),
        }


@dataclass(frozen=True, slots=True)
class Evidence:
    """Everything the draft read, mapped or not, with where it read it."""

    source_path: str
    profile_id: str
    language: str
    votes: tuple[tuple[str, int], ...]
    settings: tuple[Trace, ...]
    placed: tuple[Placed, ...]
    default_fields: tuple[str, ...]
    seen: tuple[Seen, ...]

    @property
    def placeholders(self) -> tuple[str, ...]:
        return tuple(trace.key for trace in self.settings if trace.is_placeholder)

    @property
    def missing(self) -> tuple[str, ...]:
        """The fields the defaults declare that no label on the page named."""
        found = {one.field for one in self.placed}
        return tuple(name for name in self.default_fields if name not in found)

    @property
    def unmapped(self) -> tuple[Seen, ...]:
        return tuple(one for one in self.seen if _worth_listing(one))

    def to_dict(self) -> dict[str, object]:
        return {
            "source_path": self.source_path,
            "profile_id": self.profile_id,
            "language": {
                "chosen": self.language,
                "votes": [[name, count] for name, count in self.votes],
            },
            "settings": [trace.to_dict() for trace in self.settings],
            "placeholders": list(self.placeholders),
            "fields": [one.to_dict() for one in self.placed],
            "missing": list(self.missing),
            "printed": _printed(self.seen, self.language),
            "unmapped": [_unmapped(one) for one in self.unmapped],
        }


def evidence(
    source_path: str,
    profile_id: str,
    language: str,
    votes: Sequence[tuple[str, int]],
    settings: Settings,
    seen: Sequence[Seen],
    default_fields: Sequence[str],
) -> Evidence:
    return Evidence(
        source_path=source_path,
        profile_id=profile_id,
        language=language,
        votes=tuple(votes),
        settings=_traces(settings),
        placed=tuple(
            Placed(name, one)
            for one in seen
            for name in _fields_named(one, language, default_fields)
        ),
        default_fields=tuple(default_fields),
        seen=tuple(seen),
    )


def _traces(settings: Settings) -> tuple[Trace, ...]:
    return (
        *settings.identity.traces,
        *settings.number_format.traces,
        *settings.date_formats.traces,
        *settings.currencies.traces,
        *settings.rates.traces,
    )


def _fields_named(one: Seen, language: str, default_fields: Sequence[str]) -> list[str]:
    found: list[str] = []
    for entry in one.names(language):
        group, _, name = entry.partition(".")
        if group in FIELD_GROUPS and name in default_fields and name not in found:
            found.append(name)
    return found


def _printed(seen: Sequence[Seen], language: str) -> dict[str, list[dict[str, object]]]:
    """What else the page printed that a lexicon names: headings, charges, titles, traps."""
    printed: dict[str, list[dict[str, object]]] = {kind: [] for kind in REPORTED.values()}
    for one in seen:
        for entry in one.names(language):
            group, _, name = entry.partition(".")
            if group in REPORTED:
                printed[REPORTED[group]].append(_heading(name, one))
    return printed


def _heading(name: str, one: Seen) -> dict[str, object]:
    return {
        "entry": name,
        "label": one.pair.label,
        "page": one.pair.page,
        "zone": one.pair.label_zone.name,
        "x": one.pair.label_bbox.x0,
    }


def _worth_listing(one: Seen) -> bool:
    if one.terms:
        return False
    return one.pair.mark is Mark.COLON or one.reading.shape in STRONG


def _unmapped(one: Seen) -> dict[str, object]:
    return {"label": one.pair.label, **_where(one)}


def _where(one: Seen) -> dict[str, object]:
    box = one.pair.value_bbox
    return {
        "value": one.pair.value,
        "shape": " ".join((one.reading.shape.value, *one.reading.details)),
        "how": one.pair.how.value,
        "page": one.pair.page,
        "zone": one.pair.zone.name,
        "bbox": [box.x0, box.y0, box.x1, box.y1],
    }
