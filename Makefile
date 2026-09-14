.PHONY: install samples demo corpus bench lint typecheck test check

install:
	pip install -e ".[dev]" && pre-commit install

samples:
	python scripts/make_samples.py

demo:
	python -m invoice_extractor samples/acme_invoice.pdf --layout acme --report

corpus:
	forge generate --plan corpus/plan.json --out corpus/

bench:
	@echo "make bench arrives in PR F7 of docs/FORGE_PLAN.md" >&2; exit 1

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy

test:
	pytest

check: lint typecheck test
