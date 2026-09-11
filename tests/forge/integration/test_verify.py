"""`forge verify` holds a corpus to what it claims — and says so when it does not.

Every test here corrupts one thing in a truth file that verifies cleanly and asserts the
check that should notice it does. A verifier that cannot fail proves nothing, so the
failures are the point.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from make_forge_goldens import GOLDEN_SEED
from rendering import for_each_profile, rendered

from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.produce import DocumentSpec, produce
from invoice_forge.truth.reading import TruthError
from invoice_forge.truth.verify import CHECKS, Failure, verify_corpus, verify_document

Corrupt = Callable[[dict[str, Any]], None]
PROFILE = "de-DE"


def corrupted(source: Path, tmp_path: Path, mutate: Corrupt) -> Path:
    """A copy of a verified document with one thing changed in its truth."""
    work = tmp_path / "corrupt"
    work.mkdir(parents=True, exist_ok=True)
    pdf = shutil.copy(source, work / source.name)
    truth_name = f"{source.stem}.truth.json"
    truth = json.loads((source.parent / truth_name).read_text(encoding="utf-8"))
    mutate(truth)
    path = Path(pdf).with_name(truth_name)
    path.write_text(json.dumps(truth, ensure_ascii=False), encoding="utf-8")
    return path


def checks_that_fired(failures: tuple[Failure, ...]) -> set[str]:
    return {failure.check for failure in failures}


@for_each_profile
def test_a_document_the_generator_wrote_verifies(profile_id: str) -> None:
    assert verify_document(_truth_of(profile_id)) == ()


def test_a_whole_corpus_verifies(tmp_path: Path) -> None:
    for profile_id in ("de-DE", "en-GB"):
        produce(
            DocumentSpec(profile_id, Family.CLASSIC, GOLDEN_SEED), tmp_path / f"{profile_id}.pdf"
        )
    report = verify_corpus(tmp_path)
    assert report.ok
    assert len(report.documents) == 2


def test_a_corpus_that_is_not_there_says_so(tmp_path: Path) -> None:
    with pytest.raises(TruthError, match="corpus directory not found"):
        verify_corpus(tmp_path / "absent")


def test_an_empty_directory_verifies_nothing_and_passes(tmp_path: Path) -> None:
    report = verify_corpus(tmp_path)
    assert report.ok
    assert report.documents == ()


def test_a_truth_with_no_pdf_beside_it_is_a_failure(tmp_path: Path) -> None:
    orphan = tmp_path / "alone.truth.json"
    orphan.write_text("{}", encoding="utf-8")
    failures = verify_document(orphan)
    assert checks_that_fired(failures) == {"schema"}
    assert "no PDF beside it" in failures[0].detail


def test_a_truth_that_is_not_json_is_a_failure(tmp_path: Path) -> None:
    broken = tmp_path / "broken.truth.json"
    broken.write_text("{ not json", encoding="utf-8")
    assert "invalid JSON" in verify_document(broken)[0].detail


@cache
def _charged(tmp: str) -> Path:
    """A document that carries a declared charge, because the knob for one asks for it."""
    spec = DocumentSpec(PROFILE, Family.CLASSIC, 1, (Knob.DECLARED_CHARGE,))
    produced = produce(spec, Path(tmp) / "charged.pdf")
    truth = json.loads(produced.truth.read_text(encoding="utf-8"))
    assert truth["charges"], "the declared_charge knob puts a charge on the document"
    return produced.pdf


@pytest.mark.parametrize("declared", [True, False], ids=["hidden", "evidence removed"])
def test_a_corrupted_charge_fails_the_evidence_rule(declared: bool, tmp_path: Path) -> None:
    """Either half of the rule broken — a declared charge with no evidence, or the reverse."""

    def mutate(truth: dict[str, Any]) -> None:
        if declared:
            truth["charges"][0]["declared"] = False
        else:
            truth["charges"][0]["evidence"] = []

    charged = _charged(str(tmp_path / "source"))
    failures = verify_document(corrupted(charged, tmp_path, mutate))
    assert checks_that_fired(failures) == {"evidence", "determinism"}


@pytest.mark.parametrize(
    ("name", "mutate", "expected"),
    [
        ("a moved box", lambda t: _move_box(t), {"readback", "determinism"}),
        ("a wrong printed string", lambda t: _retype(t), {"readback", "determinism"}),
        (
            "a wrong total",
            lambda t: _set_field(t, "total_amount", "9.99"),
            {"arithmetic", "determinism"},
        ),
        (
            "a wrong subtotal",
            lambda t: _set_field(t, "subtotal", "9.99"),
            {"arithmetic", "determinism"},
        ),
        ("a wrong line net", lambda t: _set_net(t), {"arithmetic", "readback", "determinism"}),
        ("a wrong vat line", lambda t: _set_vat(t), {"arithmetic", "readback", "determinism"}),
        ("a wrong page count", lambda t: _set_pages(t), {"schema", "determinism"}),
        (
            "an older schema",
            lambda t: t.__setitem__("schema", "forge-truth/0"),
            {"schema", "determinism"},
        ),
        ("an unknown rounding", lambda t: _set_rounding(t), {"schema", "determinism"}),
        ("another seed", lambda t: _set_seed(t), {"determinism"}),
    ],
)
def test_a_corrupted_truth_fails_the_check_that_should_notice(
    name: str, mutate: Corrupt, expected: set[str], tmp_path: Path
) -> None:
    failures = verify_document(corrupted(_pdf_of("de-DE"), tmp_path, mutate))
    assert checks_that_fired(failures) == expected, name


def test_a_malformed_box_is_reported_rather_than_raised(tmp_path: Path) -> None:
    def bad_box(truth: dict[str, Any]) -> None:
        truth["fields"]["invoice_number"]["evidence"][0]["bbox"] = [1, 2]

    failures = verify_document(corrupted(_pdf_of("de-DE"), tmp_path, bad_box))
    assert checks_that_fired(failures) == {"schema"}
    assert "four numbers" in failures[0].detail


def test_an_inside_out_box_is_reported(tmp_path: Path) -> None:
    def flipped(truth: dict[str, Any]) -> None:
        truth["fields"]["invoice_number"]["evidence"][0]["bbox"] = [500.0, 100.0, 100.0, 90.0]

    assert "inside out" in verify_document(corrupted(_pdf_of("de-DE"), tmp_path, flipped))[0].detail


def test_a_failure_reads_as_one_line() -> None:
    failure = Failure("a.truth.json", "readback", "the box says nothing")
    assert str(failure) == "a.truth.json: readback: the box says nothing"


def test_the_checks_are_the_ones_the_plan_names() -> None:
    assert CHECKS == ("schema", "readback", "arithmetic", "evidence", "determinism")


def test_regeneration_can_be_left_out_when_only_the_file_is_in_question(tmp_path: Path) -> None:
    failures = verify_document(corrupted(_pdf_of("de-DE"), tmp_path, _set_seed), regenerate=False)
    assert failures == ()


def _truth_of(profile_id: str) -> Path:
    document = rendered(profile_id)
    return document.pdf.with_name(f"{document.pdf.stem}.truth.json")


def _pdf_of(profile_id: str) -> Path:
    return rendered(profile_id).pdf


def _move_box(truth: dict[str, Any]) -> None:
    truth["fields"]["total_amount"]["evidence"][0]["bbox"] = [50.0, 60.0, 120.0, 70.0]


def _retype(truth: dict[str, Any]) -> None:
    truth["fields"]["invoice_number"]["printed"] = "RG-2024-000000"


def _set_field(truth: dict[str, Any], name: str, value: str) -> None:
    truth["fields"][name]["value"] = value


def _set_net(truth: dict[str, Any]) -> None:
    truth["line_items"][0]["net_amount"] = "1.00"


def _set_vat(truth: dict[str, Any]) -> None:
    truth["vat_summary"][0]["vat"] = "1.00"


def _set_pages(truth: dict[str, Any]) -> None:
    truth["document"]["pages"] = 7


def _set_rounding(truth: dict[str, Any]) -> None:
    truth["document"]["rounding"] = "sideways"


def _set_seed(truth: dict[str, Any]) -> None:
    truth["generator"]["seed"] = GOLDEN_SEED + 1
