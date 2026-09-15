"""What the engine sees on a page, before any profile has an opinion about it.

Writing a profile means naming the labels a vendor prints and the zones it prints them
in. Both are properties of the page, and neither is visible from the PDF in a text
editor: a label is whatever string the vendor chose, and a zone is a cell of the grid
this package lays over the page. Guessing them and re-running the extractor until it
works is the slow way round.

So this prints the document as the engine reads it — every line, the page and zone it
was drawn in, and the box it occupies — followed by how each vendor the registry knows
scored against it and what carried the score. A profile that will not match says so in
those numbers: a supplier anchor that found nothing scores zero, and the report shows it
against the threshold it had to clear.

Nothing here extracts. `extract` is the command that reads a document with a vendor's
vocabulary; this is the one for the moment before a vendor has one.
"""

from __future__ import annotations

from collections.abc import Sequence

from invoice_extractor.document.model import Document, TextLine
from invoice_extractor.profile.detect import PROFILE_THRESHOLD, ProfileScore

# The widest a line of a page is printed before it is cut: enough for a wrapped
# description, short enough that the zone and the box stay on one terminal row.
TEXT_WIDTH = 62
RULE = "=" * 80


def render(document: Document, scores: Sequence[ProfileScore]) -> str:
    """The whole report: the pages as the engine reads them, then the vendors it weighed."""
    return "\n".join([*_heading(document), *_pages(document), "", *_detection(scores), ""])


def _heading(document: Document) -> list[str]:
    return [
        "Document Inspection",
        RULE,
        f"source   {document.source_path}",
        f"pages    {len(document.pages)}",
        "",
    ]


def _pages(document: Document) -> list[str]:
    printed: list[str] = []
    for page in document.pages:
        printed.extend(
            [
                f"PAGE {page.number} — {page.width:.0f} x {page.height:.0f} pt, "
                f"{len(page.lines)} lines",
                *_anchors(page.anchors),
                "",
                f"  {'ZONE':<6} {'TEXT':<{TEXT_WIDTH}}  BOX (x0, y0, x1, y1)",
                "  " + "-" * (TEXT_WIDTH + 34),
                *(_line(line) for line in page.lines),
                "",
            ]
        )
    return printed


def _anchors(anchors: object) -> list[str]:
    """The four horizontals the reader found, which is where the zones come from."""
    named = (
        ("logo_bottom", "logo bottom"),
        ("totals_top", "totals top"),
        ("vat_summary_top", "VAT summary top"),
    )
    found = [
        f"  anchor   {label}: {getattr(anchors, name):.1f}"
        for name, label in named
        if getattr(anchors, name, None) is not None
    ]
    band = getattr(anchors, "table_header_band", None)
    if band is not None:
        found.append(f"  anchor   table header band: {band[0]:.1f} to {band[1]:.1f}")
    return found or ["  anchor   none found"]


def _line(line: TextLine) -> str:
    box = line.bbox
    text = line.text.strip()
    shown = text if len(text) <= TEXT_WIDTH else f"{text[: TEXT_WIDTH - 1]}…"
    return (
        f"  {line.zone.name:<6} {shown:<{TEXT_WIDTH}}  "
        f"({box.x0:6.1f},{box.y0:6.1f},{box.x1:6.1f},{box.y1:6.1f})"
    )


def _detection(scores: Sequence[ProfileScore]) -> list[str]:
    if not scores:
        return ["No profile was scored: the registry holds no vendors."]
    return [
        f"Profile detection — the threshold is {PROFILE_THRESHOLD:.2f}",
        RULE,
        f"  {'PROFILE':<12} {'SCORE':>6}  {'':<3} PARTS",
        "  " + "-" * 66,
        *(_score(one) for one in scores),
        "",
        _verdict(scores[0]),
    ]


def _score(scored: ProfileScore) -> str:
    parts = "  ".join(f"{name} {value:.2f}" for name, value in sorted(scored.parts.items()))
    mark = "OK " if scored.score >= PROFILE_THRESHOLD else "   "
    return f"  {scored.profile_id:<12} {scored.score:6.2f}  {mark} {parts}"


def _verdict(best: ProfileScore) -> str:
    """What the numbers mean for someone about to write or fix a profile."""
    if best.score >= PROFILE_THRESHOLD:
        return f"{best.profile_id} matches; `extract` will read this document with it."
    missing = sorted(name for name, value in best.parts.items() if value == 0.0)
    absent = f" Nothing scored for: {', '.join(missing)}." if missing else ""
    return (
        f"No profile matches, so `extract` would report `profile_not_detected` and read "
        f"nothing.{absent}"
    )
