# Samples specification

`samples/acme_invoice.pdf` and `samples/nordic_invoice.pdf` are the only two invoices
this project will ever see committed to it (ADR-0004's "two vendors, one JSON diff
apart" — see `docs/adr/0004-layouts-are-data.md`). Both are generated, never scanned or
hand-edited (`samples/README.md`), and both come with a golden
`<id>_invoice.expected.json` — the exact `InvoiceResult` the pipeline must produce for
that PDF. This document is the source of truth for three things, in order:

1. The exact content `scripts/make_samples.py` draws onto each PDF — every string, its
   coordinates, and the zone it must land in.
2. The exact values extraction must produce from that content — the golden targets.
3. The exact JSON shape `<id>_invoice.expected.json` is written in, derived from
   `InvoiceResult.to_dict()`.

Read `docs/LAYOUT_FORMAT.md` alongside this file — that document defines what a layout
key *means*; this one fixes what two real layouts, `acme` and `nordic`, actually
contain, down to the character.

## Shared drawing rules

Both samples are one page each, drawn under the same rules:

- **Page.** A4 portrait, 595 × 842 pt (`pymupdf.paper_rect("a4")`). One page per invoice.
- **Font.** `"helv"` (Helvetica, a PDF base-14 font — no embedding, nothing to subset),
  size `10`, for every line on both PDFs. No bold, no other size: this is a data fixture,
  not a design exercise.
- **Placement.** Every line of content is exactly one
  `page.insert_text(pymupdf.Point(x, y), text, fontsize=10, fontname="helv")` call. `y` is
  the text's **baseline**, not its top — PyMuPDF reports a taller `bbox` above and
  below it (ascender to descender), which is why the `y0` values in the evidence tables
  below don't equal the `y` a line is inserted at.
- **Columns.** Every table below gives a block's line as `(y, text)`; the x-coordinate
  is constant per block and stated once, here:

  | Block | x |
  |---|---|
  | Left column (supplier block, bill-to block) | `56` |
  | Right column (invoice-metadata block, totals block) | `400` |
  | Line-item table — `sku` | `56` |
  | Line-item table — `description` | `140` |
  | Line-item table — `quantity` | `320` |
  | Line-item table — `unit_price` | `370` |
  | Line-item table — `net_amount` | `450` |

  Every line-item cell is its own `insert_text` call — five per row, at the five x's
  above, sharing the row's `y`. PyMuPDF reports these as five separate `TextLine`s (the
  gaps between columns are wide enough that its own line-grouping never merges them),
  which is what lets the line-item extractor locate a column by its header's position
  and re-use that x for every row under it.
- **Zone grid.** A line's `Zone` is `document/zones.py`'s classification of its `BBox`
  centre against the page's own thirds:

  | | `x < 198.33` (LEFT) | `198.33 ≤ x < 396.67` (CENTER) | `x ≥ 396.67` (RIGHT) |
  |---|---|---|---|
  | `y < 280.67` (TOP) | TOP_LEFT | TOP_CENTER | TOP_RIGHT |
  | `280.67 ≤ y < 561.33` (MIDDLE) | MIDDLE_LEFT | MIDDLE_CENTER | MIDDLE_RIGHT |
  | `y ≥ 561.33` (BOTTOM) | BOTTOM_LEFT | BOTTOM_CENTER | BOTTOM_RIGHT |

  (Thirds of 595 and 842, i.e. 198.33 = 595/3, 396.67 = 2·595/3, 280.67 = 842/3,
  561.33 = 2·842/3.)
- **`BBox` precision.** Every `bbox` in this document is read from PyMuPDF's
  `page.get_text("dict")` — the same call `document/pymupdf_reader.py` uses to build a
  `TextLine` — and rounded to 2 decimal places. PyMuPDF's underlying precision is
  float32, so an unrounded value is long and meaningless (`157.70997619628906` instead
  of `157.71`); rounding to 2 decimals belongs in `document/pymupdf_reader.py` itself
  (every `BBox` it builds, not only these two samples), so that this rounding is a
  property of the reader, not a one-off cleanup applied to golden files.
- **Page numbering.** `Evidence.page` is 1-indexed. Both samples have one page, so every
  `Evidence` in both `expected.json` files has `"page": 1`.
- **The label-colon convention.** Every scalar field's label and value share one printed
  line, separated by `": "` — `"Invoice Number: INV-2024-0042"`. See
  `docs/LAYOUT_FORMAT.md`'s "label-colon convention" section for what this means for
  `labels` in the layout JSON and for the normalizer that strips it.

## The `expected.json` contract

`<id>_invoice.expected.json` is the projection of `InvoiceResult.to_dict()` that
`tests/integration/test_pipeline_golden.py` compares extraction output against. Its
shape, key by key:

```
{
  "fields": { "<name>": FieldResultJSON, ... },   // all ten scalar names, always
  "line_items": [ LineItemJSON, ... ],
  "findings": [ FindingJSON, ... ],
  "layout_id": "<layout id>",
  "source_path": "<relative, forward-slash path>"
}
```

**`fields` always has all ten keys.** Every scalar field name from `docs/LAYOUT_FORMAT.md`
is a key in `fields`, whether or not it was found — a caller never needs
`"invoice_number" in result.fields` before reading it, only
`result.fields["invoice_number"].value is not None`. Each `FieldResultJSON` is:

```
{
  "value": <str | ISO-8601 date string | decimal string> | null,
  "raw_text": <str> | null,
  "valid": <bool>,
  "evidence": EvidenceJSON | null
}
```

Every key is always present; a missing value is `null`, never an absent key — this
keeps the shape uniform regardless of whether a field was found, which is what lets a
consumer deserialize `fields` with one code path instead of a branch per field. What
`null` means depends on why the field is empty:

- **`on_all_invalid = NOT_FOUND`** (both seed layouts' setting for every field it names
  in `docs/LAYOUT_FORMAT.md`), **or no candidate was found at all** regardless of
  `on_all_invalid`: `value`, `raw_text`, and `evidence` are `null`; `valid` is `false`.
- **`on_all_invalid = BEST`**, with at least one candidate found but none passing its
  validator: `value`, `raw_text`, and `evidence` come from the top-ranked candidate
  anyway; `valid` is `false` (it still failed validation) — this is the one case where
  `value` is non-null and `valid` is `false` at once.

Neither `acme_invoice.expected.json` nor `nordic_invoice.expected.json` exercises
either path — both invoices are complete and internally consistent, so every field in
both files has a real `value` and `valid: true`. The rule above exists so a reader
knows the full shape before meeting a `NOT_FOUND` field on a different invoice, not
because these two samples need it.

`EvidenceJSON` is:

```
{
  "page": <int>,                                    // 1-indexed
  "bbox": { "x0": <float>, "y0": <float>, "x1": <float>, "y1": <float> },
  "matched_label": <str> | null,
  "strategy": "LABEL_RIGHT" | "LABEL_BELOW" | "REGEX_ANCHOR",
  "raw_text": <str>
}
```

`bbox` is an object with named keys, not a four-element array — a reader shouldn't have
to remember that index 2 is `x1`. Every field in both seed samples resolves through
`LABEL_RIGHT` — see "Why every field is `LABEL_RIGHT`" in the `acme` section below.

**Why `confidence` and `confidence_breakdown` are excluded, and `bbox` is not.** These
are the only two keys `FieldResult` carries that `expected.json` omits entirely (not
`null` — the key itself is absent). `evidence.bbox`, by contrast, **is** compared
exactly, byte for byte, the same as every other field — per ADR-0002
(`docs/adr/0002-every-value-carries-evidence.md`): `scripts/make_samples.py` draws every
line at a fixed coordinate with a fixed font, so PyMuPDF's reported bbox for a given
string is exactly reproducible, run to run and PR to PR. There is nothing to exclude.

`confidence` and `confidence_breakdown` are different in kind, not just in degree: they
are the *output* of `validation/confidence.py`'s weighted-signal algorithm, which
doesn't exist until PR7 — this document, and the `expected.json` files PR1 writes from
it, exist from PR1. A golden file can't pin the exact output of an algorithm four PRs
away from being written, and pinning it retroactively once PR7 lands would turn
`expected.json` into a second copy of that PR's tuning constants instead of a check on
whether extraction found the right values — precisely the kind of test that breaks for
reasons unrelated to the bug it should catch. So the golden test's comparison is a
**projection**, not a direct diff: it computes `InvoiceResult.to_dict()`, removes
exactly `confidence` and `confidence_breakdown` from every entry in `fields`, and
compares what's left — `evidence` (`bbox` included), `value`, `raw_text`, `valid`,
`line_items`, `findings`, `layout_id`, and `source_path` — against the committed file,
exactly. `confidence` still appears in the real `result.json` a run of the CLI writes
(`output/json_writer.py` serializes the whole `FieldResult`, unprojected); it is absent
only from the two files under `samples/`, and only because the projection removes it
before the comparison, not because `to_dict()` ever omits it.

**`LineItemJSON`** carries no `Evidence` and no confidence — line items are found by
locating a table (`header_labels`/`stop_labels`), not by the candidate-and-rank pipeline
scalar fields go through, so there is no ranking decision to audit:

```
{ "sku": <str>, "description": <str>, "quantity": <decimal string>,
  "unit_price": <decimal string>, "net_amount": <decimal string> }
```

`quantity` is `decimal.Decimal`, not `int` — consistent with `unit_price` and
`net_amount`, and consistent with ADR-0003's reasoning one type further: a quantity of
"2.5 kg" is exactly as real as a fractional currency amount, so it gets the same exact
type and the same JSON-as-string treatment, never a native JSON number.

**`FindingJSON`** isn't detailed here — both samples are arithmetically clean (see each
section below), so `"findings": []` in both files, and no `Finding` shape is exercised
by this document. `docs/adr/0005-findings-not-exceptions-for-domain-errors.md` and
`domain/findings.py` are the source of truth for what a non-empty entry looks like.

**`source_path`** is `Path(pdf_path).as_posix()` — forward slashes on every platform,
including Windows, so `expected.json` is identical whether it was generated on Windows
or Linux CI. It is the path exactly as given to `extract()` / the CLI, never resolved
to an absolute path (an absolute path would make `expected.json` different on every
machine that generates it). Both golden tests invoke extraction with the path written
exactly as `"samples/acme_invoice.pdf"` / `"samples/nordic_invoice.pdf"`, run from the
repository root — the same working-directory assumption `docs/LAYOUT_FORMAT.md`'s
`load_layout` resolution rule already depends on.

**Key order** above — `fields`, `line_items`, `findings`, `layout_id`, `source_path` —
follows `docs/ARCHITECTURE.md` §2's `InvoiceResult` field order. JSON object keys are
unordered by spec, so this is a readability convention `json_writer.py` should follow,
not something the golden comparison depends on.

---

## Sample: `acme`

Supplier **Acme Components Ltd**, Manchester, UK, VAT `GB123456789`. Customer
**Nordwind Logistik GmbH**, Hamburg, DE, VAT `DE123456789`. English labels, period
decimal / comma thousands (`"1,234.56"`), dates as `"15 Mar 2024"`, currency GBP, VAT
20%. Layout: `layouts/acme.json`.

### Page content

**Supplier block** (`x=56`, zone **TOP_LEFT**) — this block's first line
(`"Acme Components Ltd"`) is the one the PR2 integration test opens the PDF and asserts
is classified `TOP_LEFT`:

| y | Text |
|---|---|
| 60 | `Acme Components Ltd` |
| 76 | `14 Foundry Road` |
| 92 | `Manchester M1 2AB` |
| 108 | `United Kingdom` |
| 124 | `VAT Number: GB123456789` |

**Invoice metadata block** (`x=400`, zone **TOP_RIGHT**):

| y | Text |
|---|---|
| 60 | `INVOICE` |
| 76 | `Invoice Number: INV-2024-0042` |
| 92 | `Invoice Date: 15 Mar 2024` |
| 108 | `Due Date: 14 Apr 2024` |
| 124 | `Currency: GBP` |

**Bill-to block** (`x=56`, zone **MIDDLE_LEFT**):

| y | Text |
|---|---|
| 340 | `Bill To` |
| 356 | `Nordwind Logistik GmbH` |
| 372 | `Friedrichstrasse 88` |
| 388 | `20095 Hamburg` |
| 404 | `Germany` |
| 420 | `Customer VAT Number: DE123456789` |

**Line-item table** — header at `y=460`, one row per `y` after it, each cell at its
column's x from the shared table above:

| y | `sku` (56) | `description` (140) | `quantity` (320) | `unit_price` (370) | `net_amount` (450) |
|---|---|---|---|---|---|
| 460 | `SKU` | `Description` | `Qty` | `Unit Price` | `Net Amount` |
| 478 | `ACM-1001` | `Hex bolt M8 x 40, zinc` | `500` | `0.12` | `60.00` |
| 496 | `ACM-2210` | `Bearing 6204-2RS` | `40` | `3.85` | `154.00` |
| 514 | `ACM-3300` | `Steel bracket, 3 mm` | `120` | `2.30` | `276.00` |

**Totals block** (`x=400`, zone **BOTTOM_RIGHT**):

| y | Text |
|---|---|
| 620 | `Subtotal: 490.00` |
| 638 | `VAT Rate: 20.00%` |
| 656 | `VAT Amount: 98.00` |
| 674 | `Total Due: 588.00` |

Arithmetic check (why `findings` is `[]`): line items sum to `60.00 + 154.00 + 276.00 =
490.00` = subtotal; `490.00 × 20% = 98.00` = VAT amount; `490.00 + 98.00 = 588.00` =
total. All three invariants agree, to the cent.

### Why every field is `LABEL_RIGHT`

Every one of the ten fields above sits on the same printed line as its label, to the
label's right — no field in `layouts/acme.json` needs `LABEL_BELOW` or `REGEX_ANCHOR`
to be found, and no field needs a `regex` (see `docs/ARCHITECTURE.md` §5's worked
`invoice_number` example, and `docs/LAYOUT_FORMAT.md`'s worked `supplier_vat_id`
example — both match this page exactly). `LABEL_BELOW` and `REGEX_ANCHOR` are real
strategies with their own unit tests in `tests/unit/test_strategies.py`
(`extraction/strategies.py`, PR5) against `FakeDocument` fixtures — this fixed pair of
golden PDFs simply never needs them.

### Expected scalar fields

| Field | Label | Raw text (drawn line) | Value | Zone |
|---|---|---|---|---|
| `invoice_number` | `Invoice Number` | `Invoice Number: INV-2024-0042` | `"INV-2024-0042"` | TOP_RIGHT |
| `invoice_date` | `Invoice Date` | `Invoice Date: 15 Mar 2024` | `2024-03-15` | TOP_RIGHT |
| `due_date` | `Due Date` | `Due Date: 14 Apr 2024` | `2024-04-14` | TOP_RIGHT |
| `supplier_vat_id` | `VAT Number` | `VAT Number: GB123456789` | `"GB123456789"` | TOP_LEFT |
| `customer_vat_id` | `Customer VAT Number` | `Customer VAT Number: DE123456789` | `"DE123456789"` | MIDDLE_LEFT |
| `currency` | `Currency` | `Currency: GBP` | `"GBP"` | TOP_RIGHT |
| `vat_rate` | `VAT Rate` | `VAT Rate: 20.00%` | `20.00` | BOTTOM_RIGHT |
| `subtotal` | `Subtotal` | `Subtotal: 490.00` | `490.00` | BOTTOM_RIGHT |
| `vat_amount` | `VAT Amount` | `VAT Amount: 98.00` | `98.00` | BOTTOM_RIGHT |
| `total_amount` | `Total Due` | `Total Due: 588.00` | `588.00` | BOTTOM_RIGHT |

`value` is typed per field: `invoice_number`/`supplier_vat_id`/`customer_vat_id`/`currency`
are `str`; `invoice_date`/`due_date` are `datetime.date` (shown above in its ISO-8601
serialization); `vat_rate`/`subtotal`/`vat_amount`/`total_amount` are `decimal.Decimal`
(shown above in its string serialization). Every row has `valid: true`.

### Evidence

`strategy` is `"LABEL_RIGHT"` and `page` is `1` for all ten — only `matched_label` and
`bbox` vary:

| Field | `matched_label` | `bbox` (`x0`, `y0`, `x1`, `y1`) |
|---|---|---|
| `invoice_number` | `Invoice Number` | `400.0, 65.25, 543.39, 78.99` |
| `invoice_date` | `Invoice Date` | `400.0, 81.25, 517.28, 94.99` |
| `due_date` | `Due Date` | `400.0, 97.25, 502.28, 110.99` |
| `supplier_vat_id` | `VAT Number` | `56.0, 113.25, 183.84, 126.99` |
| `customer_vat_id` | `Customer VAT Number` | `56.0, 409.25, 229.4, 422.99` |
| `currency` | `Currency` | `400.0, 113.25, 467.24, 126.99` |
| `vat_rate` | `VAT Rate` | `400.0, 627.25, 482.82, 640.99` |
| `subtotal` | `Subtotal` | `400.0, 609.25, 472.83, 622.99` |
| `vat_amount` | `VAT Amount` | `400.0, 645.25, 487.27, 658.99` |
| `total_amount` | `Total Due` | `400.0, 663.25, 479.49, 676.99` |

### `samples/acme_invoice.expected.json` — full literal contents

```json
{
  "fields": {
    "invoice_number": {
      "value": "INV-2024-0042",
      "raw_text": "Invoice Number: INV-2024-0042",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 400.0, "y0": 65.25, "x1": 543.39, "y1": 78.99 },
        "matched_label": "Invoice Number",
        "strategy": "LABEL_RIGHT",
        "raw_text": "Invoice Number: INV-2024-0042"
      }
    },
    "invoice_date": {
      "value": "2024-03-15",
      "raw_text": "Invoice Date: 15 Mar 2024",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 400.0, "y0": 81.25, "x1": 517.28, "y1": 94.99 },
        "matched_label": "Invoice Date",
        "strategy": "LABEL_RIGHT",
        "raw_text": "Invoice Date: 15 Mar 2024"
      }
    },
    "due_date": {
      "value": "2024-04-14",
      "raw_text": "Due Date: 14 Apr 2024",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 400.0, "y0": 97.25, "x1": 502.28, "y1": 110.99 },
        "matched_label": "Due Date",
        "strategy": "LABEL_RIGHT",
        "raw_text": "Due Date: 14 Apr 2024"
      }
    },
    "supplier_vat_id": {
      "value": "GB123456789",
      "raw_text": "VAT Number: GB123456789",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 56.0, "y0": 113.25, "x1": 183.84, "y1": 126.99 },
        "matched_label": "VAT Number",
        "strategy": "LABEL_RIGHT",
        "raw_text": "VAT Number: GB123456789"
      }
    },
    "customer_vat_id": {
      "value": "DE123456789",
      "raw_text": "Customer VAT Number: DE123456789",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 56.0, "y0": 409.25, "x1": 229.4, "y1": 422.99 },
        "matched_label": "Customer VAT Number",
        "strategy": "LABEL_RIGHT",
        "raw_text": "Customer VAT Number: DE123456789"
      }
    },
    "currency": {
      "value": "GBP",
      "raw_text": "Currency: GBP",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 400.0, "y0": 113.25, "x1": 467.24, "y1": 126.99 },
        "matched_label": "Currency",
        "strategy": "LABEL_RIGHT",
        "raw_text": "Currency: GBP"
      }
    },
    "vat_rate": {
      "value": "20.00",
      "raw_text": "VAT Rate: 20.00%",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 400.0, "y0": 627.25, "x1": 482.82, "y1": 640.99 },
        "matched_label": "VAT Rate",
        "strategy": "LABEL_RIGHT",
        "raw_text": "VAT Rate: 20.00%"
      }
    },
    "subtotal": {
      "value": "490.00",
      "raw_text": "Subtotal: 490.00",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 400.0, "y0": 609.25, "x1": 472.83, "y1": 622.99 },
        "matched_label": "Subtotal",
        "strategy": "LABEL_RIGHT",
        "raw_text": "Subtotal: 490.00"
      }
    },
    "vat_amount": {
      "value": "98.00",
      "raw_text": "VAT Amount: 98.00",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 400.0, "y0": 645.25, "x1": 487.27, "y1": 658.99 },
        "matched_label": "VAT Amount",
        "strategy": "LABEL_RIGHT",
        "raw_text": "VAT Amount: 98.00"
      }
    },
    "total_amount": {
      "value": "588.00",
      "raw_text": "Total Due: 588.00",
      "valid": true,
      "evidence": {
        "page": 1,
        "bbox": { "x0": 400.0, "y0": 663.25, "x1": 479.49, "y1": 676.99 },
        "matched_label": "Total Due",
        "strategy": "LABEL_RIGHT",
        "raw_text": "Total Due: 588.00"
      }
    }
  },
  "line_items": [
    { "sku": "ACM-1001", "description": "Hex bolt M8 x 40, zinc", "quantity": "500", "unit_price": "0.12", "net_amount": "60.00" },
    { "sku": "ACM-2210", "description": "Bearing 6204-2RS", "quantity": "40", "unit_price": "3.85", "net_amount": "154.00" },
    { "sku": "ACM-3300", "description": "Steel bracket, 3 mm", "quantity": "120", "unit_price": "2.30", "net_amount": "276.00" }
  ],
  "findings": [],
  "layout_id": "acme",
  "source_path": "samples/acme_invoice.pdf"
}
```

---

## Sample: `nordic`

Supplier **Fjordvik Elektronik AB**, Göteborg, SE, VAT `SE556123456701`. Customer
**Solstrand Bygg AS**, Bergen, NO, VAT `NO987654321MVA`. Swedish labels, comma decimal /
space thousands (`"1 234,56"`), dates as `"2024-05-02"` (ISO 8601 — Swedish invoices
commonly print dates this way already), currency SEK, VAT 25%. Layout:
`layouts/nordic.json`. Same shape as `acme` throughout this section (see the shared
rules above and `acme`'s "Why every field is `LABEL_RIGHT`") — only content differs.

### Page content

**Supplier block** (`x=56`, zone **TOP_LEFT**):

| y | Text |
|---|---|
| 60 | `Fjordvik Elektronik AB` |
| 76 | `Industrivägen 12` |
| 92 | `411 04 Göteborg` |
| 108 | `Sweden` |
| 124 | `Momsreg.nr: SE556123456701` |

**Invoice metadata block** (`x=400`, zone **TOP_RIGHT**):

| y | Text |
|---|---|
| 60 | `FAKTURA` |
| 76 | `Fakturanummer: 2024-00873` |
| 92 | `Fakturadatum: 2024-05-02` |
| 108 | `Förfallodatum: 2024-06-01` |
| 124 | `Valuta: SEK` |

**Bill-to block** (`x=56`, zone **MIDDLE_LEFT**):

| y | Text |
|---|---|
| 340 | `Faktureras till` |
| 356 | `Solstrand Bygg AS` |
| 372 | `Fjellveien 5` |
| 388 | `5003 Bergen` |
| 404 | `Norway` |
| 420 | `Kundens momsreg.nr: NO987654321MVA` |

**Line-item table** — header at `y=460`, two rows:

| y | `sku` (56) | `description` (140) | `quantity` (320) | `unit_price` (370) | `net_amount` (450) |
|---|---|---|---|---|---|
| 460 | `Artikelnr` | `Beskrivning` | `Antal` | `Pris` | `Belopp` |
| 478 | `FJ-771` | `Kabelkanal 40x60, 2 m` | `30` | `89,00` | `2 670,00` |
| 496 | `FJ-902` | `Kopplingsdosa IP65` | `12` | `45,50` | `546,00` |

**Totals block** (`x=400`, zone **BOTTOM_RIGHT**):

| y | Text |
|---|---|
| 620 | `Netto: 3 216,00` |
| 638 | `Moms: 25,00%` |
| 656 | `Momsbelopp: 804,00` |
| 674 | `Att betala: 4 020,00` |

Arithmetic check: `2 670,00 + 546,00 = 3 216,00` = subtotal (Netto); `3216.00 × 25% =
804.00` = VAT amount (Momsbelopp); `3216.00 + 804.00 = 4020.00` = total (Att betala).
`findings` is `[]` here too.

### Expected scalar fields

| Field | Label | Raw text (drawn line) | Value | Zone |
|---|---|---|---|---|
| `invoice_number` | `Fakturanummer` | `Fakturanummer: 2024-00873` | `"2024-00873"` | TOP_RIGHT |
| `invoice_date` | `Fakturadatum` | `Fakturadatum: 2024-05-02` | `2024-05-02` | TOP_RIGHT |
| `due_date` | `Förfallodatum` | `Förfallodatum: 2024-06-01` | `2024-06-01` | TOP_RIGHT |
| `supplier_vat_id` | `Momsreg.nr` | `Momsreg.nr: SE556123456701` | `"SE556123456701"` | TOP_LEFT |
| `customer_vat_id` | `Kundens momsreg.nr` | `Kundens momsreg.nr: NO987654321MVA` | `"NO987654321MVA"` | MIDDLE_LEFT |
| `currency` | `Valuta` | `Valuta: SEK` | `"SEK"` | TOP_RIGHT |
| `vat_rate` | `Moms` | `Moms: 25,00%` | `25.00` | BOTTOM_RIGHT |
| `subtotal` | `Netto` | `Netto: 3 216,00` | `3216.00` | BOTTOM_RIGHT |
| `vat_amount` | `Momsbelopp` | `Momsbelopp: 804,00` | `804.00` | BOTTOM_RIGHT |
| `total_amount` | `Att betala` | `Att betala: 4 020,00` | `4020.00` | BOTTOM_RIGHT |

Every `Decimal` value above normalizes to plain `.`-decimal form regardless of how it
was printed — `"3 216,00"` (space thousands, comma decimal, per `layouts/nordic.json`)
becomes `Decimal("3216.00")`, exactly as `docs/LAYOUT_FORMAT.md`'s `parse_money` walk-
through describes. Every row has `valid: true`.

### Evidence

`strategy` is `"LABEL_RIGHT"` and `page` is `1` for all ten:

| Field | `matched_label` | `bbox` (`x0`, `y0`, `x1`, `y1`) |
|---|---|---|
| `invoice_number` | `Fakturanummer` | `400.0, 65.25, 529.5, 78.99` |
| `invoice_date` | `Fakturadatum` | `400.0, 81.25, 518.39, 94.99` |
| `due_date` | `Förfallodatum` | `400.0, 97.25, 517.83, 110.99` |
| `supplier_vat_id` | `Momsreg.nr` | `56.0, 113.25, 194.96, 126.99` |
| `customer_vat_id` | `Kundens momsreg.nr` | `56.0, 409.25, 243.86, 422.99` |
| `currency` | `Valuta` | `400.0, 113.25, 453.92, 126.99` |
| `vat_rate` | `Moms` | `400.0, 627.25, 466.69, 640.99` |
| `subtotal` | `Netto` | `400.0, 609.25, 468.38, 622.99` |
| `vat_amount` | `Momsbelopp` | `400.0, 645.25, 493.38, 658.99` |
| `total_amount` | `Att betala` | `400.0, 663.25, 486.73, 676.99` |

`samples/nordic_invoice.expected.json` follows the exact shape given in full for `acme`
above: the same five top-level keys in the same order, the same `FieldResultJSON` and
`EvidenceJSON` shapes, `"layout_id": "nordic"`, `"source_path":
"samples/nordic_invoice.pdf"`, and the ten fields plus two line items from the tables
in this section.
