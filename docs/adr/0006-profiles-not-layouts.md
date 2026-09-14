# ADR-0006: Profiles, not layouts (and not countries)

Status: Accepted

## Context
v0.1 configured extraction per *layout*, a name that suggests page geometry only. Real
configuration also carries language, locale, currencies, VAT rules and a vendor's own
vocabulary — and it is naturally keyed by *vendor*, not by country: two vendors in one
country print different invoices, and one vendor prints the same invoice in several.

## Decision
The unit of configuration is a **profile** (`profiles/<id>.json`): one vendor, with
language, country, number format, currencies, VAT rules, expected supplier values, field
vocabulary, parties, tables, totals block, custom fields and variants. The id is the
profile's own name. The generator and the extractor share the same profile files.

## Consequences
Configuration names say what they are; a profile can be rendered by the generator and
read back by the extractor, which makes every profile testable end to end. There is no
country-level fallback and no country-level default anywhere in code.
