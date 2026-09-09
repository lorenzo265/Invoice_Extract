"""What the pipeline reports when a document disagrees with itself.

A `Finding` is a value, never an exception: one invoice whose printed total is a cent
out does not abort the batch, it grows the result's `findings` by one entry.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto


class Severity(Enum):
    """How much a finding matters. A caller may log ERROR, keep WARNING, drop INFO."""

    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass(frozen=True, slots=True)
class Finding:
    """One named disagreement, and the field it is about when it is about one."""

    severity: Severity
    code: str
    message: str
    field: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity.name,
            "code": self.code,
            "message": self.message,
            "field": self.field,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Finding:
        about = data["field"]
        return cls(
            severity=Severity[str(data["severity"])],
            code=str(data["code"]),
            message=str(data["message"]),
            field=None if about is None else str(about),
        )
