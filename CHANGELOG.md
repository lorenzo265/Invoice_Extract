# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

### Added

- Packaging, quality gates and repository hygiene checks: `pyproject.toml`,
  `Makefile` (`make check` = lint + typecheck + test + hygiene), the CI workflow,
  pre-commit hooks, and an installable, empty `invoice_extractor` package that
  ships `py.typed`.
