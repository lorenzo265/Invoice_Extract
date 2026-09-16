"""Numbers, dates, currencies and rates, counted off the page rather than guessed."""

from __future__ import annotations

from invoice_extractor.document.model import BBox, Zone
from invoice_extractor.drafting.conventions import currencies, date_formats, number_format, rates
from invoice_extractor.drafting.pairs import How, Mark, Pair
from invoice_extractor.drafting.seen import Seen
from invoice_extractor.drafting.shapes import Reading, Shape
from invoice_extractor.drafting.trace import PLACEHOLDER
from invoice_extractor.drafting.vocabulary import Term

BOX = BBox(0.0, 0.0, 10.0, 10.0)


def seen(label: str, value: str, reading: Reading, *terms: Term) -> Seen:
    pair = Pair(label, value, 1, Zone(1, 3), Zone(1, 2), BOX, BOX, How.RIGHT, Mark.COLON)
    return Seen(pair=pair, reading=reading, terms=terms)


def amount(value: str, decimal: str, *thousands: str) -> Seen:
    return seen("Betrag", value, Reading(Shape.AMOUNT, (decimal, *thousands)))


def test_the_decimal_separator_is_the_one_most_amounts_used() -> None:
    read = number_format(
        [amount("1.234,56", ",", "."), amount("0,60", ","), amount("1,234.50", ".", ",")]
    )
    assert read.value == {"decimal_separator": ",", "thousands_separators": ["."]}
    assert read.decimal == ","
    assert "2 of 3 amounts" in read.traces[0].reason


def test_the_thousands_separators_are_every_one_seen_that_is_not_the_decimal() -> None:
    read = number_format([amount("1 234,56", ",", " "), amount("1.234,56", ",", ".")])
    assert read.value == {"decimal_separator": ",", "thousands_separators": [" ", "."]}
    assert read.traces[1].value == "' ' '.'"


def test_no_amount_with_decimals_leaves_the_number_format_to_fill_in() -> None:
    read = number_format([amount("1.234", "", ".")])
    assert read.value == {"decimal_separator": "", "thousands_separators": []}
    assert read.traces[0].is_placeholder


def test_no_thousands_separator_seen_is_said_rather_than_invented() -> None:
    read = number_format([amount("0,60", ",")])
    assert "add one if the vendor uses it" in read.traces[1].reason


def test_date_formats_are_ordered_by_how_many_dates_fit_them() -> None:
    read = date_formats(
        [
            seen("Datum", "14.06.2024", Reading(Shape.DATE, ("dd.mm.yyyy",))),
            seen("Fällig", "28.06.2024", Reading(Shape.DATE, ("dd.mm.yyyy",))),
            seen("Lieferung", "14 Juni 2024", Reading(Shape.DATE, ("d Month yyyy",))),
        ]
    )
    assert read.value == ["dd.mm.yyyy", "d Month yyyy"]
    assert [trace.value for trace in read.traces] == ["dd.mm.yyyy", "d Month yyyy"]


def test_slashed_dates_that_never_settle_the_order_say_so() -> None:
    read = date_formats(
        [seen("Date", "03/04/2024", Reading(Shape.DATE, ("dd/mm/yyyy", "mm/dd/yyyy")))]
    )
    assert read.value == ["dd/mm/yyyy", "mm/dd/yyyy"]
    assert "choose dd/mm or mm/dd" in read.traces[-1].reason


def test_one_slashed_date_that_settles_the_order_settles_it_for_all() -> None:
    read = date_formats(
        [
            seen("Date", "03/04/2024", Reading(Shape.DATE, ("dd/mm/yyyy", "mm/dd/yyyy"))),
            seen("Due", "28/04/2024", Reading(Shape.DATE, ("dd/mm/yyyy",))),
        ]
    )
    assert read.value == ["dd/mm/yyyy", "mm/dd/yyyy"]
    assert all("choose" not in trace.reason for trace in read.traces)


def test_no_date_the_loader_can_name_leaves_a_placeholder() -> None:
    read = date_formats([])
    assert read.value == [PLACEHOLDER]
    assert read.traces[0].is_placeholder


def test_a_labelled_currency_comes_first_and_a_known_code_printed_anywhere_after() -> None:
    read = currencies(
        [seen("Währung", "EUR", Reading(Shape.CURRENCY, ("EUR",)))],
        words={"USD", "Betrag", "EUR"},
        known={"USD", "EUR", "GBP"},
    )
    assert read.value == ["EUR", "USD"]
    assert read.traces[0].reason == "labelled 'Währung'"
    assert read.traces[1].reason == "printed on the page, unlabelled"


def test_no_currency_anywhere_leaves_a_placeholder() -> None:
    read = currencies([], words=set(), known={"EUR"})
    assert read.value == [PLACEHOLDER]


def test_rates_come_from_signed_percentages_and_bare_numbers_under_a_rate_label() -> None:
    column = Term("de", "column_headers", "vat_rate", "USt %")
    read = rates(
        [
            seen("USt-Satz", "19 %", Reading(Shape.PERCENT, ("19",))),
            seen("USt %", "19", Reading(Shape.AMOUNT, ("",)), column),
            seen("USt %", "7", Reading(Shape.AMOUNT, ("",)), column),
            seen("USt %", "0", Reading(Shape.AMOUNT, ("",)), column),
            seen("Rabatt", "5 %", Reading(Shape.PERCENT, ("5",))),
        ],
        decimal_separator=",",
    )
    assert read.value == {"standard": "19", "reduced": "7", "zero": "0"}
    assert read.traces[0].reason.startswith("printed 2 times")


def test_a_rate_with_a_decimal_is_written_with_a_point() -> None:
    read = rates([seen("TVA", "5,5 %", Reading(Shape.PERCENT, ("5,5",)))], decimal_separator=",")
    assert read.value == {"standard": "5.5"}


def test_no_rate_on_the_page_leaves_the_standard_rate_to_fill_in() -> None:
    read = rates([seen("Menge", "5", Reading(Shape.AMOUNT, ("",)))], decimal_separator=",")
    assert read.value == {"standard": PLACEHOLDER}
    assert read.traces[0].key == "vat.rates.standard"
