# invoice-forge

The proving ground for [`invoice-extractor`](https://github.com/lorenzo265/Invoice_Extract):
a generator of synthetic PDF invoices with exact ground truth, in sixteen languages,
five template families and thirty-one difficulty knobs.

It is a development tool, distributed apart from the engine because nobody extracting an
invoice needs it — and because its embedded fonts are most of its weight. It depends on
the engine for one thing: the vendor profiles and language lexicons the two share
(ADR-0006), which ship inside `invoice_extractor`.

```
pip install invoice-forge
forge generate --plan corpus/plan.json --out corpus/
forge verify corpus/
```

See `docs/FORGE_SPEC.md` and `docs/GROUND_TRUTH_SCHEMA.md` in the repository.
