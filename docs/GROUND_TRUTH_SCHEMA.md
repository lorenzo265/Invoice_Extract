# Ground-truth schema

Every generated PDF is accompanied by one JSON file, `<stem>.truth.json`, that states
what the document contains and where. The benchmark compares the extractor's output
against it. This document is the contract.

## Design choice

Three options were weighed:

| Option | Verdict |
|---|---|
| Truth mirrors the extractor's `InvoiceResult.to_dict()` exactly | Rejected: couples the corpus to today's result shape; every result refactor would rewrite thousands of truth files, and the truth would inherit fields that describe the extractor (confidence, strategy) rather than the document. |
| Truth in a free, generator-owned shape with a custom comparison per field | Rejected: two vocabularies, one adapter per field, drift guaranteed. |
| **Truth uses the extractor's canonical field names, in a generator-owned, versioned shape that describes the DOCUMENT; the benchmark compares through the extractor's flat view** | **Chosen.** One vocabulary (the field names), zero per-field adapters, and the truth stays valid across extractor refactors. |

The extractor already exposes a flat, name-keyed view of a result (`fields` keyed by
name in `InvoiceResult.to_dict()`, line items as rows). The benchmark reads that view
and the truth's `fields`/`line_items` and compares name by name. Anything the extractor
adds later (a new field) is compared as soon as the generator emits it under the same
name; anything the extractor does not extract yet is reported as "not covered", never
as wrong.

## Shape (`schema: "forge-truth/1"`)

```jsonc
{
  "schema": "forge-truth/1",
  "generator": { "version": "0.1.0", "seed": 42, "profile": "de", "template": "classic",
                 "knobs": ["multi_page", "vat_summary_table", "dual_currency_echo", "declared_charge"] },
  "document": { "type": "invoice", "pages": 2, "language": "de", "currency": "EUR",
                "secondary_currency": "USD", "rounding": "per_line" },
  "fields": {                                  // canonical names; value is the NORMALISED value
    "invoice_number":  { "value": "RE-2024-004217", "printed": "RE-2024-004217", "label": "Rechnungsnummer",
                         "evidence": [{ "page": 1, "bbox": [453.2, 106.4, 545.0, 116.9] }] },
    "invoice_date":    { "value": "2024-03-15", "printed": "15.03.2024", "label": "Rechnungsdatum",
                         "evidence": [{ "page": 1, "bbox": [489.1, 118.4, 545.0, 128.9] }] },
    "subtotal":        { "value": "9965.24", "printed": "9.965,24 EUR", "label": "Nettosumme",
                         "evidence": [{ "page": 2, "bbox": [...] }] },
    "total_amount":    { "value": "10841.27", "printed": "10.841,27 EUR", "label": "Rechnungsbetrag",
                         "evidence": [{ "page": 2, "bbox": [...] }] },
    "supplier_vat_id": { "value": "DE811234567", "printed": "USt-IdNr.: DE811234567", "label": "USt-IdNr.",
                         "evidence": [{ "page": 1, "bbox": [...] }, { "page": 2, "bbox": [...] }] },
    "supply_date":     { "value": null, "printed": null, "label": null, "evidence": [] }   // absent on this document
  },
  "line_items": [
    { "pos": 1, "part_number": "SW-LIC-PRO", "description": "Softwarelizenz ProSuite, 1 Arbeitsplatz, 12 Monate",
      "quantity": "25", "unit_price": "349.00", "vat_rate": "7", "net_amount": "8725.00",
      "cells": { "part_number": { "page": 1, "bbox": [...] }, "description": [{ "page": 1, "bbox": [...] }, { "page": 1, "bbox": [...] }],
                 "quantity": { "page": 1, "bbox": [...] }, "unit_price": { "page": 1, "bbox": [...] }, "net_amount": { "page": 1, "bbox": [...] } },
      "sub_items": [] }
  ],
  "charges":     [ { "type": "SHIPPING", "amount": "24.90", "vat_rate": "19", "declared": true, "label": "Versandkosten",
                     "evidence": [{ "page": 2, "bbox": [...] }] } ],
  "vat_summary": [ { "rate": "7", "base": "8725.00", "vat": "610.75", "evidence": [ ... ] },
                   { "rate": "19", "base": "1265.14", "vat": "240.38", "evidence": [ ... ] } ],
  "secondary_amounts": { "total_amount": "11787.71", "exchange_rate": "1.0873", "evidence": [ ... ] },
  "parties": { "supplier": { "name": "...", "lines": [...], "vat_id": "DE811234567", "evidence": [...] },
               "bill_to":  { ... }, "ship_to": { ... }, "mail_to": null },
  "noise": [ { "kind": "footer_legal", "page": 1, "bbox": [...] }, { "kind": "trap_label", "label": "Bestelldatum", "page": 1, "bbox": [...] } ]
}
```

Rules:

- **`fields.<name>.value` is normalised** the way the extractor normalises: dates ISO-8601,
  money and rates as plain-decimal strings, identifiers upper-cased alphanumerics with
  country prefix. `printed` is the exact string on the page; `label` the label printed
  next to it, or `null` for label-less placements.
- **Every canonical field name is present**, with `null`s when the document does not
  carry it. The set of names is `docs/FIELD_CATALOG.md` (created in PR F0 from the
  extractor's specs) — the generator and the extractor share it.
- **`evidence` is a list**: a value printed twice (a VAT id in the letterhead of every
  page) has one entry per occurrence. Bboxes are read back from the produced PDF's text
  layer, rounded to 2 decimals; the generator never writes a bbox it did not read.
- **Undeclared amounts have no evidence.** A charge with `declared: false` is folded into
  the total and appears only in `charges`; that is the point of the knob.
- **`noise`** lists what was printed to mislead, so the benchmark can report which traps
  caused which misses.
- **Determinism**: the same seed, profile, template and knobs produce byte-identical PDF
  and truth files.

## Comparison rules used by the benchmark

| Field kind | Match when |
|---|---|
| Identifiers, currency, document type | exact string equality after normalisation |
| Dates | equal `date` |
| Money, rates, quantities | equal `Decimal` (no tolerance: the truth is exact) |
| Line items | same row count, then per-row equality of every column; an extra or missing row is one error per row |
| Charges | same set of `(type, amount)`; a `declared: false` charge is scored only on the totals it affects |
| Evidence | optional, reported separately: the extractor's bbox must intersect one of the truth's evidence bboxes on the same page |

The benchmark output is a matrix — field × profile × template × knob — of hit rate,
plus a calibration table (predicted confidence vs observed hit rate), written by
`make bench` to `benchmarks/latest.json` and rendered into `benchmarks/README.md`.
