# Field catalog

The canonical names shared by the extractor (`InvoiceResult.fields`), the generator's
ground truth (`forge-truth/1`) and the benchmark. A name appears here once; code,
truth files and reports use it verbatim. Changing a name is a schema change with an ADR.

## Scalar fields (spec kind in parentheses)

| Name | Type | Normalisation | Spec kind |
|---|---|---|---|
| `invoice_number` | str | upper-case alphanumerics with `-` `/` | Label |
| `order_number` | str | idem | Label |
| `customer_number` | str | idem | Label |
| `invoice_date` | date | ISO-8601 | Label |
| `supply_date` | date | ISO-8601 | Label |
| `due_date` | date | ISO-8601 | Label |
| `supplier_vat_id` | str | country prefix + alphanumerics, upper-case | Anchor |
| `customer_vat_id` | str | idem | Label |
| `currency` | str | ISO 4217 code | Derived (vote over printed codes/symbols) |
| `secondary_currency` | str | ISO 4217 code | Derived |
| `exchange_rate` | Decimal | plain decimal | Label, else Derived (inferred from totals) |
| `iban` | str | spaces removed, upper-case, mod-97 valid | Label (pattern) |
| `customer_country` | str | ISO 3166-1 alpha-2 | Derived (VAT prefix > bill_to > ship_to > postal pattern) |
| `document_type` | enum | `invoice` \| `credit_note` | stage 3 (`classify_document`) |

## Parties (`SectionSpec`, plus `AnchorSpec` for the supplier)

`supplier`, `bill_to`, `ship_to`, `mail_to`, each with `name`, `lines[]`, `country`,
`vat_id` (may be `null`); `placeholder: true` when the block says "as bill-to".

## Tables (`TableSpec`)

`line_items[]`: `pos`, `part_number`, `description`, `quantity`, `unit`, `unit_price`,
`discount_pct`, `vat_rate`, `vat_code`, `net_amount`, `sub_items[]`, `subscription`
(`id`, `billing_cycle`, `period_start`, `period_end`, `share_pct`, `remaining_term`).
`vat_summary[]`: `rate`, `code`, `base`, `vat`.

## Totals block (`BlockSpec`)

`totals`: `subtotal`, `vat_amount`, `total_amount`, `rounding`, `charges[]`
(`type` ∈ SHIPPING, FREIGHT, ENVIRONMENTAL_FEE, SURCHARGE, CONSOLIDATION_FEE,
RECYCLING_FEE, OTHER; `amount`; `vat_rate`; `declared`).
`secondary_amounts`: the same keys echoed in `secondary_currency`, plus `exchange_rate`.

## Custom fields

Declared per profile as `LabelSpec`s under `custom_fields[]`; they appear in
`InvoiceResult.fields` under their declared name and in the benchmark when the corpus
emits them.

## Findings vocabulary

Codes are `snake_case`, stable, listed in `validation/codes.py`; severity ∈ INFO /
WARNING / ERROR; `fields[]` names the canonical fields a finding touches.
