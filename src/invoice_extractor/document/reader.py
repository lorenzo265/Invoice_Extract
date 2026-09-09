"""The vocabulary every other package reads a document in: boxes, zones, lines.

Nothing here knows a PDF library exists. `PyMuPDFReader` is one implementation of
`DocumentReader`; a fake built in a test is another, and extraction cannot tell them
apart.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol


class Zone(Enum):
    """Where on the page a line sits, on a 3x3 grid of the page's own thirds."""

    TOP_LEFT = auto()
    TOP_CENTER = auto()
    TOP_RIGHT = auto()
    MIDDLE_LEFT = auto()
    MIDDLE_CENTER = auto()
    MIDDLE_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_CENTER = auto()
    BOTTOM_RIGHT = auto()


@dataclass(frozen=True, slots=True)
class BBox:
    """A rectangle on a page, in PDF points, with `y` growing downward."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2


@dataclass(frozen=True, slots=True)
class TextLine:
    """One line of text on one page, already classified into a zone. `page` is 1-indexed."""

    page: int
    text: str
    bbox: BBox
    zone: Zone


class DocumentReader(Protocol):
    """All extraction needs of a document: how many pages it has, and the lines on one."""

    @property
    def page_count(self) -> int: ...

    def lines(self, page: int) -> Sequence[TextLine]: ...
