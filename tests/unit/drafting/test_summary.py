"""The page `profile draft` prints: what it wrote, what it read, what is left to do."""

from __future__ import annotations

from pathlib import Path

from invoice_extractor.document.model import BBox, Zone
from invoice_extractor.drafting.evidence import Evidence, Placed
from invoice_extractor.drafting.pairs import How, Mark, Pair
from invoice_extractor.drafting.seen import Seen
from invoice_extractor.drafting.shapes import Reading, Shape
from invoice_extractor.drafting.summary import render
from invoice_extractor.drafting.trace import Trace, missing
from invoice_extractor.drafting.writer import Written

BOX = BBox(0.0, 0.0, 1.0, 1.0)


def placed() -> Placed:
    pair = Pair("Rechnungs-Nr.", "RG-1", 1, Zone(1, 3), Zone(1, 2), BOX, BOX, How.RIGHT, Mark.COLON)
    return Placed("invoice_number", Seen(pair, Reading(Shape.IDENTIFIER), ()))


def written(defaults: Path | None = None, lexicon: Path | None = None) -> Written:
    root = Path("vendors")
    return Written(
        root / "profiles" / "de-DE.json", root / "drafts" / "de-DE.json", defaults, lexicon
    )


def test_the_summary_names_what_was_written_and_what_was_supplied() -> None:
    read = Evidence("a.pdf", "de-DE", "de", (("de", 12), ("nl", 2)), (), (), (), ())
    printed = render(
        read, written(Path("vendors/profiles/_defaults.json"), Path("vendors/lexicon/de.json"))
    )
    assert printed.startswith("Drafted de-DE from a.pdf")
    assert (
        "  defaults   vendors/profiles/_defaults.json  (copied: the directory had none)" in printed
    )
    assert "  lexicon    vendors/lexicon/de.json" in printed
    assert "language   de  (lexicon entries matched: de 12, nl 2)" in printed


def test_each_setting_is_one_line_with_its_value_and_its_reason() -> None:
    read = Evidence(
        "a.pdf", "de-DE", "de", (), (Trace("country", "DE", "the id says so"),), (), ("iban",), ()
    )
    printed = render(read, written())
    assert "  country                          DE                       the id says so" in printed
    assert "fields     0 labels placed: none" in printed
    assert "missing    iban" in printed


def test_placeholders_are_the_first_thing_to_do_next() -> None:
    read = Evidence(
        "a.pdf",
        "draft",
        "und",
        (),
        (missing("country", "a code"),),
        (placed(),),
        ("invoice_number",),
        (),
    )
    printed = render(read, written())
    assert "Fill in: country — the loader refuses the profile until you do." in printed
    assert "fields     1 labels placed: invoice_number" in printed
    assert "missing    none" in printed
    assert "profile lint draft --profiles vendors/profiles" in printed


def test_nothing_to_fill_in_goes_straight_to_the_next_commands() -> None:
    read = Evidence("a.pdf", "de-DE", "de", (), (), (), (), ())
    assert "Fill in" not in render(read, written())
    assert "lexicon entries matched: none" in render(read, written())
