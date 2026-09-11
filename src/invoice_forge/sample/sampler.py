"""Draw a whole document from a seed.

`random.Random(seed)` and nothing else: no module-level randomness, no clock, no
environment. The same request produces an equal document on any machine, which is what
makes a corpus reproducible rather than merely re-runnable.

The family is part of the request because what a document contains depends on what kind
of invoice it is: a subscription invoice bills periods and a goods invoice bills pieces.
Everything else the family decides is layout, and the sampler never sees it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from random import Random

from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.lexicon.schema import Lexicon
from invoice_forge.model import (
    Charge,
    CreditNoteStyle,
    Dates,
    Document,
    DocumentType,
    Identifiers,
    LineItem,
    Party,
    Payment,
    as_credit_note,
)
from invoice_forge.profiles.schema import VendorProfile
from invoice_forge.sample import identifiers as ids
from invoice_forge.sample import variations
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
# Every reference a profile may switch on, so `extra_references` can switch them all on.
OPTIONAL_REFERENCES: tuple[str, ...] = ("contract_number", "our_reference", "your_reference")


@dataclass(frozen=True, slots=True)
class SampleRequest:
    """Everything that decides what a document contains. Equal requests, equal documents."""

    profile: VendorProfile
    lexicon: Lexicon
    catalogue: Catalogue
    family: Family
    seed: int
    knobs: tuple[Knob, ...] = ()

    @property
    def content(self) -> tuple[Knob, ...]:
        """The plan's knobs plus the ones this family turns on by being itself."""
        return variations.content_knobs(self.family, self.knobs)


def sample_document(request: SampleRequest) -> Document:
    """One invoice — or the credit note that reverses it — drawn from the request's seed."""
    rng = Random(request.seed)
    knobs = request.content
    profile = request.profile
    dates = _dates(request, rng)
    supplier = _party(request, rng)
    invoice = Document(
        type=DocumentType.INVOICE,
        profile_id=profile.id,
        language=profile.language,
        currency=profile.currency,
        supplier=supplier,
        bill_to=_party(request, rng),
        ship_to=_ship_to(request, rng),
        mail_to=_mail_to(request, rng),
        identifiers=_identifiers(request, dates.invoice_date, rng),
        dates=dates,
        items=_items(request, rng),
        charges=_charges(request, rng),
        payment=_payment(request, supplier, rng),
        rounding=variations.rounding(knobs, rng),
        secondary_currency=variations.secondary_currency(profile, knobs),
        exchange_rate=_exchange_rate(request, rng),
    )
    return _credited(invoice, request, rng)


def _credited(invoice: Document, request: SampleRequest, rng: Random) -> Document:
    """A credit note is an invoice reversed, and it names the invoice it reverses.

    The number is drawn either way, so turning the knob on does not shift the stream.
    """
    number = ids.invoice_number(request.profile.language, invoice.dates.invoice_date.year, rng)
    if Knob.CREDIT_NOTE not in request.content:
        return invoice
    style: CreditNoteStyle = request.profile.credit_note_style
    return as_credit_note(invoice, number, style)


def _party(request: SampleRequest, rng: Random) -> Party:
    profile = request.profile
    return party(profile, profile.country, ids.vat_id(profile.vat_id_pattern, rng), rng)


def _dates(request: SampleRequest, rng: Random) -> Dates:
    invoice_date = date(BASE_YEAR, 1, 1) + timedelta(days=rng.randrange(DAYS_IN_THE_YEAR))
    due_date = invoice_date + timedelta(days=rng.choice(PAYMENT_DAYS))
    supply_date = invoice_date - timedelta(days=rng.randrange(SUPPLY_LEAD_DAYS))
    prints = variations.prints_supply_date(request.profile, request.content)
    return Dates(
        invoice_date=invoice_date,
        due_date=due_date,
        supply_date=supply_date if prints else None,
    )


def _identifiers(request: SampleRequest, invoice_date: date, rng: Random) -> Identifiers:
    """References are codes and initials. Nothing here is, or looks like, a person."""
    printed = variations.extensions(request.profile, request.content, OPTIONAL_REFERENCES)
    return Identifiers(
        invoice_number=ids.invoice_number(request.profile.language, invoice_date.year, rng),
        order_number=ids.reference_number("PO", rng),
        customer_number=ids.reference_number("C", rng, length=5),
        contract_number=_optional(
            "contract_number", printed, lambda: ids.reference_number("CTR", rng)
        ),
        our_reference=_optional("our_reference", printed, lambda: _initials(rng)),
        your_reference=_optional(
            "your_reference", printed, lambda: ids.reference_number("REF", rng, 4)
        ),
    )


def _ship_to(request: SampleRequest, rng: Random) -> Party:
    """Drawn either way, so the `placeholder_addresses` knob does not shift the stream."""
    drawn = _party(request, rng)
    wording = rng.choice(request.lexicon.address_placeholders)
    return variations.placeholder(drawn, wording, request.content)


def _mail_to(request: SampleRequest, rng: Random) -> Party | None:
    """A third party block, which only the `party_blocks` knob asks for."""
    drawn = _party(request, rng)
    return drawn if Knob.PARTY_BLOCKS in request.content else None


def _items(request: SampleRequest, rng: Random) -> tuple[LineItem, ...]:
    knobs = request.content
    low, high = variations.item_range(knobs, ITEM_RANGE)
    count = rng.randint(low, high)
    drawn = tuple(_item(request, position, rng) for position in range(1, count + 1))
    return variations.sectioned(drawn, request.lexicon.section_headings, knobs, rng)


def _item(request: SampleRequest, position: int, rng: Random) -> LineItem:
    domain = rng.choice(variations.domains(request.family, DOMAIN_NAMES))
    catalogue = request.catalogue
    product = rng.choice(catalogue.products(domain))
    knobs = request.content
    return LineItem(
        pos=position,
        sku=product.sku,
        description=variations.described(product, catalogue, knobs, rng),
        quantity=_quantity(rng),
        unit=product.unit,
        unit_price=product.price,
        vat_rate=variations.vat_rate(request.profile.vat_rates, knobs, rng),
        discount_percent=variations.discount_percent(knobs, rng),
        sub_items=variations.sub_items(domain, catalogue, knobs, rng),
        subscription=variations.subscription(request.family, rng),
    )


def _quantity(rng: Random) -> Decimal:
    """One row in six is fractional, so the rounding policies have something to disagree on."""
    if rng.randrange(ONE_ROW_IN) == 0:
        return Decimal(rng.choice(FRACTIONAL_QUANTITIES))
    return Decimal(rng.choice(QUANTITIES))


def _charges(request: SampleRequest, rng: Random) -> tuple[Charge, ...]:
    return variations.charges(request.profile, request.content, rng)


def _payment(request: SampleRequest, supplier: Party, rng: Random) -> Payment:
    profile = request.profile
    return Payment(
        iban=ids.iban(profile.country, rng),
        bic=ids.bic(profile.country, rng),
        bank_name=bank_name(profile.language, rng),
        account_holder=supplier.name,
        terms=rng.choice(request.lexicon.payment_terms),
    )


def _exchange_rate(request: SampleRequest, rng: Random) -> Decimal | None:
    """Drawn for every profile, printed only where one is echoed, so the stream is stable."""
    profile = request.profile
    pair = (profile.currency, profile.secondary_currency or "")
    low, high = EXCHANGE_RATES.get(pair, DEFAULT_RATE_RANGE)
    drawn = Decimal(rng.randrange(low, high)).scaleb(-RATE_SCALE)
    echoed = variations.secondary_currency(profile, request.content)
    return drawn if echoed is not None else None


def _initials(rng: Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTVW") for _ in range(REFERENCE_LETTERS))
    return f"{letters}/{rng.randrange(1000, 9999)}"


def _optional(name: str, printed: tuple[str, ...], draw: Callable[[], str]) -> str | None:
    """Draw whether or not it is printed, so the random stream does not shift with a profile."""
    value = draw()
    return value if name in printed else None
