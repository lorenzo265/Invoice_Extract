"""The closed vocabulary of template families.

`classic` is the maximal one — every block a European invoice can have. The others are
derived by switching blocks off or restyling them, never written from scratch, so one
renderer and one truth builder stay honest for all of them.
"""

from __future__ import annotations

from enum import Enum


class Family(Enum):
    CLASSIC = "classic"
    TABULAR = "tabular"
    STACKED = "stacked"
    SAAS = "saas"
    MINIMAL = "minimal"


FAMILY_NAMES: tuple[str, ...] = tuple(family.value for family in Family)
