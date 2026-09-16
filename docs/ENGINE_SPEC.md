# Engine specification — the full-capability extractor

`invoice_extractor` v0.3 turns a PDF invoice into an evidence-backed, arithmetically
checked, confidence-scored `InvoiceResult`, for any vendor described by a profile. It
keeps v0.1's principles (ADR 0001–0005) and adds five decisions (ADR 0006–0010).

## 1. Vocabulary

| Term | Meaning |
|---|---|
| **Profile** | one vendor's description (`docs/PROFILE_FORMAT.md`); the unit of configuration; replaces v0.1 layouts |
| **Variant** | a partial profile applied when a fingerprint matches (`when`); replaces "template" |
| **Spec** | a declaration of how one field is extracted: a kind, named units, profile paths; never values |
| **Unit** | a registered strategy, filter, normalizer, validator or ranker; closed vocabulary |
| **Evidence** | page, bbox, matched label, strategy, raw text — on every published value |
| **Finding** | a fact about the document (missing field, failed invariant, contradiction), with code, severity and touched fields; never an exception |
| **Reconciliation** | the cross-family pass over totals, VAT summary and line items |
| **Signal** | one named measurement per field feeding the composite confidence |

## 2. The pipeline: eight stages, one orchestration module

| # | Stage | Contract |
|---|---|---|
| 0 | `read` | `Document(pages: Sequence[Page])`; each `Page` has `TextLine`s with `BBox`, `Zone` and the page's anchors (`logo_bottom`, `table_header_band`, `totals_top`, `vat_summary_top`), computed once |
| 1 | `detect_profile` | scores every registered profile: supplier anchor match, VAT id, currency tokens, label hits; returns the best above `PROFILE_THRESHOLD` or `None`. `None` ⇒ `Finding(ERROR, "profile_not_detected")`, `valid=False`, no extraction. There is no default profile. A file-path hint may add score, never decide |
| 2 | `select_variant` | first `variants[]` whose `when` matches; returns the merged `Profile` |
| 3 | `classify_document` | `invoice` \| `credit_note` from the profile's titles and credit-reference labels; the total's sign may later promote to `credit_note`, with provenance recorded |
| 4 | `extract` | every spec, in topological order of `depends_on`, one loop, one engine; `resolved` is visible to later specs |
| 5 | `reconcile` | pure functions over `resolved`: VAT backfill from the summary, item→VAT-line linkage, charges (declared and undeclared), currency basis for dual-currency documents, confidence caps; returns `Finding`s and cap values, never mutates another field's result silently |
| 6 | `validate` | invariants (§6) and cross-field checks (§7) → `Finding`s; `checks[]` records every check run, passed or not |
| 7 | `score` | signals → composite confidence per field with calibrated weights; caps from stage 5 applied by `min()` here only |
| 8 | `emit` | `InvoiceResult` → `result.json` (+ `findings.json` mirror); all findings and checks serialized |

`pipeline.extract(pdf_path: Path, registry: ProfileRegistry) -> InvoiceResult` is the
only place stages are wired. Each stage is a module with one public function.

## 3. The engine and its six spec kinds

One `engine.run(spec, document, profile, resolved) -> FieldResult` executes every kind
through the same internal pipeline: `guard → collect → filter → normalize → validate →
rank → on_failure → publish(with Evidence)`. Kinds differ only in their `collect` units
and in what they publish.

| Kind | Collect | Publishes | Fields |
|---|---|---|---|
| `LabelSpec` | label strategies, the one the field's `placement` names first and the rest in fixed order: `label_right`, `label_beside`, `label_below` (by geometry: nearest line with horizontal overlap), `label_pattern` where a pattern is declared; a candidate that is nothing but another field's label is filtered out (`not_a_label`); zones as preference | one value | invoice_number, order_number, customer_number, customer_vat_id, invoice_date, supply_date, due_date, iban, exchange_rate (when printed), custom fields |
| `AnchorSpec` | occurrences of an expected value from the profile: exact > digits-only > fuzzy, with prefix promotion | one value + match ratio | supplier (name), supplier_vat_id, supplier address |
| `SectionSpec` | lines from a label to a stop label / blank gap / next section, bounded by `max_lines`; placeholder detection | a party block | bill_to, ship_to, mail_to |
| `TableSpec` | header row by column labels (≥ `min_header_matches`), split headers re-joined by vertical gap, column x-ranges from header words, rows by a state machine (row / continuation / sub-item / carry-forward / stop), bounded per page by `page_bounds` | rows with per-cell evidence | line_items, vat_summary |
| `BlockSpec` | the totals block by vertical clustering; components by "longest label wins"; column model per block; currency per column (printed token > profile default); identities per column (subtotal + VAT + charges = total) with tolerance; promoted column = rightmost that closes | components + charges + identity status | totals, secondary_amounts |
| `DerivedSpec` | a pure function over `resolved` | one value with `Evidence(strategy="derived")` pointing at the inputs | currency, secondary_currency, customer_country, exchange_rate (inferred) |

Engine rules:

- Units are registered by name; the vocabulary is closed; a hygiene test asserts every
  registered unit is referenced by a spec and every spec references only registered units.
- Specs are frozen dataclasses validated at import: every profile path they name must
  exist in `Profile`; exclusive slots cannot both be set.
- One identity per spec (`name`), equal to the field catalog name.
- Geometry over stream order: no unit indexes `lines[i+1]`.
- Every published value carries `Evidence`; publishing without it is a type error.
- `on_failure` ∈ `{not_found, best_invalid}`; `not_found` yields `Finding(WARNING,
  "field_missing")` for a field the profile marks `required`. A third name, `shaped`, was
  planned and is not here: publishing a candidate whose shape matched but whose content
  did not is exactly what `best_invalid` does, and a vocabulary entry no spec names is
  the thing the closed-vocabulary rule above forbids.
- Spec docstrings ≤ 10 lines; rationale lives in ADRs and the benchmark README.

## 4. Profiles

See `docs/PROFILE_FORMAT.md`. Design rules: one schema (dataclasses) and one strict
loader; one merge function; every key has a reader (hygiene test); numeric format is
profile data with no code fallback; the `ProfileRegistry` re-reads a profile whose file
mtime changed, so a profile added at runtime is detected on the next document;
`profile lint` measures readiness.

## 5. Reconciliation (stage 5)

| Function | Rule |
|---|---|
| `backfill_vat` | `vat_amount` missing or zero ← Σ `vat_summary[].vat`; fallback `total − subtotal − declared charges` only when the implied rate ∈ [0, 0.30]; negative VAT only with negative total. `vat_rate` missing ← the rate of the summary line with the largest base (the higher rate on a tie), else the rate most of the line items' net is charged at |
| `cross_check_totals_vs_summary` | three booleans (vat agrees, base agrees, arithmetic closes) → any `False` caps the confidence of the disagreeing fields at 0.5 and emits `Finding(WARNING, "totals_summary_disagree")` |
| `link_items_to_vat_lines` | each line item and declared charge gets its VAT line by rate/code; ambiguous linkage is a finding, not a guess |
| `resolve_charges` | declared charges from the block; an undeclared charge is inferred only when `total − subtotal − vat` is non-zero beyond tolerance and reported as `Finding(WARNING, "undeclared_charge_inferred")` with the amount |
| `choose_currency_basis` | for dual-currency documents, the currency in which the identities close; recorded once and reused by validation |

## 6. Invariants (stage 6)

Absolute tolerance from the profile (`totals.tolerance.absolute`, default 0.01), relative
for the grand-total identity (default 0.5 %). Each is a function returning `Finding | None`
and a `Check` record:

`subtotal_plus_vat_equals_total`, `line_items_sum_equals_subtotal`,
`line_items_sum_equals_total_when_no_vat`, `vat_equals_subtotal_times_rate`
(single-rate documents), `per_rate_vat_consistency`, `summary_base_sums_equal_subtotal`,
`summary_vat_sums_equal_vat_total`, `line_totals_plus_charges_equal_grand_total`,
`line_items_vat_sum_equals_vat_total`, `document_type_matches_total_sign` (advisory).

A profile may exempt an invariant with a reason (`invariants.exempt[]`, e.g. reverse
charge); the exemption is itself recorded as an INFO finding.

## 7. Cross-field checks

`invoice_number_in_filename`, `vat_prefix_matches_country`, `dates_in_order`
(supply ≤ invoice ≤ due), `currency_agrees_across_families`, `customer_vat_differs_from_supplier`,
`bill_to_country_matches_customer_vat`, `credit_note_references_invoice`. Each emits a
finding on failure and a check record always.

## 8. Signals and confidence (stage 7)

Sixteen named signals per field: `label_found`, `label_similarity`, `value_format_match`,
`format_pattern_match`, `format_canonical_distance`, `zone_match`,
`arithmetic_consistency`, `invariant_corroboration`, `competing_candidates`,
`runner_up_gap`, `cross_field_consistency`, `profile_match`, `length_plausible`,
`structural_completeness`, `count_plausibility`, `min_component_strength`.

`compute(signals, weights)`: booleans → 0/1; absent signals excluded; weights
renormalised over the emitted signals; clamp [0, 1]; optional monotone calibration map;
caps from stage 5 by `min()`. Fields without fitted weights use the uniform mean and are
tagged `confidence_source = "uniform"`.

## 9. Calibration (offline, deterministic)

`invoice-extractor calibrate --corpus corpus/ --truth corpus/ --out calibration/`
fits per-field weights and monotone maps on the synthetic corpus — which contains
negatives by construction (difficulty knobs, mutated documents) — and writes
`weights.json`, `calibration_maps.json` and `reliability_report.json` (predicted
confidence vs observed hit rate, per field, in ten bins). Same corpus and seed → same
files, byte for byte. Promotion of a fitted file into the repository is a reviewed PR;
there is no automatic trigger, no watermark, no thread.

## 10. What is deliberately absent

No default profile. No threshold-based routing to external reviewers. No AI review. No
per-process caches of profiles. No second schema. No history in docstrings. No value
without evidence. No finding kept only in memory.
