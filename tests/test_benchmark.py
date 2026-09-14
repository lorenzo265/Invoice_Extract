"""The benchmark: how it scores, and that the published figures are the ones it produced.

`make bench` is not part of `make check` — it needs a generated corpus and it takes
minutes — so what runs here is the scoring and rendering against hand-built results, plus
the one check that makes the published numbers trustworthy: every figure in the two
markdown files is regenerated from the committed `benchmarks/latest.json` and compared.
"""

from __future__ import annotations

import json
from decimal import Decimal

from benchmarks import matrix as matrices
from benchmarks import report as reports
from benchmarks.compare import DocumentScore, Outcome, compare
from benchmarks.run import LATEST, README, REPORT

from invoice_extractor.document.reader import BBox
from invoice_extractor.domain.models import (
    LINE_ITEM_COLUMNS,
    Evidence,
    FieldResult,
    InvoiceResult,
    LineItem,
    Strategy,
)
from invoice_extractor.extraction.specs import FIELD_ORDER

BOX = {"page": 1, "bbox": [10.0, 10.0, 60.0, 20.0]}
ELSEWHERE = {"page": 1, "bbox": [300.0, 300.0, 360.0, 310.0]}


def truth(**fields: object) -> dict[str, object]:
    """A truth file with one line item and whichever scalar fields a test names."""
    entries = {
        name: {"value": fields.get(name), "printed": None, "label": None, "evidence": [BOX]}
        for name in FIELD_ORDER
    }
    return {
        "generator": {"profile": "de-DE", "template": "classic", "knobs": ["multi_page"]},
        "fields": entries,
        "line_items": [
            {
                "part_number": "A-1",
                "description": "A thing",
                "quantity": "2",
                "unit_price": "3.50",
                "net_amount": "7.00",
            }
        ],
    }


def result(**values: object) -> InvoiceResult:
    """An extractor result carrying one matching row and whichever fields a test names."""
    return InvoiceResult(
        fields={name: _field(name, values.get(name)) for name in FIELD_ORDER},
        line_items=(LineItem("A-1", "A thing", Decimal(2), Decimal("3.50"), Decimal("7.00")),),
        findings=(),
        profile_id="de-DE",
        source_path="x.pdf",
    )


def _field(name: str, value: object, box: BBox | None = None) -> FieldResult:
    if value is None:
        return FieldResult(name=name, value=None, raw_text=None, evidence=None, valid=False)
    found = box or BBox(10.0, 10.0, 60.0, 20.0)
    evidence = Evidence(1, found, None, Strategy.LABEL_RIGHT, str(value))
    return FieldResult(
        name=name,
        value=value,
        raw_text=str(value),
        evidence=evidence,
        valid=True,
        confidence=0.9,
    )


def outcomes(score: DocumentScore) -> dict[str, Outcome]:
    return {scored.field: scored.outcome for scored in score.fields}


def test_a_value_that_matches_is_a_hit() -> None:
    score = compare("x", truth(currency="EUR"), result(currency="EUR"))
    assert outcomes(score)["currency"] is Outcome.HIT


def test_a_value_that_differs_is_a_miss() -> None:
    score = compare("x", truth(currency="EUR"), result(currency="GBP"))
    assert outcomes(score)["currency"] is Outcome.MISS


def test_money_compares_as_a_decimal_rather_than_as_a_string() -> None:
    """`19` and `19.00` are the same rate, and a benchmark that says otherwise is lying."""
    score = compare("x", truth(vat_rate="19"), result(vat_rate=Decimal("19.00")))
    assert outcomes(score)["vat_rate"] is Outcome.HIT


def test_a_field_neither_side_claims_is_absent_and_scored_in_neither() -> None:
    score = compare("x", truth(), result())
    assert outcomes(score)["currency"] is Outcome.ABSENT
    assert matrices.build([score]).fields["currency"].hit_rate is None


def test_a_value_read_where_the_document_has_none_is_a_miss() -> None:
    score = compare("x", truth(), result(currency="EUR"))
    assert outcomes(score)["currency"] is Outcome.MISS


def test_a_field_the_extractor_has_no_spec_for_is_not_covered() -> None:
    score = compare("x", truth(), result())
    assert outcomes(score)["supply_date"] is Outcome.NOT_COVERED


def test_a_miss_that_found_no_candidate_is_counted_apart_from_a_wrong_one() -> None:
    empty = compare("x", truth(currency="EUR"), result())
    wrong = compare("x", truth(currency="EUR"), result(currency="GBP"))
    assert matrices.build([empty]).fields["currency"].found_nothing == 1
    assert matrices.build([wrong]).fields["currency"].found_nothing == 0


def test_evidence_agrees_when_the_boxes_overlap() -> None:
    agreeing = compare("x", truth(currency="EUR"), result(currency="EUR"))
    assert matrices.build([agreeing]).fields["currency"].evidence_agreed == 1


def test_evidence_disagrees_when_the_extractor_read_a_different_box() -> None:
    """A right answer out of the wrong box is a warning, not a miss: it is reported apart."""
    moved = truth(currency="EUR")
    _entry(moved, "currency")["evidence"] = [ELSEWHERE]
    score = compare("x", moved, result(currency="EUR"))
    built = matrices.build([score])
    assert built.fields["currency"].hit == 1
    assert built.fields["currency"].evidence_agreed == 0


def _entry(data: dict[str, object], name: str) -> dict[str, object]:
    fields = data["fields"]
    assert isinstance(fields, dict)
    entry = fields[name]
    assert isinstance(entry, dict)
    return entry


def test_a_row_the_extractor_did_not_find_is_one_error_per_column() -> None:
    two_rows = truth()
    rows = two_rows["line_items"]
    assert isinstance(rows, list)
    rows.append({**rows[0], "part_number": "A-2"})
    score = compare("x", two_rows, result())
    assert score.rows_expected == 2
    assert score.rows_found == 1
    assert all(score.columns[column] == (1, 1) for column in LINE_ITEM_COLUMNS)


def test_a_knob_is_tallied_on_the_side_the_document_turned_it() -> None:
    """One document lands in the `on` column of its own knobs and the `off` of every other."""
    built = matrices.build([compare("x", truth(currency="EUR"), result(currency="EUR"))])
    assert built.knob_on["multi_page"].hit == 1
    assert "multi_page" not in built.knob_off
    assert built.knob_off["credit_note"].hit == 1
    assert "credit_note" not in built.knob_on


def test_confidence_lands_in_its_band() -> None:
    built = matrices.build([compare("x", truth(currency="EUR"), result(currency="EUR"))])
    assert built.calibration[-1].hit == 1


def committed() -> dict[str, object]:
    data = json.loads(LATEST.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_the_benchmark_report_is_the_one_the_committed_numbers_render_to() -> None:
    """Regenerated from `latest.json`; a difference means one of the two was hand-edited."""
    assert REPORT.read_text(encoding="utf-8") == reports.render_report(committed())


def test_the_readme_block_is_the_one_the_committed_numbers_render_to() -> None:
    text = README.read_text(encoding="utf-8")
    _, _, rest = text.partition(reports.BEGIN)
    inside, end, _ = rest.partition(reports.END)
    assert end, "README.md has lost its benchmark:end marker"
    rendered = reports.render_readme_block(committed())
    assert reports.BEGIN + inside + reports.END == rendered


def test_the_committed_numbers_were_produced_by_this_benchmark() -> None:
    report = committed()
    assert report["schema"] == "forge-bench/1"
    matrix = report["matrix"]
    assert isinstance(matrix, dict)
    assert matrix["documents"]
