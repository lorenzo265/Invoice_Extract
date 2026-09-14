# ADR-0001: Field specs are declared, not subclassed

Status: Accepted

## Context

An invoice has ten scalar fields (`invoice_number`, `invoice_date`, `due_date`,
`supplier_vat_id`, `customer_vat_id`, `currency`, `vat_rate`, `subtotal`, `vat_amount`,
`total_amount`) plus a line-item table. The obvious object-oriented shape — one class
per field, each overriding an `extract()`/`validate()` method — turns "add a field"
into "write and wire a class," and it silently welds *how to find text* to *how to
interpret it* inside each subclass. A change to ranking logic then means editing every
subclass instead of one function.

## Decision

A field is a value, not a type. `FieldSpec(name, strategies, normalizer, validator,
rankers, on_all_invalid)` (`extraction/spec.py`) names five behaviours instead of
implementing them inline:

| Slot | Closed vocabulary / source |
|---|---|
| `strategies` | `Strategy = LABEL_RIGHT \| LABEL_BESIDE \| LABEL_BELOW \| REGEX_ANCHOR` |
| `normalizer` | `extraction/normalizers.py` — `strip_label`, `parse_date`, `parse_money`, `upper_alnum`, `parse_percent` |
| `validator` | `extraction/validators.py` — `matches_pattern`, `is_date`, `is_positive_money`, `is_currency_code`, `is_percent` |
| `rankers` | `extraction/rankers.py` — `valid_first`, `zone_priority`, `closest_to_label`, `top_most` |
| `on_all_invalid` | `OnAllInvalid = BEST \| NOT_FOUND` |

The ten fields are declared as a flat list of `FieldSpec` values in `extraction/specs.py`.
One generic `extraction/engine.py` runs every spec the same way. The *data* a strategy
needs — which labels, which zones, which regex — lives in the layout (ADR-0004), never
in the spec; the spec only names which behaviours apply.

## Consequences

Adding an eleventh field is one `FieldSpec(...)` entry in `extraction/specs.py` plus a
test — never a new class, never a change to `extraction/engine.py`. Behaviour is shared
by construction: `label_right` is one function used by every field that needs it, not
copy-pasted across subclasses. The full field list is auditable in one file at a glance.

The cost sits at the boundary: a genuinely new *behaviour* — a strategy, normalizer,
validator, or ranker that doesn't exist yet — still requires touching the shared
vocabulary modules, so a small amount of extension work always lives outside
`specs.py`.

## Amendment: `strategy` became `strategies`

The slot was one strategy per field until v0.2.0, when the benchmark over the generated
corpus showed the cost of that: a vendor that sets a label at one tab stop and its value
flush right at another prints no text between the two, so `<label>: <value>` never
appears on the page and `LABEL_RIGHT` — the only strategy any field named — found no
candidate at all for eight of the ten fields. The fix is `LABEL_BESIDE` in the same
vocabulary; what made it a change to the *slot* is that both readings are ordinary, often
in one corpus, and a field cannot be asked to pick one in advance.

So a spec names a tuple, every strategy in it contributes its candidates, and the rankers
choose between them — which is what the rankers were already for. The decision above is
unchanged: a field is still a value naming behaviours, still adds no class, and still
leaves the data those behaviours need in the layout. `FieldSpec` values must stay pure compositions of function references, with
no captured state, or "reading `specs.py` tells you everything" stops being true.
Strategies must return evidence-carrying candidates for the engine to rank (ADR-0002);
the layout half of this split is ADR-0004.
