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

import pymupdf

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
# How far outside its box a word may sit and still belong to it, in points.
WORD_TOLERANCE = 0.5
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
        self._document = pymupdf.open()
        self._files = {weight: FONT_DIR / FONT_FILES[fonts, weight] for weight in Weight}
        self._fonts = {
            weight: pymupdf.Font(fontfile=str(path)) for weight, path in self._files.items()
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
            pymupdf.Point(x, y), text, fontsize=size, fontname=FONT_NAMES[weight]
        )

    def line(self, x0: float, y0: float, x1: float, y1: float, width: float) -> None:
        start, end = pymupdf.Point(x0, y0), pymupdf.Point(x1, y1)
        self._page(None).draw_line(start, end, width=width, color=RULE_COLOUR)

    def rule(self, y: float, x0: float, x1: float, width: float) -> None:
        self.line(x0, y, x1, y, width)

    def box(self, x: float, y: float, width: float, height: float) -> None:
        """An empty rectangle where a payment QR code would be. Drawn, never an image."""
        rect = pymupdf.Rect(x, y, x + width, y + height)
        self._page(None).draw_rect(rect, width=BOX_WIDTH, color=BOX_COLOUR)

    def save(self, path: Path, title: str) -> None:
        """Subset the fonts, fix the metadata, and write. Same input, same bytes.

        Without subsetting every document carries both faces whole — half a megabyte of
        font for a page that uses two hundred glyphs, and the same half megabyte in every
        document of a corpus. Subsetting is deterministic and leaves the text layer intact,
        which the golden images and `forge verify` both prove.
        """
        self._document.subset_fonts()
        self._document.set_metadata({**FIXED_METADATA, "title": title})
        self._document.save(str(path), garbage=4, deflate=True, no_new_id=True)
        self._document.close()

    def _page(self, number: int | None) -> pymupdf.Page:
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
    document = pymupdf.open(str(path))
    try:
        return tuple(
            tuple(_rounded(rect) for rect in document[page - 1].search_for(text))
            for page, text in queries
        )
    finally:
        document.close()


def text_in(path: Path, boxes: Sequence[tuple[int, BBox]]) -> tuple[str, ...]:
    """The text each box holds, read out of a finished PDF, in the order asked for.

    This is the other direction from `locate_all`, and the one `forge verify` needs: not
    "where is this string" but "what does this box actually say". A truth entry claiming a
    box is proved by reading that box, never by trusting the renderer that wrote it.

    Each page's words are extracted once and the boxes are answered from that, rather than
    asking the page per box: a corpus asks hundreds of boxes per document, and re-reading
    the page for each one costs seconds where this costs milliseconds.
    """
    document = pymupdf.open(str(path))
    try:
        pages = {page: _words(document, page) for page in {number for number, _ in boxes}}
        return tuple(_within(pages[page], box) for page, box in boxes)
    finally:
        document.close()


def _words(
    document: pymupdf.Document, page: int
) -> tuple[tuple[float, float, float, float, str], ...]:
    """Every word on a page with its box, converted out of PyMuPDF's tuples at once."""
    return tuple(
        (float(word[0]), float(word[1]), float(word[2]), float(word[3]), str(word[4]))
        for word in document[page - 1].get_text("words")
    )


def _within(words: Sequence[tuple[float, float, float, float, str]], box: BBox) -> str:
    """The words whose centre falls inside the box, in reading order, joined by spaces.

    A glyph's own box can overhang the line's by a hair, so a word belongs to the box its
    middle is in rather than the one that encloses it completely.
    """
    x0, y0, x1, y1 = box
    return " ".join(
        word[4]
        for word in words
        if x0 - WORD_TOLERANCE <= (word[0] + word[2]) / 2 <= x1 + WORD_TOLERANCE
        and y0 - WORD_TOLERANCE <= (word[1] + word[3]) / 2 <= y1 + WORD_TOLERANCE
    )


def pages_in(path: Path) -> int:
    document = pymupdf.open(str(path))
    try:
        return int(document.page_count)
    finally:
        document.close()


def page_image(path: Path, page: int, dpi: int) -> bytes:
    """One page as PNG bytes, for the golden fixtures. Identical input, identical bytes."""
    document = pymupdf.open(str(path))
    try:
        pixmap = document[page - 1].get_pixmap(dpi=dpi)
        return bytes(pixmap.tobytes("png"))
    finally:
        document.close()


def _rounded(rect: pymupdf.Rect) -> BBox:
    """Two decimals, the same precision the extractor's reader rounds its boxes to."""
    return (round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2))
