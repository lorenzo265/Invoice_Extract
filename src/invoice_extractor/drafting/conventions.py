"""How this vendor writes numbers, dates, money and tax — read off what it printed.

These are the profile keys a person cannot guess from a language: two German vendors
may print `1.234,56` and `1 234,56`, and a Swiss one `1'234.56`. The page has already
answered, many times over, and the draft counts the answers. Where the page printed no
amount with decimals, no date the loader has a name for, no currency code and no rate,
the draft writes a placeholder and says so, rather than the value of some other vendor.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from invoice_extractor.drafting.seen import Seen
from invoice_extractor.drafting.shapes import SLASHED, Shape
from invoice_extractor.drafting.trace import PLACEHOLDER, Trace, missing, traced

# The lexicon entries whose value is a VAT rate even when printed without its sign.
RATE_ENTRIES = ("totals_labels.vat_rate", "column_headers.vat_rate", "vat_summary_headers.rate")
RATE_NAMES = ("standard", "reduced")
ZERO = "0"


@dataclass(frozen=True, slots=True)
class Convention:
    """One profile key as the draft will write it, and the traces it was read from."""

    value: object
    traces: tuple[Trace, ...]
    # The decimal separator, where the convention is the number format; empty elsewhere.
    decimal: str = ""


def number_format(seen: Sequence[Seen]) -> Convention:
    """The decimal separator most amounts used, and every thousands separator beside it."""
    amounts = [one for one in seen if one.reading.shape is Shape.AMOUNT]
    decimals = Counter(one.reading.details[0] for one in amounts if one.reading.details[0])
    if not decimals:
        empty = {"decimal_separator": "", "thousands_separators": []}
        return Convention(empty, (missing("number_format", "the decimal separator"),))
    decimal, count = decimals.most_common(1)[0]
    grouped = Counter(sep for one in amounts for sep in one.reading.details[1:] if sep != decimal)
    thousands = [separator for separator, _ in grouped.most_common()]
    example = next(one for one in amounts if one.reading.details[0] == decimal)
    reason = f"{count} of {sum(decimals.values())} amounts with decimals use it"
    return Convention(
        {"decimal_separator": decimal, "thousands_separators": thousands},
        (
            traced("number_format.decimal_separator", _quoted(decimal), reason, example.pair),
            Trace("number_format.thousands_separators", _quoted(*thousands), _grouping(grouped)),
        ),
        decimal=decimal,
    )


def _quoted(*separators: str) -> str:
    """Separators as a person can see them: a space is nothing to look at unquoted."""
    return " ".join(f"'{separator}'" for separator in separators)


def _grouping(grouped: Counter[str]) -> str:
    if not grouped:
        return "no amount printed a thousands separator; add one if the vendor uses it"
    return ", ".join(f"'{separator}' in {count}" for separator, count in grouped.most_common())


def date_formats(seen: Sequence[Seen]) -> Convention:
    """Every named format a printed date fits, most often first; both slashed ones if unsure."""
    dates = [one for one in seen if one.reading.shape is Shape.DATE]
    counted = Counter(name for one in dates for name in one.reading.details)
    if not counted:
        return Convention([PLACEHOLDER], (missing("date_formats", "one of the loader's names"),))
    names = [name for name, _ in counted.most_common()]
    traces = [_date_trace(name, counted[name], dates) for name in names]
    if _only_ambiguous(dates):
        traces.append(
            Trace(
                "date_formats",
                " ".join(SLASHED),
                "every slashed date had both parts at or below 12: choose dd/mm or mm/dd",
            )
        )
    return Convention(names, tuple(traces))


def _date_trace(name: str, count: int, dates: Sequence[Seen]) -> Trace:
    example = next(one for one in dates if name in one.reading.details)
    return traced("date_formats", name, f"{count} printed dates fit it", example.pair)


def _only_ambiguous(dates: Sequence[Seen]) -> bool:
    slashed = [one for one in dates if set(one.reading.details) & set(SLASHED)]
    return bool(slashed) and all(one.reading.details == SLASHED for one in slashed)


def currencies(seen: Sequence[Seen], words: Collection[str], known: Collection[str]) -> Convention:
    """The codes the page labels as its currency, then any known code printed anywhere."""
    labelled = Counter(
        one.reading.details[0] for one in seen if one.reading.shape is Shape.CURRENCY
    )
    codes = [code for code, _ in labelled.most_common()]
    traces = [_currency_trace(code, seen) for code in codes]
    for code in sorted(known):
        if code in words and code not in codes:
            codes.append(code)
            traces.append(Trace("currencies", code, "printed on the page, unlabelled"))
    if not codes:
        return Convention([PLACEHOLDER], (missing("currencies", "the ISO 4217 code"),))
    return Convention(codes, tuple(traces))


def _currency_trace(code: str, seen: Sequence[Seen]) -> Trace:
    example = next(one for one in seen if one.reading.details[:1] == (code,))
    return traced("currencies", code, f"labelled '{example.pair.label}'", example.pair)


def rates(seen: Sequence[Seen], decimal_separator: str) -> Convention:
    """The rates the page prints: with a sign anywhere, or bare under a rate label."""
    printed = Counter(_rate_of(one, decimal_separator) for one in seen if _is_rate(one))
    printed.pop("", None)
    if not printed:
        return Convention({"standard": PLACEHOLDER}, (missing("vat.rates.standard", "the rate"),))
    ordered = [rate for rate, _ in printed.most_common() if rate != ZERO]
    named = dict(zip(RATE_NAMES, ordered, strict=False))
    if ZERO in printed:
        named["zero"] = ZERO
    traces = tuple(
        Trace(f"vat.rates.{name}", rate, f"printed {printed[rate]} times; most frequent first")
        for name, rate in named.items()
    )
    return Convention(named, traces)


def _is_rate(one: Seen) -> bool:
    if one.reading.shape is Shape.PERCENT:
        return True
    return one.reading.shape is Shape.AMOUNT and any(
        term.name in RATE_ENTRIES for term in one.terms
    )


def _rate_of(one: Seen, decimal_separator: str) -> str:
    text = one.reading.details[0] if one.reading.shape is Shape.PERCENT else one.pair.value
    number = text.replace(decimal_separator or ",", ".").replace(" ", "")
    return number if number.replace(".", "", 1).isdigit() else ""
