# Layout format

A layout is the only thing that changes between vendors (ADR-0004): label text, expected
zones, number formatting, date formatting, and the line-item table's column headers. It
is plain JSON — `layout/loader.py` is the one module that reads this shape and turns it
into a typed `Layout`; nothing else in the codebase parses a layout file, and nothing
else needs to know this document exists.

This file is the contract for that JSON: every key, its type, whether it is required,
what it means, and the exact message `layout/loader.py` raises when a file breaks the
contract. `layouts/acme.json` and `layouts/nordic.json` are two worked instances of it;
read this file first if the JSON alone leaves a question open.

## Loading a layout

The public API is `load_layout(id_or_path: str) -> Layout`. The argument is resolved
before it is read:

| Form of `id_or_path` | Resolution |
|---|---|
| Contains `/` or `\`, or ends in `.json` | Used directly as a file path (relative paths resolve against the current working directory). |
| Anything else | Treated as a built-in id and resolved to `layouts/<id_or_path>.json`, relative to the current working directory. |

This is why every command in this project's README and `Makefile` runs from the
repository root — `--layout acme` only finds `layouts/acme.json` when the process's
working directory *is* the root that directory hangs off. There is no package-data
lookup and no environment variable: one rule, always relative to where you ran the
command.

Two failures short-circuit before schema validation even starts:

- The resolved path does not exist: `"layout file not found: <resolved_path>"`.
- The file exists but is not valid JSON: `"invalid JSON in <resolved_path>: <underlying json.JSONDecodeError message>"`.
- The file parses but its top level isn't a JSON object: `"layout must be a JSON object"`.

## Message convention

Every other `LayoutError` message starts with the dotted path of the offending key —
list indices as `[i]` — followed by a plain-English statement of what's wrong, e.g.
`"fields.invoice_date.labels must be a non-empty list of strings"`. No message contains
the word "Error" or a leading label; the exception type already carries that. This
convention is what ADR-0004 means by "written for someone editing JSON, not for a
Python traceback reader" — every message below follows it, and any check
`layout/loader.py` adds later should too.

## Top-level keys

| Key | Type | Required | Meaning |
|---|---|---|---|
| `id` | `str`, non-empty | Yes | The layout's own name (`"acme"`, `"nordic"`). Matches the filename stem by convention, but the loader does not enforce that — `InvoiceResult.layout_id` is always this value, never the filename. |
| `language` | `str`, non-empty | Yes | An ISO 639-1 code (`"en"`, `"sv"`) — documentation only; nothing in `extraction/` branches on it. |
| `decimal_separator` | `str`, exactly 1 character | Yes | The character that separates whole units from fractional units in this vendor's numbers, e.g. `"."` or `","`. Must differ from `thousands_separator`. |
| `thousands_separator` | `str`, 0 or 1 characters | Yes | The character that groups digits in large numbers, e.g. `","`, `" "`, or `""` if this vendor never groups digits. |
| `date_formats` | `list[str]`, non-empty | Yes | `datetime.strptime` patterns, tried in the order given — see below. |
| `currency_symbols` | `dict[str, str]` | Yes (may be `{}`) | Maps an ISO 4217 currency code to the symbol used when rendering money in the text report — see below. |
| `fields` | `dict[str, FieldLayout]` | Yes | Exactly the ten scalar field names in the table below — no more, no fewer. |
| `line_items` | `dict` with `header_labels` and `stop_labels` | Yes | Drives the line-item table extractor — see below. |

An unrecognized top-level key is rejected, not ignored: `"<key> is not a recognized
top-level key"`. Silently ignoring a typo'd key (`"decimal_seperator"`) would leave the
real key unset with no signal beyond a confusing downstream extraction failure; failing
at load time, on the exact key, is the whole point of ADR-0004.

Missing a required key: `"<key> is required"`. Wrong type: `"<key> must be a
<expected type description>"` (the description in the table above — the eight in full:
`"id must be a non-empty string"`, `"language must be a non-empty string"`,
`"decimal_separator must be a single character"`,
`"thousands_separator must be a single character or empty"`,
`"date_formats must be a non-empty list of strings"`,
`"currency_symbols must be an object mapping currency codes to symbols"`,
`"fields must be an object mapping field names to field layouts"`,
`"line_items must be an object with header_labels and stop_labels"`). Separator
collision: `"decimal_separator and thousands_separator must be different"`.

Keys are validated in the order the table lists them, so the first error a reader meets
is the first key that is wrong, not whichever check happened to run first.

The keys of `currency_symbols` are validated as currency-code-shaped (`^[A-Z]{3}$`),
not against a master ISO 4217 list — that list is a data dependency this project
doesn't need: `"currency_symbols has a key that is not a 3-letter uppercase currency
code: <key>"`.

## `fields`: the ten scalar fields

`fields` has exactly these keys — this is the closed vocabulary `extraction/specs.py`
declares one `FieldSpec` per name for, in this order:

`invoice_number`, `invoice_date`, `due_date`, `supplier_vat_id`, `customer_vat_id`,
`currency`, `vat_rate`, `subtotal`, `vat_amount`, `total_amount`.

A missing one: `"fields.<name> is required"`. An extra key that isn't one of the ten:
`"fields.<name> is not a recognized field"` — a typo'd field name (`"vatrate"`) is a
load-time error here, never a silently-unextractable field discovered three modules
downstream.

Each value is a `FieldLayout`:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `labels` | `list[str]`, non-empty | Yes | Candidate label text this field's strategy searches for, exactly as printed — no trailing colon (see below), no regex. |
| `zones` | `list[Zone name]`, non-empty | Yes | Where this field is expected to appear. Ranking prefers a candidate found in one of these zones (`extraction/rankers.py`'s `zone_priority`) and `validation/confidence.py`'s `in_expected_zone` signal reads it — it does not forbid a match elsewhere. |
| `regex` | `str` | No | A field-specific pattern, only needed by a field whose `FieldSpec.strategies` name `REGEX_ANCHOR`, or one whose validator wants a shape check `matches_pattern` can't infer from labels alone. Neither seed layout uses it — `labels` and `zones` are enough for both `acme` and `nordic`. Compiled with `re.compile` at load time so a broken pattern fails immediately: `"fields.<name>.regex is not a valid regular expression: <re.error message>"`. |

Validation messages: `"fields.<name> must be an object"` when the value under a field
name is not one, `"fields.<name>.labels must be a non-empty list of strings"` (the
literal example ADR-0004 cites), `"fields.<name>.zones must be a non-empty list of
strings"`, `"fields.<name>.regex must be a string"`, and for an unrecognized key inside
one field object, `"fields.<name>.<subkey> is not a recognized key"`.

### Zone names

Nine values, a 3x3 grid over the page (`document/zones.py` classifies a `TextLine` by
its `BBox` centre, normalised against the page's own width and height — this file only
lists the names a layout is allowed to reference):

```
TOP_LEFT      TOP_CENTER      TOP_RIGHT
MIDDLE_LEFT   MIDDLE_CENTER   MIDDLE_RIGHT
BOTTOM_LEFT   BOTTOM_CENTER   BOTTOM_RIGHT
```

An entry in `zones` that isn't one of these nine, spelled exactly this way:
`"fields.<name>.zones[<i>] is not a recognized zone name: <value>"`.

### The label-colon convention

Every field's value is printed on the same source line as its label, separated by a
colon and one space — `"Invoice Number: INV-2024-0042"`, `"Momsreg.nr:
SE556123456701"`. A `labels` entry is the label alone, without the colon
(`"Invoice Number"`, `"Momsreg.nr"`) — the colon and the whitespace around it are
punctuation the strategy and the normalizer both know to skip past, not part of the
label text itself. This is the convention both `layouts/acme.json` and
`layouts/nordic.json` follow for every one of the ten fields; see
`docs/SAMPLES_SPEC.md` for the exact line each field is drawn on.

### `date_formats`: tried in order

`date_formats` is an ordered list of `datetime.strptime` patterns. Given a field's raw
text (with its label stripped), the date normalizer tries each pattern in the list, in
order, and returns the first one that parses successfully. A field with no format in
its layout's `date_formats` that matches its printed text fails `validators.is_date` —
that is a wrong or missing layout entry, not a reason to add a fallback format; a date
that can be read three different ways is a data-quality problem the `Finding` on that
field should surface, not paper over.

### Separators drive every locale-formatted number — not just money

`decimal_separator` and `thousands_separator` govern **every** number on the document
printed in this vendor's locale — money and percentages alike, since both are printed
with the same two punctuation marks. Given decimal separator `D` and thousands
separator `T` (which may be `""`):

1. Remove every occurrence of `T` (skip this step if `T` is empty).
2. Replace the single remaining `D` with `.`.
3. Strip anything that isn't a digit, `.`, or a leading `-`.
4. Feed the result to `decimal.Decimal(...)`.

`parse_money(separators)` is exactly this. `parse_percent` runs the identical four
steps after first stripping a trailing `%` and surrounding whitespace — this is why
`nordic`'s `"Moms: 25,00%"` (comma decimal) and `acme`'s `"VAT Rate: 20.00%"` (period
decimal) both normalize to a `Decimal` with two fractional digits: the layout's
separators are the single source of truth for how a number reads, and a field being a
percentage doesn't exempt it from that rule.

Worked example (`nordic`, `D=","`, `T=" "`): `"3 216,00"` → remove spaces →
`"3216,00"` → replace `,` with `.` → `"3216.00"` → `Decimal("3216.00")`.

### `currency_symbols`

Maps an ISO 4217 code to the symbol shown when `output/text_report.py` renders a money
value in the human-readable report — `{"GBP": "£"}`, `{"SEK": "kr"}`. It has **no**
effect on extraction: the `currency` field's own value is read from the document as
printed (`"Currency: GBP"` normalizes via `upper_alnum`, not a symbol lookup), and
`parse_money` never consults this map. A layout only needs an entry for a currency its
own invoices actually use — `acme.json` maps only `GBP`, `nordic.json` only `SEK`.

## `line_items`

| Key | Type | Required | Meaning |
|---|---|---|---|
| `header_labels` | `dict[str, list[str]]` | Yes | Exactly five keys — `sku`, `description`, `quantity`, `unit_price`, `net_amount` — each a non-empty list of acceptable header words for that column. |
| `stop_labels` | `list[str]` | Yes (may be `[]`) | Words that mark the end of the table. |

A missing column: `"line_items.header_labels.<column> is required"`. An extra column
key: `"line_items.header_labels.<column> is not a recognized column"`. Wrong shape:
`"line_items.header_labels.<column> must be a non-empty list of strings"`, and for the
map itself, `"line_items.header_labels must be an object mapping columns to header
words"`. Wrong shape for the sibling key:
`"line_items.stop_labels must be a list of strings"` — empty is allowed here (a table
with nothing printed after it still has an end: the page). An unrecognized key beside
those two: `"line_items.<key> is not a recognized key"`.

### How `header_labels` and `stop_labels` drive the table extractor

`extraction/line_items.py` locates the header row by finding, among the text on the
page, one line for each of the five columns whose text is a member of that column's
`header_labels` list — that line's position fixes the column's location. Every line
after the header is read as one row, until a line matches one of `stop_labels`, which
ends the table (that line itself is never read as a row). `header_labels` may list more
synonyms than either sample actually prints — `acme.json` accepts `"Item"` for the SKU
column even though `samples/acme_invoice.pdf` only ever prints `"SKU"` — because a
layout describes a vendor's *format*, not one specific invoice.

Two design points this implies, worth stating even though neither sample exercises
them: a `header_labels` word that's never printed on a real invoice for that vendor is
harmless (it just never matches); a `stop_labels` word that also happens to be a
column's own header word would end the table immediately, so pick stop words from the
vendor's totals block, never from the table's own vocabulary. Both seed layouts use the
subtotal field's own label as the stop word — `"Subtotal"` (`acme`), `"Netto"`
(`nordic`) — since that is the first line printed after the last row on every real
invoice this layout describes.

## Worked field: `supplier_vat_id` in `layouts/acme.json`

```json
"supplier_vat_id": {
  "labels": ["VAT Number"],
  "zones": ["TOP_LEFT"]
}
```

On `samples/acme_invoice.pdf`, the line `"VAT Number: GB123456789"` sits in the
supplier's letterhead block, top-left of the page. `labels` names the text that starts
that line; `zones` names where a match there is expected, feeding
`validation/confidence.py`'s `in_expected_zone` signal. No `regex` — a label match,
scoped by zone, is enough, the same reasoning `docs/ARCHITECTURE.md` §5 gives for
`invoice_number`. `docs/SAMPLES_SPEC.md` has the equivalent detail for all ten fields,
both layouts.
