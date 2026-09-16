"""Who the invoice is from and who it is to, as the page prints them.

A party is a block, not a field: a heading, a name, the address under it, and sometimes a
VAT id. What makes it worth a record of its own is that a vendor may print three of them
and defer two — `same as billing address` is a party that names no address, and saying so
is different from failing to read one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from invoice_extractor.domain.evidence import Evidence

# The parties a document may carry, in the order a report prints them.
PARTY_NAMES: tuple[str, ...] = ("supplier", "bill_to", "ship_to", "mail_to")


@dataclass(frozen=True, slots=True)
class Party:
    """One party block: its name, its address lines, its VAT id, and where each was read."""

    name: str | None = None
    lines: tuple[str, ...] = ()
    vat_id: str | None = None
    placeholder: bool = False
    evidence: tuple[Evidence, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "lines": list(self.lines),
            "vat_id": self.vat_id,
            "placeholder": self.placeholder,
            "evidence": [found.to_dict() for found in self.evidence],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Party:
        name, vat_id = data.get("name"), data.get("vat_id")
        return cls(
            name=None if name is None else str(name),
            lines=tuple(str(line) for line in _sequence(data, "lines")),
            vat_id=None if vat_id is None else str(vat_id),
            placeholder=bool(data.get("placeholder", False)),
            evidence=tuple(
                Evidence.from_dict(cast(Mapping[str, object], entry))
                for entry in _sequence(data, "evidence")
            ),
        )


def _sequence(data: Mapping[str, object], key: str) -> Sequence[object]:
    found = data.get(key)
    return cast(Sequence[object], found if isinstance(found, list) else ())
