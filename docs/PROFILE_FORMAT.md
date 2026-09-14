# Profile format

A **profile** describes one vendor's invoices: language, locale, currencies, VAT rules,
the label vocabulary of every field, where things are expected on the page, how the
tables and the totals block look, and the variants the vendor prints. It is JSON, one
file per profile under `profiles/`, read by exactly one module (`profile/loader.py`)
into a typed `Profile`. Nothing else parses the JSON. There is **one** schema: the
dataclasses in `profile/schema.py`; the loader validates strictly and raises
`ProfileError` whose message names the offending key path.

Profiles are the successor of v0.1's layouts. The generator (`invoice_forge`) and the
extractor share the same profile files: the generator draws what a profile describes,
the extractor reads it back.

## Layering

`profiles/_defaults.json` → `profiles/<id>.json` → the matching `variants[]` entry.
One merge function, one rule table: keys listed under `merge.append` are appended and
de-duplicated; everything else is replaced. The merged result is what every stage sees.

## Top-level keys

| Key | Type | Required | Meaning |
|---|---|---|---|
| `id` | str | yes | profile id; `InvoiceResult.profile_id` |
| `language` | str (ISO 639-1) | yes | selects the default lexicon |
| `country` | str (ISO 3166-1 alpha-2) | yes | supplier country |
| `number_format` | `{decimal_separator, thousands_separators[]}` | yes | drives every numeric parse; no fallback exists in code |
| `date_formats` | list[str] | yes | `strptime` patterns tried in order |
| `currencies` | list[str] | yes | accepted ISO 4217 codes; the first is the default |
| `vat` | `{rates[], id_pattern, id_prefix}` | yes | rates as decimal strings; pattern is a regex without the prefix |
| `supplier` | `{name, aliases[], address_lines[], vat_id}` | yes | expected values for the `AnchorSpec`s |
| `zones` | `{grid: [rows, cols]}` | no (default `[3, 3]`) | zone names are `r<i>c<j>`, 1-based; the nine 3×3 names (`top_left`…) are accepted aliases |
| `fields` | map name → `FieldProfile` | yes | one entry per scalar/label field the profile prints |
| `parties` | map `{bill_to, ship_to, mail_to}` → `SectionProfile` | yes | labels, stop labels, placeholders |
| `line_items` | `TableProfile` | yes | header labels per column, stop labels, page bounds |
| `vat_summary` | `TableProfile` | no | absent = the vendor prints no VAT summary |
| `totals` | `BlockProfile` | yes | components, charges, secondary echo |
| `custom_fields` | list[`CustomFieldProfile`] | no | `LabelSpec`s declared as data |
| `variants` | list[`{id, when, overlay}`] | no | `when` ∈ `{document_type, any_text}`; overlay is a partial profile |
| `document_types` | `{invoice_titles[], credit_note_titles[], credit_reference_labels[]}` | yes | for `classify_document` |
| `noise` | `{ignore_labels[]}` | no | labels known to be traps (order date, print date…) |

Unknown key at any level: `"<path> is not a recognized key"`. Missing required key:
`"<path> is required"`. Wrong type: `"<path> must be <description>"`.

## `FieldProfile`

| Key | Type | Meaning |
|---|---|---|
| `labels` | list[str], non-empty | label synonyms as printed, without trailing colon |
| `zones` | list[zone name] | preference, not a fence |
| `placement` | `right` \| `below` \| `pattern` (default `right`) | which label strategy leads; the others are fallbacks in fixed order |
| `pattern` | str (regex) | required when `placement = pattern`; optional validator otherwise |
| `required` | bool (default true) | a missing required field yields `Finding(WARNING, "field_missing")` |
| `exclude_labels` | list[str] | labels that must not be read as this field (traps) |

## `SectionProfile` (parties)

`labels[]`, `stop_labels[]`, `max_lines` (default 6), `placeholders[]`
("as bill-to", "same as above"…), `zones[]`.

## `TableProfile` (line items, VAT summary)

| Key | Meaning |
|---|---|
| `columns` | map canonical column → `labels[]` (at least `description` and one amount column for line items; `rate` and `vat` for the VAT summary) |
| `min_header_matches` | int (default 3) |
| `stop_labels[]` | end of the table on a page |
| `page_bounds` | `{"start": "header", "end": "totals_anchor" \| "stop_label"}` |
| `carry_forward_labels[]` | lines to skip as rows and to check as running subtotals |
| `sub_item_indent` | float (points) to classify sub-items |
| `number_columns[]` | columns parsed with the profile's number format |

## `BlockProfile` (totals)

| Key | Meaning |
|---|---|
| `components` | map component → `{labels[], kind: "amount" \| "charge", charge_type?, accumulate?}` — `subtotal`, `vat_amount`, `total_amount` are required components |
| `cluster_gap` | float, vertical gap (fraction of page height) that closes the block (default 0.08) |
| `secondary_echo` | `{labels[], rate_labels[]}` or absent |
| `tolerance` | `{absolute: "0.02", relative: "0.005"}` |

## Worked example (excerpt)

```json
{
  "id": "de-DE",
  "language": "de", "country": "DE",
  "number_format": { "decimal_separator": ",", "thousands_separators": ["."] },
  "date_formats": ["%d.%m.%Y", "%d. %B %Y"],
  "currencies": ["EUR"],
  "vat": { "rates": ["19", "7", "0"], "id_prefix": "DE", "id_pattern": "[0-9]{9}" },
  "supplier": { "name": "Rheinwerk Industriebedarf GmbH", "aliases": ["Rheinwerk"], "address_lines": ["Am Hafen 27", "47119 Duisburg"], "vat_id": "DE811234567" },
  "fields": {
    "invoice_number": { "labels": ["Rechnungsnummer", "Rechnungs-Nr."], "zones": ["r1c3"] },
    "invoice_date":   { "labels": ["Rechnungsdatum"], "zones": ["r1c3"], "exclude_labels": ["Bestelldatum", "Lieferdatum"] }
  },
  "line_items": { "columns": { "part_number": ["Artikel-Nr."], "description": ["Beschreibung"], "quantity": ["Menge"], "unit_price": ["Einzelpreis"], "vat_rate": ["USt %"], "net_amount": ["Betrag EUR"] },
                  "stop_labels": ["Nettosumme"], "page_bounds": { "start": "header", "end": "totals_anchor" }, "carry_forward_labels": ["Übertrag"] },
  "totals": { "components": { "subtotal": { "labels": ["Nettosumme"] }, "vat_amount": { "labels": ["Umsatzsteuer gesamt"] }, "total_amount": { "labels": ["Rechnungsbetrag"] },
                              "shipping": { "labels": ["Versandkosten"], "kind": "charge", "charge_type": "SHIPPING" } },
              "secondary_echo": { "labels": ["Gegenwert"], "rate_labels": ["Kurs"] } },
  "document_types": { "invoice_titles": ["RECHNUNG"], "credit_note_titles": ["GUTSCHRIFT"], "credit_reference_labels": ["zu Rechnung"] }
}
```

## `profile lint`

`invoice-extractor profile lint <id>` reports, per field, how many labels and zones the
profile declares against the median of all profiles, whether the generator can render
the profile, and the readiness tier: **T0** (a required field has no labels), **T1**
(every required field has labels but some have no zones or fewer than the median), **T2**
(at or above the median everywhere and the benchmark for this profile is green). A new
profile ships at T2 or is marked experimental in its `id` suffix.
