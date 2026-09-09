"""Generate the two sample invoices and the golden results they are judged against.

Everything this script draws, and every value the golden files pin, is a literal in the
data table below — a transcription of `docs/SAMPLES_SPEC.md`, which is the specification
this module implements. Nothing here extracts: the only thing read back out of a PDF is
each line's bounding box, through the same PyMuPDF call `document/pymupdf_reader.py`
uses, so the golden file pins the box the reader must report without anyone typing a
coordinate by hand.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import fitz

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
FONT_NAME = "helv"
FONT_SIZE = 10
LEFT_X = 56
RIGHT_X = 400
COLUMN_X = (56, 140, 320, 370, 450)
TABLE_HEADER_Y = 460
FIRST_ROW_Y = 478
ROW_STEP = 18
BBOX_PRECISION = 2
BBOX_KEYS = ("x0", "y0", "x1", "y1")
LINE_ITEM_KEYS = ("sku", "description", "quantity", "unit_price", "net_amount")
STRATEGY = "LABEL_RIGHT"
SAMPLES_DIR = Path("samples")
# A real timestamp would change the bytes on every run; the samples must not.
FIXED_TIMESTAMP = "D:20240101000000Z"

LineBoxes = Mapping[str, tuple[int, tuple[float, ...]]]
Placement = tuple[int, int, str]


@dataclass(frozen=True, slots=True)
class SampleSpec:
    """Everything about one sample, as data: what is printed and what it must extract to."""

    layout_id: str
    supplier_lines: tuple[tuple[int, str], ...]
    metadata_lines: tuple[tuple[int, str], ...]
    bill_to_lines: tuple[tuple[int, str], ...]
    table_header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    totals_lines: tuple[tuple[int, str], ...]
    field_labels: Mapping[str, str]
    expected_fields: Mapping[str, str]
    expected_line_items: tuple[tuple[str, ...], ...]


ACME = SampleSpec(
    layout_id="acme",
    supplier_lines=(
        (60, "Acme Components Ltd"),
        (76, "14 Foundry Road"),
        (92, "Manchester M1 2AB"),
        (108, "United Kingdom"),
        (124, "VAT Number: GB123456789"),
    ),
    metadata_lines=(
        (60, "INVOICE"),
        (76, "Invoice Number: INV-2024-0042"),
        (92, "Invoice Date: 15 Mar 2024"),
        (108, "Due Date: 14 Apr 2024"),
        (124, "Currency: GBP"),
    ),
    bill_to_lines=(
        (340, "Bill To"),
        (356, "Nordwind Logistik GmbH"),
        (372, "Friedrichstrasse 88"),
        (388, "20095 Hamburg"),
        (404, "Germany"),
        (420, "Customer VAT Number: DE123456789"),
    ),
    table_header=("SKU", "Description", "Qty", "Unit Price", "Net Amount"),
    rows=(
        ("ACM-1001", "Hex bolt M8 x 40, zinc", "500", "0.12", "60.00"),
        ("ACM-2210", "Bearing 6204-2RS", "40", "3.85", "154.00"),
        ("ACM-3300", "Steel bracket, 3 mm", "120", "2.30", "276.00"),
    ),
    totals_lines=(
        (620, "Subtotal: 490.00"),
        (638, "VAT Rate: 20.00%"),
        (656, "VAT Amount: 98.00"),
        (674, "Total Due: 588.00"),
    ),
    field_labels={
        "invoice_number": "Invoice Number",
        "invoice_date": "Invoice Date",
        "due_date": "Due Date",
        "supplier_vat_id": "VAT Number",
        "customer_vat_id": "Customer VAT Number",
        "currency": "Currency",
        "vat_rate": "VAT Rate",
        "subtotal": "Subtotal",
        "vat_amount": "VAT Amount",
        "total_amount": "Total Due",
    },
    expected_fields={
        "invoice_number": "INV-2024-0042",
        "invoice_date": "2024-03-15",
        "due_date": "2024-04-14",
        "supplier_vat_id": "GB123456789",
        "customer_vat_id": "DE123456789",
        "currency": "GBP",
        "vat_rate": "20.00",
        "subtotal": "490.00",
        "vat_amount": "98.00",
        "total_amount": "588.00",
    },
    expected_line_items=(
        ("ACM-1001", "Hex bolt M8 x 40, zinc", "500", "0.12", "60.00"),
        ("ACM-2210", "Bearing 6204-2RS", "40", "3.85", "154.00"),
        ("ACM-3300", "Steel bracket, 3 mm", "120", "2.30", "276.00"),
    ),
)

NORDIC = SampleSpec(
    layout_id="nordic",
    supplier_lines=(
        (60, "Fjordvik Elektronik AB"),
        (76, "Industrivägen 12"),
        (92, "411 04 Göteborg"),
        (108, "Sweden"),
        (124, "Momsreg.nr: SE556123456701"),
    ),
    metadata_lines=(
        (60, "FAKTURA"),
        (76, "Fakturanummer: 2024-00873"),
        (92, "Fakturadatum: 2024-05-02"),
        (108, "Förfallodatum: 2024-06-01"),
        (124, "Valuta: SEK"),
    ),
    bill_to_lines=(
        (340, "Faktureras till"),
        (356, "Solstrand Bygg AS"),
        (372, "Fjellveien 5"),
        (388, "5003 Bergen"),
        (404, "Norway"),
        (420, "Kundens momsreg.nr: NO987654321MVA"),
    ),
    table_header=("Artikelnr", "Beskrivning", "Antal", "Pris", "Belopp"),
    rows=(
        ("FJ-771", "Kabelkanal 40x60, 2 m", "30", "89,00", "2 670,00"),
        ("FJ-902", "Kopplingsdosa IP65", "12", "45,50", "546,00"),
    ),
    totals_lines=(
        (620, "Netto: 3 216,00"),
        (638, "Moms: 25,00%"),
        (656, "Momsbelopp: 804,00"),
        (674, "Att betala: 4 020,00"),
    ),
    field_labels={
        "invoice_number": "Fakturanummer",
        "invoice_date": "Fakturadatum",
        "due_date": "Förfallodatum",
        "supplier_vat_id": "Momsreg.nr",
        "customer_vat_id": "Kundens momsreg.nr",
        "currency": "Valuta",
        "vat_rate": "Moms",
        "subtotal": "Netto",
        "vat_amount": "Momsbelopp",
        "total_amount": "Att betala",
    },
    expected_fields={
        "invoice_number": "2024-00873",
        "invoice_date": "2024-05-02",
        "due_date": "2024-06-01",
        "supplier_vat_id": "SE556123456701",
        "customer_vat_id": "NO987654321MVA",
        "currency": "SEK",
        "vat_rate": "25.00",
        "subtotal": "3216.00",
        "vat_amount": "804.00",
        "total_amount": "4020.00",
    },
    expected_line_items=(
        ("FJ-771", "Kabelkanal 40x60, 2 m", "30", "89.00", "2670.00"),
        ("FJ-902", "Kopplingsdosa IP65", "12", "45.50", "546.00"),
    ),
)

SAMPLES: Mapping[str, SampleSpec] = {"acme": ACME, "nordic": NORDIC}


def table_placements(sample: SampleSpec) -> list[Placement]:
    """Five `insert_text` calls per table row, at the five column x-coordinates."""
    rows = ((TABLE_HEADER_Y, sample.table_header), *enumerate_rows(sample))
    return [(x, y, text) for y, cells in rows for x, text in zip(COLUMN_X, cells, strict=True)]


def enumerate_rows(sample: SampleSpec) -> list[tuple[int, tuple[str, ...]]]:
    return [(FIRST_ROW_Y + index * ROW_STEP, row) for index, row in enumerate(sample.rows)]


def placements(sample: SampleSpec) -> list[Placement]:
    """Every `insert_text` call this sample makes, as `(x, y, text)`."""
    return [
        *((LEFT_X, y, text) for y, text in sample.supplier_lines),
        *((RIGHT_X, y, text) for y, text in sample.metadata_lines),
        *((LEFT_X, y, text) for y, text in sample.bill_to_lines),
        *((RIGHT_X, y, text) for y, text in sample.totals_lines),
        *table_placements(sample),
    ]


def metadata(sample: SampleSpec) -> dict[str, str]:
    return {
        "producer": "invoice-extractor",
        "creator": "scripts/make_samples.py",
        "title": f"{sample.layout_id} sample",
        "creationDate": FIXED_TIMESTAMP,
        "modDate": FIXED_TIMESTAMP,
    }


def draw(sample: SampleSpec, pdf_path: Path) -> None:
    """Write `sample` to `pdf_path` as a one-page A4 PDF, byte-identical run to run."""
    document = fitz.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    for x, y, text in placements(sample):
        page.insert_text(fitz.Point(x, y), text, fontsize=FONT_SIZE, fontname=FONT_NAME)
    document.set_metadata(metadata(sample))
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    # no_new_id keeps PyMuPDF from writing a random trailer /ID on every save.
    document.save(str(pdf_path), garbage=4, deflate=True, no_new_id=True)
    document.close()


def line_boxes(pdf_path: Path) -> LineBoxes:
    """Every text line in the PDF, mapped to its 1-indexed page and rounded bbox."""
    boxes: dict[str, tuple[int, tuple[float, ...]]] = {}
    with fitz.open(str(pdf_path)) as document:
        for number, page in enumerate(document, start=1):
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", ()):
                    text = "".join(span["text"] for span in line["spans"])
                    boxes[text] = (number, tuple(round(v, BBOX_PRECISION) for v in line["bbox"]))
    return boxes


def drawn_line(sample: SampleSpec, label: str) -> str:
    """The one line this sample prints for `label`, per the label-colon convention."""
    matches = [text for _, _, text in placements(sample) if text.startswith(f"{label}:")]
    if len(matches) != 1:
        raise ValueError(f"{sample.layout_id}: {label!r} matches {len(matches)} drawn lines")
    return matches[0]


def field_result(sample: SampleSpec, name: str, boxes: LineBoxes) -> dict[str, object]:
    label = sample.field_labels[name]
    raw_text = drawn_line(sample, label)
    page, bbox = boxes[raw_text]
    return {
        "value": sample.expected_fields[name],
        "raw_text": raw_text,
        "valid": True,
        "evidence": {
            "page": page,
            "bbox": dict(zip(BBOX_KEYS, bbox, strict=True)),
            "matched_label": label,
            "strategy": STRATEGY,
            "raw_text": raw_text,
        },
    }


def write_expected(sample: SampleSpec, pdf_path: Path, json_path: Path) -> None:
    """Write the golden result for `sample`, reading only bounding boxes back from the PDF."""
    boxes = line_boxes(pdf_path)
    data = {
        "fields": {name: field_result(sample, name, boxes) for name in sample.expected_fields},
        "line_items": [
            dict(zip(LINE_ITEM_KEYS, row, strict=True)) for row in sample.expected_line_items
        ],
        "findings": [],
        "layout_id": sample.layout_id,
        # The golden file pins the path the golden test extracts from — always the
        # repository-relative one, never wherever this run happened to write the PDF.
        "source_path": (SAMPLES_DIR / pdf_path.name).as_posix(),
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    for sample in SAMPLES.values():
        pdf_path = SAMPLES_DIR / f"{sample.layout_id}_invoice.pdf"
        draw(sample, pdf_path)
        write_expected(sample, pdf_path, pdf_path.with_suffix(".expected.json"))


if __name__ == "__main__":
    main()
