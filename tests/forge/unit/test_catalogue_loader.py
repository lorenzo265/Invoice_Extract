"""A catalogue prices things a vendor could plausibly sell, in the language it sells them in."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from dataspec import message, write

from invoice_forge.profiles.loader import bundled_profile_ids, load_profile
from invoice_forge.sample.catalogue import (
    DOMAIN_NAMES,
    MIN_PRODUCTS,
    bundled_catalogue_ids,
    load_catalogue,
)


def product(index: int) -> dict[str, Any]:
    return {
        "sku": f"SKU-{index:03d}",
        "description": f"A thing, size {index}",
        "unit": "pcs",
        "price": f"{index}.50",
    }


def base() -> dict[str, Any]:
    products = [product(index) for index in range(1, MIN_PRODUCTS + 1)]
    return {
        "language": "xx",
        "qualifiers": ["as drawn", "delivered"],
        "domains": {name: products for name in DOMAIN_NAMES},
    }


def error(tmp_path: Path, data: object) -> str:
    return message(load_catalogue, tmp_path, "catalogue", data)


def test_a_valid_catalogue_loads(tmp_path: Path) -> None:
    catalogue = load_catalogue(write(tmp_path, "catalogue", base()))
    assert catalogue.language == "xx"
    assert catalogue.qualifiers == ("as drawn", "delivered")
    assert catalogue.products("software")[0].price == Decimal("1.50")


@pytest.mark.parametrize("language", bundled_catalogue_ids())
def test_every_bundled_catalogue_loads(language: str) -> None:
    assert load_catalogue(language).language == language


def test_every_language_a_bundled_profile_speaks_has_a_catalogue() -> None:
    """A catalogue is drawn from by language, so a missing one is a vendor with nothing to sell."""
    spoken = {load_profile(profile_id).language for profile_id in bundled_profile_ids()}
    assert spoken == set(bundled_catalogue_ids())


@pytest.mark.parametrize("domain", DOMAIN_NAMES)
def test_every_bundled_catalogue_stocks_every_domain(domain: str) -> None:
    for language in bundled_catalogue_ids():
        assert len(load_catalogue(language).products(domain)) >= MIN_PRODUCTS, language


def test_prices_never_pass_through_a_float() -> None:
    for language in bundled_catalogue_ids():
        catalogue = load_catalogue(language)
        for domain in DOMAIN_NAMES:
            for item in catalogue.products(domain):
                assert isinstance(item.price, Decimal)
                assert item.price > 0, item.sku


def test_every_bundled_catalogue_offers_qualifiers_to_lengthen_a_description_with() -> None:
    for language in bundled_catalogue_ids():
        assert load_catalogue(language).qualifiers, language


def test_a_catalogue_without_qualifiers_is_refused(tmp_path: Path) -> None:
    data = base()
    data["qualifiers"] = []
    assert error(tmp_path, data) == "qualifiers must be a non-empty list of strings"


def test_descriptions_carry_the_digits_and_units_that_defeat_a_column_reader() -> None:
    """At least one description per catalogue holds a measurement, not just words."""
    for language in bundled_catalogue_ids():
        catalogue = load_catalogue(language)
        descriptions = [
            item.description for domain in DOMAIN_NAMES for item in catalogue.products(domain)
        ]
        measured = [text for text in descriptions if any(c.isdigit() for c in text)]
        assert measured, language


def test_an_unknown_domain_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["domains"]["agriculture"] = [product(1)]
    assert error(tmp_path, data) == "domains.agriculture is not a recognized domain"


def test_a_missing_domain_names_itself(tmp_path: Path) -> None:
    data = base()
    del data["domains"]["services"]
    assert error(tmp_path, data) == "domains.services must be a list of products"


def test_a_domain_must_be_a_list(tmp_path: Path) -> None:
    data = base()
    data["domains"]["services"] = {"first": product(1)}
    assert error(tmp_path, data) == "domains.services must be a list of products"


def test_a_domain_too_thin_to_draw_from_is_refused(tmp_path: Path) -> None:
    data = base()
    data["domains"]["services"] = [product(1)]
    assert error(tmp_path, data) == f"domains.services must list at least {MIN_PRODUCTS} products"


def test_a_product_must_be_an_object(tmp_path: Path) -> None:
    data = base()
    data["domains"]["services"] = ["a bolt", "a nut", "a washer"]
    assert error(tmp_path, data) == "domains.services[0] must be an object"


def test_an_unknown_product_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["domains"]["services"] = [{**product(1), "colour": "red"}, product(2), product(3)]
    assert error(tmp_path, data) == "domains.services[0].colour is not a recognized product key"


def test_a_missing_product_key_names_its_row(tmp_path: Path) -> None:
    thin = product(2)
    del thin["unit"]
    data = base()
    data["domains"]["services"] = [product(1), thin, product(3)]
    assert error(tmp_path, data) == "domains.services[1].unit is required"


def test_a_price_is_a_decimal_written_as_a_string(tmp_path: Path) -> None:
    priced = product(1)
    priced["price"] = "free"
    data = base()
    data["domains"]["services"] = [priced, product(2), product(3)]
    expected = "domains.services[0].price must be a decimal written as a string"
    assert error(tmp_path, data) == expected


def test_an_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    data = base()
    data["vendor"] = "someone"
    assert error(tmp_path, data) == "vendor is not a recognized catalogue key"
