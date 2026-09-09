# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

Nothing yet.

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
