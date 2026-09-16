"""The vocabulary this package ships with, and what happens when it is pointed elsewhere.

An engine is installed by people who did not clone the repository, so the vendors it
knows have to travel inside the wheel rather than beside the working directory. These are
the two halves of that: the bundled data is found without anyone naming a path, and a
path that names nothing is refused instead of read as an empty registry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from invoice_extractor import ProfileRegistry, bundled, load_profile
from invoice_extractor.profile.loader import DEFAULTS_ID, lexicons_beside
from invoice_extractor.profile.schema import ProfileError


def test_the_profiles_this_package_ships_with_are_inside_it() -> None:
    """Inside the package directory, so `pip install` carries them (`pyproject.toml`)."""
    assert bundled.PROFILES.is_dir()
    assert bundled.PROFILES.parent.name == "data"
    assert bundled.PROFILES.parent.parent.name == "invoice_extractor"
    assert (bundled.PROFILES / f"{DEFAULTS_ID}.json").is_file()


def test_the_lexicons_sit_beside_the_profiles() -> None:
    """The rule the loader reads a language by, and the one a caller's own directory keeps."""
    assert bundled.LEXICONS.is_dir()
    assert lexicons_beside(bundled.PROFILES) == bundled.LEXICONS


def test_a_registry_asked_for_nothing_holds_the_bundled_vendors() -> None:
    assert len(ProfileRegistry().ids()) == len(list(bundled.PROFILES.glob("*.json"))) - 1


def test_a_profile_loads_without_anyone_naming_a_directory() -> None:
    assert load_profile("de-DE").id == "de-DE"


def test_the_bundled_vocabulary_does_not_depend_on_the_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The failure this replaced: a relative default read as an empty registry elsewhere."""
    monkeypatch.chdir(tmp_path)
    assert load_profile("de-DE").id == "de-DE"
    assert ProfileRegistry().ids()


def test_a_directory_that_is_not_there_is_refused_rather_than_read_as_empty(
    tmp_path: Path,
) -> None:
    """Silence here would look exactly like a document no vendor describes."""
    missing = tmp_path / "nowhere"
    with pytest.raises(ProfileError) as raised:
        ProfileRegistry(missing)
    assert str(raised.value) == f"no profile directory at {missing}"


def test_a_directory_without_the_shared_defaults_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProfileError) as raised:
        ProfileRegistry(tmp_path)
    assert f"holds no {DEFAULTS_ID}.json" in str(raised.value)


def test_a_deployment_that_keeps_its_own_vendors_is_read_from_there(tmp_path: Path) -> None:
    """A caller's directory, with its own lexicons beside it, exactly as the bundled one."""
    root = tmp_path / "profiles"
    root.mkdir()
    (tmp_path / "lexicon").mkdir()
    (tmp_path / "lexicon" / "en.json").write_text(
        (bundled.LEXICONS / "en.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / f"{DEFAULTS_ID}.json").write_text(
        (bundled.PROFILES / f"{DEFAULTS_ID}.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    declared = json.loads((bundled.PROFILES / "en-GB.json").read_text(encoding="utf-8"))
    (root / "acme.json").write_text(
        json.dumps({**declared, "id": "acme"}, ensure_ascii=False), encoding="utf-8"
    )
    registry = ProfileRegistry(root)
    assert registry.ids() == ("acme",)
    assert registry.get("acme").supplier.name == declared["supplier"]["name"]
