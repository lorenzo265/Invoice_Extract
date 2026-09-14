# Architecture Decision Records

An ADR captures one decision that would be expensive to reverse or non-obvious to a
reader coming in cold — not a log of every commit, and not a design doc. If a decision
doesn't meet that bar, it belongs in a docstring or `docs/ARCHITECTURE.md`, not here.

## Format

Every ADR uses the same four sections, in this order, and stays under 60 lines. Copy
this skeleton into `NNNN-kebab-case-slug.md`, where `NNNN` is the next unused
four-digit number:

```markdown
# ADR-NNNN: <decision, stated as a sentence>

Status: Accepted

## Context

The forces that made a decision necessary — the constraint, not the solution. Someone
reading only this paragraph should understand why the question came up at all.

## Decision

What was decided, stated plainly, naming the exact modules and types it lands in.

## Consequences

What this makes easier. What this makes harder. Real tradeoffs, not just upside — an
ADR with no negative consequence usually means the tradeoff wasn't looked for.
```

`Status` is one of `Proposed`, `Accepted`, `Superseded by ADR-NNNN`. A superseded ADR is
never rewritten to look right in hindsight — a new ADR replaces it and both files say
so, in each direction.

## Index

| ADR | Decision | Governs |
|---|---|---|
| [0001](0001-field-specs-declared-not-subclassed.md) | A field is declared as data, not subclassed | `extraction/spec.py`, `extraction/specs.py` |
| [0002](0002-every-value-carries-evidence.md) | Every extracted value carries its evidence | `domain/models.py` (`Evidence`, `FieldResult`) |
| [0003](0003-money-is-decimal-never-float.md) | Money is `Decimal`, never `float` | `domain/money.py` |
| [0004](0004-layouts-are-data.md) | A vendor layout is JSON, not code | `layout/schema.py`, `layout/loader.py`, `layouts/*.json` |
| [0005](0005-findings-not-exceptions-for-domain-errors.md) | Domain disagreements are `Finding`s, not exceptions | `domain/findings.py`, `validation/invariants.py` |
| [0006](0006-profiles-not-layouts.md) | The unit of configuration is a vendor profile | `profile/`, `profiles/*.json` |
| [0007](0007-one-engine-six-spec-kinds.md) | One engine runs six spec kinds | `extraction/engine.py`, `extraction/spec/` |
| [0008](0008-no-default-profile.md) | An undetected profile stops extraction | `profile/detect.py` |
| [0009](0009-calibration-needs-negatives.md) | Confidence is calibrated offline on the synthetic corpus | `scoring/`, `calibration/` |
| [0010](0010-findings-and-checks-always-serialized.md) | Findings and checks are always serialized | `validation/`, `output/json_writer.py` |

Read in this order for the fastest route through how the pipeline reasons: 0006 (what
varies between invoices, and what a profile is) → 0001 and 0007 (how a field is
declared against that variation, and the one engine that runs the declaration) → 0002
(what running a field spec produces) → 0003 (how the money in that output is typed) →
0005 and 0010 (how the pipeline reports when a value doesn't add up, and why every
report is serialized) → 0008 (what happens when no profile matches at all) → 0009 (how
the confidence attached to every value is fitted).

## When to write one

Write an ADR when a reviewer could reasonably ask "why not just—" and the answer isn't
in the code. Don't write one to restate a choice the code already makes obvious (e.g.
"this project uses pytest").
