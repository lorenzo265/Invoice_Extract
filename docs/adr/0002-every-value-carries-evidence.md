# ADR-0002: Every value carries its evidence

Status: Accepted

## Context

A wrong extracted value that looks exactly as confident as a right one is worse than a
missing value — nothing downstream signals it needs a second look. `extraction/engine.py`
also runs a `FieldSpec`'s strategy, gets back several candidates, and lets a ranker
(`extraction/rankers.py`) pick a winner; without a record of *why* one candidate beat
the others, a bad pick is unauditable after the fact, and a bug report reduces to
"re-run and hope it repros."

## Decision

Nothing is extracted without saying where it came from. `Evidence(page, bbox,
matched_label, strategy, raw_text)` (`domain/models.py`) records the page, the exact
`BBox` (`document/reader.py`) the value was read from, which label text matched (if
any), which `Strategy` produced it, and the untouched text before normalization.
`FieldResult(name, value, raw_text, evidence, confidence, confidence_breakdown, valid)`
(`domain/models.py`) carries exactly one `Evidence` — never an optional "trust me" flag,
never an aggregate summary. `extraction/strategies.py` returns `Candidate(raw_text,
evidence)` for every candidate it finds, so a losing candidate's evidence still exists
during ranking even though only the winner's survives onto `FieldResult`.

## Consequences

`InvoiceResult` becomes self-auditing: any value in `result.json` traces back to an
exact rectangle on an exact page without re-running extraction. `validation/confidence.py`
reads evidence directly — signals like `label_exact_match` and `in_expected_zone` are
questions about the `Evidence`, not a second pass over the document. Debugging a wrong
field is "open the PDF at `evidence.page`, look at `evidence.bbox`," not a guessing game.

The cost is size: every field carries four extra data points instead of a bare scalar,
so `result.json` — and `samples/*.expected.json` — is larger than a values-only output
would be. This is deliberate, not incidental: because `scripts/make_samples.py`
generates the sample PDFs with fixed `insert_text` coordinates and fixed metadata
(`docs/SAMPLES_SPEC.md`), and PyMuPDF is pinned to one version, the bbox floats it
reports back are exactly reproducible run to run — so the golden test does not fuzz or
exclude them. `tests/integration/test_pipeline_golden.py` compares evidence exactly, the
same as every other field. The earlier golden gates deliberately narrow the surface
while the engine is still being built — PR5 compares scalar fields only, PR6 adds line
items — so a bbox regression doesn't block unrelated engine work before PR8 makes the
full `expected.json` byte-identical to the CLI's `--json` output.
