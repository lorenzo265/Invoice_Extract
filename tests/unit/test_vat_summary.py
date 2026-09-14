"""The VAT summary: as a table of rates, or as a line per rate."""

from __future__ import annotations

from decimal import Decimal

from conftest import make_document, make_profile, make_table_profile, make_vat_table_profile
from invoice_extractor.extraction.specs import VAT_SUMMARY
from invoice_extractor.extraction.vat_summary import extract_vat_summary

HEIGHT = 10.0
WIDTH = 40.0
COLUMNS = {"code": 50.0, "rate": 90.0, "base": 200.0, "vat": 280.0}


def entries(y: float, *placed: tuple[str, float]) -> list:
    return [(1, text, x, y, x + WIDTH, y + HEIGHT) for text, x in placed]


def summary_document(*rows: list) -> object:
    header = entries(100.0, *((column, x) for column, x in COLUMNS.items()))
    return make_document([*header, *(entry for row in rows for entry in row)])


def vendor(**changed: object) -> object:
    return make_profile(vat_summary=make_vat_table_profile(**changed))


def read(document: object, profile: object | None = None) -> object:
    return extract_vat_summary(document, profile or vendor(), VAT_SUMMARY)


def test_a_line_of_the_summary_is_a_rate_a_base_and_a_tax() -> None:
    rows = read(
        summary_document(
            entries(120.0, ("S", 50.0), ("20 %", 90.0), ("19.25", 200.0), ("3.85", 280.0))
        )
    )
    assert len(rows) == 1
    assert (rows[0].code, rows[0].rate) == ("S", Decimal(20))
    assert (rows[0].base, rows[0].vat) == (Decimal("19.25"), Decimal("3.85"))
    assert rows[0].cells["vat"].bbox.x0 == COLUMNS["vat"]


def test_a_document_whose_vendor_prints_no_summary_reads_none() -> None:
    assert read(summary_document(), make_profile()) == ()


def test_a_page_with_no_summary_on_it_reads_none() -> None:
    bare = make_document([(1, "nothing here", 50.0, 100.0, 200.0, 110.0)])
    assert read(bare) == ()


def test_a_summary_stops_where_the_totals_block_begins() -> None:
    profile = vendor(stop_labels=("Total Due",))
    first = entries(120.0, ("S", 50.0), ("20 %", 90.0), ("19.25", 200.0), ("3.85", 280.0))
    total = entries(140.0, ("Total Due", 340.0), ("23.10", 500.0))
    after = entries(160.0, ("R", 50.0), ("5 %", 90.0), ("10.00", 200.0), ("0.50", 280.0))
    assert len(read(summary_document(first, total, after), profile)) == 1


def test_a_summary_printed_as_a_line_per_rate_is_read_by_its_own_labels() -> None:
    """No header, no columns: the words a table would have set over them introduce the numbers."""
    profile = make_profile(
        vat_summary=make_table_profile(
            columns={
                "code": ("Code",),
                "rate": ("Rate",),
                "base": ("Taxable Amount",),
                "vat": ("Tax Amount",),
            },
            min_header_matches=2,
        )
    )
    listed = make_document(
        [
            (1, "20 %", 50.0, 120.0, 70.0, 130.0),
            (1, "Taxable Amount 6,996.90 · Tax Amount 1,399.38", 200.0, 120.0, 400.0, 130.0),
            (1, "5 %", 50.0, 140.0, 70.0, 150.0),
            (1, "Taxable Amount 3,078.15 · Tax Amount 153.91", 200.0, 140.0, 400.0, 150.0),
        ]
    )
    rows = read(listed, profile)
    assert [(row.rate, row.base, row.vat) for row in rows] == [
        (Decimal(20), Decimal("6996.90"), Decimal("1399.38")),
        (Decimal(5), Decimal("3078.15"), Decimal("153.91")),
    ]


def test_a_line_that_names_only_one_of_the_two_amounts_is_not_a_summary_line() -> None:
    profile = make_profile(
        vat_summary=make_table_profile(
            columns={"rate": ("Rate",), "base": ("Taxable Amount",), "vat": ("Tax Amount",)},
            min_header_matches=2,
        )
    )
    prose = make_document(
        [
            (1, "20 %", 50.0, 120.0, 70.0, 130.0),
            (1, "Taxable Amount 6,996.90", 200.0, 120.0, 400.0, 130.0),
        ]
    )
    assert read(prose, profile) == ()


def test_a_listed_line_whose_amount_is_not_printed_reads_that_amount_as_nothing() -> None:
    """The words are there and the number is not, which is a value the page does not give."""
    profile = make_profile(
        vat_summary=make_table_profile(
            columns={"rate": ("Rate",), "base": ("Taxable Amount",), "vat": ("Tax Amount",)},
            min_header_matches=2,
        )
    )
    listed = make_document(
        [
            (1, "0 %", 50.0, 120.0, 70.0, 130.0),
            (1, "Taxable Amount 7.95 · Tax Amount exempt", 200.0, 120.0, 400.0, 130.0),
        ]
    )
    rows = read(listed, profile)
    assert rows[0].base == Decimal("7.95")
    assert rows[0].vat is None
