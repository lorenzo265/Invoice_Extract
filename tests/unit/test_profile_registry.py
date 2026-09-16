"""The registry: what it holds, and when it reads a file again."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from test_profile_reading import base, written

from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.profile.schema import ProfileError


def registry(tmp_path: Path) -> ProfileRegistry:
    return ProfileRegistry(written(tmp_path, base()))


def touch(path: Path, data: object, mtime: float) -> None:
    """Rewrite a profile with a modification time a stat call can tell apart."""
    path.write_text(json.dumps(data), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_the_registry_lists_every_profile_under_its_root(tmp_path: Path) -> None:
    assert registry(tmp_path).ids() == ("xx-XX",)


def test_the_shared_defaults_are_not_a_profile(tmp_path: Path) -> None:
    assert "_defaults" not in registry(tmp_path).ids()


def test_getting_a_profile_twice_reads_the_file_once(tmp_path: Path) -> None:
    held = registry(tmp_path)
    assert held.get("xx-XX") is held.get("xx-XX")


def test_a_profile_whose_file_changed_is_read_again(tmp_path: Path) -> None:
    held = registry(tmp_path)
    assert held.get("xx-XX").country == "XX"
    changed = base()
    changed["country"] = "YY"
    touch(held.root / "xx-XX.json", changed, mtime=2_000_000_000.0)
    assert held.get("xx-XX").country == "YY"


def test_a_change_to_the_shared_defaults_is_read_again(tmp_path: Path) -> None:
    held = registry(tmp_path)
    assert held.get("xx-XX").fields["invoice_number"].zones == ()
    overlay = {"fields": {"invoice_number": {"zones": ["r1c3"]}}}
    touch(held.root / "_defaults.json", overlay, mtime=2_000_000_000.0)
    assert held.get("xx-XX").fields["invoice_number"].zones != ()


def test_a_profile_added_while_the_registry_lives_is_found(tmp_path: Path) -> None:
    """ADR-0008: onboarding a vendor is dropping in a file, not restarting the process."""
    held = registry(tmp_path)
    assert held.ids() == ("xx-XX",)
    added = base()
    added["id"] = "yy-YY"
    (held.root / "yy-YY.json").write_text(json.dumps(added), encoding="utf-8")
    assert held.ids() == ("xx-XX", "yy-YY")
    assert held.get("yy-YY").id == "yy-YY"


def test_every_profile_under_the_root_can_be_read_at_once(tmp_path: Path) -> None:
    assert [profile.id for profile in registry(tmp_path).all()] == ["xx-XX"]


def test_asking_for_a_profile_that_is_not_there_names_the_path(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="no profile at"):
        registry(tmp_path).get("no_such_vendor")
