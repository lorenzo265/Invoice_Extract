"""One merge function and one rule table, for every layer a profile is assembled from.

`profiles/_defaults.json` is the structure every vendor shares; `profiles/<id>.json` is
what this vendor does differently; a matching `variants[]` overlay is what this document
does differently again. All three are merged the same way, so a reader who understands
one layer understands all of them.

A key under `rules.append` accumulates across layers — a vendor that adds a label for
the invoice number keeps the ones the defaults already knew. Every other key replaces,
because a vendor that declares its own zones means those zones and not more.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Label vocabularies grow layer by layer; a later layer adds synonyms rather than
# replacing the ones the defaults already list. Paths are dotted, with `*` standing for
# any single key, so one rule covers every field or every column of a table.
APPEND_PATHS: tuple[str, ...] = (
    "fields.*.labels",
    "fields.*.exclude_labels",
    "parties.*.labels",
    "parties.*.stop_labels",
    "parties.*.placeholders",
    "line_items.columns.*",
    "line_items.stop_labels",
    "line_items.carry_forward_labels",
    "vat_summary.columns.*",
    "vat_summary.stop_labels",
    "totals.components.*.labels",
    "document_types.invoice_titles",
    "document_types.credit_note_titles",
    "document_types.credit_reference_labels",
    "noise.ignore_labels",
    # A vendor's own extras are added to the ones every vendor may print, not swapped for
    # them: `custom_fields` in a profile says what this vendor usually prints, and the
    # defaults say what any of them may print when a document happens to carry it.
    "custom_fields",
)


@dataclass(frozen=True, slots=True)
class MergeRules:
    """Which dotted key paths append instead of replacing."""

    append: tuple[str, ...]

    def appends(self, path: str) -> bool:
        return any(_matches(pattern, path) for pattern in self.append)


PROFILE_RULES = MergeRules(append=APPEND_PATHS)


def merge(
    base: Mapping[str, object], overlay: Mapping[str, object], rules: MergeRules
) -> dict[str, object]:
    """`base` with `overlay` laid over it, appending where the rules say to append."""
    return _merge_mapping(base, overlay, rules, "")


def _merge_mapping(
    base: Mapping[str, object], overlay: Mapping[str, object], rules: MergeRules, path: str
) -> dict[str, object]:
    merged: dict[str, object] = dict(base)
    for key, value in overlay.items():
        merged[key] = _merge_value(base.get(key), value, rules, _join(path, key))
    return merged


def _merge_value(base: object, overlay: object, rules: MergeRules, path: str) -> object:
    if isinstance(base, Mapping) and isinstance(overlay, Mapping):
        return _merge_mapping(base, overlay, rules, path)
    if rules.appends(path) and isinstance(base, list) and isinstance(overlay, list):
        return _appended(base, overlay)
    return overlay


def _appended(base: Sequence[object], overlay: Sequence[object]) -> list[object]:
    """Both lists, in order, with anything already said left where it first appeared."""
    kept: list[object] = []
    for entry in (*base, *overlay):
        if entry not in kept:
            kept.append(entry)
    return kept


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _matches(pattern: str, path: str) -> bool:
    """A dotted pattern matches a dotted path segment by segment; `*` matches any one."""
    expected = pattern.split(".")
    actual = path.split(".")
    if len(expected) != len(actual):
        return False
    return all(part in ("*", seen) for part, seen in zip(expected, actual, strict=True))
