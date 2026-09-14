"""How ready a profile is, against the profiles already shipping."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from test_profile_reading import base, written

from invoice_extractor.profile.lint import lint, render
from invoice_extractor.profile.registry import ProfileRegistry

LABELS = ("Rechnungsnummer", "Beleg-Nr.", "Belegnummer")
ONE_LABEL = ("Rechnungsnummer",)


def declaring(profile_id: str, labels: tuple[str, ...], zones: tuple[str, ...]) -> dict[str, Any]:
    """A profile that declares exactly one field, so a tier is easy to read off it."""
    data = base()
    data["id"] = profile_id
    data["fields"] = {"invoice_number": {"labels": list(labels), "zones": list(zones)}}
    return data


def registry_of(tmp_path: Path, *others: dict[str, Any]) -> ProfileRegistry:
    """The base profile, plus one file per entry."""
    root = written(tmp_path, base())
    for other in others:
        (root / f"{other['id']}.json").write_text(json.dumps(other), encoding="utf-8")
    return ProfileRegistry(root)


def alone(tmp_path: Path, data: dict[str, Any]) -> ProfileRegistry:
    """A registry holding one profile and nothing to measure it against."""
    root = written(tmp_path, base())
    (root / "xx-XX.json").unlink()
    (root / f"{data['id']}.json").write_text(json.dumps(data), encoding="utf-8")
    return ProfileRegistry(root)


def test_a_profile_with_no_label_for_a_required_field_is_t0(tmp_path: Path) -> None:
    """The loader refuses such a file, so only a profile built in code can reach T0."""
    registry = registry_of(tmp_path)
    profile = registry.get("xx-XX")
    empty = dataclasses.replace(profile.fields["invoice_number"], labels=())
    stripped = dataclasses.replace(profile, fields={**profile.fields, "invoice_number": empty})
    report = lint(stripped, registry)
    assert report.tier == "T0"
    assert [row.name for row in report.unusable] == ["invoice_number"]


def test_a_profile_with_no_zone_is_t1(tmp_path: Path) -> None:
    profile = declaring("yy-YY", LABELS, ())
    registry = registry_of(tmp_path, profile)
    report = lint(registry.get("yy-YY"), registry)
    assert report.tier == "T1"
    assert [row.name for row in report.incomplete] == ["invoice_number"]


def test_a_profile_below_the_median_number_of_labels_is_t1(tmp_path: Path) -> None:
    registry = registry_of(
        tmp_path,
        declaring("yy-YY", ONE_LABEL, ("r1c3",)),
        declaring("zz-ZZ", LABELS, ("r1c3",)),
    )
    report = lint(registry.get("yy-YY"), registry)
    assert report.tier == "T1"
    assert report.incomplete[0].below_median


def test_a_profile_at_the_median_everywhere_is_t2(tmp_path: Path) -> None:
    registry = registry_of(tmp_path, declaring("yy-YY", LABELS, ("r1c3",)))
    assert lint(registry.get("yy-YY"), registry).tier == "T2"


def test_a_profile_measured_against_nothing_is_t2(tmp_path: Path) -> None:
    """The first profile in a registry has no median to fall short of."""
    registry = alone(tmp_path, declaring("yy-YY", ONE_LABEL, ("r1c3",)))
    assert lint(registry.get("yy-YY"), registry).tier == "T2"


def test_no_shipped_profile_is_unusable() -> None:
    """Every required field of every vendor declares a label: nothing ships at T0.

    Two vendors sit at T1 because their language offers one synonym fewer than the median
    for one date field. PR E7 is where every shipped profile is brought to T2; until then
    this test holds the floor rather than the target.
    """
    registry = ProfileRegistry()
    for profile in registry.all():
        assert lint(profile, registry).tier in ("T1", "T2"), profile.id


def test_the_two_vendors_below_the_median_are_the_two_that_are_known_to_be() -> None:
    registry = ProfileRegistry()
    below = {profile.id for profile in registry.all() if lint(profile, registry).tier != "T2"}
    assert below == {"fi-FI", "sv-SE"}


def test_the_rendered_report_names_the_tier_and_says_when_nothing_is_short() -> None:
    registry = ProfileRegistry()
    printed = render(lint(registry.get("de-DE"), registry))
    assert printed.startswith("de-DE: T2")
    assert "at or above the median" in printed


def test_the_rendered_report_names_every_field_that_falls_short(tmp_path: Path) -> None:
    registry = registry_of(tmp_path, declaring("yy-YY", LABELS, ()))
    printed = render(lint(registry.get("yy-YY"), registry))
    assert "invoice_number: 3 labels, 0 zones — no zone declared" in printed


def test_the_rendered_report_says_when_a_required_field_has_no_label(tmp_path: Path) -> None:
    registry = registry_of(tmp_path)
    profile = registry.get("xx-XX")
    empty = dataclasses.replace(profile.fields["invoice_number"], labels=())
    stripped = dataclasses.replace(profile, fields={**profile.fields, "invoice_number": empty})
    assert "required, and no label declared" in render(lint(stripped, registry))


def test_the_rendered_report_names_the_median_it_fell_short_of(tmp_path: Path) -> None:
    registry = registry_of(
        tmp_path,
        declaring("yy-YY", ONE_LABEL, ("r1c3",)),
        declaring("zz-ZZ", LABELS, ("r1c3",)),
    )
    assert "fewer labels than the median" in render(lint(registry.get("yy-YY"), registry))
