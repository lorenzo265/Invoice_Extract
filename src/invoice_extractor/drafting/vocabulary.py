"""Every label every lexicon knows, looked up in one place, whatever the language.

A profile names its language and borrows that one lexicon. A draft has no language yet:
the page is what will tell it. So the draft reads every lexicon in the directory at once
and asks, for each label the page prints, which lexicons spell a label exactly that way
and what they call it. The lexicon that answers most often is the page's language, and
each answer is the field the label introduces.

Matching is exact after folding — case and punctuation dropped, letters and digits kept
in any script — never a substring. `IBAN` inside `Citibank` is the false positive the
detector's substring match is known to carry; a draft written from one would carry it
into every profile it produced.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

# The synonym maps a lexicon holds, and the plain lists beside them. `months` and
# `month_abbreviations` are read too, for the spelled dates; `amount_in_words` and the
# sentences are not — nothing on a page is looked up against a sentence.
MAPS = (
    "document_titles",
    "header_labels",
    "totals_labels",
    "charge_labels",
    "column_headers",
    "vat_summary_headers",
    "party_headings",
    "trap_labels",
    "carry_forward",
)
LISTS = ("address_placeholders", "section_headings", "copy_stamps")
MONTH_LISTS = ("months", "month_abbreviations")


@dataclass(frozen=True, slots=True)
class Term:
    """One spelling of one entry of one lexicon: `de: header_labels.invoice_number`."""

    language: str
    group: str
    key: str
    label: str

    @property
    def name(self) -> str:
        """`header_labels.invoice_number`, or the list's own name where there is no key."""
        return f"{self.group}.{self.key}" if self.key else self.group


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """Every term of every lexicon, keyed by its folded spelling."""

    terms: Mapping[str, tuple[Term, ...]]
    months: frozenset[str]
    languages: tuple[str, ...]

    def lookup(self, label: str) -> tuple[Term, ...]:
        """Every term spelled exactly like `label`, once folded; empty where none is."""
        return self.terms.get(fold(label), ())

    def knows(self, language: str) -> bool:
        return language in self.languages


def read_vocabulary(root: Path) -> Vocabulary:
    """Every `<language>.json` under `root`, as one vocabulary."""
    lexicons = {
        path.stem: _as_object(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(root.glob("*.json"))
    }
    return from_lexicons(lexicons)


def from_lexicons(lexicons: Mapping[str, Mapping[str, object]]) -> Vocabulary:
    """The vocabulary of lexicons already read, keyed by language."""
    terms: dict[str, list[Term]] = {}
    months: set[str] = set()
    for language, lexicon in lexicons.items():
        for term in _terms(language, lexicon):
            terms.setdefault(fold(term.label), []).append(term)
        for name in MONTH_LISTS:
            months.update(word.casefold() for word in _strings(lexicon.get(name)))
    return Vocabulary(
        terms={spelling: tuple(found) for spelling, found in terms.items()},
        months=frozenset(months),
        languages=tuple(lexicons),
    )


def elect(matched: Sequence[Term]) -> tuple[tuple[str, int], ...]:
    """Each language and how many distinct entries of it the page matched, most first."""
    entries = {(term.language, term.name) for term in matched}
    votes = Counter(language for language, _ in entries)
    return tuple(sorted(votes.items(), key=lambda vote: (-vote[1], vote[0])))


def fold(text: str) -> str:
    """Case-folded letters and digits, in any script — how two labels are compared."""
    return "".join(character for character in text.casefold() if character.isalnum())


def _terms(language: str, lexicon: Mapping[str, object]) -> list[Term]:
    found: list[Term] = []
    for group in MAPS:
        entries = lexicon.get(group)
        if isinstance(entries, dict):
            for key, labels in entries.items():
                found.extend(Term(language, group, str(key), label) for label in _strings(labels))
    for group in LISTS:
        found.extend(Term(language, group, "", label) for label in _strings(lexicon.get(group)))
    return found


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _as_object(parsed: object) -> Mapping[str, object]:
    return parsed if isinstance(parsed, dict) else {}
