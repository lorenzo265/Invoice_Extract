"""How candidates are ordered when a field found more than one. Lower sorts first.

A spec lists rankers in the order they break ties, so `(valid_first, zone_priority,
closest_to_label, top_most)` reads as "a value that parsed, in the expected zone, nearest
the label that introduced it, highest on the page".
"""

from __future__ import annotations

from invoice_extractor.extraction.candidate import Evaluated
from invoice_extractor.profile.schema import FieldProfile

MISSING_ZONE = 1.0


def valid_first(evaluated: Evaluated, field_profile: FieldProfile) -> float:
    return 0.0 if evaluated.valid else 1.0


def zone_priority(evaluated: Evaluated, field_profile: FieldProfile) -> float:
    """Position in the profile's `zones` list — anywhere else sorts after all of them."""
    zones = field_profile.zones
    zone = evaluated.candidate.zone
    return float(zones.index(zone)) if zone in zones else float(len(zones))


def closest_to_label(evaluated: Evaluated, field_profile: FieldProfile) -> float:
    """The gap between a value and the label that introduced it, in points, either way."""
    return evaluated.candidate.label_distance


def top_most(evaluated: Evaluated, field_profile: FieldProfile) -> float:
    return evaluated.candidate.evidence.bbox.y0


def best_match(evaluated: Evaluated, field_profile: FieldProfile) -> float:
    """An exact hit on an expected value before a near one (`anchor_value`'s ratio)."""
    return MISSING_ZONE - evaluated.candidate.match_ratio
