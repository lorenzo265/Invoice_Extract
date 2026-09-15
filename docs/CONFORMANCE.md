# Conformance audit — what the documents require, and what the code does

Audited at `e57ea4a` (the E6 head) and resolved in E7. Every row was checked against the
code rather than against a previous audit; the "where" column names the module a reader
can open to see the claim for themselves.

Three verdicts:

| Verdict | Meaning |
|---|---|
| **implemented** | the code does what the document says, under the name the document uses |
| **different** | the code does the thing, but not the way or not under the name the document fixes — the row says how, and why the difference was kept |
| **absent** | the document names it and the code has not got it — the row says why, and what was decided |

A row marked **E7** is work this session did. A row marked **kept** or **deferred** is a
difference this session looked at and chose to leave, with the reason in the row.
Deliberate departures taken by the earlier sessions of this series are listed beside the
ones found now, not hidden by omission.

## Contents

1. [`docs/ENGINE_SPEC.md` — the extractor](#1-docsengine_specmd)
2. [`docs/ENGINE_PLAN.md` — the series and its fixed names](#2-docsengine_planmd)
3. [`docs/FIELD_CATALOG.md` — the shared vocabulary](#3-docsfield_catalogmd)
4. [`docs/PROFILE_FORMAT.md` — the profile schema](#4-docsprofile_formatmd)
5. [`docs/adr/*` — the ten decisions](#5-docsadr)
6. [`docs/FORGE_SPEC.md` and `docs/FORGE_PLAN.md` — the generator](#6-docsforge_specmd-and-docsforge_planmd)
7. [`docs/GROUND_TRUTH_SCHEMA.md`](#7-docsground_truth_schemamd)
8. [`docs/VARIATION_CATALOG.md`](#8-docsvariation_catalogmd)
9. [`docs/IMPLEMENTATION_PLAN.md` §1–§2 — the global constraints](#9-docsimplementation_planmd-12)
10. [What was decided, in one table](#10-what-was-decided-in-one-table)

---

## 1. `docs/ENGINE_SPEC.md`

### §2 — the eight stages

| # | Stage | Verdict | Where | Decision |
|---|---|---|---|---|
| 0 | `read` | implemented | `document/pymupdf_reader.py`, `document/anchors.py` | — |
| 1 | `detect_profile` | implemented | `profile/detect.py`; `pipeline.extract` | — |
| 2 | `select_variant` | **was absent → implemented** | `profile/variants.py`; `profiles/en-GB.json` | **E7.** `Variant` was loaded and validated and nothing applied it; no profile declared one. Stage 2 now runs between detection and classification, `en-GB` declares a `credit-note` variant, and `tests/integration/test_hardening.py` proves it fires on the two credit notes of that vendor and on nothing else |
| 3 | `classify_document` | implemented | `extraction/classify.py` | the total's sign does not promote to `credit_note`; see §3 below |
| 4 | `extract` | implemented | `extraction/engine.py`, `pipeline._resolve` | — |
| 5 | `reconcile` | implemented | `reconcile/stage.py` | signature differs; see §5 |
| 6 | `validate` | implemented | `validation/stage.py` | — |
| 7 | `score` | implemented | `scoring/` | — |
| 8 | `emit` | implemented | `output/json_writer.py`, `cli.py` | — |

**Stage 2's ordering.** A variant may be keyed on `document_type`, which stage 3 decides;
stage 2 runs first. `select_variant` therefore classifies against the base profile — the
only vocabulary that exists before a variant is chosen — and stage 3 then classifies
again against the merged one. A variant that changes the titles changes what stage 3
concludes, not what chose it. Written down in the module docstring.

**Stage 3, sign promotion.** ENGINE_SPEC says "the total's sign may later promote to
`credit_note`, with provenance recorded". It does not: `classify_document` reads titles
and credit-reference labels only, and `document_type_matches_total_sign` reports the
disagreement as an advisory invariant instead. *Kept*: promoting on sign would make the
advisory invariant unable to fire, and a negative total on a document titled `INVOICE` is
a fact worth reporting rather than one worth silently resolving. Recorded here because
the spec sentence is now wrong; it is left in place because deciding which of the two
behaviours is wanted is a design question, not a hardening cell.

### §3 — the engine and its six spec kinds

| Rule | Verdict | Where | Decision |
|---|---|---|---|
| one `engine.run` for every kind | **different** | `extraction/engine.py` | `run` takes `LabelSpec \| AnchorSpec \| DerivedSpec`. The three structural kinds have runners of their own — `extraction/section.py`, `line_items.py`/`table.py`, `block.py` — because what they publish is a block, a table and a set of components rather than one value. *Kept*: the spec's own table says the kinds "differ only in their collect units and in what they publish", and what they publish is exactly what a single signature could not carry. `Spec` and `Structure` are the two unions this split produced |
| closed unit vocabulary, both directions | implemented | `extraction/units/registry.py`; `tests/test_unit_registry.py` | — |
| specs validated at import | implemented | `extraction/spec.py::validate` | — |
| one identity per spec, equal to the catalog name | implemented | `extraction/specs.py` | — |
| geometry over stream order | implemented | `extraction/units/strategies.py` | proved again in E7: `test_a_value_under_its_label_is_found_however_the_stream_is_ordered` |
| evidence on every published value | implemented | `domain/models.py`, `domain/evidence.py` | — |
| `on_failure ∈ {not_found, best_invalid, shaped}` | **different — spec corrected** | `extraction/spec.py::OnFailure` | **E7.** The enum has two. `shaped` — publish a candidate whose shape matched but whose content did not — is what `best_invalid` already does, and a vocabulary entry no spec names is what the closed-vocabulary rule two rows up forbids. The spec and `ENGINE_PLAN` §2 were corrected to name the two that exist, rather than a third being added to match the prose |
| `not_found` yields `Finding(WARNING, "field_missing")` for required fields | **was absent → implemented** | `extraction/engine.py::_missing`; `pipeline._missing` | **E7.** No `field_missing` was ever emitted: a required field that did not resolve came back with `value=None` and nothing said so. It is now emitted for `LabelSpec`, `AnchorSpec` and `DerivedSpec` alike. Block components are excluded, and `docs/FIELD_CATALOG.md` says why: `subtotal`, `vat_amount`, `total_amount` and `vat_rate` are parts of a block rather than labelled fields, and a document missing one is caught by the arithmetic, which says more than its absence would |
| spec docstrings ≤ 10 lines | implemented | — | — |

### §4 — profiles

| Rule | Verdict | Where |
|---|---|---|
| one schema, one strict loader | implemented | `profile/schema.py`, `profile/loader.py` |
| one merge function | implemented | `profile/merge.py` |
| every key has a reader | implemented | `tests/test_profile_contract.py` |
| numeric format is data, no code fallback | implemented | `profile/parts.py::number_format` |
| registry re-reads on mtime change | implemented | `profile/registry.py` |
| `profile lint` measures readiness | implemented | `profile/lint.py` |

### §5 — reconciliation

All five functions exist under their own names in `reconcile/amounts.py` and
`reconcile/summary.py`, and `reconcile/stage.py` runs them in one order.

| Difference | Decision |
|---|---|
| `reconcile(resolved, profile)` in the plan takes `(fields, charges, items, summary, profile)` | *kept*: the five functions the spec names read the charges, the rows and the VAT summary, and none of those is a `FieldResult`. Passing them is what lets the stage stay a pure function of what the earlier stages published |
| `Reconciliation` carries `fields`, `charges`, `items` and `currency` beyond the plan's `findings, caps, currency_basis` | *kept*: the stage's whole purpose is to fill in what the document left out, so it has to hand back what it filled in |
| `link_items_to_vat_lines` ran and its result was discarded | **E7 — published.** The linkage was computed, produced findings, and never reached `InvoiceResult`. §5 says each line item and declared charge *gets* its VAT line, so each now carries it: `LineItem.vat_line` and `Charge.vat_line`, serialized, round-tripped, and `None` where the document prints no summary or more than one line could be the row's |

### §6–§8 — invariants, cross-field checks, signals

| Rule | Verdict | Where |
|---|---|---|
| the ten invariants, by name | implemented (10/10) | `validation/invariants.py::INVARIANTS` |
| the seven cross-field checks, by name | implemented (7/7) | `validation/cross_field.py::CHECKS` |
| `checks[]` records every rule run, passed or not | implemented | `validation/stage.py`, `domain/checks.py` |
| profile may exempt an invariant, recorded as INFO | implemented | `validation/stage.py::EXEMPT` — no shipped profile uses it; the key has a reader and a test |
| the sixteen named signals | implemented (16/16) | `scoring/signals.py::SIGNAL_NAMES` |
| `compute`: renormalise, clamp, optional map, caps by `min()` | implemented | `scoring/compute.py` |
| fields without fitted weights tagged `uniform` | implemented | `domain/models.py::UNIFORM` |

### §9–§10 — calibration, and what is deliberately absent

| Rule | Verdict | Note |
|---|---|---|
| `calibrate` writes three files, deterministically | implemented | `scoring/calibrate.py`; twice → identical bytes (tested) |
| no default profile, no external routing, no AI review, no second schema, no value without evidence, no finding kept only in memory | implemented | the last of these was the one gap: `Reconciliation.links` was a finding's worth of work kept only in memory, and E7 published it |
| `weights.json` is empty and every field scores by the uniform mean | **different — kept, and now structural** | ADR-0009 says calibration needs negatives. At E6 nine values out of 3 681 were wrong and no signal separated them. After E7 the corpus has **no** wrong scalar values at all, so there are no negatives by construction and a fit is not merely unhelpful but undefined. `fitted: false` is the honest report, and the reliability report says so per field |

---

## 2. `docs/ENGINE_PLAN.md`

### §2 — fixed names

Everything in §2 exists under its declared name, with these differences:

| Name | Difference | Decision |
|---|---|---|
| `validation/__init__.py::Check` | lives in `domain/checks.py` | *kept*: `domain/models.py` serializes a `Check`, and the domain is the inner ring — importing `validation` from it would invert the dependency. `validation/` re-exports nothing it does not own |
| `Spec` union | split into `Spec` and `Structure` | *kept*; see §3 of ENGINE_SPEC above |
| `OnFailure` | two members, not three | **E7**, spec corrected; see above |
| `reconcile()` signature and `Reconciliation` shape | wider | *kept*; see §5 above |
| `InvoiceResult` | also carries `charges` | *kept*: `docs/FIELD_CATALOG.md` requires it — a charge is a row of the totals block and not a field |
| six units deleted in E4 | `parse_money`, `parse_percent`, `is_money`, `is_percent`, `looks_numeric`, `last_page_first` | *agreed*: the closed-vocabulary rule runs in both directions, and a registered unit no spec names is exactly what `tests/test_unit_registry.py` forbids. Verified: none of the six is named by any spec, and the behaviour each carried is reachable through a unit that is named |

### §3 — the scope of each PR

E0–E6 are merged and their gates were green. E7 is this session; its scope is §4 below.

---

## 3. `docs/FIELD_CATALOG.md`

| Name | Verdict | Decision |
|---|---|---|
| the 9 labelled scalars, the 4 totals components, the 5 custom fields | implemented and measured | 18 fields in `benchmarks/latest.json` at E6 |
| `iban` | **was absent → implemented** | **E7.** The generator drew a valid IBAN and printed it in the bank footer; the truth never recorded it and no spec read it. Now: a `LabelSpec` found by shape (`label_pattern`) and judged by ISO 13616's checksum, the truth records it, and the benchmark measures it. It is *not* in the generator's `LABELLED_FIELDS`, because that set is what a lexicon declares synonyms for and is also what the renderer draws one label per document from — adding a key there would have changed the draw order and regenerated the whole corpus. `UNLABELLED_FIELDS` is the set that exists to keep those two questions apart |
| `document_type` | **was absent from the benchmark → measured** | **E7.** The truth carried `document.type`, the result carried `InvoiceResult.document_type`, and nothing compared them — so the field the whole sign of the document depends on was unmeasured. It is now reported in a section of its own, beside the fields rather than among them, because no spec resolves it: stage 3 does, before any spec runs |
| `secondary_currency`, `exchange_rate` | **different — catalog corrected** | Both are read and both are measured, under `secondary_amounts` rather than as flat scalar fields. *Kept*: the echo is one record — an amount, the rate it was converted at, the currency it is in — and a currency code published apart from the amount it prices is a code with nothing to spend it on. The catalog now says where they are |
| `customer_country`, and `country` on every party | **absent — deferred with evidence** | The catalog specifies a four-rung derivation (VAT prefix > bill_to > ship_to > postal pattern). Measured against the corpus: the first rung is *wrong* without a table this repository has not got — Greece's VAT prefix is `EL` against country code `GR`, wrong on 10 of 250 documents, and `tr-TR` prints VAT ids with no prefix at all, yielding nothing on 7 more. The other three rungs need country names per language and postal shapes per country, and no profile key, lexicon entry or ADR says where that data lives. And the corpus cannot falsify it: **every customer in it is in its supplier's own country**, so a derivation returning the supplier's country unconditionally would score 100 % and mean nothing. Deciding where the reference data lives is a schema change with an ADR, not an E7 hardening cell. `docs/FIELD_CATALOG.md` now carries this reasoning |
| line-item `pos`, `unit`, `discount_pct`, `vat_rate` | read, published, not scored | *confirmed unchanged*: the corpus records a box for five of the nine columns, `benchmarks/README.md` scores those five and reports the rest as read and not measured, and the catalog says the same. Code and documents still agree |
| line-item `vat_code`, `subscription` | not read | *confirmed unchanged*: neither is in `domain/rows.py::LINE_ITEM_COLUMNS`, and the catalog says both "wait for a corpus that prints them". Still true |
| findings vocabulary | **corrected** | `field_missing` was missing from the list, consistent with its never being emitted. Both were fixed in E7 |

---

## 4. `docs/PROFILE_FORMAT.md`

| Rule | Verdict | Note |
|---|---|---|
| layering: defaults → profile → variant | **was half-implemented → implemented** | the third layer had no applier until E7 |
| `@<map>.<key>` lexicon references | implemented | `profile/lexicon.py` |
| every top-level key, every `FieldProfile`/`SectionProfile`/`TableProfile`/`BlockProfile` key | implemented and read | `tests/test_profile_contract.py` holds "every key has a reader" |
| `required` ⇒ `Finding(WARNING, "field_missing")` | **was absent → implemented** | the key was read by `profile lint` only; now the engine reads it too |
| `variants[].when ∈ {document_type, any_text}` | implemented | both branches exercised: `en-GB` uses `document_type`, `profile/variants.py` implements `any_text` and a unit test covers it |
| `profile lint` tiers T0/T1/T2 | implemented | — |
| "a new profile ships at T2" | **was false for two profiles → true** | **E7.** `fi-FI` was T1 on `due_date` and `sv-SE` on `invoice_date`, each naming two labels where every other language named three. Both now name a third their language really uses. All 22 profiles are T2 |

---

## 5. `docs/adr/`

| ADR | Verdict | Note |
|---|---|---|
| 0001 field specs declared, not subclassed | implemented | `extraction/specs.py` is declarations only |
| 0002 every value carries evidence | implemented | including derived values, which point at the line they were computed from |
| 0003 money is `Decimal`, never float | implemented | `tests/test_repo_hygiene.py` forbids `float(` on money paths |
| 0004 layouts are data | superseded by 0006 | `layouts/` is gone; the directory at the repo root is a leftover empty folder, not read by anything |
| 0005 findings, not exceptions | implemented | and E7 removed the last silence: a required field that resolves nothing now says so |
| 0006 profiles, not layouts | implemented | one profile file per vendor, shared by both packages |
| 0007 one engine, six spec kinds | *different* | see §3 above: one engine for the three value kinds, three readers for the three structural ones |
| 0008 no default profile | implemented | proved again in E7 |
| 0009 calibration needs negatives | implemented — and now binding | with the corpus at 100 % there are no negatives, so nothing is fitted and the report says so |
| 0010 findings and checks always serialized | implemented | proved again in E7 by a round-trip over a document with both |

---

## 6. `docs/FORGE_SPEC.md` and `docs/FORGE_PLAN.md`

The generator's own definition of done (v0.2.0) is met and was re-verified this session:
`make corpus` is reproducible byte for byte, `forge verify corpus/` is green, and
`forge catalog corpus/` meets every target in the variation catalog.

| Finding | Verdict | Decision |
|---|---|---|
| **`trap_labels.delivery_date` was the language's own `supply_date` label** in 15 of the 16 lexicons | **bug → fixed** | **E7, and the largest finding of this audit.** Only `fr` had it right. Everywhere else the first `delivery_date` trap was a string the same lexicon declared as a real `supply_date` label, so a document with `trap_labels` on and `supply_date` off printed `Lieferdatum: 04-Sep-2024` while its truth said it carried no supply date. The extractor read it and was *right* to: `not_a_trap` deliberately refuses to drop a candidate a field's own label introduced. This was the whole of the 9 `supply_date` misses — a defect in the generator's lexicon, not in the extractor. All 15 now follow French: a dispatch noun and a dispatch participle, none of them a label any field owns. `tests/forge/unit/test_lexicon_loader.py` holds the invariant |
| lexicon synonyms per field: `3–5` per `VARIATION_CATALOG.md` | **different — not met, broadly** | Measured: `currency` has 1 synonym in all 16 languages; `contract_number`, `customer_vat_id`, `our_reference`, `your_reference` and `payment_terms` have 2 in all 16; `supply_date` has 2 in 13. Only the two outliers `profile lint` flags were brought up, because bringing every field to three would rewrite every lexicon and regenerate the whole corpus — the one change in this series that has already cost a session's work. *Deferred*, recorded here, and the catalog's "3–5" is the number to hold a future lexicon PR to |
| `en` lexicon's reverse-charge sentence names HMRC, and is used by `en-IE` | **different — deferred** | One lexicon serves `en-GB` and `en-IE`, so an Irish invoice prints a British tax authority. Cosmetic, and fixing it means either a second English lexicon or a per-profile override — both of which change the draw order and regenerate the corpus. Not worth that in a hardening PR |
| `tests/test_field_catalog_matches_extractor.py` named in F0 | **different** | the check exists, in `tests/test_profiles_shipped.py`, which holds catalog ⇔ generator ⇔ extractor name equality. *Kept*: one file, one subject |
| `VARIATION_CATALOG` lists a **due date** trap | absent | `TRAP_KINDS` is `order_date`, `delivery_date`, `print_date`. A due date beside an invoice date is a real trap and the corpus prints one anyway — as the real `due_date` field — so nothing is untested. *Kept*, noted |

---

## 7. `docs/GROUND_TRUTH_SCHEMA.md`

| Rule | Verdict | Note |
|---|---|---|
| `fields.<name>.value` normalised the extractor's way | implemented | `truth/values.py` |
| **every canonical field name present, with `null`s** | **was false → true for `iban`** | the truth wrote `LABELLED_FIELDS`, 18 names; the catalog names more. `iban` is now written too. `customer_country` is not, and §3 above says why |
| `evidence` is a list, read back from the produced PDF | implemented | `truth/locate.py` |
| undeclared amounts carry no evidence | implemented | and E7 re-proves it |
| `noise[]` kinds | implemented (7/7) | — |
| determinism | implemented | re-proved this session twice, including that the IBAN change left every corpus PDF **byte-identical** — only the truth files gained a field |
| the comparison rules | implemented | `benchmarks/compare.py`'s header states them, and the header's rule — "a value produced is always judged against what the document carries", an unprinted value read as `absent` — is the same rule the cells, parties and VAT lines are scored by. *Verified*: `_score`, `_columns`, `_parties`, `_vat_columns` and `_charges` all branch on whether the truth recorded a box |

---

## 8. `docs/VARIATION_CATALOG.md`

Every axis has its knob and every knob is exercised; `forge catalog` is the check and it
passes. The two rows that did not hold are the lexicon ones in §6.

---

## 9. `docs/IMPLEMENTATION_PLAN.md` §1–§2

| Constraint | Verdict |
|---|---|
| module ≤ 250 counted lines, function ≤ 40 | implemented (`tests/test_repo_hygiene.py`) |
| `mypy --strict`, no `Any` in `src/` | implemented |
| ruff clean, formatted | implemented |
| coverage: floor 90 %, repository at 100 % | implemented |
| frozen + slots dataclasses | implemented |
| `Decimal` for money | implemented |
| findings, not exceptions | implemented |
| evidence on every value | implemented |
| no TODO/FIXME markers | implemented |
| PyMuPDF the only runtime dependency | implemented |
| `pymupdf` imported in two modules only | implemented |

---

## 10. What was decided, in one table

**Fixed in E7**

| # | Finding | Fix |
|---|---|---|
| 1 | stage 2 `select_variant` did not exist | implemented, with a profile that declares a variant and tests |
| 2 | `Finding(WARNING, "field_missing")` was never emitted | implemented for label, anchor and derived specs |
| 3 | `OnFailure` named two values, the spec named three | spec corrected to the two; `shaped` is `best_invalid` |
| 4 | `Reconciliation.links` was computed and thrown away | published as `LineItem.vat_line` and `Charge.vat_line` |
| 5a | `iban` was in the catalog, read by nothing, recorded by nothing | implemented end to end and measured |
| 5b | `document_type` was in the catalog and measured by nothing | measured |
| 13 | **15 of 16 lexicons made a field's own label its trap** | fixed; `supply_date` went 0.955 → 1.000 |
| 14 | `fi-FI` and `sv-SE` were below the lint median | a real third synonym each; all 22 profiles T2 |
| 15 | `is_iban` let the profile's locating pattern override the standard's shape | the validator now enforces ISO 13616 itself |
| 19 | **a table was closed by a stop label printed beside it, not across it** | found by a hardening cell, not by the audit: `multi_rate` with `vat_summary_table` *off* prints the VAT summary on the left and the totals block on the right, sharing a band of the page and no column. `Arvonlisävero:` three hundred points to the right of the summary's last column closed the summary after one row of three, and `vat_rate` then came from the wrong line. A stop label now closes a table only where it is drawn across the table's own width. This combination existed in no base cell: every `multi_rate` document in the 250 also had `vat_summary_table` on |

**Deferred, with the reason**

| # | Finding | Why not now |
|---|---|---|
| 5c | `customer_country` and party `country` | the derivation needs reference data no document places, and the corpus cannot falsify it — every customer is in its supplier's country |
| 16 | lexicon synonym counts below the documented 3–5 | rewriting every lexicon regenerates the whole corpus; the two the lint flags were fixed |
| 17 | the `en` lexicon's HMRC sentence on Irish invoices | same reason, and cosmetic |
| 18 | the total's sign does not promote to `credit_note` | doing so would silence the advisory invariant that reports the disagreement; which behaviour is wanted is a design question |

**What the hardening cells were worth**

Twenty cells were appended to `corpus/plan.json`, one per failure mode the corpus can
print. They found one bug the audit had not — item 19 — because they turned on a knob
combination the base corpus never drew: `multi_rate` appears 13 times in the 250 and is
paired with `vat_summary_table` every one of them. The cell that turned the first on
without the second is the whole reason the defect is fixed rather than latent.

**Confirmed as already correct**

Items 6 and 7 of the brief — the unscored line-item columns, and `vat_code`/`subscription`
being unread — were checked against both the code and the documents and still agree.
So do the four deliberate departures of the earlier sessions: `Check` in `domain/`, the
wider `reconcile()`, the six deleted units, and the empty `weights.json`. The benchmark's
`absent` rule is stated in `benchmarks/compare.py`'s header and is the same rule applied
to cells, parties and VAT lines.
