"""Where a draft lands on disk, what it brings with it, and what it refuses to touch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from invoice_extractor.drafting.evidence import Evidence
from invoice_extractor.drafting.vocabulary import from_lexicons
from invoice_extractor.drafting.writer import skeleton, write

LEXICONS = {"de": {"header_labels": {"invoice_number": ["Rechnungs-Nr."]}, "months": ["Juni"]}}


def source(tmp_path: Path) -> Path:
    """A registry root with its defaults and one lexicon beside it."""
    root = tmp_path / "source" / "profiles"
    root.mkdir(parents=True)
    (root / "_defaults.json").write_text('{"fields": {}}', encoding="utf-8")
    lexicon = tmp_path / "source" / "lexicon"
    lexicon.mkdir()
    (lexicon / "de.json").write_text(json.dumps(LEXICONS["de"]), encoding="utf-8")
    return root


def evidence() -> Evidence:
    return Evidence("a.pdf", "de-DE", "de", (), (), (), (), ())


def profile(language: str = "de") -> dict[str, object]:
    return {"id": "de-DE", "language": language, "lexicon": language}


def test_the_profile_goes_among_the_profiles_and_the_evidence_beside_the_lexicons(
    tmp_path: Path,
) -> None:
    out = tmp_path / "vendors" / "profiles"
    written = write(profile(), evidence(), out, source(tmp_path), from_lexicons(LEXICONS))
    assert written.profile == out / "de-DE.json"
    assert written.evidence == tmp_path / "vendors" / "drafts" / "de-DE.json"
    assert json.loads(written.profile.read_text(encoding="utf-8"))["id"] == "de-DE"
    assert json.loads(written.evidence.read_text(encoding="utf-8"))["profile_id"] == "de-DE"


def test_the_defaults_and_the_lexicon_are_copied_where_the_directory_lacks_them(
    tmp_path: Path,
) -> None:
    out = tmp_path / "vendors" / "profiles"
    written = write(profile(), evidence(), out, source(tmp_path), from_lexicons(LEXICONS))
    assert written.defaults == out / "_defaults.json"
    assert written.lexicon == tmp_path / "vendors" / "lexicon" / "de.json"
    assert json.loads(written.lexicon.read_text(encoding="utf-8")) == LEXICONS["de"]


def test_a_directory_that_has_them_keeps_its_own(tmp_path: Path) -> None:
    out = tmp_path / "vendors" / "profiles"
    out.mkdir(parents=True)
    (out / "_defaults.json").write_text("{}", encoding="utf-8")
    (tmp_path / "vendors" / "lexicon").mkdir()
    (tmp_path / "vendors" / "lexicon" / "de.json").write_text("{}", encoding="utf-8")
    written = write(profile(), evidence(), out, source(tmp_path), from_lexicons(LEXICONS))
    assert (written.defaults, written.lexicon) == (None, None)
    assert (out / "_defaults.json").read_text(encoding="utf-8") == "{}"


def test_a_language_no_lexicon_speaks_gets_a_skeleton_to_fill_in(tmp_path: Path) -> None:
    out = tmp_path / "vendors" / "profiles"
    written = write(profile("he"), evidence(), out, source(tmp_path), from_lexicons(LEXICONS))
    assert written.lexicon is not None
    skeleton_written = json.loads(written.lexicon.read_text(encoding="utf-8"))
    assert skeleton_written["language"] == "he"
    assert skeleton_written["header_labels"] == {"invoice_number": ["?"]}
    assert skeleton_written["months"] == []


def test_a_profile_already_there_is_refused_by_name(tmp_path: Path) -> None:
    out = tmp_path / "vendors" / "profiles"
    root = source(tmp_path)
    write(profile(), evidence(), out, root, from_lexicons(LEXICONS))
    with pytest.raises(FileExistsError, match=r"de-DE\.json already exists; pass --id"):
        write(profile(), evidence(), out, root, from_lexicons(LEXICONS))


def test_the_skeleton_has_every_entry_the_other_lexicons_have_and_nothing_filled() -> None:
    drafted = skeleton("xx", from_lexicons(LEXICONS))
    assert drafted["header_labels"] == {"invoice_number": ["?"]}
    assert drafted["totals_labels"] == {}
    assert drafted["section_headings"] == ["?"]
