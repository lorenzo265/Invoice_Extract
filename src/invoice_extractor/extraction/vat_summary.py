"""The VAT summary, shaped: one line per rate the document charges.

A single-rate invoice states its rate in the totals block and prints no summary; a
document that charges two prints a small table instead, and that table is what reconciles
the totals (`docs/ENGINE_SPEC.md` §5). It is read by the same engine as the line items —
a header, then rows — and differs only in what its columns mean.

Some vendors print that summary as a line per rate rather than as a table, with every
number introduced by the word a table would have set over its column: `20 %  Taxable
Amount 6,996.90 · Tax Amount 1,399.38`. There is no header to find, so such a line is
read by those same labels, out of the same profile.

A vendor that prints no summary is not a failure and reports nothing: `vat_summary` is
absent from the profile, or nothing on the page says one is there, and the result carries
no rows.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal

from invoice_extractor.document.model import Document, TextPart
from invoice_extractor.document.rows import CellRow, cell_rows_of
from invoice_extractor.domain.evidence import Evidence, Strategy
from invoice_extractor.domain.rows import VatSummaryRow
from invoice_extractor.extraction.spec import TableSpec
from invoice_extractor.extraction.table import Cells, read_table
from invoice_extractor.extraction.units.normalizers import parse_number
from invoice_extractor.profile.schema import Profile, TableProfile

# A number as a page prints one, from its first digit to whatever is not part of it.
# The apostrophes are Swiss thousands separators, typed and typeset.
NUMBER = re.compile("-?\\d[\\d\\s.,\u2019']*")
PERCENT = "%"


def extract_vat_summary(
    document: Document, profile: Profile, spec: TableSpec
) -> tuple[VatSummaryRow, ...]:
    """Every line of the VAT summary this document prints, as a table or as a list.

    The line-item table is named as the one this is not: both are read by the same engine,
    and a line-item header uses several of a summary's words.
    """
    table = profile.vat_summary
    if table is None:
        return ()
    reading = read_table(document, table, spec.required_columns, profile.line_items)
    if reading.rows:
        return tuple(_row(row.cells, profile, spec.columns) for row in reading.rows)
    return _listed(document, table, profile)


def _row(cells: Cells, profile: Profile, columns: Sequence[str]) -> VatSummaryRow:
    code = cells.get("code")
    return VatSummaryRow(
        code=None if code is None else code.text,
        rate=_number(cells, "rate", profile),
        base=_number(cells, "base", profile),
        vat=_number(cells, "vat", profile),
        cells=_evidence(cells, columns),
    )


def _number(cells: Cells, column: str, profile: Profile) -> Decimal | None:
    cell = cells.get(column)
    return None if cell is None else parse_number(cell.text, profile)


def _evidence(cells: Cells, columns: Sequence[str]) -> Mapping[str, Evidence]:
    return {column: cells[column].evidence for column in columns if column in cells}


def _listed(document: Document, table: TableProfile, profile: Profile) -> tuple[VatSummaryRow, ...]:
    """A summary printed as a line per rate, each number introduced by its column's word."""
    found = [
        _listed_row(row, table, profile)
        for page in document.pages
        for row in cell_rows_of(page.lines)
    ]
    return tuple(row for row in found if row is not None)


def _listed_row(row: CellRow, table: TableProfile, profile: Profile) -> VatSummaryRow | None:
    """This row as such a line, where it is one: a rate, and a base and a tax beside it."""
    amounts = next((cell for cell in row.cells if _introduces_both(cell.text, table)), None)
    rated = next((cell for cell in row.cells if PERCENT in cell.text), None)
    if amounts is None or rated is None:
        return None
    return VatSummaryRow(
        rate=parse_number(rated.text.replace(PERCENT, ""), profile),
        base=_labelled(amounts.text, table.columns.get("base", ()), profile),
        vat=_labelled(amounts.text, table.columns.get("vat", ()), profile),
        cells={
            "rate": _evidence_of(row.page, rated),
            "base": _evidence_of(row.page, amounts),
            "vat": _evidence_of(row.page, amounts),
        },
    )


def _introduces_both(text: str, table: TableProfile) -> bool:
    columns = table.columns
    return _says(text, columns.get("base", ())) and _says(text, columns.get("vat", ()))


def _says(text: str, labels: Sequence[str]) -> bool:
    return any(label.casefold() in text.casefold() for label in labels if label.strip())


def _labelled(text: str, labels: Sequence[str], profile: Profile) -> Decimal | None:
    """The number this label introduces, up to wherever that number stops."""
    for label in labels:
        at = text.casefold().find(label.casefold())
        if at < 0:
            continue
        found = NUMBER.search(text[at + len(label) :])
        if found is not None:
            return parse_number(found.group(0), profile)
    return None


def _evidence_of(page: int, cell: TextPart) -> Evidence:
    return Evidence(
        page=page,
        bbox=cell.bbox,
        matched_label=None,
        strategy=Strategy.TABLE_CELL,
        raw_text=cell.text.strip(),
    )
