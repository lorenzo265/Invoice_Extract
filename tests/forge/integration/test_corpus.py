"""Generating a corpus from a plan, and reporting what it covers.

A corpus is its plan: these tests run one, verify what came out, and check that the
catalog reports the gaps a small corpus obviously has rather than quietly passing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from make_forge_goldens import FIXTURES, fixture_pdf

from invoice_forge.commands import generate_corpus, report_catalog, verify
from invoice_forge.corpus.catalog import catalog, met_all, render_table
from invoice_forge.corpus.generate import PLAN_NAME, generate, write_plan
from invoice_forge.corpus.plan import PLAN_SCHEMA, cell_name, load_plan, plan_from_arguments
from invoice_forge.corpus.survey import survey_corpus
from invoice_forge.families import Family
from invoice_forge.knobs import KNOB_NAMES
from invoice_forge.truth.verify import verify_corpus

PROFILES = ("de-DE", "en-GB")
SEED = 42


def small_plan(count: int = 2) -> object:
    return plan_from_arguments(PROFILES, [Family.CLASSIC], count=count, seed=SEED)


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A four-document corpus, generated once for the tests that read it."""
    directory = tmp_path_factory.mktemp("generated")
    generate(small_plan(), directory)
    return directory


def test_a_plan_produces_one_pdf_and_one_truth_per_cell(corpus: Path) -> None:
    assert len(sorted(corpus.glob("*.pdf"))) == 4
    assert len(sorted(corpus.glob("*.truth.json"))) == 4


def test_the_documents_are_named_in_plan_order(corpus: Path) -> None:
    plan = small_plan()
    expected = [f"{cell_name(index, cell)}.pdf" for index, cell in enumerate(plan.cells)]
    assert [path.name for path in sorted(corpus.glob("*.pdf"))] == expected


def test_the_plan_is_left_beside_the_documents(corpus: Path) -> None:
    written = load_plan(corpus / PLAN_NAME)
    assert written == small_plan()
    assert json.loads((corpus / PLAN_NAME).read_text(encoding="utf-8"))["schema"] == PLAN_SCHEMA


def test_a_generated_corpus_verifies(corpus: Path) -> None:
    report = verify_corpus(corpus)
    assert report.ok, [str(failure) for failure in report.failures]
    assert len(report.documents) == 4


def test_running_the_plan_again_writes_the_same_bytes(corpus: Path, tmp_path: Path) -> None:
    again = tmp_path / "again"
    generate(small_plan(), again)
    for original in sorted(corpus.glob("*.pdf")):
        assert (again / original.name).read_bytes() == original.read_bytes(), original.name


def test_a_corpus_generated_from_a_written_plan_matches_the_arguments(tmp_path: Path) -> None:
    """The two routes into `generate` are one route: a plan file, or the cross product."""
    plan_path = tmp_path / "plan.json"
    write_plan(small_plan(), plan_path)
    from_file = tmp_path / "from_file"
    from_arguments = tmp_path / "from_arguments"
    generate(load_plan(plan_path), from_file)
    generate(small_plan(), from_arguments)
    for original in sorted(from_arguments.glob("*.pdf")):
        assert (from_file / original.name).read_bytes() == original.read_bytes()


def test_the_survey_counts_what_the_corpus_holds(corpus: Path) -> None:
    survey = survey_corpus(corpus)
    assert survey.documents == 4
    assert survey.pairs["de-DE", "classic"] == 2
    assert survey.pairs["en-GB", "classic"] == 2
    assert survey.pairs["fr-FR", "classic"] == 0
    assert len(survey.item_counts) == 4
    assert survey.credit_notes == 0


def test_the_catalog_reports_every_knob_the_variation_catalog_names(corpus: Path) -> None:
    rows = catalog(corpus)
    knobs = {row.axis for row in rows if row.section == "Knobs"}
    assert knobs == set(KNOB_NAMES)


def test_the_catalog_reports_a_pair_no_document_covers_as_unmet(corpus: Path) -> None:
    unmet = {row.axis for row in catalog(corpus) if not row.met}
    assert "fr-FR x classic" in unmet
    assert "de-DE x classic" not in unmet


def test_a_small_corpus_does_not_meet_a_two_hundred_and_fifty_document_contract(
    corpus: Path,
) -> None:
    assert not met_all(catalog(corpus))


def test_the_table_names_every_row_and_says_how_many_are_unmet(corpus: Path) -> None:
    rows = catalog(corpus)
    printed = render_table(rows, 4)
    assert "4 documents" in printed
    assert "Profile x family" in printed
    assert "Coverage targets" in printed
    for row in rows:
        assert row.axis in printed
    assert f"of {len(rows)} rows not met" in printed


def test_the_committed_fixture_corpus_verifies() -> None:
    """The plan's own gate: `forge verify tests/forge/fixtures/` exits 0."""
    assert verify(str(FIXTURES)) == 0
    assert fixture_pdf().is_file()


def test_the_command_line_generates_verifies_and_catalogues(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = str(tmp_path / "corpus")
    assert generate_corpus(None, "de-DE", "classic", 2, SEED, out) == 0
    assert "2 documents" in capsys.readouterr().out
    assert verify(out) == 0
    assert "verified" in capsys.readouterr().out
    assert report_catalog(out) == 1
    assert "rows not met" in capsys.readouterr().out


def test_generating_into_a_directory_that_exists_is_fine(tmp_path: Path) -> None:
    out = tmp_path / "corpus"
    out.mkdir()
    (out / "a-note.txt").write_text("left behind", encoding="utf-8")
    written = generate(small_plan(count=1), out)
    assert len(written.documents) == 2
    assert written.pages >= 2
