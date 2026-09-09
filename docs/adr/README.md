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

Read in this order for the fastest route through how the pipeline reasons: 0004 (what
varies between invoices) → 0001 (how a field is defined against that variation) → 0002
(what running a field spec produces) → 0003 (how the money in that output is typed) →
0005 (how the pipeline reports when a value doesn't add up).

## When to write one

Write an ADR when a reviewer could reasonably ask "why not just—" and the answer isn't
in the code. Don't write one to restate a choice the code already makes obvious (e.g.
"this project uses pytest").
