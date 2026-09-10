"""Draw a string that a pattern accepts, from a deliberately tiny pattern language.

A profile states its VAT id as a regular expression, and the sampler has to produce ids
that match it. Rather than keep a second key saying how to fill the first, the sampler
reads the pattern itself — which works because every national VAT id, IBAN body and
postal code in scope is literals and fixed-length character classes and nothing more.
Anything richer is refused rather than half-supported.
"""

from __future__ import annotations

import re
from random import Random
from string import ascii_uppercase

DIGITS = "0123456789"
ALPHABETS = {
    r"\d": DIGITS,
    "[0-9]": DIGITS,
    "[A-Z]": ascii_uppercase,
    "[0-9A-Z]": DIGITS + ascii_uppercase,
    "[A-Z0-9]": ascii_uppercase + DIGITS,
}
TOKEN = re.compile(r"(\\d|\[[^\]]*\])(?:\{(\d+)\})?|(.)", re.DOTALL)


def fill(pattern: str, rng: Random) -> str:
    """A string `re.fullmatch(pattern, ...)` accepts. Raises `ValueError` on richer syntax."""
    drawn = []
    for token in TOKEN.finditer(pattern):
        character_class, repeat, literal = token.groups()
        if character_class is None:
            drawn.append(_literal(literal))
            continue
        alphabet = ALPHABETS.get(character_class)
        if alphabet is None:
            raise ValueError(f"unsupported character class in pattern: {character_class}")
        drawn.append("".join(rng.choice(alphabet) for _ in range(int(repeat or 1))))
    return "".join(drawn)


def _literal(character: str) -> str:
    if character in "\\+*?()|^$":
        raise ValueError(f"unsupported pattern syntax: {character}")
    return character
