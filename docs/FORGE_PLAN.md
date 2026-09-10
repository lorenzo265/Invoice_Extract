# Forge plan — PR series F0–F7

Executed under the gate protocol of `docs/IMPLEMENTATION_PLAN.md` §1 (branch
`pr/F<N>-<slug>`, one PR's scope, `make check` green, template, CI, self-review,
squash-merge, next). Three failed gate attempts: `docs/BLOCKED.md`, stop.

Refactoring the existing extractor packages to accommodate the generator is expected
and welcome (see the quality premise in `AGENTS.md`); every such change is recorded
under "Decisions" and proven by the existing golden tests.

## Global constraints for this series

- New package `src/invoice_forge/`; tests under `tests/forge/`; same tooling, same
  hygiene (module ≤ 250, function ≤ 40, `Decimal`, frozen records, `mypy --strict`).
- `fitz` imported only in `invoice_forge/render/pdf.py` and the extractor's reader.
- No new dependency. Fonts bundled. `random.Random(seed)` only; never `random` module
  functions, never time.
- The base corpus PDFs are NOT committed; `corpus/plan.json`, the golden PNGs and the
  truth files of a small **fixture corpus** (`tests/forge/fixtures/`, ≤ 12 documents)
  are.

---

## PR F0 — Field catalog and package skeleton

**Goal.** One shared vocabulary of field names, and an empty, wired generator package.

**Scope.** `docs/FIELD_CATALOG.md` (every canonical field the extractor knows, its
type, normalisation rule and whether it is scalar, party, table or totals — generated
by a script from the extractor's specs and checked by a test that they agree);
`src/invoice_forge/{__init__,knobs,cli}.py`; `src/invoice_forge/fonts/` with the five
Liberation files and `LICENSE`; `tests/forge/test_knobs.py`,
`tests/test_field_catalog_matches_extractor.py`; `tests/test_repo_hygiene.py` updated
(repository line budget removed; per-module/function limits kept; `fitz` allowed in
the two named modules); `Makefile` targets `corpus`, `bench` (stubs that fail
clearly), `pyproject.toml` script entry `forge`.

**Gate.** `make check`; `forge --help` exits 0.

## PR F1 — Document model and sampler

**Scope.** `model/`, `sample/`, `profiles/schema.py` + `loader.py`, `lexicon/loader.py`,
profiles `en-GB`, `de-DE`, `fr-FR`, `sv-SE`, lexicons `en`, `de`, `fr`, `sv`;
`tests/forge/unit/` for: totals recompute under both rounding policies, credit-note
inversion, IBAN checksum validity, VAT id pattern conformity, profile/lexicon loader
errors naming the JSON path, sampler determinism (same seed → equal model).

**Gate.** `make check`.

## PR F2 — Renderer and the `classic` family

**Scope.** `render/{pdf,text,table,pagination}.py`, `layout/{spec,classic}.py`,
`truth/builder.py` (values + placement log → truth JSON with readback bboxes),
`forge render-one`; golden test: `render-one --profile de-DE --family classic --seed 7`
must reproduce the prototype's content structure (two pages, carry-forward, VAT
summary, declared shipping, secondary echo, footer) and be byte-deterministic; a
golden PNG per profile (4) committed under `tests/forge/fixtures/`.

**Gate.** `make check`; `forge verify` on the four rendered documents.

## PR F3 — Verification and catalog

**Scope.** `truth/verify.py` (`forge verify`: readback, arithmetic, declared/undeclared
evidence rule, determinism by regeneration), `forge catalog` (coverage against
`docs/VARIATION_CATALOG.md` rows), `corpus/plan.json` format + `forge generate --plan`.

**Gate.** `make check`; `forge verify tests/forge/fixtures/` exits 0; a deliberately
corrupted truth file makes it exit non-zero (test).

## PR F4 — Knobs, part one (structure)

**Scope.** `multi_page`, `carry_forward`, `page_numbering`, `wrapped_description`,
`sub_items`, `section_subtotals`, `discount`, `party_blocks`, `placeholder_addresses`,
`trap_labels`, `customer_vat_position`, `repeat_letterhead`; one unit test per knob on
the model/placement log (no PDF) and one integration test per knob on a rendered
document.

**Gate.** `make check`; `forge verify` on the fixture corpus regenerated with these knobs.

## PR F5 — Knobs, part two (money and tax) and the remaining families

**Scope.** `multi_rate`, `vat_summary_table`, `declared_charge`, `undeclared_charge`,
`rounding_per_line`, `rounding_total`, `dual_currency_echo`, `credit_note`,
`exemption_verbiage`, `amount_in_words`, `thousands_variant`, `stamp_copy`,
`bank_footer`, `noise_footer`, `payment_terms_block`; families `tabular`, `stacked`,
`saas`, `minimal` as `FamilySpec` values with golden PNGs.

**Gate.** `make check`; `forge catalog` on the fixture corpus shows every knob at least
once on and once off.

## PR F6 — Remaining profiles and the base corpus

**Scope.** Profiles and lexicons for the remaining languages/countries in
`docs/FORGE_SPEC.md` §3.1; diacritic test strings; `corpus/plan.json` for the ~250
document base corpus meeting the coverage targets; `make corpus`.

**Gate.** `make check`; `make corpus && forge verify corpus/ && forge catalog corpus/`
with every coverage target met; `make corpus` twice → identical hashes.

## PR F7 — Benchmark

**Scope.** `benchmarks/run.py` (`make bench`): extractor over `corpus/`, comparison per
`docs/GROUND_TRUTH_SCHEMA.md`, `benchmarks/latest.json` + `benchmarks/README.md`
(matrix field × profile × family × knob, calibration table, "not covered" list);
README section "How good is it, measured"; CHANGELOG `0.2.0`; tag `v0.2.0`.

**Gate.** `make check`; `make bench` produces both files; the README block is generated
from `latest.json`, not typed.

## Definition of done for v0.2.0

- [ ] F0–F7 merged in order, CI green each.
- [ ] `make corpus` reproducible byte for byte; `forge verify corpus/` green.
- [ ] `forge catalog corpus/` meets every target in `docs/VARIATION_CATALOG.md`.
- [ ] `make bench` matrix published; every extractor field either measured or listed
      as "not covered".
- [ ] No real company, bank, person or identifier anywhere in profiles, lexicons,
      catalogues or fixtures (hygiene test).
