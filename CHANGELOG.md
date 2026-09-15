# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

### Added

- **Ten invariants and seven cross-field checks, each recorded whether or not it had
  anything to say** (`validation/`, ENGINE_SPEC §6–§7). The arithmetic is asked ten
  questions — the block against itself, the rows against the block, the summary against
  both, the sign of the total against what kind of document it says it is — and the
  values are asked seven more: the dates in the order dates run in, the VAT prefix its
  country writes, one registration not being both parties, a credit note saying what it
  credits. Each answers yes, no, or *this document cannot be asked that*, and every
  answer becomes a `Check` on the result: a rule that held and a rule that never applied
  are different facts, and the findings alone could not tell them apart.
- **`InvoiceResult.checks`**, and a profile key to go with them: `invariants.exempt[]`
  excuses a vendor from a rule with a reason — a reverse-charge invoice states no tax and
  is right not to — and the exemption is reported as an INFO finding rather than being
  silent.
- **Sixteen named signals and a fitted confidence** (`scoring/`, ENGINE_SPEC §8). A
  field's confidence is the weighted mean of the signals it could emit — the label it
  matched and how near it was to the declared one, the shape of the value, the zone, how
  many candidates there were and how clearly the winner won, which rules corroborate it,
  how well the vendor was recognised, how much of the document came back. A signal a
  field cannot be asked is absent rather than zero, and the weights are renormalised over
  the ones it did emit. `confidence_breakdown` now carries those signals, so any number
  the extractor prints can be taken apart by the reader (ADR-0002 for the confidence).
- **`invoice-extractor calibrate`** and the `calibration/` it writes (ENGINE_SPEC §9):
  weights fitted where a corpus with known answers got a field wrong, a monotone curve
  per field saying what a score of each size has been worth, and
  `reliability_report.json` — predicted against observed, in ten bands, per field. Same
  corpus, same files, byte for byte. Every band is credited with one hit and one miss
  before it is believed, so a fit never claims more than the corpus behind it supports.
- On the 250-document corpus: the confidences are off by **0.5 %** on average (expected
  calibration error 0.0048, against the ≤ 0.05 the plan asks for), and `make bench` now
  reports that figure beside the calibration curve.
- **`BlockSpec`: the totals block, read as the block it is.** The block is the run of
  rows that names the most of a profile's components, in one column, close together — so
  a table heading that says `VAT %` loses to a block that names four — and the longest
  label a row starts with is what names it, so `Total VAT` is the tax and not the total.
  An amount is read beside its label, or, where a vendor stacks them, at the label's own
  x on the next row. A block that prints its amounts twice is read in the column where
  net plus tax plus charges comes to the total.
- **Charges and the second currency** (`domain/totals.py`): `InvoiceResult.charges` and
  `InvoiceResult.secondary_amounts`. A charge the page names carries its type and the box
  it was read from; the total echoed in another currency carries that currency, what it
  comes to and the rate it was converted at.
- **Stage 5, reconciliation** (`reconcile/`): the five functions of `ENGINE_SPEC.md` §5.
  The tax a block does not state comes from the VAT summary, else from what the total
  adds to the net where that could be a rate at all; the one rate a multi-rate document
  is at comes from the rate its summary is mostly at, or from the rate most of what it
  sold is charged at; what the total carries that nothing declares is a charge, reported
  as one; where the summary and the block disagree, both are said out loud and the
  disagreeing field is capped at half its confidence. Everything filled in is a `Finding`
  (ADR-0005) and points at what it was worked out from (ADR-0002).
- On the 250-document corpus: **every totals field right on every family** — `subtotal`
  1.000 (was 0.992), `vat_rate` 1.000 (was 0.964), `vat_amount` and `total_amount` 1.000
  — every charge the corpus prints read with its type and amount (19 of 19), every
  undeclared charge found in the arithmetic (13 of 13), and every second-currency echo
  read with its rate (5 of 5).
- **`TableSpec`: the line items and the VAT summary, read cell by cell.** A table's
  columns are where *this document* drew them — the header words say so, and a cell
  belongs to the heading whose edge it lines up with — and a state machine says what each
  printed row under the header is: a row, the rest of a description, a component indented
  under its row, the line a page break carried, a section's own subtotal, or the totals
  block that ends the table. A table that runs over a page break is one table.
- **`SectionSpec`: the party blocks.** A heading, then the column under it, down to a
  stop label, a gap, or the profile's `max_lines`. A name too wide for its column is set
  over two lines and read back as one name, because the page sets a name in its own
  weight; a block that says `same as billing address` defers rather than fails; a VAT id
  printed inside the block is a value and not a line of the address.
- **Rows, parties and VAT lines in the result** (`domain/rows.py`, `domain/parties.py`):
  `InvoiceResult.parties` and `InvoiceResult.vat_summary` beside `line_items`, each row
  carrying the box every cell of it was read from (ADR-0002). A `LineItem` now holds the
  nine columns `docs/FIELD_CATALOG.md` names, its components, and those boxes.
- **A line's drawn runs.** `TextLine.parts` keeps the runs a reader joined into one line,
  with the box and the weight of each: two column headings a few points apart arrive as
  one line, and a table's columns are exactly what those two boxes say.
- On the 250-document corpus: **every document's row count read exactly** (250 of 250,
  up from 49), every scored line-item cell right (5,927 rows), every VAT-summary line and
  cell right, and every party block's name and address right. No scalar field moved.

### Changed

- **The confidence is fitted rather than assumed.** The five hand-weighted signals of
  v0.1 are gone; a field with no fitted weights is scored with the uniform mean and says
  so in `confidence_source`. The text report prints the seventeen checks in place of the
  three invariants, each with the arithmetic it came to.
- **The totals are read from the block, not from labels.** `subtotal`, `vat_amount`,
  `total_amount` and `vat_rate` are published by the `BlockSpec` rather than by four
  `LabelSpec`s, with `Strategy.BLOCK_ROW` on their evidence. The units only those four
  specs named — `parse_money`, `parse_percent`, `is_money`, `is_percent`, `looks_numeric`
  and `last_page_first` — are gone with them: the vocabulary is closed in both directions
  (`ENGINE_SPEC.md` §3), and a unit nothing names is code that cannot run.
- **The arithmetic knows about charges.** `totals_reconcile` adds every charge the
  document carries, and `vat_rate_consistent` taxes the net plus the charges the block
  declared — and does not run at all on a document its summary shows is at more than one
  rate, which is what `vat_equals_subtotal_times_rate` has always meant.
- **The line-item table ends at a stop label** rather than at the totals anchor: the
  anchor is found before any vendor is known, and a page whose descriptions wrap reads it
  in the wrong place. `page_bounds` still says which, per profile.
- **A VAT summary is not read out of a line-item header.** The two vocabularies overlap —
  `Rate`, `Net`, `VAT Code` — so a row that names more of the other table's columns than
  of this one's is that table's header. A vendor that prints the summary as a line per
  rate instead of a table is read by the same labels.
- **The benchmark scores a cell only where the corpus says one was printed.** The truth
  records a box per cell a document drew; a column a vendor does not print is `absent` and
  scored in neither direction, as an absent field already was. Parties and the VAT summary
  are scored the same way and reported in their own sections.

### Added

- **One engine, several spec kinds (ADR-0007).** `extraction/engine.py` runs every field
  through the same internal pipeline — guard, collect, filter, normalize, validate, rank,
  on-failure, publish — and only the collect step differs between kinds. `LabelSpec`
  reads the text a label introduces, `AnchorSpec` looks for a value the profile already
  expects, `DerivedSpec` computes one from the page and the fields already resolved.
- **A closed vocabulary, named rather than imported (`extraction/units/`).** A spec names
  its units as strings — `"parse_money"`, `"looks_numeric"`, `"last_page_first"` — and
  `extraction/spec.py` refuses one that names a unit, a source or a dependency nothing
  registered. The check runs while `extraction/specs.py` is imported, so a typo is an
  import error rather than a field that silently never resolves.
- **Seven more fields read**: `order_number`, `customer_number` and `supply_date` from
  the catalog, and `contract_number`, `our_reference`, `your_reference` and
  `credit_reference` through `custom_fields`, which a vendor declares for the extras it
  prints in its header block. The shared defaults declare all four, so a document that
  carries one is read whether or not its vendor usually prints it.
- **`classify_document` (stage 3).** A document is an invoice or a credit note, decided
  by the title it prints, the reference it makes to the invoice it credits, and the sign
  of its total; `InvoiceResult.document_type` carries the answer.
- On the 250-document corpus: fourteen of seventeen fields at 100%, `subtotal` 99.2%,
  `vat_rate` 96.4%, `supply_date` 95.5%, and `payment_terms` the one name no spec reads
  yet. Every field is at or above where it stood before, and none below.

### Changed

- **`currency` is derived, not read from a label.** The vendor's own code that the page
  prints most is the document's currency, which separates it from the one a converted
  total is echoed in without reading a label for either. A derived value still carries
  evidence: the derivation reports the line it counted from.
- **`supplier_vat_id` is found by expectation.** The profile knows the vendor's VAT id,
  so the page is searched for that value rather than for whatever a label introduces —
  which is what a letterhead printing `NTVAINTRACOMMUNAUTAIRE FR7…` needs.
- **An amount is only what is mostly a number.** A candidate whose text is a sentence
  carrying digits — a bank footer's IBAN, a page count — is dropped before ranking, and
  the currency code a vendor prints beside the amount is taken off first, by the same
  rule the parser uses.

### Added

- **A document is read once, whole (`docs/ENGINE_SPEC.md` §2, stage 0).** `read(pdf)`
  returns a `Document` of `Page`s, each with its lines already zoned and the four
  anchors found on it — where the letterhead ends, where a table's header band is, where
  the totals block starts, and where a VAT summary starts. Every anchor is found from the
  page's own drawing, before any vendor is known, and any of them may be absent.
- **Profile detection (ADR-0008).** `detect_profile` scores every registered profile on
  the supplier's own name, its VAT id, the currency and the share of its label vocabulary
  the page carries, and returns the best above `PROFILE_THRESHOLD` or `None`. A file-path
  hint may promote a profile that was already close; it can never carry one over the
  threshold. On the 250-document corpus, detection picks the vendor that printed the
  document 250 times out of 250.
- **`invoice-extractor profile lint <id>`**, which measures a profile against the median
  of every other profile in the registry and reports a readiness tier — T0 where a
  required field has no label, T1 where one has no zone or fewer labels than the median,
  T2 otherwise.
- **`InvoiceResult.valid`**, derived from the findings and never set beside them
  (ADR-0010), and `profile_id` that is `None` when no vendor matched.
- The benchmark reports profile detection beside the field matrix.

### Changed

- **`extract(pdf_path, registry)`** replaces `extract(pdf_path, profile)`: the pipeline
  detects the vendor itself. The CLI follows — `invoice-extractor extract <pdf>` with no
  `--profile`, and `--profiles PATH` to point at a directory of them.
- **`Zone` is a `(row, col)` record**, not one of nine enum members, so the grid a page
  is cut on is data rather than a fixed nine. `document/reader.py` and its
  `DocumentReader` protocol are replaced by `document/model.py`: a test builds a
  `Document` rather than faking a reader.
- A profile's supplier name is matched by case-folded letters and digits **in any
  script**, so a Greek vendor is recognised by its own name rather than scoring zero on
  an ASCII-only fold.

### Added

- **Vendor profiles, shared with the generator (ADR-0006).** `profiles/<id>.json`
  describes one vendor — language, locale, currencies, VAT rules, the supplier as it
  prints itself, the label vocabulary of every field, the party blocks, the two tables
  and the totals block — and both packages read the same file: `invoice_forge` draws
  what it says, `invoice_extractor` reads it back. `profile/loader.py` is the only
  module in this package that parses the JSON, and it raises `ProfileError` naming the
  offending key path (`docs/PROFILE_FORMAT.md`).
- **`profiles/_defaults.json` and lexicon references.** A profile names its language and
  writes `"@header_labels.invoice_number"` where it means every synonym that language
  offers; the shared defaults carry the structure every vendor has in common. Sixteen
  languages and twenty-two vendors are described without a label list being copied
  twice.
- **`ProfileRegistry`**, which re-reads a profile whose file or shared defaults changed,
  so a vendor added while the process runs is found on the next document (ADR-0008).
- **A reader manifest as a test.** `tests/test_profile_contract.py` asserts that every
  key the loader accepts becomes a field of the record it builds, and that every field
  comes from a key — a profile key that does nothing fails the suite.

### Changed

- **`extract(pdf_path, profile)`** replaces `extract(pdf_path, layout)`, and the CLI
  takes `--profile` instead of `--layout`. `InvoiceResult.layout_id` is now
  `profile_id`.
- **`part_number` and `discount_pct`** are the canonical names of the columns previously
  called `sku` and `discount`, in both packages and in the truth files
  (`docs/FIELD_CATALOG.md` is the one place a canonical name is named).
- **A vendor's supplier is declared, not drawn.** Every document a profile produces now
  carries the same supplier name, address and VAT id — the values the extractor's
  supplier anchors will expect — instead of one sampled per document.
- **Numbers are parsed with every thousands separator a vendor writes**, not only the
  first one its profile lists.
- `profiles/` and `lexicon/` moved from inside `invoice_forge` to the root of the working
  directory, because they are now shared data rather than one package's fixtures.

### Removed

- **`layouts/`, `samples/` and `src/invoice_extractor/layout/`.** Profiles replace
  layouts and the generated corpus replaces the two golden samples; `make samples` and
  `scripts/make_samples.py` go with them, and `make demo` now extracts a committed
  corpus fixture. `docs/LAYOUT_FORMAT.md` and `docs/SAMPLES_SPEC.md` are replaced by
  `docs/PROFILE_FORMAT.md`.
- `scripts/make_field_catalog.py`: `docs/FIELD_CATALOG.md` is now the contract the code
  is measured against rather than a file generated from it.

### Added

- **`LABEL_BESIDE`, a fourth extraction strategy.** A vendor that sets its labels at one
  tab stop and its values flush right at another draws no text between the two, so the
  reader sees two lines rather than one and `<label>: <value>` never appears on the
  page at all. The new strategy reads the nearest thing printed to the right of a line
  that is only the label, on the same line of the page.

### Changed

- **`FieldSpec.strategy` is now `FieldSpec.strategies`.** One field is printed more than
  one way, and a spec cannot be asked to pick in advance: every strategy it names
  contributes its candidates and the rankers choose between them, which is what the
  rankers were already for. Every one of the ten fields now looks both ways along its
  line. See the amendment in
  [ADR-0001](docs/adr/0001-field-specs-declared-not-subclassed.md).
- A field's expected zones are now preferred on the candidate rather than on the lines
  searched, because a zone says where the *value* is. A label at the last tab stop of
  the middle third and its value flush right in the right third are one row of one
  block; filtering the page before searching threw the label away.
- `strip_label` strips a label only from text that starts with it, so a colon inside a
  value handed over on its own — which is every candidate `LABEL_BESIDE` finds — stays
  part of the value.

### Measured

- `make bench` over the 250-document base corpus: scalar fields **19.3% → 82.1%**.
  Of the 447 remaining misses, 437 still find no candidate; almost all of them are the
  `stacked` family, which prints each value on the line *under* its label — that is
  `LABEL_BELOW`, a strategy that exists and that no spec names yet.

## [0.2.0]

`invoice_forge`: a generator of synthetic invoices with exact ground truth, and the
first measured answer to "how good is the extractor".

### Added

- **A generator, `invoice_forge`.** `forge render-one`, `forge generate`, `forge verify`
  and `forge catalog` produce PDFs and a `forge-truth/1` JSON beside each one, recording
  every value, the box it was read back out of, and the noise printed beside it.
  PyMuPDF stays the only runtime dependency.
- **Twenty-two vendor profiles** over sixteen languages and twenty-one countries, each
  with its own lexicon of label synonyms, product catalogue, number and date formats,
  legal forms, cities and IBAN shape. Nothing falls back to English: a profile whose
  words are missing is refused by name.
- **Five template families** — `classic`, `tabular`, `stacked`, `saas`, `minimal` — the
  last four declared as `classic` with blocks restyled or switched off, never as a
  second renderer. A golden PNG per profile and family is compared pixel for pixel.
- **Thirty-one difficulty knobs**, the closed vocabulary of
  `docs/VARIATION_CATALOG.md`: multi-page tables with carried-forward subtotals, trap
  labels, placeholder addresses, sub-items, section subtotals, several VAT rates,
  undeclared charges, two rounding policies, dual-currency echoes, totals spelled out
  in words, and the rest.
- **A 250-document base corpus.** `corpus/plan.json` is committed and the documents are
  not: `make corpus` regenerates them byte for byte, `forge verify` reads every
  recorded box back out of the PDF, and `forge catalog` reports the corpus against
  every coverage target the variation catalog sets.
- **A benchmark.** `make bench` runs the extractor over the corpus with a layout built
  from each vendor's own labels, and writes `benchmarks/latest.json`,
  `benchmarks/README.md` and the block in `README.md` — a matrix of field by profile,
  by family and by knob, a calibration table, and the list of fields the extractor does
  not cover. Every published figure is generated; a test fails if one is hand-edited.

### Fixed

- A line-item description could run into the quantity beside it. The quantity is set
  flush right, so it reaches back from its anchor; a description now stops one gutter
  short of the widest quantity, measured in both faces rather than assumed.
- `party_blocks` gave a one-column family three columns at the same x, printing three
  companies on top of each other. The knob now only divides the room a family already
  sets two blocks in.
- A company name wider than its block ran into the block beside it. Party lines wrap
  now, measured in the face they are set in.
- A long copy stamp sat on the first line of the reference block. A stamped document
  starts its references a line lower.

### Changed

- PyMuPDF is imported as `pymupdf` rather than through the deprecated `fitz` alias.

## [0.1.0]

The first release: a PDF invoice becomes a typed, evidence-backed `InvoiceResult`.

### Added

- **Public API.** `extract(pdf_path, layout) -> InvoiceResult` and
  `load_layout(id_or_path) -> Layout`, with `InvoiceResult`, `Layout` and `LayoutError`
  exported alongside them. The package ships `py.typed`.
- **Document boundary.** A PDF becomes `TextLine`s carrying a `BBox` rounded to two
  decimals and a `Zone` on a 3x3 grid, behind the `DocumentReader` protocol. `fitz` is
  imported in exactly one module.
- **Layouts as data.** `layouts/acme.json` (English, GBP) and `layouts/nordic.json`
  (Swedish, SEK) drive extraction; `layout/loader.py` validates a layout top down and
  raises `LayoutError` naming the exact JSON key at fault.
- **Ten scalar fields, declared not subclassed.** One `FieldSpec` per field composes a
  strategy, a normalizer, a validator, rankers and an `on_all_invalid` policy; one
  generic engine runs them all.
- **Evidence on every value.** Each `FieldResult` carries the page, bounding box,
  matched label, strategy and untouched raw text it came from.
- **Line items.** The table is located by its header row and read until a stop label,
  with a `Finding` for any row that cannot be read.
- **Invariants as findings.** `totals_reconcile`, `line_items_sum` and
  `vat_rate_consistent` report rather than raise; money is `Decimal` end to end.
- **Explainable confidence.** Five weighted signals per field, stored as
  `confidence_breakdown` beside the value.
- **Output.** `output/json_writer.py` writes the full result as JSON with `Decimal` as a
  string and `date` as ISO-8601; `output/text_report.py` renders the report shown in
  `README.md`; `python -m invoice_extractor` exposes both.
- **Reproducible fixtures.** `scripts/make_samples.py` regenerates both sample PDFs and
  their golden `expected.json` byte for byte.
- **Quality gates.** `make check` — ruff lint and format, `mypy --strict`, pytest with a
  90% coverage floor, and a repository hygiene scan for the size budget, the `fitz`
  boundary, suppressions, work markers and markdown links — run on Python 3.11 and 3.12
  in CI.
