"""What the pipeline looked at, whether or not anything was wrong with it (ENGINE_SPEC §6).

A `Finding` says what is wrong; a `Check` says what was checked. The two are not the
same record because their absences are not the same: an invoice whose arithmetic was
never checked and one whose arithmetic checked out both have no finding about it, and
only the checks tell them apart.

`passed` is `None` for a check that did not apply — an operand the document does not
carry, a rule this vendor is exempt from, a question that is not asked of this kind of
document. That is a third answer, not a failure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class Check:
    """One rule, the fields it is about, and what it found when it was applied."""

    code: str
    passed: bool | None
    fields: tuple[str, ...] = ()
    detail: str = ""

    @property
    def applied(self) -> bool:
        return self.passed is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "passed": self.passed,
            "fields": list(self.fields),
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Check:
        passed = data["passed"]
        return cls(
            code=str(data["code"]),
            passed=None if passed is None else bool(passed),
            fields=tuple(str(name) for name in cast(Sequence[object], data.get("fields", ()))),
            detail=str(data.get("detail", "")),
        )
