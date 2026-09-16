"""The label vocabulary a profile borrows from its language.

A vendor's words for "invoice number" are its language's words, and the generator prints
them from `lexicon/<language>.json`. Repeating those lists inside every profile would be
sixteen languages copied into twenty files, drifting apart on the first correction, so a
profile references them instead: `"@header_labels.invoice_number"` in a `labels` list
expands to every synonym the language offers, and a plain string beside it is a label
only this vendor prints.

The reference is resolved here, once, while the profile is being loaded. Nothing
downstream knows a lexicon exists.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from invoice_extractor import bundled
from invoice_extractor.profile.schema import ProfileError

LEXICON_ROOT = bundled.LEXICONS
REFERENCE = "@"


def read_lexicon(language: str, root: Path = LEXICON_ROOT) -> Mapping[str, object]:
    """The language's lexicon as JSON. Raises `ProfileError` when it is missing or broken."""
    path = root / f"{language}.json"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        raise ProfileError(f"lexicon {language} is not readable at {path}") from unreadable
    except json.JSONDecodeError as invalid:
        raise ProfileError(f"lexicon {language} is not valid JSON: {invalid.msg}") from invalid
    if not isinstance(parsed, dict):
        raise ProfileError(f"lexicon {language} must be an object")
    return parsed


def expand(entries: Sequence[str], lexicon: Mapping[str, object], path: str) -> tuple[str, ...]:
    """Every label in `entries`, with each `@map.key` reference replaced by its synonyms."""
    labels: list[str] = []
    for entry in entries:
        for label in _one(entry, lexicon, path):
            if label not in labels:
                labels.append(label)
    return tuple(labels)


def _one(entry: str, lexicon: Mapping[str, object], path: str) -> tuple[str, ...]:
    if not entry.startswith(REFERENCE):
        return (entry,)
    name, _, key = entry.removeprefix(REFERENCE).partition(".")
    found = lexicon.get(name)
    if found is None:
        raise ProfileError(f"{path} references {entry}, which no lexicon entry names")
    return _strings(found, key, entry, path)


def _strings(found: object, key: str, entry: str, path: str) -> tuple[str, ...]:
    """A reference names either a whole list of phrases or one key of a synonym map."""
    if not key:
        return _as_strings(found, entry, path)
    if not isinstance(found, dict) or key not in found:
        raise ProfileError(f"{path} references {entry}, which no lexicon entry names")
    return _as_strings(found[key], entry, path)


def _as_strings(found: object, entry: str, path: str) -> tuple[str, ...]:
    if not isinstance(found, list) or not all(isinstance(item, str) for item in found):
        raise ProfileError(f"{path} references {entry}, which is not a list of labels")
    return tuple(str(item) for item in found)
