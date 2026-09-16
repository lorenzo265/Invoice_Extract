"""One page, observed: every pair, with what its value looks like and what its label means.

The three stages a draft is made of — pairs from geometry, shapes from characters, terms
from the lexicons — meet here, once, in a record every later module reads. A `Seen` with
no terms is a label no lexicon spells, which on a page in a new language is all of them;
its shape and its place are still evidence, and the draft reports them as such.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from invoice_extractor.document.model import Document
from invoice_extractor.drafting.pairs import SEPARATOR, Pair, harvest
from invoice_extractor.drafting.shapes import KnownId, Reading, read
from invoice_extractor.drafting.vocabulary import Term, Vocabulary, elect

# How many distinct entries of one lexicon a page has to print before the page is read as
# being in that language. Two is a coincidence — `Total` is a word in several — and
# three is a vendor's header block.
MIN_VOTES = 3
# ISO 639-2 for *undetermined*: the language a draft names when no lexicon spoke.
UNDETERMINED = "und"


@dataclass(frozen=True, slots=True)
class Seen:
    """A pair, the shape of its value, and the lexicon entries its label is spelled like."""

    pair: Pair
    reading: Reading
    terms: tuple[Term, ...]

    def names(self, language: str) -> tuple[str, ...]:
        """The entries this label names in `language`, or in any language where none does.

        `Datum` is the invoice date in German and in Dutch; where the page is German the
        German entry is the one meant, and the same key either way. Where the label is
        in no entry of the page's language at all — an English line on a German invoice
        — whatever language spells it is what the draft has.
        """
        own = tuple(dict.fromkeys(term.name for term in self.terms if term.language == language))
        return own or tuple(dict.fromkeys(term.name for term in self.terms))


def observe(
    document: Document, vocabulary: Vocabulary, known_ids: Sequence[KnownId]
) -> tuple[Seen, ...]:
    """Every pair on the page, read for its shape and looked up in every lexicon."""
    return tuple(
        Seen(
            pair=pair,
            reading=read(pair.value, vocabulary.months, known_ids),
            terms=vocabulary.lookup(pair.label),
        )
        for pair in harvest(document)
    )


def votes(
    document: Document, seen: Sequence[Seen], vocabulary: Vocabulary
) -> tuple[tuple[str, int], ...]:
    """Each language and how many of its entries the page prints, most first.

    Every whole line is looked up as well as every pair's label: a title such as
    `RECHNUNG` stands alone at the top of the page and says the language as clearly as
    any label does, and never becomes a pair.
    """
    lines = [
        term
        for text in document.text()
        for term in vocabulary.lookup(text.strip().removesuffix(SEPARATOR))
    ]
    return elect([*lines, *(term for one in seen for term in one.terms)])


def language_of(
    counted: Sequence[tuple[str, int]], declared: str | None, vocabulary: Vocabulary
) -> tuple[str, bool]:
    """The language the profile will name, and whether no lexicon speaks it yet.

    A language the person declared wins. Otherwise the most-voted lexicon, where it
    cleared `MIN_VOTES`; otherwise `und` — ISO 639-2 for *undetermined* — and a skeleton
    lexicon to be filled in, because a draft that invented a language would be wrong in
    a way a placeholder cannot be.
    """
    if declared is not None:
        return declared, not vocabulary.knows(declared)
    if counted and counted[0][1] >= MIN_VOTES:
        return counted[0][0], False
    return UNDETERMINED, True
