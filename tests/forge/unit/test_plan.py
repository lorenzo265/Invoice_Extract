"""A plan names every document a corpus holds, and the loader refuses anything else."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from dataspec import message, write

from invoice_forge.corpus.plan import PLAN_SCHEMA, Plan, cell_name, load_plan, plan_from_arguments
from invoice_forge.families import Family
from invoice_forge.jsonspec import SpecError
from invoice_forge.knobs import Knob
from invoice_forge.produce import DocumentSpec


def base() -> dict[str, Any]:
    return {
        "schema": PLAN_SCHEMA,
        "cells": [
            {"profile": "de-DE", "family": "classic", "seed": 7, "knobs": []},
            {"profile": "en-GB", "family": "classic", "seed": 8, "knobs": ["multi_page"]},
        ],
    }


def error(tmp_path: Path, data: object) -> str:
    return message(load_plan, tmp_path, "plan", data)


def test_a_valid_plan_loads_every_cell(tmp_path: Path) -> None:
    plan = load_plan(write(tmp_path, "plan", base()))
    assert [cell.profile_id for cell in plan.cells] == ["de-DE", "en-GB"]
    assert plan.cells[0].family is Family.CLASSIC
    assert plan.cells[0].seed == 7
    assert plan.cells[1].knobs == (Knob.MULTI_PAGE,)


def test_knobs_may_be_left_out_entirely(tmp_path: Path) -> None:
    data = base()
    del data["cells"][0]["knobs"]
    assert load_plan(write(tmp_path, "plan", data)).cells[0].knobs == ()


def test_a_plan_round_trips_through_its_own_dictionary(tmp_path: Path) -> None:
    plan = load_plan(write(tmp_path, "plan", base()))
    again = load_plan(write(tmp_path, "again", plan.to_dict()))
    assert again == plan


def test_a_plan_of_another_schema_is_refused(tmp_path: Path) -> None:
    data = base()
    data["schema"] = "forge-plan/0"
    assert error(tmp_path, data).startswith("schema must be 'forge-plan/1'")


def test_a_plan_with_no_cells_is_refused(tmp_path: Path) -> None:
    data = base()
    data["cells"] = []
    assert error(tmp_path, data) == "cells must be a non-empty list of documents"


def test_an_unknown_top_level_key_is_refused(tmp_path: Path) -> None:
    data = base()
    data["documents"] = []
    assert error(tmp_path, data) == "documents is not a recognized plan key"


def test_an_unknown_cell_key_is_refused(tmp_path: Path) -> None:
    data = base()
    data["cells"][0]["template"] = "classic"
    assert error(tmp_path, data) == "cells[0].template is not a recognized cell key"


def test_a_cell_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["cells"][1] = "de-DE"
    assert error(tmp_path, data) == "cells[1] must be an object"


def test_a_cell_without_a_profile_is_refused(tmp_path: Path) -> None:
    data = base()
    del data["cells"][0]["profile"]
    assert error(tmp_path, data) == "cells[0].profile must be a non-empty string"


def test_an_unknown_family_lists_the_known_ones(tmp_path: Path) -> None:
    data = base()
    data["cells"][0]["family"] = "baroque"
    assert error(tmp_path, data).startswith("cells[0].family must be one of: ")


@pytest.mark.parametrize("seed", ["7", -1, 1.5, True])
def test_a_seed_must_be_a_whole_number_at_least_zero(tmp_path: Path, seed: object) -> None:
    data = base()
    data["cells"][0]["seed"] = seed
    assert error(tmp_path, data) == "cells[0].seed must be a whole number, zero or more"


def test_an_unknown_knob_is_refused_by_position(tmp_path: Path) -> None:
    data = base()
    data["cells"][1]["knobs"] = ["multi_page", "wobble"]
    assert error(tmp_path, data).startswith("cells[1].knobs[1] must be one of: ")


def test_a_missing_plan_file_names_the_path(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="plan file not found"):
        load_plan(tmp_path / "absent.json")


def test_the_cross_product_is_every_profile_by_every_family_by_the_count() -> None:
    plan = plan_from_arguments(["de-DE", "en-GB"], [Family.CLASSIC], count=3, seed=42)
    assert len(plan.cells) == 6
    assert [cell.seed for cell in plan.cells] == [42, 43, 44, 42, 43, 44]
    assert {cell.profile_id for cell in plan.cells} == {"de-DE", "en-GB"}


def test_the_same_offset_is_the_same_seed_in_every_profile() -> None:
    plan = plan_from_arguments(["de-DE", "en-GB"], [Family.CLASSIC], count=2, seed=100)
    by_profile: dict[str, list[int]] = {}
    for cell in plan.cells:
        by_profile.setdefault(cell.profile_id, []).append(cell.seed)
    assert by_profile["de-DE"] == by_profile["en-GB"]


def test_a_cross_product_with_nothing_in_it_is_refused() -> None:
    with pytest.raises(SpecError, match="at least one profile and one family"):
        plan_from_arguments([], [Family.CLASSIC], count=1, seed=0)
    with pytest.raises(SpecError, match="at least one profile and one family"):
        plan_from_arguments(["de-DE"], [], count=1, seed=0)


def test_a_count_below_one_is_refused() -> None:
    with pytest.raises(SpecError, match="count must be at least 1"):
        plan_from_arguments(["de-DE"], [Family.CLASSIC], count=0, seed=0)


def test_a_cell_name_is_ordered_and_says_what_made_it() -> None:
    cell = DocumentSpec("de-DE", Family.CLASSIC, 7)
    assert cell_name(0, cell) == "0001_de-DE_classic_s7"
    assert cell_name(41, cell) == "0042_de-DE_classic_s7"


def test_cell_names_sort_into_plan_order() -> None:
    plan = Plan(tuple(DocumentSpec("de-DE", Family.CLASSIC, seed) for seed in range(12)))
    names = [cell_name(index, cell) for index, cell in enumerate(plan.cells)]
    assert names == sorted(names)
