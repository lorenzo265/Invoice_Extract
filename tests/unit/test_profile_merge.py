"""The one merge function every profile layer is assembled with."""

from __future__ import annotations

from invoice_extractor.profile.merge import PROFILE_RULES, MergeRules, merge

REPLACE = MergeRules(append=())


def test_a_key_only_the_overlay_has_is_added() -> None:
    assert merge({"a": 1}, {"b": 2}, REPLACE) == {"a": 1, "b": 2}


def test_a_key_both_have_is_replaced() -> None:
    assert merge({"a": 1}, {"a": 2}, REPLACE) == {"a": 2}


def test_nested_objects_are_merged_key_by_key() -> None:
    base = {"vat": {"id_prefix": "DE", "id_pattern": "x"}}
    merged = merge(base, {"vat": {"id_prefix": "AT"}}, REPLACE)
    assert merged == {"vat": {"id_prefix": "AT", "id_pattern": "x"}}


def test_a_list_replaces_unless_a_rule_says_it_appends() -> None:
    base = {"fields": {"invoice_number": {"labels": ["A"], "zones": ["r1c3"]}}}
    overlay = {"fields": {"invoice_number": {"labels": ["B"], "zones": ["r2c2"]}}}
    merged = merge(base, overlay, PROFILE_RULES)
    assert merged == {"fields": {"invoice_number": {"labels": ["A", "B"], "zones": ["r2c2"]}}}


def test_an_appended_list_keeps_what_was_already_said_once() -> None:
    base = {"noise": {"ignore_labels": ["Bestelldatum", "Druckdatum"]}}
    overlay = {"noise": {"ignore_labels": ["Druckdatum", "Kopie"]}}
    merged = merge(base, overlay, PROFILE_RULES)
    assert merged == {"noise": {"ignore_labels": ["Bestelldatum", "Druckdatum", "Kopie"]}}


def test_a_star_in_a_rule_matches_any_one_segment() -> None:
    base = {"line_items": {"columns": {"description": ["Beschreibung"]}}}
    overlay = {"line_items": {"columns": {"description": ["Bezeichnung"]}}}
    merged = merge(base, overlay, PROFILE_RULES)
    expected = {"line_items": {"columns": {"description": ["Beschreibung", "Bezeichnung"]}}}
    assert merged == expected


def test_a_rule_does_not_match_a_shorter_or_longer_path() -> None:
    rules = MergeRules(append=("fields.*.labels",))
    assert not rules.appends("fields.labels")
    assert not rules.appends("fields.invoice_number.labels.0")
    assert rules.appends("fields.invoice_number.labels")


def test_merging_does_not_change_either_side() -> None:
    base = {"a": {"b": [1]}}
    overlay = {"a": {"b": [2]}}
    merge(base, overlay, MergeRules(append=("a.b",)))
    assert base == {"a": {"b": [1]}}
    assert overlay == {"a": {"b": [2]}}
