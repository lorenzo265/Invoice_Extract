# Contributing

This file is for a person arriving at the repository for the first time. It says what to
read, in what order, and what you are allowed to ignore. `AGENTS.md` is a different
document, addressed to an autonomous agent working on this code — you do not need it.

## What this repository holds

Two programs, in one working tree, distributed apart.

| | what it is | you need it when |
|---|---|---|
| **`invoice_extractor`** | the engine: a PDF in, a typed and evidence-backed result out | always |
| **`invoice_forge`** | a generator of synthetic invoices with exact ground truth | only when changing how the engine is *measured* |

They share no code — neither imports the other's modules — and they share one thing:
the vendor profiles and language lexicons under `src/invoice_extractor/data/`. The
generator draws what a profile describes and the extractor reads it back, which is how a
change to either is caught by the other (ADR-0006).

**If you are here to read invoices, `invoice_forge` is 46 % of the code you can ignore.**

## Read these three files, in this order

Half a day, and everything else follows from them. They are the three most depended-upon
modules in the project, which is why they are the three to read.

1. **`src/invoice_extractor/profile/schema.py`** — what a vendor *is*. Thirty-five modules
   depend on it. Every label, zone, number format and table description a vendor has is a
   field of these records, and nothing in the engine names a vendor any other way.
2. **`src/invoice_extractor/document/model.py`** — what a *page* is. A line, its box, and
   the zone of the grid it was drawn in. Everything geometric is expressed in these.
3. **`src/invoice_extractor/domain/models.py`** — what a *result* is. Fields, rows,
   parties, findings, checks, and the evidence each carries.

Then `src/invoice_extractor/pipeline.py`, which is the only module that wires stages
together and does nothing itself. It is eighty lines and it is the map of the whole
engine: read the page, detect the vendor, pick the variant, classify, extract, reconcile,
validate, score, emit.

## Then, when you need them

- **`docs/ARCHITECTURE.md`** — the eight stages and the six boundaries, with diagrams.
  Read §1 and §5; §5 follows one value from the page to the result.
- **`docs/ENGINE_SPEC.md`** — the contract the engine keeps. Where it and the code
  disagree, the spec wins and the disagreement is a bug.
- **`docs/adr/`** — ten decisions and why. `0006` (profiles, not layouts) and `0002`
  (every value carries evidence) explain more of the design than anything else.
- **`docs/CONFORMANCE.md`** — every requirement against what the code actually does,
  including what was deliberately left undone and why. Read it before concluding
  something is missing by accident.

## Seeing it work

```bash
make install                  # both distributions, editable
make demo                     # extract one invoice and print the report
invoice-extractor inspect <pdf>   # what the engine SEES: every line, its zone, its box
```

`inspect` is the one to reach for when a document is not read correctly. It prints the
page as the engine reads it and how each known vendor scored against it, so you can see
whether the problem is the profile's labels, its zones, or that no vendor matched at all.

## Adding a vendor

A vendor is a JSON file, not code. `docs/PROFILE_FORMAT.md` is the format and
`src/invoice_extractor/data/profiles/de-DE.json` is a short worked example — most of a
profile is inherited from `_defaults.json`, so a new one declares only what this vendor
does differently.

```bash
invoice-extractor inspect invoice.pdf              # read the labels off the page
invoice-extractor profile lint <id>                # is it as complete as its peers?
invoice-extractor extract invoice.pdf --report     # what does it read now?
```

A profile is ready at tier **T2**. A deployment keeping its own vendors elsewhere passes
`--profiles <dir>`; the lexicons are expected in a `lexicon/` beside it.

## The rules that will reject your change

`make check` is the gate, and it is the same one CI runs. It is lint, `mypy --strict` and
the tests, and the tests include the repository's own hygiene rules:

- a module is at most 250 counted lines, a function at most 40;
- money is `Decimal`, never `float`; records are frozen dataclasses;
- a document that disagrees with itself produces a `Finding`, never an exception
  (ADR-0005);
- every published value carries the box it was read from (ADR-0002);
- the unit vocabulary is closed in both directions — a registered unit no spec names is
  as much an error as a spec naming a unit that does not exist;
- every profile key has a reader, and every module has an importer;
- no `TODO` markers, no unjustified suppressions, no `print`.

Coverage is configured to fail under 90 % and the repository sits at 100 %. A change that
drops it is a change with untested lines in it.

`make bench` is the second gate, and it needs the corpus: `make corpus` first, which
takes a few minutes and is not in git (`corpus/plan.json` is — the corpus is regenerated
from it, byte for byte). No field may score lower than it did before your change.

## Where the time goes

`make check` is about four minutes and `make bench` about four more, so run them once you
believe you are done rather than after each edit. A single test is
`pytest tests/unit/test_engine.py -k label --no-cov` — the `--no-cov` matters, because the
coverage floor is measured over the whole suite and one file cannot meet it.
