# ADR-0007: One engine, six spec kinds

Status: Accepted

## Context
Label-anchored fields, expected-value fields, address sections, tables and the totals
block are different collection problems, and a codebase that grows organically ends up
with one engine per problem plus hand-written classes for what no engine expresses.
Three engines share little, drift apart, and hide behaviour in class hierarchies.

## Decision
One engine runs every field through the same internal pipeline (guard, collect, filter,
normalize, validate, rank, on-failure policy, publish with evidence). What differs is the
**spec kind**: `LabelSpec`, `AnchorSpec`, `SectionSpec`, `TableSpec`, `BlockSpec`,
`DerivedSpec`. A spec is a frozen declaration naming registered units and profile paths;
it never holds values. Units form a closed vocabulary; a test asserts every registered
unit is used and every spec uses only registered units.

## Consequences
Adding a field is adding a declaration and its tests. Tables and the totals block become
data-driven like scalars. Spec docstrings are capped at ten lines; rationale lives in
ADRs and the benchmark README, so the engine stays the size of its behaviour.
