"""`profile draft`: a vendor profile written from one document, for a person to correct.

The inverse of `inspect`. `inspect` shows the page so a person can write a profile;
this writes the profile the page suggests, with the evidence for every key beside it,
so the person starts from a draft rather than from a blank file. It is a drafting tool
and nothing else: the engine never runs it, and a document no profile matches still
comes back `profile_not_detected` (ADR-0008). A draft's mistakes are a person's to
catch before the profile reads anything — which is why each guess carries its reason.

What a draft reads without a language: where each label sits, what shape each value
has, who the supplier is, how numbers and dates are written. What it reads with the
lexicons: which field each label names, and which language the page is in. On a page
in a language no lexicon covers, the second half is empty and the first is the whole
draft, plus a skeleton lexicon and the list of labels to put in it.
"""

from __future__ import annotations

from dataclasses import dataclass

from invoice_extractor.document.model import Document
from invoice_extractor.drafting import assemble, conventions, identity, seen
from invoice_extractor.drafting.evidence import Evidence, evidence
from invoice_extractor.drafting.shapes import KnownId
from invoice_extractor.drafting.vocabulary import Vocabulary, read_vocabulary
from invoice_extractor.profile.loader import DEFAULTS_ID, lexicons_beside, read_profile_json
from invoice_extractor.profile.registry import ProfileRegistry

FALLBACK_ID = "draft"


@dataclass(frozen=True, slots=True)
class Draft:
    """A profile, the evidence it was written from, and the vocabulary it was read with."""

    profile: dict[str, object]
    evidence: Evidence
    vocabulary: Vocabulary

    @property
    def id(self) -> str:
        return str(self.profile["id"])


def draft(
    document: Document,
    registry: ProfileRegistry,
    profile_id: str | None = None,
    language: str | None = None,
) -> Draft:
    """One document, read against the registry's lexicons and vendors, as a draft profile."""
    vocabulary = read_vocabulary(lexicons_beside(registry.root))
    observed = seen.observe(document, vocabulary, known_ids(registry))
    counted = seen.votes(document, observed, vocabulary)
    chosen, _ = seen.language_of(counted, language, vocabulary)
    settings = _settings(document, observed, registry)
    default_fields = assemble.default_field_names(
        read_profile_json(registry.root / f"{DEFAULTS_ID}.json")
    )
    name = profile_id or _named(chosen, settings.identity.country)
    return Draft(
        profile=assemble.assemble(name, chosen, settings, observed, default_fields),
        evidence=evidence(
            document.source_path, name, chosen, counted, settings, observed, default_fields
        ),
        vocabulary=vocabulary,
    )


def known_ids(registry: ProfileRegistry) -> tuple[KnownId, ...]:
    """The shape of a VAT id in every country a registered profile describes, once each."""
    found: dict[str, KnownId] = {}
    for profile in registry.all():
        found.setdefault(
            profile.country, KnownId(profile.country, profile.vat.id_prefix, profile.vat.id_pattern)
        )
    return tuple(found.values())


def _settings(
    document: Document, observed: tuple[seen.Seen, ...], registry: ProfileRegistry
) -> assemble.Settings:
    numbers = conventions.number_format(observed)
    known_codes = {code for profile in registry.all() for code in profile.currencies}
    words = {word for text in document.text() for word in text.split()}
    return assemble.Settings(
        identity=identity.identity(document, observed, known_ids(registry)),
        number_format=numbers,
        date_formats=conventions.date_formats(observed),
        currencies=conventions.currencies(observed, words, known_codes),
        rates=conventions.rates(observed, numbers.decimal),
    )


def _named(language: str, country: str) -> str:
    """`de-AT` where both halves are known; the fallback name where either is not."""
    if language == seen.UNDETERMINED or country == identity.UNKNOWN_COUNTRY:
        return FALLBACK_ID
    return f"{language}-{country}"
