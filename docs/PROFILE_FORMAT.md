# Profile format

A **profile** describes one vendor's invoices: language, locale, currencies, VAT rules,
the label vocabulary of every field, where things are expected on the page, how the
tables and the totals block look, and the variants the vendor prints. It is JSON, one
file per profile under `src/invoice_extractor/data/profiles/`, which is inside the package so that
`pip install` carries it, read by exactly one module (`profile/loader.py`) into a typed
`Profile`. A deployment keeping its own vendors elsewhere passes that directory to
`ProfileRegistry` or to `--profiles`; everything below applies to it identically. Nothing else in this package
parses the JSON. There is **one** schema: the dataclasses in `profile/schema.py`; the
loader validates strictly and raises `ProfileError` whose message names the offending
key path.

Profiles are the successor of v0.1's layouts. The generator (`invoice_forge`) and the
extractor share the same profile files (ADR-0006): the generator draws what a profile
describes, the extractor reads it back. Each program validates the half it needs and
names the other half without parsing it, so neither can quietly stop describing the same
vendor. The generator's half is the `render` object; everything else is this document.

## Layering

`_defaults.json` → `<id>.json` → the matching `variants[]` entry.
One merge function, one rule table (`profile/merge.py`): the key paths listed in
`APPEND_PATHS` — every label vocabulary, and `custom_fields` — are appended and
de-duplicated; everything else is replaced. The merged result is what every stage sees.

`custom_fields` appends because the defaults say what any vendor *may* print in its
header block and a profile says what this one usually prints: a document that carries a
reference its vendor rarely prints is still read, and a vendor that words the reference
its own way adds that wording rather than losing the shared one.

## Labels come from the language

A vendor's words for "invoice number" are its language's words, and the generator prints
them from `<language>.json` in the `lexicon/` directory beside the profiles'. Repeating those lists inside
every profile would be sixteen languages copied into twenty-two files, so a label list
may **reference** them instead: an entry of the form `"@<map>.<key>"` expands to every
synonym the lexicon offers under that key, and `"@<list>"` expands a plain list of
phrases. A plain string beside a reference is a label only this vendor prints. The
reference is resolved while the profile is loaded; nothing downstream knows a lexicon
exists.

```json
"invoice_number": { "labels": ["@header_labels.invoice_number", "Beleg-Nr."] }
```

A reference no lexicon entry names is a `ProfileError`, like any other bad key.

## Top-level keys

| Key | Type | Required | Meaning |
|---|---|---|---|
| `id` | str | yes | profile id; `InvoiceResult.profile_id` |
| `language` | str (ISO 639-1) | yes | selects the default lexicon |
| `country` | str (ISO 3166-1 alpha-2) | yes | supplier country |
| `lexicon` | str | yes | the language's label vocabulary, `<id>.json` in the `lexicon/` beside the profiles |
| `number_format` | `{decimal_separator, thousands_separators[]}` | yes | drives every numeric parse; no fallback exists in code |
| `date_formats` | list[str] | yes | one of `yyyy-mm-dd`, `dd.mm.yyyy`, `dd/mm/yyyy`, `d Month yyyy`, `dd-Mon-yyyy`; the generator prints them and the loader turns them into the `strptime` patterns that read them back |
| `currencies` | list[str] | yes | accepted ISO 4217 codes; the first is the default, the second the one a document echoes |
| `vat` | `{rates{}, id_pattern, id_prefix}` | yes | `rates` maps `standard`/`reduced`/`zero` to decimal strings; `id_pattern` is a regex for what follows the prefix, and `id_prefix` may be empty where a country's VAT id carries none |
| `supplier` | `{name, aliases[], address_lines[], vat_id}` | yes | this vendor as it prints itself: the expected values for the `AnchorSpec`s, and what the generator draws |
| `render` | object | yes | the generator's half of the file; this package names it and reads nothing inside it |
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

A format that spells its month sorts after one that reads digits, because `strptime`
reads month names in the C locale only.

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
| `columns` | map canonical column → `labels[]` (at least `description` and `net_amount` for line items; `rate` and `vat` for the VAT summary) |
| `min_header_matches` | int (default 3) |
| `stop_labels[]` | end of the table on a page |
| `page_bounds` | `{"start": "header", "end": "totals_anchor" \| "stop_label"}` — the shipped defaults end both tables at a stop label: the totals anchor is found before any vendor is known, and a page whose rows wrap reads it in the wrong place |
| `carry_forward_labels[]` | lines to skip as rows and to check as running subtotals |
| `sub_item_indent` | float (points) to classify sub-items |
| `number_columns[]` | columns parsed with the profile's number format |

## `BlockProfile` (totals)

| Key | Meaning |
|---|---|
| `components` | map component → `{labels[], kind: "amount" \| "charge" \| "rate", charge_type?, accumulate?}` — `subtotal`, `vat_amount`, `total_amount` are required components |
| | `amount` is a line of money the identity is made of; `charge` is money added to it and named as a charge, with `charge_type` naming which of the catalog's kinds it is; `rate` is the one rate a single-rate document prints in its block, read without its sign and added to nothing |
| `cluster_gap` | float, vertical gap (fraction of page height) that closes the block (default 0.08) |
| `secondary_echo` | `{labels[], rate_labels[]}` or absent |
| `tolerance` | `{absolute: "0.02", relative: "0.005"}` |

## Worked example

`src/invoice_extractor/data/profiles/de-DE.json`, in full — everything it does not say,
`_defaults.json` and the `de` lexicon beside it say:

```json
{
  "id": "de-DE",
  "language": "de",
  "country": "DE",
  "lexicon": "de",
  "number_format": { "decimal_separator": ",", "thousands_separators": [".", " "] },
  "date_formats": ["dd.mm.yyyy", "d Month yyyy"],
  "currencies": ["EUR", "USD"],
  "vat": {
    "rates": { "standard": "19", "reduced": "7", "zero": "0" },
    "id_prefix": "DE",
    "id_pattern": "\\d{9}"
  },
  "supplier": {
    "name": "Nordlicht Industriebedarf GmbH & Co. KG",
    "aliases": ["Nordlicht"],
    "address_lines": ["Am Hafen 60", "91195 Leipzig", "Deutschland"],
    "vat_id": "DE879668745"
  },
  "custom_fields": [
    { "name": "contract_number", "labels": ["@header_labels.contract_number"],
      "zones": ["r1c3", "r1c2"], "required": false }
  ],
  "render": { "address_format": { "postal_code_position": "before_city", "country_line": true },
              "charges_used": ["SHIPPING", "ENVIRONMENTAL_FEE", "SURCHARGE"],
              "prints_supply_date": true, "credit_note_style": "negative_amounts",
              "families": ["classic", "tabular", "stacked", "saas", "minimal"],
              "fonts": "sans" }
}
```

And the excerpt of `_defaults.json` those keys are laid over:

```json
{
  "fields": {
    "invoice_number": { "labels": ["@header_labels.invoice_number"], "zones": ["r1c3", "r1c2"] },
    "invoice_date": { "labels": ["@header_labels.invoice_date"], "zones": ["r1c3", "r1c2"] }
  },
  "line_items": {
    "columns": { "part_number": ["@column_headers.part_number"],
                 "description": ["@column_headers.description"],
                 "quantity": ["@column_headers.quantity"],
                 "unit_price": ["@column_headers.unit_price"],
                 "net_amount": ["@column_headers.net_amount"] },
    "stop_labels": ["@totals_labels.subtotal", "@totals_labels.total_amount"],
    "page_bounds": { "start": "header", "end": "stop_label" },
    "carry_forward_labels": ["@carry_forward.incoming", "@carry_forward.outgoing"]
  },
  "totals": {
    "components": { "subtotal": { "labels": ["@totals_labels.subtotal"] },
                    "vat_amount": { "labels": ["@totals_labels.vat_amount"] },
                    "total_amount": { "labels": ["@totals_labels.total_amount"] },
                    "vat_rate": { "labels": ["@totals_labels.vat_rate"], "kind": "rate" },
                    "shipping": { "labels": ["@charge_labels.SHIPPING"],
                                  "kind": "charge", "charge_type": "SHIPPING" } },
    "tolerance": { "absolute": "0.01", "relative": "0.005" }
  },
  "document_types": { "invoice_titles": ["@document_titles.invoice"],
                      "credit_note_titles": ["@document_titles.credit_note"],
                      "credit_reference_labels": ["@header_labels.credit_reference"] },
  "noise": { "ignore_labels": ["@trap_labels.order_date", "@trap_labels.delivery_date",
                               "@trap_labels.print_date"] }
}
```

## `invariants`

| Key | Meaning |
|---|---|
| `exempt` | `[{code, reason}]` — the arithmetic rules this vendor's invoices are not held to, each with the reason it does not apply (e.g. a reverse-charge invoice states no tax). `code` must name one of the rules in `docs/ENGINE_SPEC.md` §6 and §7; the exemption is reported as an INFO finding, so it is visible in the result rather than silent |

## `profile draft`

`invoice-extractor profile draft <pdf> --out <dir> [--id <id>] [--language <code>]`
writes `<dir>/<id>.json` — the overlay a person would otherwise start from a blank file —
and `<dir>/../drafts/<id>.json` beside it, with the reason for every key. The layout is
the one the loader already imposes: `profiles/`, `lexicon/` and `drafts/` are siblings,
so `--out vendors/profiles` is the same directory `--profiles vendors/profiles` reads.
Where `<dir>` has no `_defaults.json` the draft copies the one it was made against, and
where `lexicon/` beside it lacks the page's language it copies that too — or writes a
skeleton with `?` in every entry where no shipped lexicon speaks the language.

What the draft writes, and from what:

| Key | Read from |
|---|---|
| `language`, `lexicon` | the lexicon whose entries the page prints most (three or more), or `--language`; else `und`, ISO 639-2 for *undetermined* |
| `supplier.name`, `address_lines` | the letterhead: the left-margin lines above the first gap, labelled lines left out |
| `supplier.vat_id`, `country`, `vat.id_prefix`, `vat.id_pattern` | the value labelled as the supplier's id, else the first value shaped like a known country's id and not labelled as the customer's; the pattern is the known country's, or read off the id itself |
| `number_format` | the decimal separator most amounts with decimals used, and every thousands separator seen beside it |
| `date_formats` | every named format a printed date fits, most often first; both slashed formats where no date settles the order, and the evidence says to choose |
| `currencies` | the codes labelled as the currency, then any known code printed anywhere |
| `vat.rates` | the percentages printed, most frequent as `standard`, next as `reduced`, `0` as `zero` |
| `fields.<name>.zones` | the zone the *value* sat in, for every field the defaults declare whose label a lexicon spells; a label only another language spells is added to the field's `labels` |
| `parties.<name>.zones` | the zone each party heading sat in |

Everything else stays with `_defaults.json`. A key the page gave nothing for is written
as `?` — a placeholder the loader refuses by name, so a profile with a hole in it cannot
read a document — and the summary lists every one. The evidence file also carries the
column headings, party headings, charges, titles and traps the page printed, and the
`unmapped` worksheet: every labelled value no lexicon names, with its shape (a date, an
amount, a percentage, a VAT id of which country) and its zone. On a page in a new
language that worksheet is the lexicon, waiting to be written.

## `profile lint`

`invoice-extractor profile lint <id>` reports, per field, how many labels and zones the
profile declares against the median of all profiles, whether the generator can render
the profile, and the readiness tier: **T0** (a required field has no labels), **T1**
(every required field has labels but some have no zones or fewer than the median), **T2**
(at or above the median everywhere and the benchmark for this profile is green). A new
profile ships at T2 or is marked experimental in its `id` suffix.
