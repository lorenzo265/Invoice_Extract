"""The rendered page, pixel for pixel, against the image committed for it.

FORGE_SPEC §5.3 asks for exactly this: a golden image per profile, compared exactly. It
is the only test that notices a glyph moving two points to the left — everything else
checks that values are where the truth says they are, not that the page still looks the
way it was reviewed. When it fails, look at the new image; if the change is wanted, run
`python scripts/make_forge_goldens.py` and commit what it writes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from make_forge_goldens import GOLDEN_DPI, GOLDEN_PAGE, golden_path
from rendering import for_each_profile, rendered

from invoice_forge.layout.classic import A4
from invoice_forge.lexicon.loader import bundled_lexicon_ids, load_lexicon
from invoice_forge.profiles.schema import FontFamily
from invoice_forge.render.pdf import Canvas, locate_all, page_image
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.text import wrap

REGENERATE = "python scripts/make_forge_goldens.py"
SAMPLE_SIZE = 11.0
SAMPLE_TOP = 100.0


@for_each_profile
def test_a_golden_image_is_committed_for_every_profile(profile_id: str) -> None:
    path = golden_path(profile_id)
    assert path.is_file(), f"no golden image for {profile_id}; run {REGENERATE}"
    assert path.stat().st_size > 0


@for_each_profile
def test_the_page_renders_exactly_as_it_was_reviewed(profile_id: str) -> None:
    document = rendered(profile_id)
    expected = golden_path(profile_id).read_bytes()
    image = page_image(document.pdf, GOLDEN_PAGE, GOLDEN_DPI)
    assert image == expected, (
        f"the rendered page differs from the committed image; if wanted, run {REGENERATE}"
    )


@pytest.mark.parametrize("language", bundled_lexicon_ids())
@pytest.mark.parametrize("fonts", list(FontFamily))
def test_every_language_prints_its_own_hard_characters(
    language: str, fonts: FontFamily, tmp_path: Path
) -> None:
    """A glyph a font does not have is a blank on the page, and the truth would still say
    it is there. So each lexicon's diacritic string is drawn in both faces and read back."""
    sample = load_lexicon(language).diacritics
    path = tmp_path / f"{language}_{fonts.value}.pdf"
    _draw_sample(sample, fonts, path)
    lines = wrap(sample, A4.right - A4.left, lambda text: len(text) * SAMPLE_SIZE)
    located = locate_all(path, [(1, line) for line in lines])
    for line, hits in zip(lines, located, strict=True):
        assert hits, f"{fonts.value} cannot print {line!r} in {language}"


def _draw_sample(sample: str, fonts: FontFamily, path: Path) -> None:
    sheet = Sheet(A4, fonts)
    sheet.new_page()
    lines = wrap(sample, A4.right - A4.left, lambda text: len(text) * SAMPLE_SIZE)
    for index, line in enumerate(lines):
        sheet.draw(A4.left, SAMPLE_TOP + index * SAMPLE_SIZE * 2, line, SAMPLE_SIZE)
    sheet.save(path, "diacritics")


def test_a_canvas_refuses_to_draw_before_a_page_is_started() -> None:
    canvas = Canvas(A4, FontFamily.SANS)
    with pytest.raises(RuntimeError, match="no page has been started"):
        canvas.rule(10.0, 0.0, 10.0, 1.0)
