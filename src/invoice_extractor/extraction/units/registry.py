"""The names a spec may use, and nothing else.

A spec is a declaration, so what it names has to be a closed vocabulary — otherwise
"declared, not coded" is only true until someone passes a lambda. Every unit this
package offers is registered here under one name; the engine looks a name up and refuses
one it does not know, and `tests/test_unit_registry.py` holds the two directions of the
rule: every registered unit is named by some spec, and every name a spec uses is
registered.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from invoice_extractor.document.model import TextLine
from invoice_extractor.extraction.candidate import Candidate, Normalizer, Ranker, Validator
from invoice_extractor.extraction.units import filters, normalizers, rankers, strategies, validators
from invoice_extractor.profile.schema import FieldProfile, Profile

# Every strategy reads the same two things: the lines of a document, and the terms this
# field is looking for — its labels, its patterns, or the values the profile expects.
Collect = Callable[[Sequence[TextLine], Sequence[str]], list[Candidate]]
Filter = Callable[[Sequence[Candidate], FieldProfile, Profile], list[Candidate]]

# The three ways a vendor prints a label and its value, in the order a tie is broken.
LABEL_STRATEGIES: tuple[str, ...] = ("label_right", "label_beside", "label_below")

STRATEGIES: Mapping[str, Collect] = {
    "label_right": strategies.label_right,
    "label_beside": strategies.label_beside,
    "label_below": strategies.label_below,
    "label_pattern": strategies.label_pattern,
    "anchor_value": strategies.anchor_value,
}

FILTERS: Mapping[str, Filter] = {
    "not_a_trap": filters.not_a_trap,
    "looks_numeric": filters.looks_numeric,
}

NORMALIZERS: Mapping[str, Normalizer] = {
    "strip_label": normalizers.strip_label,
    "parse_date": normalizers.parse_date,
    "parse_money": normalizers.parse_money,
    "parse_percent": normalizers.parse_percent,
    "upper_alnum": normalizers.upper_alnum,
}

VALIDATORS: Mapping[str, Validator] = {
    "is_date": validators.is_date,
    "is_money": validators.is_money,
    "is_percent": validators.is_percent,
    "is_identifier": validators.is_identifier,
    "is_vat_id": validators.is_vat_id,
}

RANKERS: Mapping[str, Ranker] = {
    "valid_first": rankers.valid_first,
    "zone_priority": rankers.zone_priority,
    "closest_to_label": rankers.closest_to_label,
    "top_most": rankers.top_most,
    "last_page_first": rankers.last_page_first,
    "best_match": rankers.best_match,
}

REGISTERED: Mapping[str, Mapping[str, object]] = {
    "strategy": dict(STRATEGIES),
    "filter": dict(FILTERS),
    "normalizer": dict(NORMALIZERS),
    "validator": dict(VALIDATORS),
    "ranker": dict(RANKERS),
}
