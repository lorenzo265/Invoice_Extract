# Implementation plan

This document is executed, not read for inspiration. It fixes, for each of ten pull
requests, the files to create, the public names to use, the tests to write and the
command that decides whether the PR is done. Everything an implementer would otherwise
have to invent is decided here; what is not decided here is decided by the simplest
option consistent with `docs/ARCHITECTURE.md`, recorded in the PR description.

## 1. How to use this plan

The loop, for `N` in `0..9`:

1. Branch `pr/N-<slug>` from the latest `main`.
2. Implement only the "Scope" of PR `N`. Nothing from a later PR, however convenient.
3. Run `make check` until green. It is the same command CI runs.
4. Open a PR with `.github/pull_request_template.md` fully filled in.
5. Wait for CI green. Run the self-review checklist in `AGENTS.md` against the diff.
6. Squash-merge with a Conventional Commits message. Delete the branch. Start PR `N+1`.

A PR's **Gate** is a list of commands. Every command must exit `0`. There is no partial
pass. Three failed gate attempts in a row on the same PR: stop, write `docs/BLOCKED.md`
(PR number, exact command, full output, the three things tried), and end the session.
Never weaken a threshold, skip a test, edit `samples/*.expected.json`, or add a
suppression to get past a gate.

## 2. Global constraints

| Constraint | Value |
|---|---|
| Python | `>= 3.11` (`slots=True`, `tomllib`, `typing.Self`) |
| Runtime dependency | `PyMuPDF` only (`import fitz`) |
| Dev dependencies | `ruff`, `mypy`, `pytest`, `pytest-cov`, `pre-commit` — nothing else, ever |
| Layout | `src/invoice_extractor/`, `py.typed` shipped |
| Lint / format | `ruff` — rules `E, F, I, N, UP, B, SIM, RUF`, line length 100 |
| Types | `mypy --strict` on `src/`; `ignore_missing_imports` scoped to `fitz` only |
| Tests | `pytest --cov=invoice_extractor --cov-fail-under=90` |
| Size budget | `src/` ≤ 2200 non-blank non-comment lines; module ≤ 250; function ≤ 40 (AST-counted) |
| Money | `decimal.Decimal`, never `float`; parsed only through `normalizers.parse_money` |
| Dates | `datetime.date` |
| Records | `@dataclass(frozen=True, slots=True)` for every spec, layout, evidence and result type |
| Public API typing | no `Any` |
| Domain errors | `Finding` values; exceptions only for invalid input and programmer errors |
| Evidence | every scalar `FieldResult` carries `Evidence(page, bbox, matched_label, strategy, raw_text)` |
| Working directory | every command runs from the repository root (layout ids resolve to `layouts/<id>.json`) |

Per-PR source budget: at most ~400 changed lines of `src/` (tests and docs excluded).
Estimated final size by module (a budget, not a target):

| Module | Lines | Module | Lines |
|---|---|---|---|
| `document/reader.py` | 45 | `extraction/rankers.py` | 40 |
| `document/zones.py` | 30 | `extraction/engine.py` | 90 |
| `document/pymupdf_reader.py` | 60 | `extraction/specs.py` | 60 |
| `domain/findings.py` | 25 | `extraction/line_items.py` | 130 |
| `domain/money.py` | 25 | `validation/invariants.py` | 90 |
| `domain/models.py` | 130 | `validation/confidence.py` | 70 |
| `layout/schema.py` | 50 | `pipeline.py` | 60 |
| `layout/loader.py` | 160 | `output/json_writer.py` | 40 |
| `extraction/spec.py` | 50 | `output/text_report.py` | 110 |
| `extraction/strategies.py` | 110 | `cli.py` + `__main__.py` + `__init__.py` | 80 |
| `extraction/normalizers.py` | 80 | **Total** | **≈ 1 700** |
| `extraction/validators.py` | 50 | | |

## 3. Names fixed in advance

These signatures are the contract between PRs. Implement them exactly; add private
helpers freely. `document/`, `layout/` and `domain/` are described by the diagrams in
`docs/ARCHITECTURE.md` §2; the JSON shapes by `docs/SAMPLES_SPEC.md` and
`docs/LAYOUT_FORMAT.md`.

```python
# document/reader.py
class Zone(Enum): TOP_LEFT, TOP_CENTER, TOP_RIGHT, MIDDLE_LEFT, MIDDLE_CENTER, MIDDLE_RIGHT, BOTTOM_LEFT, BOTTOM_CENTER, BOTTOM_RIGHT
@dataclass(frozen=True, slots=True)
class BBox: x0: float; y0: float; x1: float; y1: float
    @property center(self) -> tuple[float, float]
@dataclass(frozen=True, slots=True)
class TextLine: page: int; text: str; bbox: BBox; zone: Zone          # page is 1-indexed
class DocumentReader(Protocol):
    @property page_count(self) -> int
    def lines(self, page: int) -> Sequence[TextLine]

# document/zones.py
def classify(bbox: BBox, page_width: float, page_height: float) -> Zone

# document/pymupdf_reader.py  — the only module that imports fitz
class PyMuPDFReader:                       # satisfies DocumentReader; context manager
    def __init__(self, pdf_path: Path) -> None   # raises FileNotFoundError
    def __enter__(self) -> Self; def __exit__(...) -> None
    page_count: int (property); def lines(self, page: int) -> Sequence[TextLine]

# domain/findings.py
class Severity(Enum): INFO, WARNING, ERROR
@dataclass(frozen=True, slots=True)
class Finding: severity: Severity; code: str; message: str; field: str | None = None

# domain/money.py
CENT: Decimal = Decimal("0.01")
def quantize_cents(value: Decimal) -> Decimal
def within_tolerance(left: Decimal, right: Decimal, tolerance: Decimal = CENT) -> bool

# domain/models.py
FieldValue = str | date | Decimal
class Strategy(Enum): LABEL_RIGHT, LABEL_BELOW, REGEX_ANCHOR    # lives here, next to Evidence, so domain/ never imports extraction/
@dataclass(frozen=True, slots=True)
class Evidence: page: int; bbox: BBox; matched_label: str | None; strategy: Strategy; raw_text: str
@dataclass(frozen=True, slots=True)
class FieldResult: name: str; value: FieldValue | None; raw_text: str | None; evidence: Evidence | None
                   valid: bool; confidence: float = 0.0; confidence_breakdown: Mapping[str, float] = field(default_factory=dict)
@dataclass(frozen=True, slots=True)
class LineItem: sku: str; description: str; quantity: Decimal; unit_price: Decimal; net_amount: Decimal
@dataclass(frozen=True, slots=True)
class InvoiceResult:
    fields: Mapping[str, FieldResult]      # all ten names, in extraction.specs.FIELD_ORDER
    line_items: tuple[LineItem, ...]; findings: tuple[Finding, ...]; layout_id: str; source_path: str
    def to_dict(self) -> dict[str, object]
    @classmethod def from_dict(cls, data: Mapping[str, object]) -> InvoiceResult

# layout/schema.py
@dataclass(frozen=True, slots=True)
class FieldLayout: labels: tuple[str, ...]; zones: tuple[Zone, ...]; regex: re.Pattern[str] | None = None
@dataclass(frozen=True, slots=True)
class LineItemsLayout: header_labels: Mapping[str, tuple[str, ...]]; stop_labels: tuple[str, ...]
@dataclass(frozen=True, slots=True)
class Layout: id: str; language: str; decimal_separator: str; thousands_separator: str
              date_formats: tuple[str, ...]; currency_symbols: Mapping[str, str]
              fields: Mapping[str, FieldLayout]; line_items: LineItemsLayout
class LayoutError(ValueError)

# layout/loader.py
def load_layout(id_or_path: str) -> Layout         # raises LayoutError (messages: docs/LAYOUT_FORMAT.md)

# extraction/spec.py   (re-exports Strategy from domain.models for callers' convenience)
class OnAllInvalid(Enum): BEST, NOT_FOUND
@dataclass(frozen=True, slots=True)
class Candidate: raw_text: str; evidence: Evidence; zone: Zone; label_distance: float   # zone = source TextLine.zone
@dataclass(frozen=True, slots=True)
class Evaluated: candidate: Candidate; value: FieldValue | None; valid: bool
Normalizer = Callable[[Candidate, Layout], FieldValue | None]
Validator  = Callable[[FieldValue, FieldLayout], bool]
Ranker     = Callable[[Evaluated, FieldLayout], float]      # lower sorts first
@dataclass(frozen=True, slots=True)
class FieldSpec: name: str; strategy: Strategy; normalizer: Normalizer; validator: Validator
                 rankers: tuple[Ranker, ...]; on_all_invalid: OnAllInvalid

# extraction/strategies.py
StrategyFn = Callable[[Sequence[TextLine], FieldLayout], list[Candidate]]
def label_right(lines, field_layout) -> list[Candidate]
def label_below(lines, field_layout) -> list[Candidate]
def regex_anchor(lines, field_layout) -> list[Candidate]
STRATEGIES: Mapping[Strategy, StrategyFn]

# extraction/normalizers.py   (each one strips the label first; see PR5)
def parse_number(text: str, layout: Layout) -> Decimal | None    # the four separator steps, on raw text
def strip_label(candidate, layout) -> str
def parse_date(candidate, layout) -> date | None
def parse_money(candidate, layout) -> Decimal | None
def parse_percent(candidate, layout) -> Decimal | None
def upper_alnum(candidate, layout) -> str

# extraction/validators.py
def matches_pattern(default: str) -> Validator      # layout regex overrides default
def is_date(value, field_layout) -> bool
def is_positive_money(value, field_layout) -> bool
def is_currency_code(value, field_layout) -> bool
def is_percent(value, field_layout) -> bool

# extraction/rankers.py
def valid_first(evaluated, field_layout) -> float
def zone_priority(evaluated, field_layout) -> float
def closest_to_label(evaluated, field_layout) -> float
def top_most(evaluated, field_layout) -> float

# extraction/engine.py
@dataclass(frozen=True, slots=True)
class Extraction: field: FieldResult; candidate_count: int; zone: Zone | None   # zone of the winning line
def run(spec: FieldSpec, lines: Sequence[TextLine], layout: Layout) -> Extraction

# extraction/specs.py
FIELD_ORDER: tuple[str, ...]                # the ten names, in order
FIELD_SPECS: tuple[FieldSpec, ...]          # same order

# extraction/line_items.py
@dataclass(frozen=True, slots=True)
class TableExtraction: items: tuple[LineItem, ...]; findings: tuple[Finding, ...]
def extract_line_items(lines: Sequence[TextLine], layout: Layout) -> TableExtraction

# validation/invariants.py
INVARIANT_NAMES: tuple[str, ...] = ("totals_reconcile", "line_items_sum", "vat_rate_consistent")
def totals_reconcile(fields) -> Finding | None
def line_items_sum(fields, line_items) -> Finding | None
def vat_rate_consistent(fields) -> Finding | None
def check_all(fields: Mapping[str, FieldResult], line_items: Sequence[LineItem]) -> tuple[Finding, ...]

# validation/confidence.py
SIGNAL_WEIGHTS: Mapping[str, float]
def score(extraction: Extraction, field_layout: FieldLayout, findings: Sequence[Finding]) -> FieldResult

# pipeline.py
def extract(pdf_path: Path, layout: Layout) -> InvoiceResult

# output/json_writer.py
def to_json(result: InvoiceResult) -> str
def write_json(result: InvoiceResult, path: Path) -> None

# output/text_report.py
def render(result: InvoiceResult, layout: Layout) -> str

# __init__.py
__all__ = ["extract", "load_layout", "InvoiceResult", "Layout", "LayoutError", "__version__"]
```

---

## PR0 — Bootstrap

**Goal.** An installable, empty package whose quality gates are all wired and green.

**Scope.** `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`,
`.pre-commit-config.yaml`, `.gitignore`, `LICENSE` (MIT), `CHANGELOG.md` (Unreleased
section only), `src/invoice_extractor/__init__.py` (`__version__ = "0.1.0"`,
`__all__ = ["__version__"]` for now), `src/invoice_extractor/py.typed`,
`tests/__init__.py` absent (use `pythonpath`), `tests/test_repo_hygiene.py` with the
assertions in Appendix A that are meaningful on an empty package (size budget, no
`print`, no `TODO`, fitz import location, no suppressions without justification).

**Design notes.**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "invoice-extractor"
version = "0.1.0"
description = "Evidence-backed extraction of structured data from PDF invoices."
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = ["PyMuPDF>=1.24"]

[project.optional-dependencies]
dev = ["ruff>=0.6", "mypy>=1.11", "pytest>=8", "pytest-cov>=5", "pre-commit>=3.7"]

[project.scripts]
invoice-extractor = "invoice_extractor.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
invoice_extractor = ["py.typed"]

[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF"]

[tool.mypy]
strict = true
files = ["src"]
python_version = "3.11"

[[tool.mypy.overrides]]
module = "fitz"
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "scripts"]
addopts = "--cov=invoice_extractor --cov-report=term-missing --cov-fail-under=90"

[tool.coverage.run]
branch = true
source = ["src/invoice_extractor"]
```

`Makefile` (tabs, POSIX shell; `.PHONY` for every target):

```make
.PHONY: install samples demo lint typecheck test check
install:   ; pip install -e ".[dev]" && pre-commit install
samples:   ; python scripts/make_samples.py
demo:      ; python -m invoice_extractor samples/acme_invoice.pdf --layout acme --report
lint:      ; ruff check . && ruff format --check .
typecheck: ; mypy
test:      ; pytest
check: lint typecheck test
```

The hygiene test runs inside `test` (it is a pytest module), so `check` covers all four
gates. `.github/workflows/ci.yml`: one job on `ubuntu-latest`, Python `3.11` and
`3.12` matrix, steps `actions/checkout@v4` → `actions/setup-python@v5` → `pip install -e
".[dev]"` → `make check`; triggers `push` to `main` and `pull_request`.
`.pre-commit-config.yaml`: `ruff` (with `--fix`) and `ruff-format` from
`astral-sh/ruff-pre-commit`, plus `end-of-file-fixer` and `trailing-whitespace` from
`pre-commit/pre-commit-hooks`. `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`,
`.coverage`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `dist/`, `build/`,
`*.egg-info/`, `out/`.

`tests/test_repo_hygiene.py` scans `src/` with `ast` and plain text; see Appendix A.
Coverage with an empty package: `--cov-fail-under=90` over zero statements reports 100%.

**Tests.** `test_version_is_semver`, plus the Appendix A hygiene tests that apply.

**Gate.** `make check`.

**Out of scope.** Any module under `src/` other than `__init__.py`. Any sample.

**Self-review.** No dependency outside the two lists above. `make check` green on a
fresh clone in a fresh virtual environment.

---

## PR1 — Samples

**Goal.** Two fictional invoice PDFs and their golden `expected.json`, generated by
code, byte-for-byte reproducible.

**Scope.** `scripts/make_samples.py`, `samples/README.md`, `samples/acme_invoice.pdf`,
`samples/acme_invoice.expected.json`, `samples/nordic_invoice.pdf`,
`samples/nordic_invoice.expected.json`, `tests/integration/test_samples_deterministic.py`.

**Design notes.** `docs/SAMPLES_SPEC.md` is the whole specification: page size, font,
every `(x, y, text)` triple, and the expected values. The script holds that content as
data and exposes a small importable API (pytest adds `scripts/` to `pythonpath`, so
tests do `from make_samples import SAMPLES, draw, write_expected`):

```python
@dataclass(frozen=True, slots=True)
class SampleSpec:                       # everything about one sample, as data
    layout_id: str; supplier_lines: tuple[tuple[int, str], ...]; metadata_lines: ...
    bill_to_lines: ...; table_header: tuple[str, ...]; rows: tuple[tuple[str, ...], ...]
    totals_lines: tuple[tuple[int, str], ...]; expected_fields: Mapping[str, str]
SAMPLES: Mapping[str, SampleSpec]       # {"acme": ..., "nordic": ...}
def draw(sample: SampleSpec, pdf_path: Path) -> None
def write_expected(sample: SampleSpec, pdf_path: Path, json_path: Path) -> None
def main() -> None                      # both samples into samples/
```

Per sample the script does three things:

1. **Draw.** `doc = fitz.open(); page = doc.new_page(width=595, height=842)`; one
   `page.insert_text(fitz.Point(x, y), text, fontsize=10, fontname="helv")` per line and
   per table cell (five calls per table row, at the column x's of the spec).
2. **Save deterministically.** `doc.set_metadata({"producer": "invoice-extractor",
   "creator": "scripts/make_samples.py", "title": "<id> sample", "creationDate":
   "D:20240101000000Z", "modDate": "D:20240101000000Z"})` then
   `doc.save(path, garbage=4, deflate=True, no_new_id=True)`. `no_new_id=True` is what
   makes the bytes reproducible: without it PyMuPDF writes a random trailer `/ID` on every
   save. With it, a freshly created document has no `/ID` at all, and two runs are
   byte-identical (verified against PyMuPDF 1.27).
3. **Write `expected.json`.** Values come from the script's own data table (never
   re-extracted). The `evidence.bbox` of each scalar field is read back from the PDF just
   written, with `fitz`, using the same call the reader will use
   (`page.get_text("dict")`, line bbox rounded to 2 decimals) — so the golden file pins
   the bbox the reader must report, without anyone typing coordinates by hand. Shape and
   key order: `docs/SAMPLES_SPEC.md` "The `expected.json` contract". Serialize with
   `json.dumps(data, indent=2, ensure_ascii=False) + "\n"`.

`samples/` is frozen after this PR merges. A later PR that changes any file under
`samples/` fails self-review; the extractor adapts to the samples, never the reverse.

**Tests.** `test_make_samples_is_byte_deterministic` (run the script twice into
`tmp_path`, compare SHA-256 of all four files), `test_committed_samples_match_generator`
(regenerate into `tmp_path`, compare bytes with the committed files),
`test_expected_json_arithmetic_is_consistent` (for both files: line nets sum to subtotal,
subtotal + vat = total, subtotal × rate / 100 = vat, using `Decimal`).

**Gate.** `make samples && git diff --exit-code samples/` and `make check`.

**Out of scope.** Any `src/` module. Any reader.

**Self-review.** The four sample files are committed. The script imports `fitz` (it is a
script, not `src/`, so the hygiene rule does not apply). No coordinate in the script
disagrees with `docs/SAMPLES_SPEC.md`.

---

## PR2 — Document boundary

**Goal.** Text lines with bounding boxes and zones, behind a protocol, with `fitz`
confined to one module.

**Scope.** `src/invoice_extractor/document/__init__.py`, `document/reader.py`,
`document/zones.py`, `document/pymupdf_reader.py`, `tests/conftest.py`,
`tests/unit/test_zones.py`, `tests/unit/test_reader.py`,
`tests/integration/test_pymupdf_reader.py`.

**Design notes.** `zones.classify` takes the bbox centre, divides by page width/height,
and maps each axis to thirds: `< 1/3` → LEFT/TOP, `< 2/3` → CENTER/MIDDLE, else
RIGHT/BOTTOM. `PyMuPDFReader` opens the file in `__init__` (raising
`FileNotFoundError` with the path in the message if missing), closes it in `__exit__`,
and builds `TextLine`s from `page.get_text("dict")`: one per `line` in each `block`,
`text` = concatenation of the spans' text, `bbox` rounded to 2 decimals (`round(v, 2)`),
`zone` from `classify` with `page.rect.width/height`, `page` 1-indexed. Lines are
returned in reading order: sorted by `(bbox.y0, bbox.x0)`. Everything `fitz` returns is
converted to this module's own typed values before leaving the function that received
it; no `fitz` object escapes.

`tests/conftest.py` defines `FakeDocument`: constructed from a list of
`(page, text, x0, y0, x1, y1)` tuples, computes zones with `classify` for an A4 page,
satisfies `DocumentReader`. Also a `line(text, x, y)` helper producing a `TextLine` at
`x, y` with the sample font metrics (`y0 = y - 10.75`, `y1 = y + 2.99`, width
`≈ 5.5 × len(text)`), so unit tests can lay out a fake page in the same coordinates as
the samples.

**Tests.** `test_classify_maps_each_third_to_its_zone` (parametrized over the nine
zones), `test_classify_uses_bbox_centre_not_corner`, `test_textline_is_immutable`,
`test_fake_document_satisfies_protocol`;
integration: `test_reader_returns_supplier_name_in_top_left` (both samples),
`test_reader_rounds_bbox_to_two_decimals`, `test_reader_raises_for_missing_file`,
`test_table_cells_arrive_as_separate_lines` (row at `y=478` has five lines).

**Gate.** `make check`.

**Out of scope.** Any label matching. Any layout.

**Self-review.** `grep -rn "import fitz" src/` lists exactly one file.

---

## PR3 — Domain

**Goal.** The result types, exact money helpers and findings, with a JSON round trip.

**Scope.** `domain/__init__.py`, `domain/findings.py`, `domain/money.py`,
`domain/models.py` (including `Strategy`), `tests/unit/test_money.py`,
`tests/unit/test_models.py`, `tests/unit/test_findings.py`.

**Design notes.** `to_dict` produces exactly the shape in `docs/SAMPLES_SPEC.md`
(`Decimal` → `str(value)`, `date` → `isoformat()`, `Strategy` → its name, `BBox` → object
with `x0..y1`, `fields` keyed by name in the order given, `confidence` and
`confidence_breakdown` included). `from_dict` is the inverse and must infer the value
type from the field name: dates for `invoice_date`/`due_date`, `Decimal` for
`vat_rate`/`subtotal`/`vat_amount`/`total_amount`, `str` otherwise — that mapping lives
in `models.py` as `VALUE_TYPES: Mapping[str, type]`, and `extraction/specs.py` (PR5)
must agree with it. `Finding.to_dict` / `from_dict` are on `Finding` itself.
`money.within_tolerance` compares `abs(left - right) <= tolerance`.

**Tests.** `test_quantize_cents_rounds_half_even`, `test_within_tolerance_at_boundary`,
`test_invoice_result_round_trips_through_dict` (a fully populated result),
`test_to_dict_serializes_decimal_as_string_and_date_as_iso`,
`test_from_dict_restores_value_types_by_field_name`,
`test_to_dict_keeps_field_order`, `test_finding_round_trips_through_dict`,
`test_models_are_frozen` (assigning raises `FrozenInstanceError`).

**Gate.** `make check`.

**Out of scope.** Any extraction. `parse_money` (that is a normalizer, PR5).

---

## PR4 — Layout

**Goal.** Vendor layouts as validated data.

**Scope.** `layout/__init__.py`, `layout/schema.py`, `layout/loader.py`,
`layouts/acme.json`, `layouts/nordic.json` (already in the seed — verify against
`docs/LAYOUT_FORMAT.md`, fix the JSON if it disagrees, never the document),
`tests/unit/test_loader.py`, `tests/unit/test_layouts_bundled.py`.

**Design notes.** `load_layout` resolves the argument per `docs/LAYOUT_FORMAT.md`
"Loading a layout", reads with `json.loads`, then validates top-down, raising the first
`LayoutError` it meets with the exact message from that document. Validation is a set of
small private functions, one per key family (`_require_str`, `_require_separator`,
`_parse_field`, `_parse_line_items`); each builds the dotted path it reports. Zone names
are resolved with `Zone[name]` inside a `try/except KeyError`. `regex` is compiled at
load time. Unknown keys at any level are errors.

**Tests.** One test per error message in `docs/LAYOUT_FORMAT.md`, named after it
(`test_missing_required_key_names_the_key`, `test_unknown_top_level_key_is_rejected`,
`test_field_labels_must_be_non_empty_list`, `test_unknown_zone_name_reports_index`,
`test_invalid_regex_reports_re_error`, `test_separators_must_differ`,
`test_extra_field_name_is_rejected`, `test_missing_line_item_column_is_reported`,
`test_file_not_found_message_names_resolved_path`, `test_invalid_json_message`),
plus `test_id_resolves_to_layouts_directory` and `test_path_with_slash_is_used_directly`;
bundled: `test_bundled_layouts_load` (both), `test_bundled_layout_labels_match_samples_spec`
(every `labels[0]` of both layouts appears verbatim in the corresponding sample's drawn
text — read the strings from `samples/*.expected.json` `raw_text`).

**Gate.** `make check`.

**Out of scope.** Using a layout to extract anything.

---

## PR5 — Scalar engine

**Goal.** The ten scalar fields extracted with evidence from both samples.

**Scope.** `extraction/spec.py` (complete), `extraction/strategies.py`,
`extraction/normalizers.py`, `extraction/validators.py`, `extraction/rankers.py`,
`extraction/engine.py`, `extraction/specs.py`, `pipeline.py` (scalar fields only;
`line_items=()`, `findings=()`, confidence left at `0.0`), `__init__.py` exports
`extract`, `load_layout`, `InvoiceResult`, `Layout`, `LayoutError`;
`tests/unit/test_strategies.py`, `test_normalizers.py`, `test_validators.py`,
`test_rankers.py`, `test_engine.py`, `test_specs.py`,
`tests/integration/test_pipeline_golden.py` (scalar projection only).

**Design notes.**

*Strategies.* Label matching is case-insensitive, on the line's text with surrounding
whitespace stripped. `label_right`: for each label in `field_layout.labels`, every line
whose text starts with `label` followed by optional whitespace, a colon, and at least
one non-space character is a candidate; `raw_text` is the whole line;
`evidence.matched_label` is the label as written in the layout; `label_distance = 0.0`.
`label_below`: a line whose whole text equals a label is an anchor; the candidate is the
nearest line on the same page with `bbox.y0 > anchor.bbox.y0` and horizontal overlap
with the anchor; `label_distance = candidate.y0 - anchor.y0`; `raw_text` is that line's
text; `matched_label` the label. `regex_anchor`: requires `field_layout.regex` (a field
whose spec uses this strategy on a layout without `regex` yields no candidates); every
line whose text matches is a candidate with `raw_text = match.group(0)`,
`matched_label=None`, `label_distance = 0.0`. All three restrict the search to lines
whose `zone` is in `field_layout.zones` first and fall back to all lines only if that
yields nothing — the zone list is a preference, not a fence.

*Normalizers.* `strip_label` returns the text after the first `:` when
`matched_label` is set, else the raw text, stripped. `parse_date` tries
`datetime.strptime(text, fmt).date()` over `layout.date_formats` in order. `parse_number`
applies the four steps in `docs/LAYOUT_FORMAT.md` "Separators drive every
locale-formatted number" to raw text and is the one place they are implemented;
`parse_money` is `strip_label` followed by `parse_number`; `parse_percent` strips a
trailing `%` then does the same.
`upper_alnum` keeps `[A-Za-z0-9]` and upper-cases. Each returns `None` on failure, never
raises.

*Validators.* `matches_pattern(default)` builds a validator that uses
`field_layout.regex` when present, else `re.compile(default)`, with `fullmatch` on
`str(value)`. `is_date`: `isinstance(value, date)`. `is_positive_money`: `Decimal` and
`> 0`. `is_currency_code`: `fullmatch(r"[A-Z]{3}")`. `is_percent`: `Decimal` in
`[0, 100]`.

*Rankers.* Lower sorts first. `valid_first`: `0.0` if valid else `1.0`. `zone_priority`:
index of the candidate's zone in `field_layout.zones`, or `len(zones)`.
`closest_to_label`: `label_distance`. `top_most`: `bbox.y0`.

*Engine.* `run`: candidates = `STRATEGIES[spec.strategy](lines, layout.fields[spec.name])`;
evaluate each (`value = spec.normalizer(candidate, layout)`, `valid = value is not None
and spec.validator(value, field_layout)`); sort by the tuple of `spec.rankers`; the
winner is the first valid one, else per `on_all_invalid`: `BEST` → the first evaluated
candidate with `valid=False`; `NOT_FOUND` → `FieldResult(name, None, None, None,
valid=False)`. `candidate_count = len(candidates)`; `zone` is the `TextLine.zone` of the
winning candidate's line (`None` when nothing was found) — strategies carry it by
building each `Candidate` from the `TextLine` it came from. The engine never touches `fitz`,
never reads a file and never raises for a document it cannot understand.

*Specs.* `FIELD_SPECS`, in `FIELD_ORDER`:

| Field | strategy | normalizer | validator | rankers | on_all_invalid |
|---|---|---|---|---|---|
| `invoice_number` | LABEL_RIGHT | `strip_label` | `matches_pattern(r"[A-Z0-9][A-Z0-9/-]{2,}")` | `valid_first, zone_priority, top_most` | NOT_FOUND |
| `invoice_date` | LABEL_RIGHT | `parse_date` | `is_date` | `valid_first, zone_priority, top_most` | NOT_FOUND |
| `due_date` | LABEL_RIGHT | `parse_date` | `is_date` | `valid_first, zone_priority, top_most` | NOT_FOUND |
| `supplier_vat_id` | LABEL_RIGHT | `upper_alnum` | `matches_pattern(r"[A-Z]{2}[A-Z0-9]{2,12}")` | `valid_first, zone_priority, top_most` | NOT_FOUND |
| `customer_vat_id` | LABEL_RIGHT | `upper_alnum` | `matches_pattern(r"[A-Z]{2}[A-Z0-9]{2,12}")` | `valid_first, zone_priority, top_most` | NOT_FOUND |
| `currency` | LABEL_RIGHT | `upper_alnum` | `is_currency_code` | `valid_first, zone_priority, top_most` | NOT_FOUND |
| `vat_rate` | LABEL_RIGHT | `parse_percent` | `is_percent` | `valid_first, zone_priority, closest_to_label` | NOT_FOUND |
| `subtotal` | LABEL_RIGHT | `parse_money` | `is_positive_money` | `valid_first, zone_priority, closest_to_label` | NOT_FOUND |
| `vat_amount` | LABEL_RIGHT | `parse_money` | `is_positive_money` | `valid_first, zone_priority, closest_to_label` | NOT_FOUND |
| `total_amount` | LABEL_RIGHT | `parse_money` | `is_positive_money` | `valid_first, zone_priority, closest_to_label` | NOT_FOUND |

`LABEL_BELOW` and `REGEX_ANCHOR` are exercised by unit tests on `FakeDocument`, not by
any bundled field. `pipeline.extract` (this PR): open `PyMuPDFReader`, collect the lines
of every page, run every spec, build `InvoiceResult(fields, (), (), layout.id,
pdf_path.as_posix())`.

**Tests.** Strategies (on `FakeDocument`):
`test_label_right_reads_value_after_colon`, `test_label_right_is_case_insensitive`,
`test_label_right_ignores_line_where_label_is_the_whole_text`,
`test_label_right_prefers_expected_zone_then_falls_back`,
`test_label_below_picks_nearest_line_under_anchor`, `test_label_below_records_distance`,
`test_regex_anchor_returns_match_text_without_label`,
`test_regex_anchor_yields_nothing_without_regex`.
Normalizers: table-driven `test_parse_money` over `("1,234.56", ".", ",") → 1234.56`,
`("3 216,00", ",", " ") → 3216.00`, `("-12.5", ".", "") → -12.5`, `("abc") → None`;
`test_parse_date_tries_formats_in_order`, `test_parse_percent_strips_percent_sign`,
`test_upper_alnum_drops_punctuation`, `test_strip_label_without_label_returns_stripped_text`.
Validators: one test per validator, both directions, plus
`test_matches_pattern_prefers_layout_regex`. Rankers: one test each. Engine:
`test_run_returns_not_found_when_no_candidates`, `test_run_best_keeps_invalid_top_candidate`,
`test_run_orders_by_rankers_in_sequence`, `test_run_reports_candidate_count`,
`test_run_reports_zone_of_winning_line`.
Specs: `test_field_order_matches_layout_format_document` (the ten names, in order),
`test_value_types_agree_with_models`. Golden (integration):
`test_scalar_fields_match_expected_json` parametrized over `acme` and `nordic`, comparing
`to_dict()["fields"]` minus `confidence`/`confidence_breakdown` against the file.

**Gate.** `make check`.

**Out of scope.** Line items, invariants, confidence, CLI, writers.

**Self-review.** No strategy, normalizer, validator or ranker performs I/O. No function
over 40 lines (the label matchers are the ones that grow — split early).

---

## PR6 — Line items

**Goal.** The line-item table extracted from both samples.

**Scope.** `extraction/line_items.py`, `pipeline.py` (wire `line_items`, and the
table's findings into `findings`), `tests/unit/test_line_items.py`,
`tests/integration/test_pipeline_golden.py` (add line items to the projection).

**Design notes.** Algorithm, on the lines of one page:

1. **Header row.** For each of the five columns, find lines whose stripped text equals
   (case-insensitive) one of `header_labels[column]`. The header row is a set of five
   such lines, one per column, whose `bbox.y0` agree within 2 pt. If no page has one,
   return `TableExtraction((), (Finding(WARNING, "line_items_header_not_found", ...),))`.
2. **Column anchors.** Each column's anchor is its header line's `bbox.x0`. Columns are
   sorted by anchor; a cell belongs to the column whose anchor is the greatest one
   `≤ cell.x0 + 2`.
3. **Rows.** Lines with `y0 > header.y0`, in reading order, grouped by `y0` within 2 pt.
   Stop before the first group containing a line whose text starts with a
   `stop_labels` entry (case-insensitive).
4. **Cells.** Assign each line in a group to its column. A group missing any of the five
   columns, or whose `quantity`/`unit_price`/`net_amount` fail `parse_number`, yields
   `Finding(WARNING, "line_item_incomplete", message naming the row's y0 and the missing
   column)` and no `LineItem`.
5. `sku` and `description` are the cells' text stripped; the three numbers go through
   `normalizers.parse_number(text, layout)` (PR5), so a table cell and a totals line are
   read by the same separator rules.

Rows keep their page order; the result covers all pages, first page's table first.

**Tests.** `test_extracts_all_rows_until_stop_label`, `test_description_with_digits_and_commas_stays_whole`,
`test_missing_cell_yields_warning_finding_and_skips_row`, `test_no_header_yields_warning_and_empty_table`,
`test_header_synonyms_are_accepted`, `test_stop_label_line_is_not_a_row`,
`test_numbers_use_layout_separators` (nordic `"2 670,00"` → `2670.00`). Golden:
`test_line_items_match_expected_json` (both samples).

**Gate.** `make check`.

**Out of scope.** Invariants, confidence.

---

## PR7 — Validation

**Goal.** Arithmetic invariants as findings, and an explainable confidence per field.

**Scope.** `validation/__init__.py`, `validation/invariants.py`,
`validation/confidence.py`, `pipeline.py` (wire both), `tests/unit/test_invariants.py`,
`tests/unit/test_confidence.py`, `tests/integration/test_pipeline_findings.py`.

**Design notes.**

*Invariants.* Each function reads `FieldResult.value` and returns `None` when the
invariant holds. When an operand is missing or not a `Decimal`, it returns
`Finding(WARNING, <name>, "<name> skipped: <field> not found", field=<field>)`. When the
arithmetic disagrees beyond `money.within_tolerance` it returns `Finding(ERROR, <name>,
"<lhs expression> = <lhs> but <rhs field> is <rhs>", field=<rhs field>)`.
`totals_reconcile`: `subtotal + vat_amount` vs `total_amount` (field `total_amount`).
`line_items_sum`: `sum(net_amount)` vs `subtotal` (field `subtotal`); with zero line
items it returns the WARNING form. `vat_rate_consistent`:
`quantize_cents(subtotal × vat_rate / 100)` vs `vat_amount` (field `vat_amount`).
`check_all` returns the three results in `INVARIANT_NAMES` order, `None`s dropped.

*Confidence.* `SIGNAL_WEIGHTS = {"label_exact_match": 0.25, "in_expected_zone": 0.15,
"validator_passed": 0.30, "single_candidate": 0.10, "invariants_agree": 0.20}` (sums to
1.0). Each signal is `0.0` or `1.0`: `label_exact_match` — `evidence.matched_label` is
not `None`; `in_expected_zone` — `extraction.zone` is in `field_layout.zones` (never
recompute a zone here: the engine already stored the winning line's zone);
`validator_passed` — `field.valid`;
`single_candidate` — `candidate_count == 1`; `invariants_agree` — no `ERROR` finding
whose `field` is this field's name. A field with `value is None` scores `0.0` with an
all-zero breakdown. `score` returns `dataclasses.replace(field, confidence=round(total, 2),
confidence_breakdown=breakdown)`.

*Pipeline.* Order: scalar fields → line items → `check_all` → `score` each field →
`InvoiceResult`. Findings tuple = table findings followed by invariant findings.

**Tests.** Invariants: `test_totals_reconcile_holds_within_a_cent`,
`test_totals_reconcile_reports_error_with_both_sides`,
`test_line_items_sum_warns_when_no_items`, `test_vat_rate_consistent_quantizes_before_compare`,
`test_missing_operand_yields_warning_not_error`, `test_check_all_preserves_name_order`.
Confidence: `test_all_signals_lit_scores_one`, `test_missing_field_scores_zero`,
`test_error_finding_on_field_clears_invariants_signal`,
`test_breakdown_lists_every_signal`, `test_weights_sum_to_one`. Integration:
`test_clean_samples_have_no_findings_and_full_confidence` (both samples: `findings == ()`,
every `confidence == 1.0`), `test_mutated_total_yields_error_finding` (build
`dataclasses.replace(SAMPLES["acme"], totals_lines=...)` with `Total Due: 589.00`, `draw`
it into `tmp_path`, extract; assert exactly one ERROR finding, code `totals_reconcile`,
and `total_amount.confidence < 1.0`).

**Gate.** `make check`.

**Out of scope.** CLI, writers.

---

## PR8 — Output and CLI

**Goal.** `python -m invoice_extractor` produces the JSON and the report shown in
`README.md`; the full golden test passes.

**Scope.** `output/__init__.py`, `output/json_writer.py`, `output/text_report.py`,
`cli.py`, `__main__.py`, `tests/unit/test_json_writer.py`, `tests/unit/test_text_report.py`,
`tests/unit/test_cli.py`, `tests/integration/test_pipeline_golden.py` (full
projection: everything except `confidence` and `confidence_breakdown`),
`tests/integration/test_cli_end_to_end.py`.

**Design notes.** `to_json` = `json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"`.
`text_report.render` prints exactly the layout in `README.md` "See it run": header block
(`source`, `layout`), the field table (`FIELD`, `VALUE`, `CONF`, `EVIDENCE` = `p<page>`,
strategy name, matched label in quotes or `-`), the line-item table, the `Invariants`
block — one line per name in `INVARIANT_NAMES`: `[ok]` when no finding carries that
code, `[!!]` for ERROR, `[??]` for WARNING, followed by the finding message or, for
`[ok]`, the arithmetic rendered from the field values — then the counts line. The report is
pure rendering: it never re-runs an invariant or recomputes a confidence. Money is
always rendered as the raw decimal value, with no currency prefix — `currency_symbols`
is validated by the loader and available on `Layout`, but no v0.1.0 output consumes it.

`cli.main(argv: Sequence[str] | None = None) -> int`: `argparse` with positional `pdf`,
required `--layout`, optional `--json PATH`, flag `--report`. With neither `--json` nor
`--report`, print the report. `FileNotFoundError` and `LayoutError` → message on stderr,
return `1`. Any completed extraction → `0`. `__main__.py`: `raise SystemExit(main())`.

**Tests.** `test_to_json_ends_with_newline_and_is_stable`, `test_json_round_trips_through_from_dict`,
`test_report_marks_ok_when_no_finding`, `test_report_marks_error_finding`,
`test_report_shows_dash_for_missing_field`, `test_cli_writes_json_file`,
`test_cli_prints_report_by_default`, `test_cli_returns_one_for_missing_pdf`,
`test_cli_returns_one_for_bad_layout_with_message`. Integration:
`test_full_result_matches_expected_json` (both samples, full projection),
`test_demo_command_output_matches_readme` (run `main([...acme..., "--report"])`,
compare to the block in `README.md` extracted between the fences).

**Gate.** `make check` and `make demo`.

**Out of scope.** New extraction behaviour.

---

## PR9 — Documentation and release

**Goal.** The repository reads as finished.

**Scope.** `README.md` (regenerate "See it run" from real output, complete "Extending"
with a worked new-field example, add a "Running one test" line and a supported Python
line), `CHANGELOG.md` (`0.1.0` section: what ships), `docs/ARCHITECTURE.md` and
`docs/LAYOUT_FORMAT.md` reconciled with the code (documents follow code where they
diverged; record each divergence in the PR description), `tests/test_repo_hygiene.py`
gains `test_markdown_links_resolve`, tag `v0.1.0`.

**Design notes.** The link check parses every `*.md` in the repo for `](path)` targets
that are relative (no scheme, no `#` only) and asserts the file exists. No new source
behaviour.

**Gate.** `make check`, `make demo`, and `git tag v0.1.0` created on the merge commit.

**Self-review.** README's report block is byte-identical to `make demo` output (the PR8
integration test already enforces it). Every module in `docs/ARCHITECTURE.md` §4 exists;
every existing module is in that table (package-marker `__init__.py` files are exempt).

---

## 4. Definition of done for v0.1.0

- [ ] PR0–PR9 merged in order, each with CI green and a filled template.
- [ ] `make check` green on `main` under Python 3.11 and 3.12.
- [ ] `make samples` reproduces the four committed sample files byte for byte.
- [ ] `make demo` prints the report in `README.md`.
- [ ] Hygiene test reports `src/` within budget; the count is in the PR9 description.
- [ ] Every module in `docs/ARCHITECTURE.md` §4 exists and nothing else does under `src/`.
- [ ] `git log` on `main` is ten squash commits after the seed commit, all Conventional.
- [ ] Tag `v0.1.0` exists.

## Appendix A — `tests/test_repo_hygiene.py`

Every assertion runs over `src/invoice_extractor/` unless stated. All are plain `ast` or
text scans; none imports the package.

| Test | Assertion |
|---|---|
| `test_source_within_line_budget` | non-blank, non-comment lines (a line whose stripped text is empty or starts with `#`) across all `.py` files ≤ 2200 |
| `test_no_module_over_250_lines` | same count per file ≤ 250 |
| `test_no_function_over_40_lines` | for every `FunctionDef`/`AsyncFunctionDef`, `end_lineno - lineno + 1 ≤ 40` |
| `test_fitz_imported_only_in_pymupdf_reader` | `Import`/`ImportFrom` of `fitz` appears only in `document/pymupdf_reader.py` and appears there |
| `test_no_float_calls_in_domain` | no `Call` to a `Name` `float` in `domain/*.py` |
| `test_no_print_in_source` | no `Call` to `Name` `print` |
| `test_no_todo_markers` | none of `TODO`, `FIXME`, `XXX`, `HACK` in any `.py` under `src/` or `tests/` |
| `test_suppressions_carry_justification` | every line containing `# noqa` or `# type: ignore` also contains a second `#` comment after it |
| `test_no_absolute_paths` | no `/home/`, `/Users/`, `C:\\` in `src/`, `tests/`, `scripts/`, `docs/`, `README.md` |
| `test_no_email_addresses` | regex `[\w.+-]+@[\w-]+\.[\w.]+` finds nothing in the same set |
| `test_no_urls_outside_docs` | `https?://` appears only in `README.md`, `docs/**`, `.github/**`, `.pre-commit-config.yaml`, `pyproject.toml` |
| `test_public_api_has_no_any` | `Any` is not imported in `__init__.py`, `pipeline.py` or `domain/models.py` |
| `test_dataclasses_are_frozen` | every `@dataclass` decorator in `domain/`, `layout/schema.py`, `extraction/spec.py`, `document/reader.py` has `frozen=True` |
| `test_markdown_links_resolve` (PR9) | every relative `](target)` in any `*.md` points at an existing file |
