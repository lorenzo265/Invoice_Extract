"""How candidates are ordered when a field found more than one. Lower sorts first.

A spec lists rankers in the order they break ties, so `(valid_first, zone_priority,
top_most)` reads as "a value that parsed, in the expected zone, highest on the page".
"""

from __future__ import annotations

from invoice_extractor.extraction.spec import Evaluated
from invoice_extractor.layout.schema import FieldLayout


def valid_first(evaluated: Evaluated, field_layout: FieldLayout) -> float:
    return 0.0 if evaluated.valid else 1.0


def zone_priority(evaluated: Evaluated, field_layout: FieldLayout) -> float:
    """Position in the layout's `zones` list — anywhere else sorts after all of them."""
    zones = field_layout.zones
    zone = evaluated.candidate.zone
    return float(zones.index(zone)) if zone in zones else float(len(zones))


def closest_to_label(evaluated: Evaluated, field_layout: FieldLayout) -> float:
    return evaluated.candidate.label_distance


def top_most(evaluated: Evaluated, field_layout: FieldLayout) -> float:
    return evaluated.candidate.evidence.bbox.y0
