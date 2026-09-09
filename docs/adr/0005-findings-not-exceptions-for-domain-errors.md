# ADR-0005: Findings, not exceptions, for domain errors

Status: Accepted

## Context

`validation/invariants.py` can discover that a real, successfully-read invoice
disagrees with itself — a supplier's own rounding mistake, a typo'd printed total. That
is information *about the document*, not a defect in this program. Raising on it would
abort processing an otherwise-fine invoice over one bad number, and would conflate "this
PDF's own numbers don't add up" with "this program crashed."

## Decision

Domain disagreements are data, not control flow. `domain/findings.py` defines `Finding`
with severity `INFO | WARNING | ERROR`. The three invariants in `validation/invariants.py`
— `totals_reconcile`, `line_items_sum`, `vat_rate_consistent` (ADR-0003's 0.01 tolerance)
— each *emit* a `Finding` on disagreement and never raise; the invoice still extracts,
and `InvoiceResult.findings` (`domain/models.py`) just grows by one entry. A value that
fails an `extraction/validators.py` check, or a field whose candidates are all invalid
and falls back to `OnAllInvalid.NOT_FOUND` (ADR-0001), is the per-field form of the same
rule: it describes the document, so it surfaces as `FieldResult.valid=False` on the
result — never as an exception, and not as a `Finding` either, which is reserved for
cross-field disagreement.

Exceptions are kept for what they're actually good at: input this pipeline cannot
proceed past at all. A malformed `layouts/*.json` raises `LayoutError` (ADR-0004); a
missing or unreadable PDF path raises too. `pipeline.py`'s `extract(pdf_path, layout) ->
InvoiceResult` has exactly two outcomes — a complete `InvoiceResult` (however many
ERROR-severity findings it carries), or a raised exception for input the pipeline never
even started on. There is no third, partially-failed return shape.

## Consequences

Extraction is total over any structurally readable PDF: one bad total never hides the
other nine fields. Findings compose — a caller can log ERROR, keep WARNING, drop INFO —
instead of wrapping every invariant in its own `try/except`. The CLI's exit code stays a
one-line rule (`cli.py`): exit 0 whenever `extract()` ran, however many findings it
returned; non-zero only when `pipeline.py` itself raised, i.e. genuinely invalid input.

The tradeoff: a caller must actually *read* `InvoiceResult.findings` — an ERROR finding
stops nothing by itself, so code that ignores the list can ship a reconciliation failure
downstream unnoticed. That is the deliberate half of the tradeoff, not an oversight: the
alternative — raising — fails an entire batch on the first invoice with a rounding typo.
Each `Finding` stays legible against the field it concerns because that field still
carries its own `Evidence` (ADR-0002); the two were never designed to need a shared key.
