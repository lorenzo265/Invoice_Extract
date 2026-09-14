# Engine plan — PR series E0–E7

Executed under the gate protocol of `docs/IMPLEMENTATION_PLAN.md` §1 plus the
benchmark gate in `AGENTS.md`. Series F (the generator and the corpus) is merged before
E0 starts; `make corpus` and `make bench` exist.

## 1. Global constraints

- Public API: `extract(pdf_path, registry) -> InvoiceResult`, `load_profile(id_or_path)
  -> Profile`, `ProfileRegistry`, `InvoiceResult`, `__version__`.
- Per-module ≤ 250 lines, per-function ≤ 40, `mypy --strict`, `Decimal`, frozen records,
  `Evidence` on every value, findings not exceptions, no new dependency.
- Every PR: `make check` green, `make bench` green, no field regresses on
  `benchmarks/latest.json` versus `main`, "Decisions" filled.
- Each PR ≤ ~600 changed source lines (this series replaces modules; tests and profiles
  excluded from the count).

## 2. Fixed names (in addition to v0.1's `document/`, `domain/models.py`, `domain/findings.py`)

```python
# profile/schema.py
@dataclass(frozen=True, slots=True) class NumberFormat: decimal_separator: str; thousands_separators: tuple[str, ...]
@dataclass(frozen=True, slots=True) class FieldProfile: labels: tuple[str, ...]; zones: tuple[Zone, ...]; placement: Placement; pattern: re.Pattern[str] | None; required: bool; exclude_labels: tuple[str, ...]
@dataclass(frozen=True, slots=True) class SectionProfile, TableProfile, BlockProfile, CustomFieldProfile, Variant, DocumentTypes, VatProfile, SupplierProfile
@dataclass(frozen=True, slots=True) class Profile: id, language, country, number_format, date_formats, currencies, vat, supplier, zones_grid, fields, parties, line_items, vat_summary, totals, custom_fields, variants, document_types, noise
class ProfileError(ValueError)
# profile/loader.py
def load_profile(id_or_path: str) -> Profile
def merge(base: Mapping, overlay: Mapping, rules: MergeRules) -> dict
# profile/registry.py
class ProfileRegistry: def __init__(self, root: Path); def get(self, id) -> Profile; def all(self) -> Sequence[Profile]   # mtime-aware
# profile/detect.py
PROFILE_THRESHOLD: float
@dataclass(frozen=True, slots=True) class ProfileScore: profile_id: str; score: float; parts: Mapping[str, float]
def detect_profile(document: Document, registry: ProfileRegistry, path_hint: str | None) -> tuple[Profile | None, tuple[ProfileScore, ...]]
# profile/lint.py
def lint(profile: Profile, registry: ProfileRegistry) -> LintReport   # tier T0/T1/T2 + per-field rows

# document/model.py
@dataclass(frozen=True, slots=True) class Anchors: logo_bottom: float | None; table_header_band: tuple[float, float] | None; totals_top: float | None; vat_summary_top: float | None
@dataclass(frozen=True, slots=True) class Page: number: int; width: float; height: float; lines: tuple[TextLine, ...]; anchors: Anchors
@dataclass(frozen=True, slots=True) class Document: pages: tuple[Page, ...]; source_path: str
@dataclass(frozen=True, slots=True) class Zone: row: int; col: int   # 1-based; name() -> "r{row}c{col}"

# extraction/spec/*.py
class SpecKind(Enum): LABEL, ANCHOR, SECTION, TABLE, BLOCK, DERIVED
class OnFailure(Enum): NOT_FOUND, BEST_INVALID, SHAPED
@dataclass(frozen=True, slots=True) class LabelSpec / AnchorSpec / SectionSpec / TableSpec / BlockSpec / DerivedSpec   # all with name, depends_on, on_failure
Spec = LabelSpec | AnchorSpec | SectionSpec | TableSpec | BlockSpec | DerivedSpec
# extraction/engine.py
def run(spec: Spec, document: Document, profile: Profile, resolved: Mapping[str, FieldResult]) -> FieldResult
def order(specs: Sequence[Spec]) -> tuple[Spec, ...]        # stable topological order of depends_on
# extraction/specs/__init__.py
SPECS: tuple[Spec, ...]                                      # the catalog, in order
# extraction/units/registry.py
STRATEGIES, FILTERS, NORMALIZERS, VALIDATORS, RANKERS: Mapping[str, Callable]

# reconcile/__init__.py
@dataclass(frozen=True, slots=True) class Reconciliation: findings: tuple[Finding, ...]; caps: Mapping[str, float]; currency_basis: str | None
def reconcile(resolved: Mapping[str, FieldResult], profile: Profile) -> Reconciliation
# validation/__init__.py
@dataclass(frozen=True, slots=True) class Check: code: str; passed: bool | None; fields: tuple[str, ...]; detail: str
def validate(resolved, reconciliation, profile) -> tuple[tuple[Finding, ...], tuple[Check, ...]]
# scoring/
def extract_signals(field: FieldResult, context: ScoringContext) -> Mapping[str, float]
def compute(signals: Mapping[str, float], weights: FieldWeights | None, caps: float | None) -> Scored
def calibrate(corpus: Path, out: Path) -> CalibrationReport                 # CLI: invoice-extractor calibrate
# domain/models.py (changes)
InvoiceResult: fields: Mapping[str, FieldResult]; parties: Mapping[str, Party]; line_items; vat_summary; totals; secondary_amounts; findings; checks; profile_id: str | None; document_type; valid: bool; source_path
```

## 3. The PRs

### E0 — Profiles, field catalog, retirement of layouts

**Scope.** `profile/schema.py`, `loader.py`, `registry.py`, `merge`; `profiles/_defaults.json`
and the four base profiles (`en-GB`, `de-DE`, `fr-FR`, `sv-SE`) **shared with the
generator** (move `invoice_forge`'s profiles here and make the generator read them);
`docs/FIELD_CATALOG.md` reconciled with `forge-truth/1` (rename keys in the generator if
they differ — the catalog wins); delete `layouts/`, `samples/`, `layout/`; hygiene tests
"every profile key has a reader" (initially against a reader manifest) and "no unit
unreferenced".
**Tests.** Loader error messages (one test per message class), merge rules, registry
mtime reload, catalog ⇔ truth key equality.
**Gate.** `make check`; `make corpus` still green with shared profiles; `make bench`
runs (fields "not covered" allowed at this PR only).

### E1 — Document model and profile detection

**Scope.** `document/model.py` (`Document`, `Page`, `Anchors`, generic `Zone` grid),
`pymupdf_reader.py` rewritten to build pages with anchors; `profile/detect.py`
(scored, thresholded, no default); `profile/lint.py`; CLI `profile lint`.
**Tests.** anchors on synthetic pages; detection picks the right profile on every corpus
document; a document from an unknown profile yields `profile_not_detected` and
`valid=False`; a profile added at runtime is detected without restart; lint tiers.
**Gate.** `make check`; `make bench` reports 100 % profile detection on the corpus.

### E2 — The engine, LabelSpec, AnchorSpec, DerivedSpec

**Scope.** `extraction/units/` (strategies incl. geometric `label_below`, filters,
normalizers with profile number format, validators, rankers), `extraction/spec/`,
`extraction/engine.py` (`run`, `order`), specs for the 13 scalar fields of the catalog
plus supplier anchors; `classify_document`; pipeline stages 0–4 wired.
**Tests.** unit per unit on `FakeDocument`; engine ordering; on_failure policies;
evidence always present (type-level and test); the 13 scalar fields on the corpus.
**Gate.** `make check`; `make bench`: every scalar field ≥ 0.95 hit rate on `classic`
documents without difficulty knobs, and no regression.

### E3 — SectionSpec and TableSpec

**Scope.** parties (bill_to, ship_to, mail_to, placeholders), `line_items` (with sub-items,
subscription columns, carry-forward, page bounds), `vat_summary`.
**Tests.** state machine per row kind; page bounds stop at the totals anchor and at stop
labels; multi-page tables; knob-driven corpus cells (`multi_page`, `wrapped_description`,
`sub_items`, `section_subtotals`, `placeholder_addresses`).
**Gate.** `make check`; `make bench`: line-item row-count exact on ≥ 0.95 of documents;
per-cell hit rate ≥ 0.95; no regression.

### E4 — BlockSpec and reconciliation

**Scope.** `totals` and `secondary_amounts` as `BlockSpec`; `reconcile/` (five functions of
`ENGINE_SPEC.md` §5); declared and undeclared charges; dual-currency basis; pipeline
stage 5 wired.
**Tests.** block clustering; longest-label-wins; column promotion; identities with
tolerance; undeclared charge inference and its finding; dual-currency echo.
**Gate.** `make check`; `make bench`: totals fields ≥ 0.97 on all families; charges
`(type, amount)` exact on ≥ 0.95; no regression.

### E5 — Validation, signals, calibration

**Scope.** `validation/` (ten invariants, seven cross-field checks, `Check` records,
profile exemptions), `scoring/` (sixteen signals, `compute`, `calibrate` CLI,
`reliability_report.json`), pipeline stages 6–7 wired; `calibration/` committed from a
run on the base corpus.
**Tests.** each invariant both ways; exemptions recorded; signals table-driven;
`calibrate` deterministic (twice → identical bytes); reliability report shape.
**Gate.** `make check`; `make bench` emits the calibration curve; expected calibration
error ≤ 0.05 on the corpus; no regression.

### E6 — Pipeline, CLI, report, docs, release

**Scope.** `pipeline.py` with the eight stages; `emit` with `findings.json`; text report
regenerated; `docs/ARCHITECTURE.md` rewritten for v0.3 (diagrams included); README
"How good is it, measured" generated from `benchmarks/latest.json`; ADR index updated;
CHANGELOG `0.3.0`; tag `v0.3.0`.
**Gate.** `make check`; `make bench` green with every catalog field covered or listed as
not covered with a reason; `make demo` output byte-identical to the README block.

### E7 — Hardening against the known failure modes

**Scope.** One corpus cell and one test per known failure mode of label-based
extractors, each proven green: currency outside the profile list (must be a finding, not
silence); unknown profile (finding, no extraction); trailing attachment after totals
(no rows); out-of-order text stream (geometric `label_below`); trap labels near dates;
custom field declared in a profile appears in results and benchmark; profile added at
runtime; numbers with every thousands separator; MM/DD profile; credit note with
reference; undeclared charge; findings survive `to_dict`/`from_dict`.
**Gate.** `make check`; `make bench` green on every hardening cell; `profile lint`
reports T2 for every shipped profile.

## 4. Definition of done for v0.3.0

- [ ] E0–E7 merged in order, both gates green each.
- [ ] Every field in `docs/FIELD_CATALOG.md` is measured in `benchmarks/latest.json`.
- [ ] `calibration/reliability_report.json` committed and referenced from the README.
- [ ] `profile lint` T2 for every profile under `profiles/`.
- [ ] No module without an importer; no unit unreferenced; no profile key unread.
- [ ] `docs/ARCHITECTURE.md` describes v0.3, not v0.1.
