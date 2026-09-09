# ADR-0003: Money is Decimal, never float

Status: Accepted

## Context

`validation/invariants.py` checks that an invoice's own numbers agree with each other:
`totals_reconcile` (subtotal + vat_amount == total_amount), `line_items_sum`
(sum(net_amount) == subtotal), `vat_rate_consistent` (subtotal * vat_rate ==
vat_amount), each within a 0.01 currency-unit tolerance. Binary floating point cannot
represent most decimal fractions exactly — `0.1 + 0.2 != 0.3` — so a `float` pipeline
would need every comparison fuzzed, and the 0.01 tolerance would end up hiding
representation error instead of measuring the real-world rounding it's meant for.
Summed across a line-item table, that error compounds silently.

## Decision

Every monetary value is `decimal.Decimal`, end to end, never `float`. Parsing starts it:
`extraction/normalizers.py`'s `parse_money(separators)` converts raw text straight to
`Decimal`. `domain/money.py` owns the arithmetic and rounding helpers so no other module
hand-rolls Decimal math. Every money-typed field on `domain/models.py` — `subtotal`,
`vat_amount`, `total_amount`, `unit_price`, `net_amount` — is typed `Decimal`, and stays
`Decimal` through `to_dict`/`from_dict`. `output/json_writer.py` serialises `Decimal` as
a JSON *string* (`"98.00"`), never a JSON number: most JSON readers round-trip numbers
through IEEE-754, which would reintroduce exactly the error this ADR removes. The same
reasoning applies one type over: dates are `datetime.date`, never a string or a
timestamp float, for the same "don't let a lossy native type back in" rule.

## Consequences

The 0.01 tolerance in `validation/invariants.py` now measures only real-world rounding
(a supplier rounding each line before summing), not floating-point noise. Equality in
tests is exact and reproducible. A `Decimal` round-trips through JSON without drift.

Every call site touching money must construct `Decimal` from strings, never from float
literals — `Decimal("0.01")`, not `Decimal(0.01)` — or the bug this ADR exists to avoid
comes back through the constructor. `domain/money.py` is the one place allowed to be
fluent in this; everywhere else imports it rather than re-deriving rounding rules. A
`Decimal` that fails `extraction/validators.py`'s `is_positive_money` doesn't raise — the
field comes back with `valid=False` (ADR-0005) — and the pre-parse text is never lost either way, because
`Evidence.raw_text` (ADR-0002) keeps the original `"1 234,56"` regardless of what
`parse_money` made of it.
