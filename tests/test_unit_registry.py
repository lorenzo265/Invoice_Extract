"""The vocabulary is closed, and both directions of that are checked.

`docs/ENGINE_SPEC.md` §3: units are registered by name, the vocabulary is closed, and a
test asserts that every registered unit is referenced by a spec and every spec references
only registered units. A unit nothing names is code that cannot run; a name nothing
registers is a field that would silently never resolve.
"""

from __future__ import annotations

import pytest

from invoice_extractor.extraction.spec import AnchorSpec, DerivedSpec, strategies_for
from invoice_extractor.extraction.specs import SPECS
from invoice_extractor.extraction.units.derivations import DERIVATIONS
from invoice_extractor.extraction.units.registry import (
    FILTERS,
    NORMALIZERS,
    RANKERS,
    REGISTERED,
    STRATEGIES,
    VALIDATORS,
)


def named(what: str) -> set[str]:
    """Every name the shipped specs use of one kind of unit."""
    used: set[str] = set()
    for spec in SPECS:
        if isinstance(spec, DerivedSpec):
            if what == "derivation":
                used.add(spec.derive)
            continue
        if what == "normalizer":
            used.add(spec.normalizer)
        elif what == "validator":
            used.add(spec.validator)
        elif what == "ranker":
            used.update(spec.rankers)
        elif what == "filter":
            used.update(spec.filters)
        elif what == "strategy":
            used.update(strategies_for(spec, declares_a_pattern=True))
    return used


@pytest.mark.parametrize(
    ("what", "registered"),
    [
        ("strategy", STRATEGIES),
        ("filter", FILTERS),
        ("normalizer", NORMALIZERS),
        ("validator", VALIDATORS),
        ("ranker", RANKERS),
        ("derivation", DERIVATIONS),
    ],
)
def test_every_registered_unit_is_named_by_a_spec(what: str, registered: object) -> None:
    assert isinstance(registered, dict)
    unused = set(registered) - named(what)
    assert not unused, f"registered {what}s nothing names: {sorted(unused)}"


@pytest.mark.parametrize(
    ("what", "registered"),
    [
        ("strategy", STRATEGIES),
        ("filter", FILTERS),
        ("normalizer", NORMALIZERS),
        ("validator", VALIDATORS),
        ("ranker", RANKERS),
        ("derivation", DERIVATIONS),
    ],
)
def test_every_unit_a_spec_names_is_registered(what: str, registered: object) -> None:
    assert isinstance(registered, dict)
    unknown = named(what) - set(registered)
    assert not unknown, f"{what}s named by a spec that nothing registers: {sorted(unknown)}"


def test_the_registry_lists_every_kind_of_unit_there_is() -> None:
    assert set(REGISTERED) == {"strategy", "filter", "normalizer", "validator", "ranker"}


def test_an_anchor_collects_by_looking_for_what_it_expected() -> None:
    spec = next(entry for entry in SPECS if isinstance(entry, AnchorSpec))
    assert strategies_for(spec, declares_a_pattern=False) == ("anchor_value",)


def test_a_label_field_without_a_pattern_does_not_run_the_pattern_strategy() -> None:
    """A label is not a regular expression; compiling one as if it were finds the label."""
    spec = next(entry for entry in SPECS if entry.name == "invoice_number")
    assert "label_pattern" not in strategies_for(spec, declares_a_pattern=False)
    assert "label_pattern" in strategies_for(spec, declares_a_pattern=True)
