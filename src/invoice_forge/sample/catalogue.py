"""What is being sold, per language, per vendor domain.

Catalogues are package data for the same reason profiles and lexicons are: a corpus must
generate identically wherever it is generated from. Descriptions carry digits, commas,
units and codes on purpose — "M8 x 40", "IP65", "2,5 mm²" — because that is what defeats
a naive column reader.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from invoice_forge.jsonspec import (
    SpecError,
    read_object,
    reject_unknown,
    require_decimal,
    require_filled_strings,
    require_mapping,
    require_text,
)

CATALOGUE_DIR = Path(__file__).parent / "catalogues"
DOMAIN_NAMES: tuple[str, ...] = ("industrial", "electronics", "software", "services")
PRODUCT_KEYS = ("part_number", "description", "unit", "price")
TOP_LEVEL_KEYS = ("language", "qualifiers", "domains")
MIN_PRODUCTS = 3


@dataclass(frozen=True, slots=True)
class Product:
    """One thing a vendor sells, priced as its own catalogue prices it."""

    part_number: str
    description: str
    unit: str
    price: Decimal


@dataclass(frozen=True, slots=True)
class Catalogue:
    """One language's products, grouped by the kind of business that sells them."""

    language: str
    # Phrases a supplier appends to a description; what `wrapped_description` lengthens with.
    qualifiers: tuple[str, ...]
    domains: Mapping[str, tuple[Product, ...]]

    def products(self, domain: str) -> tuple[Product, ...]:
        return self.domains[domain]


def load_catalogue(id_or_path: str) -> Catalogue:
    """Load a bundled catalogue by language id, or any catalogue by path."""
    return _parse(read_object(_resolve(id_or_path), "catalogue"))


def bundled_catalogue_ids() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in CATALOGUE_DIR.glob("*.json")))


def _resolve(id_or_path: str) -> Path:
    looks_like_a_path = "/" in id_or_path or "\\" in id_or_path or id_or_path.endswith(".json")
    return Path(id_or_path) if looks_like_a_path else CATALOGUE_DIR / f"{id_or_path}.json"


def _parse(data: Mapping[str, object]) -> Catalogue:
    reject_unknown(data, TOP_LEVEL_KEYS, "", "catalogue key")
    domains = require_mapping(data, "domains", "domains", "an object with one entry per domain")
    reject_unknown(domains, DOMAIN_NAMES, "domains.", "domain")
    return Catalogue(
        language=require_text(data, "language", "language"),
        qualifiers=require_filled_strings(data, "qualifiers", "qualifiers"),
        domains={name: _products(domains, name) for name in DOMAIN_NAMES},
    )


def _products(domains: Mapping[str, object], name: str) -> tuple[Product, ...]:
    path = f"domains.{name}"
    entries = domains.get(name)
    if not isinstance(entries, list):
        raise SpecError(f"{path} must be a list of products")
    if len(entries) < MIN_PRODUCTS:
        raise SpecError(f"{path} must list at least {MIN_PRODUCTS} products")
    return tuple(_product(entry, f"{path}[{index}]") for index, entry in enumerate(entries))


def _product(entry: object, path: str) -> Product:
    if not isinstance(entry, dict):
        raise SpecError(f"{path} must be an object")
    reject_unknown(entry, PRODUCT_KEYS, f"{path}.", "product key")
    return Product(
        part_number=require_text(entry, "part_number", f"{path}.part_number"),
        description=require_text(entry, "description", f"{path}.description"),
        unit=require_text(entry, "unit", f"{path}.unit"),
        price=require_decimal(entry, "price", f"{path}.price"),
    )
