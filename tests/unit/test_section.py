"""Party blocks: a heading, a name, an address under it, and what ends the block."""

from __future__ import annotations

import dataclasses

from conftest import make_document, make_profile, make_section_profile
from invoice_extractor.domain.evidence import Strategy
from invoice_extractor.extraction.section import read_party, read_section, read_supplier
from invoice_extractor.extraction.spec import SectionSpec

LEFT = 50.0
RIGHT = 320.0
HEIGHT = 10.0
LEADING = 12.0


def block(x: float, y: float, *lines: str, page: int = 1, bold: int = 1) -> list:
    """A heading and the lines under it, the first `bold` of them set in a bold face."""
    drawn = []
    for index, text in enumerate(lines):
        top = y + LEADING * index
        drawn.append((page, text, x, top, x + 140.0, top + HEIGHT, index < bold))
    return drawn


def document(*blocks: list) -> object:
    entries = [line[:6] for block_lines in blocks for line in block_lines]
    built = make_document(entries)
    bold = {(line[0], line[1]) for block_lines in blocks for line in block_lines if line[6]}
    return _with_weights(built, bold)


def _with_weights(built: object, bold: set[tuple[int, str]]) -> object:
    """The same document, with the runs a page set in bold marked as bold."""
    pages = tuple(
        dataclasses.replace(
            page,
            lines=tuple(
                dataclasses.replace(
                    line,
                    parts=tuple(
                        dataclasses.replace(part, bold=(line.page, line.text) in bold)
                        for part in line.cells
                    ),
                )
                for line in page.lines
            ),
        )
        for page in built.pages
    )
    return dataclasses.replace(built, pages=pages)


def bill_to(**changed: object) -> object:
    return make_section_profile(labels=("Bill To",), **changed)


def test_a_block_is_its_name_and_the_address_under_it() -> None:
    page = document(block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "1 Elm Close", "Leeds"))
    party = read_party(page, bill_to(), make_profile())
    assert party is not None
    assert party.name == "Acme Systems Ltd"
    assert party.lines == ("1 Elm Close", "Leeds")
    assert party.evidence[0].strategy is Strategy.SECTION_LINE


def test_a_name_too_wide_for_its_column_is_still_one_name() -> None:
    """Both lines of it are set in the block's own weight; the address under them is not."""
    page = document(
        block(LEFT, 100.0, "Bill To", "Acme Systems", "& Partners Ltd", "1 Elm Close", bold=3)
    )
    party = read_party(page, bill_to(), make_profile())
    assert party is not None
    assert party.name == "Acme Systems & Partners Ltd"
    assert party.lines == ("1 Elm Close",)


def test_a_vat_id_printed_in_the_block_is_a_value_and_not_a_line_of_the_address() -> None:
    page = document(
        block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "1 Elm Close", "VAT No.: GB123456789")
    )
    party = read_party(page, bill_to(), make_profile())
    assert party is not None
    assert party.vat_id == "GB123456789"
    assert party.lines == ("1 Elm Close",)


def test_a_block_that_defers_to_another_says_so_and_names_no_address() -> None:
    page = document(block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "same as billing address"))
    party = read_party(page, bill_to(placeholders=("same as billing address",)), make_profile())
    assert party is not None
    assert party.placeholder
    assert party.lines == ()


def test_a_placeholder_wrapped_over_two_lines_is_still_a_placeholder() -> None:
    page = document(
        block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "same as the", "billing address")
    )
    party = read_party(page, bill_to(placeholders=("same as the billing address",)), make_profile())
    assert party is not None
    assert party.placeholder


def test_another_blocks_heading_ends_this_one() -> None:
    page = document(
        block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "1 Elm Close", "Ship To", "Elsewhere Ltd")
    )
    party = read_party(page, bill_to(stop_labels=("Ship To",)), make_profile())
    assert party is not None
    assert party.lines == ("1 Elm Close",)


def test_a_block_stops_where_the_column_stops() -> None:
    """The table under it is a long way down; nothing that far away is an address line."""
    page = document(
        block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "1 Elm Close"),
        block(LEFT, 300.0, "Pos.", "1"),
    )
    party = read_party(page, bill_to(), make_profile())
    assert party is not None
    assert party.lines == ("1 Elm Close",)


def test_a_block_may_stand_a_few_lines_under_its_heading() -> None:
    """A vendor leaves two lines of room under `Bill To:` before the name. The room opens
    the block; it is the gap between the lines of the block that ends it."""
    page = document(
        block(LEFT, 100.0, "Bill To"),
        block(LEFT, 128.0, "Acme Systems Ltd", "1 Elm Close"),
    )
    party = read_party(page, bill_to(), make_profile())
    assert party is not None
    assert party.name == "Acme Systems Ltd"
    assert party.lines == ("1 Elm Close",)


def test_a_block_far_under_a_heading_is_not_that_headings_block() -> None:
    page = document(
        block(LEFT, 100.0, "Bill To"),
        block(LEFT, 160.0, "Acme Systems Ltd", "1 Elm Close"),
    )
    party = read_party(page, bill_to(), make_profile())
    assert party is not None
    assert party.name is None
    assert party.lines == ()


def test_a_block_set_wholly_in_bold_still_has_one_name() -> None:
    """Weight tells a name from an address only where the two differ. A vendor that sets
    the whole block in bold has said nothing with it, and the first line is the name."""
    page = document(
        block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "1 Elm Close", "Leeds", bold=4)
    )
    party = read_party(page, bill_to(), make_profile())
    assert party is not None
    assert party.name == "Acme Systems Ltd"
    assert party.lines == ("1 Elm Close", "Leeds")


def test_a_block_reads_its_own_column_and_not_the_one_beside_it() -> None:
    page = document(
        block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "1 Elm Close"),
        block(RIGHT, 100.0, "Ship To", "Elsewhere Ltd", "2 Oak Row"),
    )
    party = read_party(page, bill_to(), make_profile())
    assert party is not None
    assert party.lines == ("1 Elm Close",)


def test_a_block_the_document_does_not_print_is_not_read() -> None:
    page = document(block(LEFT, 100.0, "Ship To", "Elsewhere Ltd"))
    assert read_party(page, bill_to(), make_profile()) is None


def test_the_supplier_block_starts_at_the_name_the_vendor_prints_itself_under() -> None:
    """Nothing opens a letterhead, so everything under the name belongs to the address."""
    page = document(block(LEFT, 60.0, "Test Supplies Ltd", "1 Test Street", "VAT No.: GB123456789"))
    party = read_supplier(page, make_profile())
    assert party is not None
    assert party.name == "Test Supplies Ltd"
    assert party.lines == ("1 Test Street",)
    assert party.vat_id == "GB123456789"


def test_a_spec_names_which_block_it_reads() -> None:
    page = document(block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "1 Elm Close"))
    vendor = make_profile(parties={"bill_to": bill_to()})
    party = read_section(SectionSpec(name="bill_to", source="bill_to"), page, vendor)
    assert party is not None
    assert party.name == "Acme Systems Ltd"


def test_a_spec_for_a_block_this_vendor_does_not_describe_reads_nothing() -> None:
    page = document(block(LEFT, 100.0, "Bill To", "Acme Systems Ltd"))
    spec = SectionSpec(name="mail_to", source="mail_to")
    assert read_section(spec, page, make_profile()) is None


def test_a_letterhead_the_page_does_not_print_is_not_read() -> None:
    """A continuation page prints no letterhead, and a vendor unnamed is a vendor unread."""
    page = document(block(LEFT, 100.0, "Bill To", "Acme Systems Ltd"))
    assert read_supplier(page, make_profile()) is None


def test_a_block_runs_no_further_than_the_lines_its_profile_allows() -> None:
    page = document(
        block(LEFT, 100.0, "Bill To", "Acme Systems Ltd", "1 Elm Close", "Leeds", "United Kingdom")
    )
    party = read_party(page, bill_to(max_lines=2), make_profile())
    assert party is not None
    assert party.lines == ("1 Elm Close",)
