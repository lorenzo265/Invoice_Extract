# ADR-0004: A vendor layout is data

Status: Accepted

## Context

Two vendors format invoices differently — different label text ("Fakturanummer" vs.
"Invoice Number"), different zones a value is expected in, different decimal and
thousands separators, different date formats. This is exactly the variation ADR-0001
already refused to encode as a class per field; encoding it as a class per *vendor*
(`AcmeExtractor`, `NordicExtractor`) would make the same mistake one level up — "add a
vendor" would mean writing and testing Python, and the difference between two vendors
would be a code diff instead of a data diff.

## Decision

A layout is JSON, not Python: `layouts/acme.json`, `layouts/nordic.json`. Shape: `id`,
`language`, `decimal_separator`, `thousands_separator`, `date_formats`,
`currency_symbols`, `fields` (per field: `labels`, `zones`, optional `regex`), and
`line_items` (`header_labels` per column, `stop_labels`). `layout/schema.py` defines
this shape; `layout/loader.py` validates a loaded file against it and raises
`LayoutError` whose message names the exact failing path — e.g.
`"fields.invoice_date.labels must be a non-empty list of strings"` — written for
someone editing JSON, not for a Python traceback reader.

No pydantic: the validated shape is small and fixed, the person changing it is editing
data rather than writing Python, and hand-written checks in `layout/loader.py` keep
every error message under this project's direct control instead of a library's default
phrasing — and keep the runtime dependency list at PyMuPDF alone (`pyproject.toml`).

## Consequences

Adding a vendor means adding `layouts/<id>.json` and samples — never touching `src/`.
"Vendor X reworded their invoice header" is a one-line JSON diff, reviewable by someone
who doesn't read Python. A malformed layout fails loudly, at load time, with a message
that names the JSON path rather than an attribute error three frames into extraction.

The cost is a second source of truth for field names: `layout/schema.py` and
`extraction/spec.py` (ADR-0001) agree only through the string keys under `fields.<name>`,
so a typo'd field name in a layout is a silent data-shape mismatch unless
`layout/loader.py`'s validation (and its tests) catch it. And layouts only configure the
behaviours ADR-0001 already named — a genuinely new extraction *strategy* is still a
code change; no layout file can invent one.
