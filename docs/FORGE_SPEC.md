# `invoice_forge` — synthetic invoice corpus generator

`invoice_forge` produces realistic B2B invoice PDFs with exact ground truth, in the
languages and layouts European invoices actually come in, from a seed. It is the
proving ground for `invoice_extractor`: accuracy is measured against a corpus in which
every value, label and position is known, and reported per axis of variation.

Read with `docs/VARIATION_CATALOG.md` (what varies), `docs/GROUND_TRUTH_SCHEMA.md` (what
is recorded) and `docs/reference/forge/prototype/` (what "realistic" looks like).

## 1. Principles

- **Fiction by construction.** Company names, addresses, VAT ids, IBANs, product
  catalogues and label lexicons are generated or dictionary words. No real company,
  bank or invoice is copied.
- **Consistent by construction.** Totals derive from items and charges; the rounding
  policy is a knob. A generated document never contradicts itself unless a knob says
  so, and then the truth records it.
- **Deterministic.** Same seed, profile, family and knobs → byte-identical PDF and truth.
- **Nothing hidden.** Everything in the truth is in the PDF text layer, visible, on the
  page the truth says. `forge verify` proves it after every generation.
- **The maximal family first.** `classic` carries every block a European invoice can
  have; simpler families are derived by switching blocks off, never written from
  scratch. That keeps one renderer and one truth builder honest for all families.

## 2. Package layout

```
src/invoice_forge/
  __init__.py            Knob, __version__
  cli.py                 forge generate | catalog | verify | render-one (the argument surface)
  commands.py            what each subcommand does, once its arguments are parsed
  profiles/              one JSON per vendor profile (+ profiles/schema.py, loader.py)
  lexicon/               per-language label lexicons (JSON) + loader.py, spelling.py
  model/                 DocumentModel: parties, identifiers, dates, money, items, charges, vat, payment
  sample/                ContentSampler: catalogues, names, addresses, ids, IBAN/VAT generators
  layout/                TemplateFamily declarations: spec.py, columns.py, classic.py,
                         derived.py (tabular, stacked, saas, minimal), variants.py (knobs)
  render/                pdf.py (the only pymupdf importer besides the extractor's reader), sheet.py,
                         text.py, wording.py, table.py, pagination.py, header.py, blocks.py,
                         summary.py, totals.py, placement.py, context.py, renderer.py
  truth/                 builder.py, values.py, locate.py (writing) + verify.py, checks.py,
                         readback.py, reading.py (proving)
  corpus/                plan.py (forge-plan/1), generate.py, survey.py, catalog.py
  produce.py             one cell of a corpus: sample, render, read back, write both files
  fonts/                 Liberation Sans/Serif + LICENSE
  knobs.py               the closed vocabulary of difficulty knobs
  fields.py              the canonical field names, restated from the extractor and tied by a test
tests/forge/             unit (no PDF) + integration (small corpus, determinism, verify)
benchmarks/              make bench output: latest.json + README.md
```

## 3. Components

### 3.1 `VendorProfile` (data)

One JSON per profile. Keys: `id`, `country`, `language`, `currency`,
`secondary_currency` (optional), `decimal_separator`, `thousands_separators` (list to
draw from), `date_formats` (list), `vat_rates` (`standard`, `reduced`, `zero`),
`vat_id_pattern`, `address_format` (postal code position, country line), `lexicon`
(language id; per-profile overrides allowed), `charges_used`, `prints_supply_date`,
`credit_note_style` (`negative_amounts` | `credit_wording`), `extensions` (custom
fields such as contract number), `families` (which template families apply), `fonts`
(`sans` | `serif`). Initial profiles, in build order: `en-GB`, `de-DE`, `fr-FR`, `sv-SE`;
then `en-IE`, `de-AT`, `de-CH`, `fr-BE`, `fr-LU`, `nl-NL`, `nl-BE`, `da-DK`, `no-NO`,
`fi-FI`, `es-ES`, `pt-PT`, `it-IT`, `pl-PL`, `cs-CZ`, `sk-SK`, `el-GR`, `tr-TR`. All
twenty-two are bundled, and nothing falls back: a profile whose language or country the
word tables do not cover is refused by name rather than printed in English.

### 3.2 Lexicon (data)

Per language: for each canonical field, 3–5 label synonyms as printed on real-world
invoices of that language, plus the table header words per column, the totals
component labels, the document-type titles (invoice, credit note), the trap labels
(order date, delivery date, print date), the carry-forward wording, the exemption
sentences, and the amount-in-words rules. English is always present as a fallback
synonym set, because bilingual invoices are common.

The amount-in-words rules are the one optional block. A lexicon declares them by naming
one of five joining styles — `english`, `germanic_compound`, `nordic_compound`,
`romance`, `spaced` — and the words each style joins. A language none of the five
spells writes no total in words at all: Finnish declines its numerals, Italian and
Spanish elide theirs, the Slavic languages inflect after the count, and a lexicon that
named a style anyway would print a total no native reader would accept. So
`amount_in_words` may be absent, and the `amount_in_words` knob prints nothing on a
document whose language has no rules for it. Eight of the sixteen bundled lexicons
spell: `en`, `de`, `nl`, `da`, `no`, `sv`, `fr`, `tr`.

### 3.3 `TemplateFamily` (code, declarative)

A family is a declaration of blocks, their placement and their style. Blocks are the
closed vocabulary below; a family lists which are present and how they look.

| Block | Options |
|---|---|
| `letterhead` | position left/right/centre; with a drawn text logo; repeated on every page or first only |
| `title` | document type title; optional copy stamp |
| `metadata` | `list` (label: value, right-aligned values), `table` (bordered two-column), `stacked` (label above value); content set |
| `parties` | 1–3 blocks (bill-to, ship-to, mail-to) in one or two rows; placeholder text allowed |
| `payment_terms` | own block or a sentence in the footer |
| `items` | column set and order; ruled or unruled; header wording; wrapped descriptions; sub-items; section subtotals; discount column |
| `pagination` | rows per page; carry-forward lines; "page x of y" placement |
| `vat_summary` | none / list / table / table with codes and sections |
| `totals` | component order; charges; rounding line; amount in words; secondary-currency echo |
| `payment` | IBAN/BIC block; QR-like placeholder box (drawn rectangle, no image) |
| `footer` | legal lines; terms; repeated per page |

Families in scope:

| Family | Definition |
|---|---|
| `classic` | **the maximal family**: every block present, `metadata` as list, two party blocks, ruled table with wrapped descriptions, carry-forward, VAT summary table, charges, secondary echo, payment block, legal footer. This is the prototype, extended. |
| `tabular` | `classic` with `metadata` as a bordered table and the VAT summary with codes and sections |
| `stacked` | labels printed above values (metadata and totals), unruled table — the layout that defeats "label to the right" strategies |
| `saas` | subscription columns (subscription id, billing cycle, period, share %, remaining term), sub-items, section subtotals |
| `minimal` | `classic` with pagination, VAT summary, parties beyond bill-to, payment block and footer switched off — the one-page simple invoice |

Every family is expressed as a `FamilySpec` value (frozen dataclass) consumed by the
same renderer; adding a family is adding a declaration and its golden test. A block a
family omits is `None` on that record, which is how the simpler families are `classic`
with blocks switched off rather than layouts of their own.

### 3.4 `DocumentModel` (code)

Frozen dataclasses: `Party`, `Identifiers`, `Dates`, `Money` (`Decimal` + currency),
`LineItem` (with optional `SubItem`s and `Subscription` fields), `Charge`
(`type`, `amount`, `vat_rate`, `declared`), `VatLine`, `Totals`, `Payment`,
`Document` (type, language, pages are decided at render time). `Totals` is computed
from items and charges by one function with the rounding policy as an argument; the
model never stores a total that was not computed.

### 3.5 `ContentSampler` (code)

`random.Random(seed)` only. Draws: a product catalogue by vendor domain (industrial
supplies, electronics, software subscriptions, services) with descriptions containing
digits, commas, units and codes; quantities (integer and fractional); prices (2 and 4
decimals); 1–40 items; 1–3 VAT rates by profile; charges by profile probability;
fictional company names by language morphology; addresses by profile format; VAT ids
matching the profile pattern; IBANs with a valid checksum and a fictional bank code;
credit notes by inverting an invoice and referencing it.

### 3.6 Renderer (code)

PyMuPDF only. Text placement through measured widths (`pymupdf.Font.text_length`) so
right-aligned amounts and wrapped descriptions are exact; drawn rules and boxes for
tables and the QR placeholder; page breaks with carry-forward; header/footer per page;
fonts embedded from `invoice_forge/fonts/`; metadata fixed; `save(garbage=4,
deflate=True, no_new_id=True)`. The renderer returns a `Placement` per value it printed —
what it says, which page, and the point it was drawn at — which the truth builder resolves
to bboxes by reading the PDF back and taking the occurrence nearest that point. Recording
the point is what keeps a string an invoice prints twice from being located at the wrong
one of them.

### 3.7 Truth builder and verification (code)

Builds `forge-truth/1` (see `docs/GROUND_TRUTH_SCHEMA.md`): normalised values from the
model, printed strings and labels from the renderer's placement log, bboxes from
`page.search_for` on the produced PDF (rounded to 2 decimals). `forge verify` re-opens
every PDF in a corpus and asserts: every truth evidence bbox contains its printed text
on that page; totals, VAT lines and item nets recompute; declared charges have
evidence and undeclared ones do not; the document is byte-identical to a regeneration
from its recorded seed/profile/family/knobs.

### 3.8 Knobs (code, closed vocabulary)

The knob names in `docs/VARIATION_CATALOG.md`, as an `Enum`. A knob affects the
sampler (what content), the family (which blocks), or the renderer (how), and the
truth records which knobs were on. Knobs have no free parameters; a variant that needs
a parameter is a second knob.

**A knob is the other value of its axis.** The catalog names an axis and the values in
scope; the family or the profile declares one of them, and turning the knob on replaces it
with the other. `classic` is the maximal family, so a knob that touches it usually takes
something away — `bank_footer` is the invoice that does not say where to pay it, and
`vat_summary_table` is the summary printed as a list rather than a table. A knob whose axis
a document does not have changes nothing: `dual_currency_echo` on a vendor that deals in
one currency, `party_blocks` on a family with one party column.

The three places a knob lands, and the module that owns each:

| Where | Module | Knobs |
|---|---|---|
| the family's declaration | `layout/variants.py` | `carry_forward`, `page_numbering`, `trap_labels`, `party_blocks`, `customer_vat_position`, `repeat_letterhead`, `column_set`, `discount`, `vat_summary_table`, `amount_in_words`, `exemption_verbiage`, `bank_footer`, `noise_footer`, `payment_terms_block`, `stamp_copy` |
| the document's content | `sample/variations.py` | `multi_page`, `wrapped_description`, `sub_items`, `section_subtotals`, `placeholder_addresses`, `multi_rate`, `charges`, `declared_charge`, `undeclared_charge`, `rounding_per_line`, `rounding_total`, `dual_currency_echo`, `credit_note`, `supply_date`, `extra_references` |
| the words it commits to | `render/wording.py` | `thousands_variant` |

Two knobs that name the two values of one axis cannot both be on. `knobs.check_knobs`
refuses the pair at `produce`, which every route into the generator passes through, so a
plan cell that asks for both rounding policies is a plan to fix rather than a document to
render.

A family implies content as well as layout — `saas` bills subscriptions in sections with
components under them, drawn from the domains billed by the period rather than by the
piece. That is what the family *is*, so `sample/variations.py` turns those on for it and
the truth still records only the knobs the plan asked for: the plan asked for `saas`.

## 4. CLI

```
forge generate --profiles en-GB,de-DE --families classic --count 20 --seed 42 --out corpus/
forge generate --plan corpus/plan.json          # a plan lists every (profile, family, knobs, seed) cell
forge catalog corpus/                            # coverage against VARIATION_CATALOG.md, as a table
forge verify corpus/                             # readback + arithmetic + determinism; non-zero exit on any failure
forge render-one --profile de-DE --family classic --knobs multi_page,dual_currency_echo --seed 7 --out one.pdf
```

A plan is `forge-plan/1`: one cell per document, so a corpus is a manifest rather than
a recipe with a random element.

```jsonc
{ "schema": "forge-plan/1",
  "cells": [ { "profile": "de-DE", "family": "classic", "seed": 7, "knobs": ["multi_page"] } ] }
```

`--profiles/--families/--count/--seed` builds the same plan in memory from the cross
product, and `generate` leaves the plan it ran beside the documents either way.

`make corpus` generates the base corpus into `corpus/` from `corpus/plan.json` (the
plan is committed; the PDFs are not — they are reproducible). `make bench` runs the
extractor over the corpus and writes `benchmarks/`.

## 5. Acceptance of the generator

1. `forge generate` twice with the same plan → identical SHA-256 for every file.
2. `forge verify` passes on the whole base corpus.
3. Every profile renders its language's diacritic test string; a golden PNG per
   profile × family is committed and compared pixel-exact.
4. `forge catalog` shows every coverage target in `docs/VARIATION_CATALOG.md` met.
5. A hygiene test asserts no string from a denylist of real-company patterns appears
   in profiles, lexicons or catalogues (the denylist itself is structural: legal-form
   suffixes attached to well-known brand stems are checked by pattern, not by a list
   of names).

## 6. Later families (not in this plan)

A Brazilian NF-e DANFE layout (dense bordered boxes, tax columns per item, access key
barcode area) is a natural fifth family and a strong demonstration of the block model;
it is deferred until the European families are complete.
