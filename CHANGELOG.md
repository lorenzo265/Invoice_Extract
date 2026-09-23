# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

### Fixed

- **The vendor's own tax id is no longer read as the customer's.** A vendor prints its
  registration under the same words the customer's sits under — `DIC:` on a Czech page, `VAT
  Reg. No.:` in an English letterhead — and the label reads both, with the closer one winning.
  A candidate for the customer's registration whose value is the profile's own
  `supplier.vat_id`, compared without punctuation and without the country prefix either side
  may leave out, is now dropped before the rankers choose (`not_the_suppliers_own`, asked for
  by `customer_vat_id`).

## [0.5.0] — 2026-09-23

### Added

- **`invoice-extractor profile draft <pdf> --out <dir>`** — the profile one document
  suggests, written for a person to correct. The inverse of `inspect`: where `inspect`
  shows the page so a profile can be written, `profile draft` writes the profile the
  page suggests and the evidence for every key beside it, under `drafts/<id>.json`.
  Read without a language: every `label: value` the page prints, from punctuation and
  geometry; the shape of every value — a date and which of the loader's formats it fits,
  an amount and the separators it was printed with, a VAT id and the country its prefix
  names; the supplier from the letterhead. Read with every shipped lexicon at once: which
  field each label names, and which language the page is in, by vote. The overlay
  written is what a hand-written profile has needed every time so far: the supplier
  block, the number and date conventions, the currency, the rates, and the zone each
  field's value actually sat in. Drafted from one corpus fixture into an empty
  directory, the profile lints at T2 and reads the document back with every header
  field at 1.00 — `tests/integration/test_profile_draft.py` holds that proof. A page in
  a language no lexicon speaks gets a skeleton lexicon, the labels it did print as the
  profile's own, and a worksheet of every labelled value with its shape and zone. A key
  the page gave nothing for is `?`, which the loader refuses by name. Nothing is
  overwritten: a draft over an existing profile is refused, and `--id` names it
  differently. A drafting tool only — the engine never runs it (ADR-0008).

### Fixed

The first real invoices this engine was run on — one vendor's ERP output, in twelve
countries — read every header field and lost the totals block, the party blocks and one
custom field, each to a rule the synthetic corpus had never exercised. Each is fixed
against a document built line by line in the shape the page had.

- **A totals block whose labels are set flush right is read whole.** `Subtotal`, `VAT`
  and `Total` end at the same x and start apart, `VAT` being the narrower word. The block
  finder grouped rows by their labels' left edges within two points, so the block fell
  apart into single rows and only `Total` survived — `subtotal` came back empty and
  `vat_amount` was backfilled from the summary. A column is now set against an `Edge`,
  its labels' left edges where those agree and their right edges otherwise, and a cell is
  in the column where its matching edge is on that line (`extraction/units/totals_block.py`).
- **A party block may stand a few lines under its heading, and may be set wholly in
  bold.** The vendor leaves two lines of room under `Bill To:` before the customer's name,
  and the rule that ends a block at a gap of one and a half line heights ended it before it
  began: both parties came back with no name and no address. The first line under a
  heading now has room of its own (`HEADING_GAP`, three heights of the heading) and the
  gap between the block's own lines is still what ends it. The same vendor sets the whole
  bill-to block in bold, and the reader that takes the bold run as the name took the
  address with it; weight now names the lines only where the block has two weights in it,
  and a block set in one leaves the first line as the name (`extraction/section.py`).
- **A label is never a value, and `placement` leads.** The vendor sets every value at a
  tab stop to the right of its label, so the line under `Payment Terms:` is `Payment
  Date:`, the next label. `label_below` offered it, it reads like a sentence, and it sat
  ten points from its label where the real value sat a hundred and ten: `payment_terms`
  came back as the words `Payment Date:`. A new filter, `not_a_label`, drops a candidate
  that is nothing but a label the profile declares for another field, a vendor's extra
  or a party block — or such a label with its own value after it — and every `LabelSpec`
  runs it after `not_a_trap`. And the profile's `placement`, which `docs/PROFILE_FORMAT.md`
  said names the strategy that leads and which nothing read, now does: `strategies_for`
  pools the leading strategy's candidates first, and since the rankers sort stably, it is
  the one that wins a tie (`extraction/units/filters.py`, `extraction/spec.py`).
- **The totals block is read from whichever page carries it.** The vendor prints a page
  of terms after the one it adds up on, so the block finder, which read the last page
  only, found nothing there and `subtotal` and `total_amount` came back empty on every
  such document. Every page is now searched, and the block is the run of rows naming
  the most components on any of them; where two pages name as much, the later one is
  the block, because a subtotal carried forward says the same words on the page before.
  An amount's zone is classified against the page it was drawn on rather than the last
  (`extraction/units/totals_block.py`, `extraction/block.py`).
- **`profile draft` spells the paths it prints one way on every OS.** Its summary
  interpolated each `Path` it wrote as it was, so on Windows the files it names and the two
  commands it ends with — the ones meant to be pasted back — came out with backslashes,
  beside a source path the reader already spells with forward slashes. Every path it prints
  is now `as_posix()` (`drafting/summary.py`).

## [0.4.0] — 2026-09-15

The engine, packaged as one. v0.3.0 was a repository you cloned; this is a library you
install. Nothing about how a document is read has changed — every number in the benchmark
below is the one v0.3.0 measured — and everything about how the engine reaches a caller
has.

### Added

- **The vendors and their languages travel inside the wheel.** `profiles/` and `lexicon/`
  were directories at the root of the working directory, outside `src/`, so
  `pip install` delivered an engine that knew no vendor at all and reported every
  document as `profile_not_detected` — the same answer a genuinely unrecognised invoice
  gets, which left a caller no way to tell a broken install from an unknown vendor. They
  now live under `src/invoice_extractor/data/`, are declared as package data, and are
  found through `importlib.resources` rather than relative to whatever directory the
  caller started in. `invoice_extractor/bundled.py` is the one module that knows where.
- **`invoice-extractor inspect <pdf>`** — the page as the engine reads it: every line
  with the zone and the box it was drawn in, the anchors the reader found, and how each
  known vendor scored against the document with the parts that carried the score. Writing
  a profile means naming labels and zones, and both are properties of the page that
  nothing else showed you. Where no vendor matches, it says which part of the score found
  nothing, which is the question a person about to write a profile is actually asking.
- **`CONTRIBUTING.md`** — what to read first (three modules, named and justified), what
  may be ignored (the generator, which is 46 % of the code and none of the engine), and
  the rules that will reject a change. `AGENTS.md` is addressed to an agent; this one is
  for a person.

### Changed

- **Python floor lowered to 3.10.** `requires-python` in both distributions, the mypy
  `python_version` and the ruff `target-version` declare 3.10, and CI runs a 3.10, 3.11
  and 3.12 matrix. Nothing under `src/` needed to change: the engine already ran whole on
  3.10. The one 3.11-only construct in the tree was the `tomllib` import in
  `tests/test_repo_hygiene.py`, which read the `package-data` table of the two
  pyprojects; it now reads that table as a text scan, like every other check in that
  file. No dependency was added, runtime or development.
- **Two distributions, one working tree.** `invoice-extractor` is the engine and the
  vocabulary it reads with: 195 KB, one dependency. `invoice-forge`, under `tools/forge/`,
  is the generator it is proved against — it depends on the engine for the profile files
  the two share (ADR-0006) and carries the two megabytes of embedded fonts it draws with.
  A caller extracting invoices was installing a generator of them; now it is not.
  `make install` still installs both, editable, because a contributor wants both.
- **A profile directory that is not there is refused, not read as empty.** `ProfileRegistry`
  raises `ProfileError` naming the path when it is not a directory, or holds no
  `_defaults.json`. It used to return no vendors and let every document come back
  unread — the failure mode that hides a misconfiguration behind a plausible result. A
  directory that exists and holds no vendor yet is still allowed: adding the first one
  while running is what the mtime cache is for (ADR-0008).

### Fixed

- **A variant re-read the bundled lexicons instead of the caller's.** Stage 2 resolved
  them by joining a root with an absolute default, which in `pathlib` discards the root.
  A deployment with its own vendors would have had its own language quietly replaced the
  moment a variant matched. Both layers go through one `lexicons_beside()` now.

## [0.3.0] — 2026-09-15

The full-capability extractor: a vendor is a **profile** rather than a layout, one engine
runs **six kinds of spec** over it, and what comes back is not a list of fields but a
document — its rows, its party blocks, its totals block, the charges it carries and the
currency it echoes. Everything it publishes carries the box it was read from; everything
it checked comes back as a `Check`; and the confidence beside every value is **fitted on a
corpus whose answers are written down** rather than assumed. Measured on that corpus:
every field of `docs/FIELD_CATALOG.md` scored and none excused, **every value the 270
documents carry read correctly** (4,160 of 4,160), every line-item cell, every VAT line
and every party block right, and confidences off by under half a percent.

### Added — hardening (E7)

- **Stage 2, `select_variant`, exists.** A profile's `variants[]` were loaded and
  validated and nothing applied them. The stage now runs between detection and
  classification: the first variant whose `when` matches is merged over the profile,
  through the same merge function and the same strict loader every other layer goes
  through. `profiles/en-GB.json` declares one — on a credit note, and only on a credit
  note, the reference to the invoice being reversed is a required field.
- **`Finding(WARNING, "field_missing")` is emitted.** `docs/ENGINE_SPEC.md` §3 and
  `docs/PROFILE_FORMAT.md` both said a required field that resolves nothing reports
  itself; nothing did. A label spec, an anchor spec and a derivation all report it now —
  so a document priced in a currency its vendor's profile does not list comes back
  saying so instead of coming back empty.
- **`iban` is read and measured.** The generator drew a valid one and printed it in the
  bank footer; no spec read it and the truth never recorded it. It is found by its shape
  rather than by a label — `IBAN` is the word in every language here — and judged by ISO
  13616's checksum, which is what tells it from a VAT id.
- **`document_type` is measured.** The truth carried it, the result carried it, and the
  benchmark compared neither. 270 of 270.
- **Each line item and each charge carries the VAT line that taxes it.**
  `link_items_to_vat_lines` ran, produced findings and threw its answer away;
  `LineItem.vat_line` and `Charge.vat_line` publish it, serialized like everything else.
- **Twenty hardening cells** at the end of `corpus/plan.json`, one per known failure mode
  of label-based extractors, with `tests/integration/test_hardening.py` proving each.
- **`mm/dd/yyyy` is a date format a profile may declare.** No vendor here does — they are
  all European — but `03/04/2024` is a different day under it, and which day a vendor
  means has to be declarable rather than guessed.

### Fixed — hardening (E7)

- **A table is no longer closed by a stop label printed beside it.** A vendor that sets
  its VAT summary on the left and its totals on the right puts `Total:` at the same
  height as a summary line and three hundred points away from it. That word closed the
  summary after one row of three, and the headline VAT rate then came from the wrong
  line. A stop label now closes a table only where it is drawn across the table's own
  width — geometry deciding, as everywhere else.
- **A trap label is no longer the label of the field it traps.** Fifteen of the sixteen
  lexicons made `trap_labels.delivery_date` one of the same language's own
  `supply_date` labels — `Lieferdatum`, `Leverdatum`, `Data di consegna`. A document
  with traps on and no supply date therefore printed one, and the extractor read it and
  was right to. All fifteen now follow French: a dispatch noun and a dispatch
  participle, neither of them a label any field owns. `supply_date` went 0.955 → 1.000,
  which was the last field under 1.
- **`is_iban` enforces the standard's shape rather than the profile's.** Everywhere else
  a vendor knows its own shapes better; an IBAN is ISO 13616's to define, and a profile
  pattern looser than it only widens what is accepted.

### Changed — hardening (E7)

- **Every shipped profile is T2.** `fi-FI` named two ways to say a due date and `sv-SE`
  two to say an invoice date, where every other language named three. Each now names a
  third its language really uses.
- **`OnFailure` has two members and the spec says two.** `shaped` was named by
  `ENGINE_SPEC.md` and by no code; it is what `best_invalid` already does, and a
  vocabulary entry no spec names is what the closed-vocabulary rule forbids. The spec was
  corrected rather than the enum widened.
- **`docs/CONFORMANCE.md`**: every requirement of every specification in `docs/`, against
  what the code does, with a decision recorded for each difference — including the ones
  deliberately left open, and why.

### Added

- **Stage 8 writes two files.** `--json PATH` still writes everything; beside it goes
  `PATH.findings.json`, carrying what the document said about itself and every rule it
  was put through, with nothing to scroll past to reach them (ENGINE_SPEC §2). Both come
  from the one result, so they cannot disagree.
- **`payment_terms` is read.** The fifth custom field the catalog names is a sentence
  rather than a reference — it has no shape worth declaring, so it is judged by reading
  like one (`is_sentence`). Every field in `docs/FIELD_CATALOG.md` is now measured in
  `benchmarks/latest.json`; nothing is listed as not covered.
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

- **`docs/ARCHITECTURE.md` describes v0.3**: the eight stages, the six boundaries, every
  module of the eleven packages, and how a value is read from a page that never printed a
  label for it. ADR-0004 (layouts are data) is marked superseded by ADR-0006 in both
  directions, as the ADR format requires.
- **A value the page never printed is absent, not missed.** The benchmark scored a field
  the vendor knew and drew nowhere as a miss, while scoring an unprinted cell, party block
  and VAT line as absent — one rule for four families now: a value *produced* is judged
  against what the document carries (so a rate worked out of the rows is still right), and
  a value *not produced* is a miss only where the page printed one.
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
