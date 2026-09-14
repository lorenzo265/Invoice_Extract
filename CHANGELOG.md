# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

### Added

- **`LABEL_BESIDE`, a fourth extraction strategy.** A vendor that sets its labels at one
  tab stop and its values flush right at another draws no text between the two, so the
  reader sees two lines rather than one and `<label>: <value>` never appears on the
  page at all. The new strategy reads the nearest thing printed to the right of a line
  that is only the label, on the same line of the page.

### Changed

- **Python floor lowered to 3.10.** `requires-python`, the mypy `python_version` and the
  ruff `target-version` now declare 3.10, and CI runs a 3.10, 3.11 and 3.12 matrix.
  `PyMuPDFReader.__enter__` annotates its own class directly instead of `typing.Self`,
  which does not exist before 3.11 and was the only 3.11-only construct in `src/`.
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
