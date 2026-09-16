"""The fitted files: what they say, what an absent one means, and that a fit repeats."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from invoice_extractor.scoring.calibrate import calibrate, fitted
from invoice_extractor.scoring.fit import Sample
from invoice_extractor.scoring.weights import (
    CALIBRATION_ROOT,
    MAPS_FILE,
    REPORT_FILE,
    WEIGHTS_FILE,
    Calibration,
    load,
    write,
)

FIXTURES = Path("tests/forge/fixtures/corpus")


def test_a_run_with_no_fitted_files_scores_with_the_uniform_mean(tmp_path: Path) -> None:
    """An uncalibrated run is a run, not an error: there is no half-fitted state."""
    load.cache_clear()
    calibration = load(tmp_path)
    assert calibration.weights_for("invoice_number") is None
    assert calibration.curve_for("invoice_number") is None


def test_what_was_written_is_what_is_read_back(tmp_path: Path) -> None:
    load.cache_clear()
    fitted = Calibration(
        weights={"invoice_number": {"label_found": 0.5}},
        curves={"invoice_number": ((0.2, 0.3), (0.9, 1.0))},
    )
    write(fitted, tmp_path)
    read = load(tmp_path)
    assert read.weights_for("invoice_number") == {"label_found": 0.5}
    assert read.curve_for("invoice_number") == ((0.2, 0.3), (0.9, 1.0))


def test_a_file_that_says_nothing_this_package_reads_is_read_as_nothing(tmp_path: Path) -> None:
    load.cache_clear()
    (tmp_path / WEIGHTS_FILE).write_text('{"schema": "x"}', encoding="utf-8")
    curves = '{"fields": {"a": [[0.1], "x", [0.2, 0.4]]}}'
    (tmp_path / MAPS_FILE).write_text(curves, encoding="utf-8")
    read = load(tmp_path)
    assert read.weights == {}
    assert read.curve_for("a") == ((0.2, 0.4),)


def test_the_committed_fit_is_the_one_this_package_ships() -> None:
    load.cache_clear()
    committed = load(CALIBRATION_ROOT)
    assert committed.curves, "calibration/ is committed and read at run time"
    assert all(_rises(curve) for curve in committed.curves.values())


def test_a_fit_on_one_corpus_twice_is_the_same_fit_byte_for_byte(tmp_path: Path) -> None:
    """The one promise a committed fit rests on (ENGINE_SPEC §9)."""
    first, second = tmp_path / "first", tmp_path / "second"
    calibrate(FIXTURES, first)
    calibrate(FIXTURES, second)
    for name in (WEIGHTS_FILE, MAPS_FILE, REPORT_FILE):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_a_fit_reports_what_it_saw_and_how_far_off_it_was(tmp_path: Path) -> None:
    report = calibrate(FIXTURES, tmp_path)
    assert report.documents == len(list(FIXTURES.glob("*.pdf")))
    assert 0.0 <= report.expected_calibration_error <= 1.0
    entry = next(entry for entry in report.fields if entry.name == "invoice_number")
    assert entry.count == report.documents
    assert entry.hit_rate == 1.0
    assert sum(band.count for band in entry.bands) == entry.count


def test_the_report_is_written_where_a_reader_can_read_it(tmp_path: Path) -> None:
    report = calibrate(FIXTURES, tmp_path)
    written = json.loads((tmp_path / REPORT_FILE).read_text(encoding="utf-8"))
    assert written["corpus"]["documents"] == report.documents
    assert written["expected_calibration_error"] == report.expected_calibration_error
    assert set(written["fields"]) == {entry.name for entry in report.fields}


def test_too_few_documents_to_fit_a_curve_to_leave_the_scores_as_they_are(
    tmp_path: Path,
) -> None:
    report = calibrate(FIXTURES, tmp_path)
    assert report.calibration.curves == {}, "six documents are not a corpus to fit on"


def _rises(curve: tuple[tuple[float, float], ...]) -> bool:
    values = [value for _, value in curve]
    return values == sorted(values)


def test_what_a_set_of_samples_fits_to(tmp_path: Path) -> None:
    """The fit itself, without a corpus: weights where there were negatives, a curve per field."""
    right = [Sample({"label_found": 1.0, "zone_match": 1.0}, True)] * 30
    wrong = [Sample({"label_found": 0.0, "zone_match": 1.0}, False)] * 10
    calibration = fitted({"invoice_number": [*right, *wrong]})
    assert calibration.weights_for("invoice_number") == {"label_found": 1.0}
    curve = calibration.curve_for("invoice_number")
    assert curve is not None
    assert [value for _, value in curve] == sorted(value for _, value in curve)


def test_a_field_with_too_few_samples_to_fit_gets_neither_weights_nor_a_curve() -> None:
    calibration = fitted({"invoice_number": [Sample({"label_found": 1.0}, True)]})
    assert calibration.weights == {}
    assert calibration.curves == {}


def test_a_truth_file_that_says_something_odd_is_read_as_saying_nothing(tmp_path: Path) -> None:
    """A field with no entry, and a number that is not one: neither is a right answer."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for pdf in sorted(FIXTURES.glob("*.pdf"))[:2]:
        truth_path = pdf.with_name(pdf.name.removesuffix(".pdf") + ".truth.json")
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        truth["fields"]["invoice_number"] = "not an object"
        truth["fields"]["subtotal"] = {"value": "not a number"}
        shutil.copy(pdf, corpus / pdf.name)
        (corpus / truth_path.name).write_text(json.dumps(truth), encoding="utf-8")
    report = calibrate(corpus, tmp_path / "out")
    scored = {entry.name: entry.hit_rate for entry in report.fields}
    assert scored["invoice_number"] == 0.0, "a truth entry that is not an entry answers nothing"
    assert scored["subtotal"] == 0.0, "a number that will not parse is not the number read"
