"""`inspect`: the page as the engine reads it, for the moment before a vendor has a profile.

Everything here is built in memory rather than read off a PDF, because what the report
has to get right is the three cases a person writing a profile actually meets: a vendor
that matches, one that does not, and a page the reader found no anchors on.
"""

from __future__ import annotations

from conftest import make_document
from invoice_extractor.document.model import Anchors, Document, Page
from invoice_extractor.output.inspection import render
from invoice_extractor.profile.detect import PROFILE_THRESHOLD, ProfileScore

PARTS = {"supplier": 0.0, "vat_id": 0.0, "labels": 0.2, "currency": 1.0}


def document() -> Document:
    return make_document(
        [
            (1, "Invoice Number: INV-1", 360.0, 60.0, 545.0, 74.0),
            (1, "Total Due: 120.00", 360.0, 700.0, 545.0, 714.0),
        ]
    )


def test_every_line_is_printed_with_the_zone_and_the_box_a_profile_is_written_against() -> None:
    printed = render(document(), ())
    assert "Invoice Number: INV-1" in printed
    assert "r1c3" in printed or "r1c2" in printed, "the zone a profile would declare"
    assert "360.0" in printed, "and the box it was drawn in"
    assert "PAGE 1" in printed


def test_a_vendor_that_clears_the_threshold_is_reported_as_matching() -> None:
    scored = ProfileScore(profile_id="xx-XX", score=0.9, parts=PARTS)
    printed = render(document(), (scored,))
    assert "xx-XX matches" in printed
    assert f"{PROFILE_THRESHOLD:.2f}" in printed


def test_a_vendor_that_falls_short_is_told_what_scored_nothing() -> None:
    """The report a person writing a profile needs: which part of the score is missing."""
    scored = ProfileScore(profile_id="xx-XX", score=0.12, parts=PARTS)
    printed = render(document(), (scored,))
    assert "No profile matches" in printed
    assert "profile_not_detected" in printed
    assert "Nothing scored for: supplier, vat_id" in printed


def test_a_registry_with_no_vendors_says_so_rather_than_printing_an_empty_table() -> None:
    assert "No profile was scored" in render(document(), ())


def test_a_page_the_reader_found_no_anchors_on_says_so() -> None:
    bare = Document(
        pages=(
            Page(
                number=1,
                width=595.0,
                height=842.0,
                lines=(),
                anchors=Anchors(
                    logo_bottom=None,
                    table_header_band=None,
                    totals_top=None,
                    vat_summary_top=None,
                ),
            ),
        ),
        source_path="bare.pdf",
    )
    assert "anchor   none found" in render(bare, ())


def test_a_long_line_is_printed_whole_rather_than_cut() -> None:
    """The bank line carries the IBAN after a name and an address, and it is the point.

    `inspect` exists so a profile can be written against what the page says. A value cut
    to fit a column is a value the person cannot read, and the longest lines on an
    invoice — bank details, legal sentences, wrapped descriptions — are where the
    interesting ones hide.
    """
    bank = "Bankverbindung: Citibank, Wien Konto:1851-055, BLZ: 18140 - IBAN AT121234567890123456"
    printed = render(make_document([(1, bank, 128.0, 772.0, 466.0, 789.0)]), ())
    assert bank in printed, "the whole line, not a prefix of it"
    assert "…" not in printed, "and nothing marked as cut"
