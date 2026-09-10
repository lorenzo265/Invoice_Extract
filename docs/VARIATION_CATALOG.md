# Variation catalog

What real B2B invoices vary in, and the generator knob that reproduces each axis. This
is the coverage contract: `forge catalog` reports the corpus against exactly these rows.

## Language and locale

| Axis | Values in scope | Knob / mechanism |
|---|---|---|
| Language of labels | `en` (GB, IE), `de` (DE, AT, CH), `fr` (FR, BE, LU), `sv`, `da`, `no`, `fi`, `nl`, `es`, `pt`, `it`, `pl`, `cs`, `sk`, `el`, `tr` | one `VendorProfile` per language/country pair; label lexicon with 3–5 synonyms per field |
| Decimal separator | `,` (most of Europe) / `.` (GB, IE, and English-language exports) | profile |
| Thousands separator | `.`, ` ` (narrow space), `'` (CH), none | knob `thousands_variant` |
| Date format | `dd.mm.yyyy`, `dd/mm/yyyy`, `yyyy-mm-dd`, `d Month yyyy`, `dd-Mon-yyyy` | profile list, one drawn per document |
| Currency | EUR, GBP, SEK, DKK, NOK, CHF, PLN, CZK, TRY, HUF, ZAR | profile |
| Secondary currency echo | totals and VAT summary repeated in a second currency with the rate printed | knob `dual_currency_echo` |
| VAT id format | country prefix + national pattern (pattern-shaped, fictional digits) | profile |
| Diacritics | `ä ö ü ß é è ç å ø æ ő ł ś ż č ř ş ğ ı` and Greek | embedded font; profile lexicon; test string per language |

## Document type and structure

| Axis | Values | Knob |
|---|---|---|
| Document type | invoice; credit note referencing an invoice (negative amounts or "credit" wording) | `credit_note` |
| Pages | 1; 2 (the common case); 3–6 | `multi_page`, driven by item count and rows-per-page |
| Carry-forward | subtotal carried across pages ("carried forward" / "brought forward") | `carry_forward` |
| Page numbering | "Page x of y" in header or footer | `page_numbering` |
| Copy stamp | "COPY" / "DUPLICATE" text across the page | `stamp_copy` |

## Header and parties

| Axis | Values | Knob |
|---|---|---|
| Supplier block position | left, right, centred letterhead | template family |
| Metadata block form | label: value list; two-column bordered table; label above value | family (`classic` list, `tabular`, `stacked`) |
| Metadata content | invoice no., date, due date, supply/delivery date, order no., customer no., contract no., payment terms, our/your reference | `supply_date`, `extra_references` |
| Trap labels near the invoice date | order date, delivery date, print date, due date | `trap_labels` |
| Party blocks | bill-to only; bill-to + ship-to; bill-to + ship-to + mail-to; placeholder ("as bill-to") | `party_blocks`, `placeholder_addresses` |
| Customer VAT id placement | in bill-to block; in metadata; next to the supplier's (trap) | `customer_vat_position` |

## Line-item table

| Axis | Values | Knob |
|---|---|---|
| Column set | any subset/order of: pos, part number, description, quantity, unit, unit price, discount %, VAT code/rate, net amount; plus subscription columns: subscription id, billing cycle, period start/end, share %, remaining term | family + `column_set` |
| Description length | 1 line; wrapped to 2–3 lines | `wrapped_description` |
| Sub-items | indented component lines under a parent, with or without prices | `sub_items` |
| Item count | 1–40 | sampler |
| Section subtotals | groups with their own subtotal line | `section_subtotals` |
| Discount | per-line discount column or a discount line in totals | `discount` |
| Difficult descriptions | digits, commas, units and codes inside text ("M8 x 40, zinc", "IP65", "2,5 mm²") | catalogue |

## Totals and tax

| Axis | Values | Knob |
|---|---|---|
| Totals components | subtotal, VAT, total; plus shipping/freight, environmental fee, surcharge, consolidation fee, recycling fee, rounding | family + `charges` |
| Charge declared or not | printed as its own line, or silently folded into the total | `declared_charge` / `undeclared_charge` |
| VAT rates per document | 1, 2, 3 (standard, reduced, zero/exempt) | `multi_rate` |
| VAT summary form | none; list; table with rate/base/VAT columns; table with VAT codes and section headers | `vat_summary_table` |
| Exemption wording | reverse-charge / intra-community / export sentences when a rate is zero | `exemption_verbiage` |
| Rounding policy | per line then summed; or on the total | `rounding_per_line` / `rounding_total` |
| Amount in words | total spelled out | `amount_in_words` |

## Footer and noise

| Axis | Values | Knob |
|---|---|---|
| Bank details | IBAN (valid checksum, fictional bank), BIC, account holder | `bank_footer` |
| Legal text | registration court, managing director, tax number, terms of sale | `noise_footer` |
| Payment terms block | own block with due date, discount for early payment | `payment_terms_block` |
| Repeated letterhead | supplier name and VAT id on every page | `repeat_letterhead` |

## Coverage targets for the base corpus (~250 documents)

- Every profile × every family at least once.
- Every knob on in at least 10 documents and off in at least 10.
- Item counts: at least 20 documents with 1 item, 20 with 10+, 5 with 30+.
- Page counts: at least 60% two-page, 15% single-page, 10% three pages or more.
- Document types: at least 15% credit notes.
