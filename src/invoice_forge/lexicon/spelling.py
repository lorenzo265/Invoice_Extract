"""Spelling a total out in words, the way an invoice that prints one does.

The words are the lexicon's; only the joining is here, and a language declares which of
five rules it joins by. A language whose rule is none of these is a lexicon that names a
new style and an entry in each table below — never a test on the language code.

| Style | Twenty-one | Twelve hundred | What joins the groups |
|---|---|---|---|
| `english` | `twenty-one` | `one thousand two hundred` | a space, `and` before a small rest |
| `germanic_compound` | `einundzwanzig` | `eintausendzweihundert` | nothing: it is one word |
| `nordic_compound` | `tjugoett` | `ett tusen tvåhundra` | a space between scale groups |
| `romance` | `vingt et un` | `mille deux cents` | a space |
| `spaced` | `yirmi dört` | `bin iki yüz` | a space, and nothing is ever glued |

`romance` carries the three irregularities French spells numbers with: the seventies and
the nineties count in teens (`soixante et onze`, `quatre-vingt-douze`), `et` joins
twenty-one but not eighty-one, and `vingt` takes a plural only when the number ends there
— `quatre-vingts`, but `quatre-vingt mille`. That last rule is why every function here is
told whether it is spelling the end of the number.

A scale word after a count greater than one is the lexicon's `scale_many`: French writes
`deux cents` where it counts `cent`, Finnish `kaksisataa` where it counts `sata`. A
language that inflects nothing lists the same two words twice. `romance` is the one style
where the plural also waits for the end of the number, which is what tells `deux cents`
from `deux cent mille`.

A million is a noun rather than a scale word in all five — `eine Million`, `deux
millions` — so the lexicon spells it whole and no style has an opinion about it.

Amounts are spelled unsigned. A credit note prints its sign in the figures above this
line, and no lexicon here carries a word for "minus".
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

from invoice_forge.lexicon.schema import AmountInWords
from invoice_forge.model import to_cents

HUNDRED = 100
THOUSAND = 1000
MILLION = 1000 * 1000
# Below twenty every number has a word of its own; `tens[0]` is twenty.
NAMED = 20
TENS_BASE = 2
TEN = 10
# The two French tens that are counted in teens: seventy is sixty-ten, ninety is eighty-ten.
TEEN_TENS = (7, 9)
FRENCH_EIGHTY = 8
SCALE_SIZES: tuple[tuple[int, int], ...] = ((THOUSAND, 1), (HUNDRED, 0))
HUNDRED_SCALE = 0

ENGLISH = "english"
GERMANIC = "germanic_compound"
NORDIC = "nordic_compound"
ROMANCE = "romance"
SPACED = "spaced"

Head = Callable[[int, int, bool, AmountInWords], str]
Join = Callable[[str, str, int], str]
Small = Callable[[int, bool, AmountInWords], str]


def spell_amount(value: Decimal, words: AmountInWords) -> str:
    """A total in words: "one thousand two hundred pounds and fifty pence".

    Rounded with `to_cents`, so the words and the figures beside them round alike.
    """
    whole, fraction = divmod(to_cents(abs(value)), 1)
    units, cents = int(whole), int(fraction * HUNDRED)
    spelled = f"{spell_number(units, words)} {_currency(words.currency_unit, units)}"
    if not cents:
        return spelled
    tail = f"{spell_number(cents, words)} {_currency(words.currency_fraction, cents)}"
    return f"{spelled} {words.joiner} {tail}"


def spell_number(value: int, words: AmountInWords, final: bool = True) -> str:
    """A whole number in words. `final` is false where the number goes on afterwards."""
    if value >= MILLION:
        return _millions(value, words, final)
    for size, index in SCALE_SIZES:
        if value >= size:
            return _scaled(value, size, index, words, final)
    return _SMALL[words.style](value, final, words)


def _millions(value: int, words: AmountInWords, final: bool) -> str:
    """The lexicon spells the million whole, so the joining rules do not reach it."""
    count, rest = divmod(value, MILLION)
    one, many = words.million
    head = one if count == 1 else f"{spell_number(count, words, final=False)} {many}"
    return head if not rest else f"{head} {spell_number(rest, words, final)}"


def _scaled(value: int, size: int, index: int, words: AmountInWords, final: bool) -> str:
    """`<count> <scale>` and whatever is left over, joined the way the style joins."""
    count, rest = divmod(value, size)
    head = _HEADS[words.style](count, index, final and not rest, words)
    if not rest:
        return head
    return _JOINS[words.style](head, spell_number(rest, words, final), rest)


def _currency(forms: tuple[str, str], count: int) -> str:
    return forms[0] if count == 1 else forms[1]


def _english_head(count: int, index: int, final: bool, words: AmountInWords) -> str:
    spelled = words.scale_one if count == 1 else spell_number(count, words, final=False)
    return f"{spelled} {_scale(count, index, words)}"


def _germanic_head(count: int, index: int, final: bool, words: AmountInWords) -> str:
    spelled = words.scale_one if count == 1 else spell_number(count, words, final=False)
    return f"{spelled}{_scale(count, index, words)}"


def _nordic_head(count: int, index: int, final: bool, words: AmountInWords) -> str:
    """One takes a space — `etthundra` compounds, `etttusen` would not be a word."""
    if count == 1:
        return f"{words.scale_one} {words.scales[index]}"
    return f"{spell_number(count, words, final=False)}{_scale(count, index, words)}"


def _romance_head(count: int, index: int, final: bool, words: AmountInWords) -> str:
    """`cent` and `mille` stand alone at one, and take their plural where the number ends."""
    scale = words.scales[index] if count == 1 or not final else words.scale_many[index]
    if count == 1:
        return scale
    return f"{spell_number(count, words, final=False)} {scale}"


def _spaced_head(count: int, index: int, final: bool, words: AmountInWords) -> str:
    """Nothing is glued, and one is not counted: `bin`, `iki bin`, `yüz`, `iki yüz`."""
    if count == 1:
        return words.scales[index]
    return f"{spell_number(count, words, final=False)} {_scale(count, index, words)}"


def _scale(count: int, index: int, words: AmountInWords) -> str:
    """The scale word, in the form a count greater than one puts it in."""
    return words.scales[index] if count == 1 else words.scale_many[index]


def _english_join(head: str, rest: str, value: int) -> str:
    """ "one thousand and five", but "one thousand two hundred and five"."""
    return f"{head} and {rest}" if value < HUNDRED else f"{head} {rest}"


def _compound_join(head: str, rest: str, value: int) -> str:
    return f"{head}{rest}"


def _spaced_join(head: str, rest: str, value: int) -> str:
    return f"{head} {rest}"


def _spaced_small(value: int, final: bool, words: AmountInWords) -> str:
    """The ten and the unit as two words: `yirmi dört`, `dvacet čtyři`."""
    if value < NAMED:
        return words.units[value]
    ten, unit = divmod(value, TEN)
    base = words.tens[ten - TENS_BASE]
    return base if not unit else f"{base} {words.units[unit]}"


def _english_small(value: int, final: bool, words: AmountInWords) -> str:
    if value < NAMED:
        return words.units[value]
    ten, unit = divmod(value, TEN)
    base = words.tens[ten - TENS_BASE]
    return base if not unit else f"{base}-{words.units[unit]}"


def _germanic_small(value: int, final: bool, words: AmountInWords) -> str:
    """The unit comes first: `vierundzwanzig` is four-and-twenty."""
    if value < NAMED:
        return words.units[value]
    ten, unit = divmod(value, TEN)
    base = words.tens[ten - TENS_BASE]
    return base if not unit else f"{words.units[unit]}{words.joiner}{base}"


def _nordic_small(value: int, final: bool, words: AmountInWords) -> str:
    """The ten comes first, and a trailing one is the counting form: `tjugoett`."""
    if value < NAMED:
        return words.units[value]
    ten, unit = divmod(value, TEN)
    base = words.tens[ten - TENS_BASE]
    if not unit:
        return base
    return f"{base}{words.scale_one if unit == 1 else words.units[unit]}"


def _romance_small(value: int, final: bool, words: AmountInWords) -> str:
    if value < NAMED:
        return words.units[value]
    ten, unit = divmod(value, TEN)
    if ten in TEEN_TENS:
        return _romance_teen_ten(ten, unit, words)
    base = words.tens[ten - TENS_BASE]
    if not unit:
        return f"{base}s" if ten == FRENCH_EIGHTY and final else base
    if unit == 1 and ten != FRENCH_EIGHTY:
        return f"{base} {words.joiner} {words.units[1]}"
    return f"{base}-{words.units[unit]}"


def _romance_teen_ten(ten: int, unit: int, words: AmountInWords) -> str:
    """Seventy is sixty plus a teen, ninety is eighty plus one: `quatre-vingt-douze`."""
    if not unit:
        return words.tens[ten - TENS_BASE]
    stem = words.tens[ten - TENS_BASE - 1]
    teen = words.units[TEN + unit]
    if ten == TEEN_TENS[0] and unit == 1:
        return f"{stem} {words.joiner} {teen}"
    return f"{stem}-{teen}"


_HEADS: Mapping[str, Head] = {
    ENGLISH: _english_head,
    GERMANIC: _germanic_head,
    NORDIC: _nordic_head,
    ROMANCE: _romance_head,
    SPACED: _spaced_head,
}

_JOINS: Mapping[str, Join] = {
    ENGLISH: _english_join,
    GERMANIC: _compound_join,
    NORDIC: _spaced_join,
    ROMANCE: _spaced_join,
    SPACED: _spaced_join,
}

_SMALL: Mapping[str, Small] = {
    ENGLISH: _english_small,
    GERMANIC: _germanic_small,
    NORDIC: _nordic_small,
    ROMANCE: _romance_small,
    SPACED: _spaced_small,
}
