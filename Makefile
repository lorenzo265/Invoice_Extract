.PHONY: install demo corpus bench lint typecheck test check

install:
	pip install -e ".[dev]" && pre-commit install

corpus:
	forge generate --plan corpus/plan.json --out corpus/

demo:
	python -m invoice_extractor extract tests/forge/fixtures/corpus/0001_fr-FR_classic_s7.pdf --report

bench:
	python -m benchmarks.run

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy

test:
	pytest

check: lint typecheck test
