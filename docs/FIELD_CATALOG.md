# Field catalog

The canonical names shared by the extractor (`InvoiceResult.fields`), the generator's
ground truth (`forge-truth/1`) and the benchmark. A name appears here once; code,
truth files and reports use it verbatim. Changing a name is a schema change with an ADR.

## Scalar fields (spec kind in parentheses)

| Name | Type | Normalisation | Spec kind |
|---|---|---|---|
| `invoice_number` | str | upper-case alphanumerics with `-` `/` | Label |
| `order_number` | str | idem | Label |
| `customer_number` | str | idem | Label |
| `invoice_date` | date | ISO-8601 | Label |
| `supply_date` | date | ISO-8601 | Label |
| `due_date` | date | ISO-8601 | Label |
| `supplier_vat_id` | str | country prefix + alphanumerics, upper-case | Anchor |
| `customer_vat_id` | str | idem | Label |
| `currency` | str | ISO 4217 code | Derived (vote over printed codes/symbols) |
| `iban` | str | spaces removed, upper-case, mod-97 valid | Label (pattern) |
| `document_type` | enum | `invoice` \| `credit_note`, `null` where no profile matched | stage 3 (`classify_document`) |

`document_type` is the one name here that no spec resolves: stage 3 settles it before any
spec runs, so it is published as `InvoiceResult.document_type` rather than in `fields`,
and the benchmark reports it in a section of its own beside them.

`iban` is the one that no label introduces in a way a lexicon could list. A vendor prints
its account number inside the run of text its bank details are, after the word `IBAN`,
which is the word in every language this repository speaks; so the profile declares the
shape rather than synonyms, `label_pattern` finds it, and the checksum — not the shape —
is what tells it from a VAT id, which is also two letters and then digits.

### Named here, read under another name

| Name | Where it is | Why |
|---|---|---|
| `secondary_currency` | `InvoiceResult.secondary_amounts.currency` | the echo is one record — an amount, the rate it was converted at and the currency it is in — and splitting the currency out of it would publish a code with nothing to spend it on. Measured under `secondary_amounts` in `benchmarks/latest.json` |
| `exchange_rate` | `InvoiceResult.secondary_amounts.exchange_rate` | idem: a rate is the rate *of* that echo. Measured under `secondary_amounts` |

### Named here and not read yet

`customer_country` waits, and so does the `country` of every party block, because the
derivation this catalog specifies for it — VAT prefix > bill_to > ship_to > postal
pattern — cannot be built from anything the repository holds, and cannot be measured by
the corpus if it were:

- The first rung is wrong without a table this repository has not got: Greece's VAT
  prefix is `EL` and its country code is `GR`, so a prefix read as a code is wrong on 10
  of the 250 documents; and `tr-TR` prints VAT ids with no prefix at all, so the rung
  yields nothing on 7 more.
- The other three rungs need country names per language and postal shapes per country.
  No profile key, lexicon entry or ADR says where that data lives, and deciding is a
  schema change rather than a field.
- The corpus cannot falsify it either way: every customer in it is in its supplier's own
  country, so a derivation that returned the supplier's country and nothing else would
  score 100 % and mean nothing. Measuring something that cannot fail is what ADR-0009
  says calibration may not do, and a field is no different.

The honest report is therefore that the field is named and not read, as `vat_code` and
`subscription` are below — not a hit rate that agrees with itself.

## Parties (`SectionSpec`, plus `AnchorSpec` for the supplier)

`supplier`, `bill_to`, `ship_to`, `mail_to`, each with `name`, `lines[]`, `country`,
`vat_id` (may be `null`); `placeholder: true` when the block says "as bill-to".

A block a document does not print is absent from `parties` rather than empty in it; a
party's `country` waits for the derivation that reads one (`customer_country`).

## Tables (`TableSpec`)

`line_items[]`: `pos`, `part_number`, `description`, `quantity`, `unit`, `unit_price`,
`discount_pct`, `vat_rate`, `vat_code`, `net_amount`, `sub_items[]`, `subscription`
(`id`, `billing_cycle`, `period_start`, `period_end`, `share_pct`, `remaining_term`).
`vat_summary[]`: `rate`, `code`, `base`, `vat`.

Every column is optional, because every column is a vendor's choice: a table that prints
no article number has rows without one. Each cell a row was read from carries its own box
(`cells`), which is `Evidence` at the grain a table has. `vat_code` and `subscription`
wait for a corpus that prints them; the corpus records a box for five of the nine
columns, so `benchmarks/README.md` scores those five and reports the rest as read and not
measured.

## Totals block (`BlockSpec`)

`totals`: `subtotal`, `vat_amount`, `total_amount`, `vat_rate`, `rounding`, `charges[]`
(`type` ∈ SHIPPING, ENVIRONMENTAL_FEE, SURCHARGE, CONSOLIDATION_FEE, RECYCLING_FEE,
ROUNDING, OTHER; `amount`; `vat_rate`; `declared`).
`secondary_amounts`: the same keys echoed in `secondary_currency`, plus `exchange_rate`.

The four amounts are fields of the catalog and are published in `InvoiceResult.fields`
like any other. The charges are not: a charge is a row of the block, and they are
published beside the fields as `InvoiceResult.charges`, each with the box it was read
from. `OTHER` is what a charge no line of the page declares is called — stage 5 finds it
in the arithmetic and cannot know what it is for (`docs/ENGINE_SPEC.md` §5), and
`declared` is `false` on it.

`vat_rate` is the one rate a single-rate document charges, printed beside the tax in the
totals block. A document that charges more than one carries them per line item and per
VAT-summary row instead, and the block prints no single rate: stage 5 fills it in from
the rate its VAT summary is mostly at, or — where it prints no summary either — from the
rate most of what it sold is charged at, and says which in a `Finding`.

## Custom fields

Declared per profile as `LabelSpec`s under `custom_fields[]`; they appear in
`InvoiceResult.fields` under their declared name and in the benchmark beside every other
field. The names this repository ships are five, all of them things a vendor prints
around its header block: `contract_number`, `our_reference`, `your_reference`,
`credit_reference` and `payment_terms`. All five are declared in
`profiles/_defaults.json`, so any vendor that prints one is read. Four are references and
are judged as such; `payment_terms` is a sentence, and a sentence has no shape worth
declaring — it is judged by reading like one (`is_sentence`). A name here is a name like
any other in this catalog: the generator writes it into the truth under the same string,
and a value the page never printed is absent rather than missed.

## Findings vocabulary

Codes are `snake_case` and stable; severity ∈ INFO / WARNING / ERROR. A finding that is
about one field names it. The codes a run can produce are the seventeen rule names of
`validation/` (ENGINE_SPEC §6 and §7, one per rule), `invariant_exempt`, the
reconciliation's `backfilled_from_summary`, `backfilled_from_line_items`,
`vat_implied_from_total`, `undeclared_charge_inferred`, `totals_summary_disagree` and
`vat_line_ambiguous`, the table's `line_item_cell_unreadable` and
`line_items_header_not_found`, the engine's `field_missing`, and `profile_not_detected`.

`field_missing` is what a `LabelSpec` or an `AnchorSpec` reports when it resolved nothing
and the profile marks the field `required` — the vendor's own claim that every invoice it
sends carries the field, against a document that does not. A field the profile marks
optional is one the vendor prints only sometimes, and a document without it contradicts
nothing. The totals block has no such code: `subtotal`, `vat_amount`, `total_amount` and
`vat_rate` are components of a block rather than labelled fields, and a document missing
one is caught by the arithmetic instead (§6), which says more than its absence would.

Beside the findings, a result carries a `Check` per rule — its code, whether it passed,
the fields it is about and the arithmetic it came to — because a rule that held and one
that never applied are different facts and the findings alone cannot tell them apart.
