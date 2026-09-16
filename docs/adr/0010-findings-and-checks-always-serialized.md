# ADR-0010: Findings and checks are always serialized

Status: Accepted

## Context
A validation layer that computes rich results but serializes only a boolean loses the
reasons the moment the process ends. Consumers then see `valid: false` with nothing to
act on, and calibration cannot learn which checks matter.

## Decision
Every stage that judges the document emits `Finding`s (code, severity, message, touched
fields) and `Check` records (code, passed, fields, detail — including checks that
passed). Both are fields of `InvoiceResult`, round-trip through `to_dict`/`from_dict`,
and appear in `result.json`; `findings.json` mirrors them. `valid` is derived from the
findings (no ERROR), never set independently.

## Consequences
`result.json` is self-explaining. The benchmark can score findings against the truth's
`noise` and knob records. Nothing about a document's validation exists only in memory.
