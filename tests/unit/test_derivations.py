"""Values no line carries, computed from lines that do."""

from __future__ import annotations

import dataclasses

from conftest import make_document, make_profile
from invoice_extractor.extraction.units.derivations import DERIVATIONS, Derived, currency


def page(*texts: str) -> object:
    return make_document(
        [
            (1, text, 56.0, 60.0 + index * 14, 300.0, 72.0 + index * 14)
            for index, text in enumerate(texts)
        ]
    )


def trading_in(*codes: str) -> object:
    return dataclasses.replace(make_profile(), currencies=codes)


def derived(found: Derived | None) -> object:
    return None if found is None else found.value


def test_the_currency_is_the_vendors_code_the_page_prints() -> None:
    assert derived(currency(page("Total 100.00 GBP"), trading_in("GBP"), {})) == "GBP"


def test_the_currency_a_page_prints_most_wins_over_the_one_it_echoes() -> None:
    document = page("Subtotal 80.00 EUR", "VAT 20.00 EUR", "Total 100.00 EUR", "= 108.00 USD")
    assert derived(currency(document, trading_in("EUR", "USD"), {})) == "EUR"


def test_a_page_that_names_no_code_the_vendor_trades_in_derives_nothing() -> None:
    assert currency(page("Total 100.00"), trading_in("GBP"), {}) is None


def test_a_tie_is_settled_by_the_order_the_vendor_declares() -> None:
    document = page("Total 100.00 EUR", "= 108.00 USD")
    assert derived(currency(document, trading_in("EUR", "USD"), {})) == "EUR"


def test_the_line_reported_is_the_first_one_the_winning_code_was_printed_on() -> None:
    """Evidence for a derived value points at a line, and at the first one carrying it."""
    document = page("Subtotal 80.00 EUR", "Total 100.00 EUR")
    found = currency(document, trading_in("EUR"), {})
    assert found is not None
    assert found.line.text == "Subtotal 80.00 EUR"


def test_every_derivation_is_registered_under_its_own_name() -> None:
    assert DERIVATIONS["currency"] is currency
