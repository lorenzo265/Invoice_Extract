# Agent Operating Rules

Operating rules for the autonomous agent implementing this repository. Read this file
in full before writing any code, and again before starting each new PR.

## Mission

`invoice-extractor` turns a layout-described PDF invoice into a structured, auditable
result: ten scalar fields, a table of line items, and a `Finding` for every arithmetic
invariant that disagrees — with every value traceable back to the exact text line,
bounding box, and strategy that produced it. The goal is not to cover every invoice
layout in the wild; it is to handle each layout it claims with full rigor, so a reader
can open the source, follow one field from PDF byte to JSON output, and trust every
step in between.

Alongside it, `invoice_forge` generates the corpus the extractor is measured against:
realistic, multilingual, arithmetically consistent invoice PDFs with exact ground
truth, from a seed. You are building this repository one pull request at a time, first
against `docs/IMPLEMENTATION_PLAN.md` (the extractor, PR0–PR9) and then against
`docs/FORGE_PLAN.md` (the generator, F0–F7). This file is the rulebook you follow while
you do it.

## Quality premise

Quality over continuity. If something can be better — easier to maintain, more
readable, simpler to extend — change it, without fear of touching code that works.
Rebuilding a subsystem, or the whole project, from scratch is legitimate when it is
the path to the best possible code.

- Never patch a broken design or one built with limits that complicate expansion.
  Diagnose the cause and rebuild the piece. A patch is acceptable only as a declared
  containment, with the rebuild already planned in the PR description.
- A refactor that leaves code worse "to avoid touching too much" is rejected in review.
- Proof that a rebuild preserves behaviour is still measurement: gates, golden tests,
  before/after snapshots. Rebuilding does not waive proving.

## Read order

Read these in order, once before you start and again before any PR that touches the
area a document covers:

| Order | Document | Why |
|---|---|---|
| 1 | `AGENTS.md` (this file) | The rules you operate under before writing a line of code. |
| 2 | `docs/IMPLEMENTATION_PLAN.md` | The ten PRs, in order, each with its exact scope and gate. |
| 3 | `docs/ARCHITECTURE.md` | The module boundaries and data flow the plan assumes. |
| 4 | `docs/SAMPLES_SPEC.md` | The fixture data (`acme`, `nordic`) every golden test asserts against. |
| 5 | `docs/LAYOUT_FORMAT.md` | The JSON schema that drives extraction — read before touching `layout/` or `extraction/`. |
| 6 | `docs/FORGE_PLAN.md` | The generator's PRs, F0–F7, each with its exact scope and gate. |
| 7 | `docs/FORGE_SPEC.md` | The generator's design — read before touching `invoice_forge/`. |
| 8 | `docs/VARIATION_CATALOG.md` | What the corpus must vary, and the knob for each axis. |
| 9 | `docs/GROUND_TRUTH_SCHEMA.md` | The ground-truth contract the benchmark compares against. |

If a document and the code disagree, the document is out of date, not wrong: fix the
document in the same PR that changes the behavior it describes.

## The loop

For each PR `N` in the plan, in order:

1. **Branch.** Update `main` to the latest merged state, then create
   `pr/N-<slug>`, where `<slug>` is a short kebab-case name for the PR's scope
   (e.g. `pr/2-document-reader`).
2. **Implement only that PR's scope.** Re-read the PR's entry in
   `docs/IMPLEMENTATION_PLAN.md` before writing code. Do not implement anything that
   belongs to a later PR, even if it would be convenient now — a later PR's own gate
   must be the first thing that exercises it.
3. **Run `make check` locally** (lint + typecheck + test + hygiene). Fix everything
   until it is green. This is the same command CI runs; there is no such thing as
   "passes in CI but not locally" for this repo.
4. **Open a PR** using `.github/pull_request_template.md`. Fill every section — an
   empty Decisions section means you made no judgment calls, not that you skipped it.
5. **Wait for CI to go green** on the opened PR. If it fails, fix and push — see the
   three-strikes rule below.
6. **Run the self-review checklist** (below, mirrored in the PR template) against the
   actual diff, not from memory.
7. **Squash-merge** into `main` with a Conventional Commits message summarizing the
   PR's net effect (see Commit standard). Delete the branch.
8. **Move to PR `N+1`.** Never batch two plan PRs into one branch, and never start the
   next PR while this one is still open.

**Three failed gate attempts in a row, on the same PR:** stop. Do not try a fourth
variation, and do not weaken a threshold, skip a test, or add a suppression to force
it green. Write `docs/BLOCKED.md` instead, containing: the PR number and scope, the
exact command you ran, its full output, and the three things you tried. Leave the
branch as it is and stop working on this repository until a human has read
`docs/BLOCKED.md`.

## Non-negotiables

- **Never weaken a threshold** to make a gate pass — not `--cov-fail-under`, not the
  size budget, not a hygiene limit. If the real fix is bigger than the PR's scope
  allows, the scope was wrong; shrink the scope, don't loosen the ruler.
- **Never edit `samples/*.expected.json` to make a test pass.** Those files are the
  ground truth the extractor is judged against. If a golden test fails, the extractor
  is wrong; fix `src/`.
- **Never add `# noqa` or `# type: ignore` without a same-line comment explaining why
  the suppression is correct, not convenient** — for example
  `# type: ignore[no-any-return]  # pymupdf is unannotated; scoped in pyproject.toml`.
  A suppression with no stated reason is a threshold weakened in disguise.
- **Never add a dependency, runtime or development.** `pyproject.toml`, written once
  in PR0, already carries everything the whole plan needs: PyMuPDF (`pymupdf`) at
  runtime; `ruff`, `mypy`, `pytest`, `pytest-cov`, and `pre-commit` for development. If
  a later PR seems to need something new, solve it with the standard library or the
  tools already in hand — that need is not a reason to touch the dependency lists. If
  it is genuinely unsolvable that way, that is what the three-strikes rule above is
  for, not a workaround.
- **Never exceed the size budget**: no module over 250 lines, no function over 40
  lines, in every package under `src/`. `tests/test_repo_hygiene.py` checks this by
  parsing the AST, not by a rough count — don't try to game it with dense single-line
  statements. Hitting the ceiling mid-PR is a signal to extract a module, not a signal
  to ask for more room. There is no repository-wide line total: the repository is
  growing, and a cap on its size would be a cap on what it can do.
- **Never leave a `TODO`, `FIXME`, or commented-out code block.** Work that is
  genuinely out of scope for this PR either already has a later PR in
  `docs/IMPLEMENTATION_PLAN.md` to hold it, or it doesn't belong in the repository.
- **Stop and write `docs/BLOCKED.md` after three failed gate attempts** on the same
  PR — see The loop, above. Do not keep iterating past the third attempt.

## Scope grows; the standards do not

The repository is growing from a compact extractor into a full-capability one, with a
corpus generator alongside it. Every standard in this file — names, function size,
typing, `Decimal`, frozen records, findings-not-exceptions, evidence on every value,
F.I.R.S.T. tests, Conventional Commits — applies unchanged to every new package.

- **`src/invoice_forge/`** is that new package, with its own tests under `tests/forge/`,
  the same tooling and the same hygiene checks.
- **`pymupdf` may be imported by exactly two modules** in the repository. The import
  name is `pymupdf`, never the deprecated `fitz` alias, which prints a warning to
  stderr on every import:
  `invoice_extractor/document/pymupdf_reader.py` and `invoice_forge/render/pdf.py`.
- **No runtime dependency beyond PyMuPDF**, for either package. Fonts are bundled
  files, not a dependency. Randomness is `random.Random(seed)` — never the `random`
  module's own functions, never the clock.
- **Fonts are embedded from `src/invoice_forge/fonts/`** (Liberation, OFL). Never rely
  on a system font; the corpus must render identically on every machine.

## Languages

The corpus covers Latin- and Greek-script European languages. Right-to-left scripts
(Arabic, Hebrew) are out of scope for this repository. Do not add profiles, fonts or
code paths for them.

## Code standard

Clean Code, applied concretely to this codebase:

- **Names reveal intention.** A reader should not need the function body to know what
  it does. Bad: `def proc(d, l)`. Good:
  `def extract_scalar_fields(document: DocumentReader, layout: Layout) -> list[FieldResult]`.
- **Functions stay at or under 40 lines** (enforced by the hygiene test). When a function
  grows past that while you're writing it, extract a well-named helper — don't
  compress it to fit. A function that matches a label, parses its value, and ranks
  candidates is three functions wearing one name.
- **One level of abstraction per function.** `pipeline.extract()` orchestrates: it
  calls the document reader, the layout loader, the engine, the validators, and the
  writer. It does not itself parse a date string or compute a confidence weight —
  those live one level down, in `normalizers.py` and `confidence.py`.
- **No boolean parameters.** `def find_label(line: TextLine, exact: bool) -> ...`
  forces a reader to check the signature to understand any call site —
  `find_label(line, True)` says nothing on its own. Prefer a named strategy or a
  closed vocabulary: this codebase already does it right with
  `Strategy = LABEL_RIGHT | LABEL_BELOW | REGEX_ANCHOR` instead of a `use_regex: bool`.
- **Comments explain why, never what.** Bad: `# loop over lines` above a `for` loop.
  Good: `# PyMuPDF can return lines out of visual order on rotated pages; sort by y0
  before matching "label right of" candidates.`
- **Extraction failures are data, not control flow.** A field that can't be found, or
  that fails its validator, comes back as a `FieldResult` with `valid=False` — never a
  raised exception. A cross-field disagreement (a total that doesn't reconcile, line
  items that don't sum to the subtotal) is what `Finding(severity=..., ...)` is for:
  `validation/invariants.py` emits one per invariant it checks, and never raises
  either. Exceptions are reserved for programmer errors and invalid input: a malformed
  layout JSON, a PDF path that doesn't exist.
- **Money is always `decimal.Decimal`.** Never `float`, never `round()` on a monetary
  value. Parse it through `normalizers.parse_money`, which knows the layout's decimal
  and thousands separators; never call `float(text)` on a currency value anywhere.
- **Results and specs are frozen.** `@dataclass(frozen=True, slots=True)` on every
  `Result`/`Spec` type. Immutability is what makes `Evidence` trustworthy — nothing
  downstream can mutate a `FieldResult` after ranking has already decided it.
- **No `Any` in the public API, and `mypy --strict` is not a suggestion.** The one
  exception is `ignore_missing_imports` and `follow_imports = "skip"` for `pymupdf`
  itself, scoped in `pyproject.toml`: the library ships no annotations, so every value
  it hands back is an `Any` the boundary module converts into a typed value of ours.
  That does not license `Any` anywhere else — including at the boundary in
  `pymupdf_reader.py`: wrap `pymupdf`'s untyped values in this module's own typed return
  values immediately; never let one escape.

## Test standard

- **F.I.R.S.T.** Fast — unit tests run in milliseconds, with no PDF parsing and no
  disk I/O. Independent — no test depends on another test's side effects or run
  order. Repeatable — the same result on any machine, with no wall-clock time and no
  environment-dependent paths. Self-validating — a test asserts and passes or fails;
  it never prints a value for a human to eyeball. Timely — the test for a module lands
  in the same PR as the module, never "added later".
- **One behavior per test.** If a test's name needs "and" to describe it, it is two
  tests. A test that asserts five unrelated things fails opaquely; a focused test
  fails with a name that already tells you what broke.
- **Test names are sentences.** `test_label_right_returns_none_when_label_is_absent`,
  not `test_label_right_2` or `test_strategy_case3`. The name is the spec: reading a
  test file's function names top to bottom should read like a list of behaviors.
- **Unit tests use `FakeDocument`, never a real PDF.** Everything under
  `tests/unit/` builds its `TextLine`s in memory through the `FakeDocument` fixture in
  `tests/conftest.py`. A unit test that opens a PDF is testing PyMuPDF, not this
  codebase's logic, and it is slow for no benefit.
- **PDFs appear only in `tests/integration/`.** That is where `samples/*.pdf` and the
  golden `samples/*.expected.json` files are exercised end to end, through the real
  `pymupdf_reader.py`. Anything provable without opening a PDF file, prove that way.

## Commit standard

Conventional Commits, one logical change per commit. This project's allowed types:

| Type | Use for | Example |
|---|---|---|
| `feat` | New capability visible to a caller of the library or CLI | `feat(extraction): add label_right strategy for scalar fields` |
| `fix` | Correcting wrong behavior | `fix(normalizers): parse_money handle thousands separator before decimal point` |
| `test` | Tests only, no production code change | `test(pipeline): add golden assertion for nordic line items` |
| `docs` | Documentation only | `docs(layout): document stop_labels in LAYOUT_FORMAT.md` |
| `refactor` | No behavior change, structure only | `refactor(engine): extract candidate ranking into rankers.py` |
| `build` | Build system, packaging, dependency versions | `build(pyproject): pin ruff and mypy to the versions this repo is tested against` |
| `ci` | CI workflow changes | `ci(workflow): run mypy --strict on src only` |
| `chore` | Everything else that isn't user- or developer-facing | `chore(gitignore): ignore local .coverage files` |

The squash-merge commit message for a PR is one of these, describing the PR's net
effect — not a concatenation of every intermediate commit made on the branch.

## Self-review checklist

Run this against the real diff before opening every PR. The same list lives in
`.github/pull_request_template.md` for you to check off there:

- [ ] `make check` passes locally (lint + typecheck + test + hygiene), with no step skipped or weakened.
- [ ] This PR implements exactly one plan item — no scope from an earlier or later PR leaked in.
- [ ] No `# noqa`, `# type: ignore`, or lowered coverage/size threshold was added without a same-line comment justifying it.
- [ ] No new dependency — runtime or development — was added; `pyproject.toml`'s dependency lists are unchanged.
- [ ] No file under `samples/*.expected.json` was edited.
- [ ] Every new or changed function is ≤ 40 lines and every module is ≤ 250 lines, in every package under `src/`.
- [ ] Every new public function and class is fully typed; no `Any` leaked in.
- [ ] No `TODO`, `FIXME`, or commented-out code in the diff.
- [ ] Commit message(s) follow Conventional Commits.
- [ ] The PR description's Decisions section records every judgment call made under uncertainty — or explicitly says there were none.

## Working discipline for long tasks

- Create every output file at the start of the work and append to it section by
  section; never hold a whole document in memory until the end.
- Do not launch sub-agents.

## What to do when uncertain

There is no one to ask while a PR is in flight. When the plan or the architecture doc
doesn't fully determine an implementation detail:

1. Choose the simplest option consistent with `docs/ARCHITECTURE.md`. Consistent beats
   clever; simple beats flexible.
2. Record what you chose and why in the PR description's Decisions section, in one or
   two sentences — enough for a reviewer to see the fork in the road and agree or
   overrule it later.
3. Do not stop and wait for input, and do not open the PR with the decision unmade.
   Move forward, document the call, and let the self-review checklist and CI catch
   anything the decision got wrong.
