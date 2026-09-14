"""Which vendor printed a document, and what it means when the answer is nobody."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_profile_reading import base, written

from conftest import make_document
from invoice_extractor.profile.detect import PROFILE_THRESHOLD, detect_profile, score_profile
from invoice_extractor.profile.registry import ProfileRegistry

SUPPLIER = "Beispiel Handel GmbH"
VAT_ID = "XX123456789"
LEADING = 14.0


def page(*texts: str) -> object:
    return make_document(
        [
            (1, text, 56.0, 60.0 + index * LEADING, 300.0, 72.0 + index * LEADING)
            for index, text in enumerate(texts)
        ]
    )


def registry_of(tmp_path: Path, *extra: tuple[str, str]) -> ProfileRegistry:
    """The one profile of `test_profile_reading`, plus a differently named copy per entry."""
    root = written(tmp_path, base())
    for profile_id, supplier in extra:
        other = base()
        other["id"] = profile_id
        other["supplier"] = {**other["supplier"], "name": supplier, "vat_id": f"{profile_id}-1"}
        (root / f"{profile_id}.json").write_text(json.dumps(other), encoding="utf-8")
    return ProfileRegistry(root)


def test_a_document_carrying_a_vendors_name_and_vat_id_is_that_vendors(tmp_path: Path) -> None:
    registry = registry_of(tmp_path)
    document = page(SUPPLIER, f"USt-IdNr. {VAT_ID}", "Rechnungsnummer RE-1", "EUR")
    profile, scores = detect_profile(document, registry)
    assert profile is not None
    assert profile.id == "xx-XX"
    assert scores[0].score > PROFILE_THRESHOLD


def test_a_document_no_profile_matches_is_nobodys(tmp_path: Path) -> None:
    profile, scores = detect_profile(
        page("A company that is in no registry"), registry_of(tmp_path)
    )
    assert profile is None
    assert scores
    assert scores[0].score < PROFILE_THRESHOLD


def test_an_empty_registry_detects_nothing(tmp_path: Path) -> None:
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "_defaults.json").write_text("{}", encoding="utf-8")
    profile, scores = detect_profile(page(SUPPLIER), ProfileRegistry(tmp_path / "profiles"))
    assert profile is None
    assert scores == ()


def test_the_vendor_that_printed_it_beats_one_that_only_shares_its_language(
    tmp_path: Path,
) -> None:
    registry = registry_of(tmp_path, ("yy-YY", "Another Handel GmbH"))
    document = page(SUPPLIER, f"USt-IdNr. {VAT_ID}", "Rechnungsnummer RE-1", "EUR")
    profile, scores = detect_profile(document, registry)
    assert profile is not None
    assert profile.id == "xx-XX"
    assert scores[0].score > scores[1].score


def test_a_path_hint_promotes_but_cannot_decide(tmp_path: Path) -> None:
    registry = registry_of(tmp_path)
    document = page("Nothing this profile would recognise")
    with_hint, scores = detect_profile(document, registry, "invoices/xx-XX/0001.pdf")
    assert with_hint is None
    assert scores[0].parts["path_hint"] == 1.0


def test_a_score_says_what_each_part_contributed(tmp_path: Path) -> None:
    profile = ProfileRegistry(written(tmp_path, base())).get("xx-XX")
    scored = score_profile(profile, "beispielhandelgmbh", "")
    assert scored.parts["supplier"] == 1.0
    assert scored.parts["vat_id"] == 0.0
    assert scored.profile_id == "xx-XX"


@pytest.mark.parametrize("alias", ["Beispiel", SUPPLIER])
def test_a_vendor_is_recognised_by_its_shorter_names_too(tmp_path: Path, alias: str) -> None:
    profile = ProfileRegistry(written(tmp_path, base())).get("xx-XX")
    assert score_profile(profile, alias.lower().replace(" ", ""), "").parts["supplier"] == 1.0


def test_a_vendor_whose_name_is_not_written_in_latin_letters_is_still_found(
    tmp_path: Path,
) -> None:
    """The corpus is printed in sixteen languages; an ASCII-only fold would score zero."""
    greek = base()
    greek["id"] = "el-GR"
    greek["supplier"] = {**greek["supplier"], "name": "Θαλασσιά Εμπορική Α.Ε.", "aliases": []}
    root = written(tmp_path, base())
    (root / "el-GR.json").write_text(json.dumps(greek), encoding="utf-8")
    profile = ProfileRegistry(root).get("el-GR")
    scored = score_profile(profile, _folded("Θαλασσιά  Εμπορική, Α.Ε. — Τιμολόγιο"), "")
    assert scored.parts["supplier"] == 1.0


def _folded(text: str) -> str:
    return "".join(character for character in text.casefold() if character.isalnum())


def test_a_profile_that_declares_no_field_scores_nothing_for_its_labels(tmp_path: Path) -> None:
    data = base()
    data["fields"] = {}
    profile = ProfileRegistry(written(tmp_path, data)).get("xx-XX")
    assert score_profile(profile, "beispielhandelgmbh", "").parts["labels"] == 0.0
