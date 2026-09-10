"""The generator's one PyMuPDF module: put text on a page, and read the page back.

Everything above this file works in points and strings; only here does a page exist.
Two rules make a corpus reproducible and provable:

- **Measured, not guessed.** `width` asks the font how wide a string will be, so a
  right-aligned amount lands exactly where the layout says and a wrapped description
  breaks where it will really break.
- **Recorded, not remembered.** Every placement that carries a value is logged with the
  point it was drawn at; `read_back` finds that string in the produced PDF and returns
  the box it actually occupies. The generator never writes a bounding box it did not
  read from its own output.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import fitz

from invoice_forge.layout.spec import PageGeometry, Weight
from invoice_forge.profiles.schema import FontFamily

FONT_DIR = Path(__file__).parent.parent / "fonts"
FONT_FILES = {
    (FontFamily.SANS, Weight.REGULAR): "LiberationSans-Regular.ttf",
    (FontFamily.SANS, Weight.BOLD): "LiberationSans-Bold.ttf",
    (FontFamily.SERIF, Weight.REGULAR): "LiberationSerif-Regular.ttf",
    (FontFamily.SERIF, Weight.BOLD): "LiberationSerif-Bold.ttf",
}
FONT_NAMES = {Weight.REGULAR: "F", Weight.BOLD: "FB"}
RULE_COLOUR = (0.3, 0.3, 0.3)
BOX_COLOUR = (0.45, 0.45, 0.45)
BOX_WIDTH = 0.6
# A fixed instant, so two runs of the same seed differ in no byte at all.
FIXED_METADATA = {
    "producer": "invoice_forge",
    "creator": "invoice_forge",
    "creationDate": "D:20240101000000Z",
    "modDate": "D:20240101000000Z",
    "keywords": "",
    "subject": "",
    "author": "",
}


BBox = tuple[float, float, float, float]


class Canvas:
    """A document being drawn. One instance renders one PDF, front to back."""

    def __init__(self, geometry: PageGeometry, fonts: FontFamily) -> None:
        self.geometry = geometry
        self._document = fitz.open()
        self._files = {weight: FONT_DIR / FONT_FILES[fonts, weight] for weight in Weight}
        self._fonts = {
            weight: fitz.Font(fontfile=str(path)) for weight, path in self._files.items()
        }

    @property
    def pages(self) -> int:
        return int(self._document.page_count)

    def new_page(self) -> None:
        page = self._document.new_page(width=self.geometry.width, height=self.geometry.height)
        for weight, path in self._files.items():
            page.insert_font(fontname=FONT_NAMES[weight], fontfile=str(path))

    def width(self, text: str, size: float, weight: Weight = Weight.REGULAR) -> float:
        return float(self._fonts[weight].text_length(text, fontsize=size))

    def text(
        self, x: float, y: float, text: str, size: float, weight: Weight, page: int | None = None
    ) -> None:
        """Draw at a baseline, on the current page or on an earlier one still open.

        A page already left is still open until `save`, which is how "page 1 of 3" reaches
        page 1: the number of pages is not known until the last row has been placed.
        """
        self._page(page).insert_text(
            fitz.Point(x, y), text, fontsize=size, fontname=FONT_NAMES[weight]
        )

    def rule(self, y: float, x0: float, x1: float, width: float) -> None:
        start, end = fitz.Point(x0, y), fitz.Point(x1, y)
        self._page(None).draw_line(start, end, width=width, color=RULE_COLOUR)

    def box(self, x: float, y: float, width: float, height: float) -> None:
        """An empty rectangle where a payment QR code would be. Drawn, never an image."""
        rect = fitz.Rect(x, y, x + width, y + height)
        self._page(None).draw_rect(rect, width=BOX_WIDTH, color=BOX_COLOUR)

    def save(self, path: Path, title: str) -> None:
        self._document.set_metadata({**FIXED_METADATA, "title": title})
        self._document.save(str(path), garbage=4, deflate=True, no_new_id=True)
        self._document.close()

    def _page(self, number: int | None) -> fitz.Page:
        """Fetched by index, never held: adding a page invalidates every `Page` object."""
        if not self.pages:
            raise RuntimeError("no page has been started; call new_page() first")
        return self._document[-1 if number is None else number - 1]


def locate_all(path: Path, queries: Sequence[tuple[int, str]]) -> tuple[tuple[BBox, ...], ...]:
    """For each `(page, text)` asked for, every box that string occupies on that page.

    A string printed twice on one page comes back twice, in reading order; the caller
    decides which occurrence belongs to which placement by comparing against the point it
    drew at. One open, however many queries, because a corpus asks thousands of them.
    """
    document = fitz.open(str(path))
    try:
        return tuple(
            tuple(_rounded(rect) for rect in document[page - 1].search_for(text))
            for page, text in queries
        )
    finally:
        document.close()


def page_image(path: Path, page: int, dpi: int) -> bytes:
    """One page as PNG bytes, for the golden fixtures. Identical input, identical bytes."""
    document = fitz.open(str(path))
    try:
        pixmap = document[page - 1].get_pixmap(dpi=dpi)
        return bytes(pixmap.tobytes("png"))
    finally:
        document.close()


def _rounded(rect: fitz.Rect) -> BBox:
    """Two decimals, the same precision the extractor's reader rounds its boxes to."""
    return (round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2))
