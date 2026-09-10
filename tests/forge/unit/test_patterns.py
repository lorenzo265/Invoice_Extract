"""The pattern filler draws strings the pattern itself accepts, and refuses richer syntax."""

from __future__ import annotations

import re
from random import Random

import pytest

from invoice_forge.sample.patterns import fill

PATTERNS = (
    r"DE\d{9}",
    r"GB\d{9}",
    r"FR[0-9A-Z]{2}\d{9}",
    r"SE\d{12}",
    r"[A-Z]{2}\d \d[A-Z]{2}",
    r"\d{3} \d{2}",
    r"[A-Z0-9]{4}",
    r"[0-9]{2}-[0-9]{2}",
)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_what_is_drawn_matches_the_pattern_it_was_drawn_from(pattern: str) -> None:
    for seed in range(20):
        assert re.fullmatch(pattern, fill(pattern, Random(seed)))


def test_the_same_seed_draws_the_same_string() -> None:
    assert fill(r"DE\d{9}", Random(4)) == fill(r"DE\d{9}", Random(4))


def test_a_pattern_of_literals_is_itself() -> None:
    assert fill("ABC-123", Random(0)) == "ABC-123"


def test_a_class_without_a_count_draws_one_character() -> None:
    assert len(fill(r"\d", Random(0))) == 1


@pytest.mark.parametrize("pattern", [r"[a-z]{3}", r"[^A-Z]{2}"])
def test_an_unsupported_character_class_is_refused(pattern: str) -> None:
    with pytest.raises(ValueError, match="unsupported character class"):
        fill(pattern, Random(0))


@pytest.mark.parametrize("pattern", [r"AB+", r"A(B)", r"A|B", r"A*", r"A?", r"^A", r"A$"])
def test_richer_regular_expression_syntax_is_refused(pattern: str) -> None:
    with pytest.raises(ValueError, match="unsupported pattern syntax"):
        fill(pattern, Random(0))
