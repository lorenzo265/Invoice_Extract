.PHONY: install demo corpus bench lint typecheck test check

# Two distributions, one working tree. `invoice-extractor` is the engine a caller
# installs; `invoice-forge` is the generator it is proved against, which a caller has no
# use for. A contributor wants both, editable.
install:
	pip install -e ".[dev]" -e tools/forge && pre-commit install

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
