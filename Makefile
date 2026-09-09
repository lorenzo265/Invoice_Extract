.PHONY: install samples demo lint typecheck test check

install:
	pip install -e ".[dev]" && pre-commit install

samples:
	python scripts/make_samples.py

demo:
	python -m invoice_extractor samples/acme_invoice.pdf --layout acme --report

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy

test:
	pytest

check: lint typecheck test
