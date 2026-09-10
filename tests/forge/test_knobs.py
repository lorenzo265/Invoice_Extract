"""The knob vocabulary is exactly the axes `docs/VARIATION_CATALOG.md` names."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from invoice_forge.knobs import KNOB_NAMES, Knob, parse_knobs, split_knobs

CATALOG = Path("docs/VARIATION_CATALOG.md")
# The catalog's Knob column also names template families, a separate closed vocabulary.
FAMILY_NAMES = frozenset({"classic", "tabular", "stacked", "saas", "minimal"})
TOKEN = re.compile(r"`([a-z][a-z_]*)`")
SNAKE_CASE = re.compile(r"[a-z][a-z_]*")


def documented_knobs() -> list[str]:
    """Every knob the catalog names, in the order it names them."""
    found: list[str] = []
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        found += [
            token
            for token in TOKEN.findall(cells[-1])
            if token not in FAMILY_NAMES and token not in found
        ]
    return found


def test_every_documented_axis_has_a_knob() -> None:
    assert set(documented_knobs()) <= set(KNOB_NAMES)


def test_no_knob_is_undocumented() -> None:
    assert set(KNOB_NAMES) <= set(documented_knobs())


def test_knob_names_are_unique() -> None:
    assert len(set(KNOB_NAMES)) == len(KNOB_NAMES)


def test_knob_names_are_snake_case() -> None:
    assert all(SNAKE_CASE.fullmatch(name) for name in KNOB_NAMES)


def test_parse_knobs_keeps_the_order_given() -> None:
    assert parse_knobs(["multi_page", "credit_note"]) == (Knob.MULTI_PAGE, Knob.CREDIT_NOTE)


def test_parse_knobs_names_an_unknown_knob() -> None:
    with pytest.raises(ValueError, match=re.escape("unknown knob: multipage")):
        parse_knobs(["multipage"])


def test_split_knobs_reads_a_comma_separated_argument() -> None:
    assert split_knobs("multi_page, credit_note") == (Knob.MULTI_PAGE, Knob.CREDIT_NOTE)


def test_split_knobs_of_an_empty_argument_is_no_knobs() -> None:
    assert split_knobs("") == ()
