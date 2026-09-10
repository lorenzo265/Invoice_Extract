"""Draw a whole document from a seed.

`random.Random(seed)` and nothing else: no module-level randomness, no clock, no
environment. The same request produces an equal document on any machine, which is what
makes a corpus reproducible rather than merely re-runnable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from random import Random

from invoice_forge.knobs import Knob
from invoice_forge.lexicon.schema import Lexicon
from invoice_forge.model import (
    Charge,
    Dates,
    Document,
    DocumentType,
    Identifiers,
    LineItem,
    Party,
    Payment,
    RoundingPolicy,
)
from invoice_forge.profiles.schema import VendorProfile
from invoice_forge.sample import identifiers as ids
from invoice_forge.sample.catalogue import DOMAIN_NAMES, Catalogue
from invoice_forge.sample.parties import bank_name, party

BASE_YEAR = 2024
DAYS_IN_THE_YEAR = 364
PAYMENT_DAYS = (14, 30, 45)
SUPPLY_LEAD_DAYS = 8
# The range docs/VARIATION_CATALOG.md gives the sampler. How often each count is drawn
# is the corpus plan's business, not this function's: it steers the seeds, not the range.
ITEM_RANGE = (1, 40)
QUANTITIES = (1, 2, 3, 4, 5, 10, 12, 20, 25, 40, 50, 100)
FRACTIONAL_QUANTITIES = ("0.5", "1.5", "2.5", "7.5")
ONE_ROW_IN = 6
REDUCED_RATE_DOMAIN = "software"
CHARGE_AMOUNTS = ("9.90", "24.90", "45.00", "120.00")
CHARGE_IN = 2
RATE_SCALE = 4
# Exchange rates are fictional but not absurd: a Swedish invoice echoing euros quotes a
# rate near 0.09, not near parity. Keyed by (currency, secondary currency), in units of
# 10**-RATE_SCALE; a pair no vendor has declared yet gets the near-parity default.
EXCHANGE_RATES = {
    ("EUR", "USD"): (10400, 11200),
    ("SEK", "EUR"): (830, 920),
}
DEFAULT_RATE_RANGE = (9000, 12000)
REFERENCE_LETTERS = 2


@dataclass(frozen=True, slots=True)
class SampleRequest:
    """Everything that decides what a document contains. Equal requests, equal documents."""

    profile: VendorProfile
    lexicon: Lexicon
    catalogue: Catalogue
    seed: int
    knobs: tuple[Knob, ...] = ()


def sample_document(request: SampleRequest) -> Document:
    """One invoice, drawn from the request's seed."""
    rng = Random(request.seed)
    profile = request.profile
    dates = _dates(profile, rng)
    supplier = _party(request, rng)
    return Document(
        type=DocumentType.INVOICE,
        profile_id=profile.id,
        language=profile.language,
        currency=profile.currency,
        supplier=supplier,
        bill_to=_party(request, rng),
        ship_to=_party(request, rng),
        identifiers=_identifiers(request, dates.invoice_date, rng),
        dates=dates,
        items=_items(request, rng),
        charges=_charges(profile, rng),
        payment=_payment(request, supplier, rng),
        rounding=RoundingPolicy.PER_LINE,
        secondary_currency=profile.secondary_currency,
        exchange_rate=_exchange_rate(profile, rng),
    )


def _party(request: SampleRequest, rng: Random) -> Party:
    profile = request.profile
    return party(profile, profile.country, ids.vat_id(profile.vat_id_pattern, rng), rng)


def _dates(profile: VendorProfile, rng: Random) -> Dates:
    invoice_date = date(BASE_YEAR, 1, 1) + timedelta(days=rng.randrange(DAYS_IN_THE_YEAR))
    due_date = invoice_date + timedelta(days=rng.choice(PAYMENT_DAYS))
    supply_date = invoice_date - timedelta(days=rng.randrange(SUPPLY_LEAD_DAYS))
    return Dates(
        invoice_date=invoice_date,
        due_date=due_date,
        supply_date=supply_date if profile.prints_supply_date else None,
    )


def _identifiers(request: SampleRequest, invoice_date: date, rng: Random) -> Identifiers:
    """References are codes and initials. Nothing here is, or looks like, a person."""
    extensions = request.profile.extensions
    return Identifiers(
        invoice_number=ids.invoice_number(request.profile.language, invoice_date.year, rng),
        order_number=ids.reference_number("PO", rng),
        customer_number=ids.reference_number("C", rng, length=5),
        contract_number=_optional(
            "contract_number", extensions, lambda: ids.reference_number("CTR", rng)
        ),
        our_reference=_optional("our_reference", extensions, lambda: _initials(rng)),
        your_reference=_optional(
            "your_reference", extensions, lambda: ids.reference_number("REF", rng, 4)
        ),
    )


def _items(request: SampleRequest, rng: Random) -> tuple[LineItem, ...]:
    low, high = ITEM_RANGE
    count = rng.randint(low, high)
    return tuple(_item(request, position, rng) for position in range(1, count + 1))


def _item(request: SampleRequest, position: int, rng: Random) -> LineItem:
    domain = rng.choice(DOMAIN_NAMES)
    product = rng.choice(request.catalogue.products(domain))
    rates = request.profile.vat_rates
    return LineItem(
        pos=position,
        sku=product.sku,
        description=product.description,
        quantity=_quantity(rng),
        unit=product.unit,
        unit_price=product.price,
        vat_rate=rates.reduced if domain == REDUCED_RATE_DOMAIN else rates.standard,
    )


def _quantity(rng: Random) -> Decimal:
    """One row in six is fractional, so the rounding policies have something to disagree on."""
    if rng.randrange(ONE_ROW_IN) == 0:
        return Decimal(rng.choice(FRACTIONAL_QUANTITIES))
    return Decimal(rng.choice(QUANTITIES))


def _charges(profile: VendorProfile, rng: Random) -> tuple[Charge, ...]:
    drawn = rng.randrange(CHARGE_IN)
    if not profile.charges_used or drawn == 0:
        return ()
    return (
        Charge(
            type=rng.choice(profile.charges_used),
            amount=Decimal(rng.choice(CHARGE_AMOUNTS)),
            vat_rate=profile.vat_rates.standard,
            declared=True,
        ),
    )


def _payment(request: SampleRequest, supplier: Party, rng: Random) -> Payment:
    profile = request.profile
    return Payment(
        iban=ids.iban(profile.country, rng),
        bic=ids.bic(profile.country, rng),
        bank_name=bank_name(profile.language, rng),
        account_holder=supplier.name,
        terms=rng.choice(request.lexicon.payment_terms),
    )


def _exchange_rate(profile: VendorProfile, rng: Random) -> Decimal | None:
    """Drawn for every profile, printed only where one is declared, so the stream is stable."""
    pair = (profile.currency, profile.secondary_currency or "")
    low, high = EXCHANGE_RATES.get(pair, DEFAULT_RATE_RANGE)
    drawn = Decimal(rng.randrange(low, high)).scaleb(-RATE_SCALE)
    return drawn if profile.secondary_currency is not None else None


def _initials(rng: Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTVW") for _ in range(REFERENCE_LETTERS))
    return f"{letters}/{rng.randrange(1000, 9999)}"


def _optional(name: str, extensions: tuple[str, ...], draw: Callable[[], str]) -> str | None:
    """Draw whether or not it is printed, so the random stream does not shift with a profile."""
    value = draw()
    return value if name in extensions else None
