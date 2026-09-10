"""One invoice, as a value. Everything derived is a property, so nothing can disagree."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from invoice_forge.model.items import LineItem
from invoice_forge.model.money import Charge, RoundingPolicy, Totals
from invoice_forge.model.totals import compute_totals


class DocumentType(Enum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"


class CreditNoteStyle(Enum):
    """How a vendor writes a credit note: negative amounts, or positive with wording."""

    NEGATIVE_AMOUNTS = "negative_amounts"
    CREDIT_WORDING = "credit_wording"


CREDIT_NOTE_STYLE_NAMES: tuple[str, ...] = tuple(style.value for style in CreditNoteStyle)


@dataclass(frozen=True, slots=True)
class Party:
    """A company on the document: who is billing, who is billed, where it ships."""

    name: str
    lines: tuple[str, ...]
    vat_id: str | None = None
    placeholder: str | None = None


@dataclass(frozen=True, slots=True)
class Identifiers:
    """Every reference number the header block can print."""

    invoice_number: str
    order_number: str
    customer_number: str
    contract_number: str | None = None
    our_reference: str | None = None
    your_reference: str | None = None
    credit_reference: str | None = None


@dataclass(frozen=True, slots=True)
class Dates:
    invoice_date: date
    due_date: date
    supply_date: date | None = None


@dataclass(frozen=True, slots=True)
class Payment:
    """The bank block. The IBAN's checksum is valid; the bank does not exist."""

    iban: str
    bic: str
    bank_name: str
    account_holder: str
    terms: str


@dataclass(frozen=True, slots=True)
class Document:
    """A complete invoice, before anyone decides how it looks or how many pages it takes."""

    type: DocumentType
    profile_id: str
    language: str
    currency: str
    supplier: Party
    bill_to: Party
    identifiers: Identifiers
    dates: Dates
    items: tuple[LineItem, ...]
    charges: tuple[Charge, ...]
    payment: Payment
    rounding: RoundingPolicy
    ship_to: Party | None = None
    mail_to: Party | None = None
    secondary_currency: str | None = None
    exchange_rate: Decimal | None = None

    @property
    def totals(self) -> Totals:
        """Derived on every read: the model cannot hold a total nobody computed."""
        return compute_totals(self.items, self.charges, self.rounding)

    @property
    def vat_rates(self) -> tuple[Decimal, ...]:
        return tuple(line.rate for line in self.totals.vat_lines)


def as_credit_note(document: Document, number: str, style: CreditNoteStyle) -> Document:
    """The same document as a credit note that references the invoice it reverses."""
    identifiers = dataclasses.replace(
        document.identifiers,
        invoice_number=number,
        credit_reference=document.identifiers.invoice_number,
    )
    reversed_document = dataclasses.replace(
        document, type=DocumentType.CREDIT_NOTE, identifiers=identifiers
    )
    if style is CreditNoteStyle.CREDIT_WORDING:
        return reversed_document
    return dataclasses.replace(
        reversed_document,
        items=tuple(_negated_item(item) for item in document.items),
        charges=tuple(_negated_charge(charge) for charge in document.charges),
    )


def _negated_item(item: LineItem) -> LineItem:
    return dataclasses.replace(item, quantity=-item.quantity)


def _negated_charge(charge: Charge) -> Charge:
    return dataclasses.replace(charge, amount=-charge.amount)
