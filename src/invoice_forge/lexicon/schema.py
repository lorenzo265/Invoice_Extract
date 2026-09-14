"""The typed shape of a language's lexicon: everything an invoice says, in that language.

A lexicon carries synonyms, not one string per idea. Real invoices in one language do not
agree on what to call the invoice number, and a corpus that used one word per field would
measure a label matcher against a dictionary of size one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from invoice_forge.fields import LABELLED_FIELDS, TABLE_COLUMNS
from invoice_forge.model import CHARGE_TYPE_NAMES

# Where each labelled field is printed decides which map holds its synonyms.
TOTALS_FIELDS: tuple[str, ...] = ("vat_rate", "subtotal", "vat_amount", "total_amount")
HEADER_FIELDS: tuple[str, ...] = tuple(
    name for name in LABELLED_FIELDS if name not in TOTALS_FIELDS
)

TITLE_KINDS: tuple[str, ...] = ("invoice", "credit_note")
TRAP_KINDS: tuple[str, ...] = ("order_date", "delivery_date", "print_date")
CARRY_KINDS: tuple[str, ...] = ("incoming", "outgoing")
EXEMPTION_KINDS: tuple[str, ...] = ("reverse_charge", "intra_community", "export")
PARTY_KINDS: tuple[str, ...] = ("bill_to", "ship_to", "mail_to")
VAT_SUMMARY_COLUMNS: tuple[str, ...] = ("code", "rate", "base", "vat")

MONTHS_IN_A_YEAR = 12
MAX_SYNONYMS = 5
# The two scale words a number is built from below a million: a hundred and a thousand.
SCALE_WORDS = 2

AMOUNT_IN_WORDS_STYLES: tuple[str, ...] = (
    "english",
    "germanic_compound",
    "nordic_compound",
    "romance",
    "spaced",
)


@dataclass(frozen=True, slots=True)
class AmountInWords:
    """The words a language spells a total with. The rule that joins them is `style`.

    `scale_one` is the form of "one" that stands before a scale word, which is not always
    the word for one: German counts `ein` and Swedish `ett` where both say `eine`/`en`
    on their own. `scale_many` is the form a scale word takes after a count greater than
    one, which several languages inflect: Finnish counts `sata` but `kaksisataa`, French
    writes `cent` but `deux cents`. A million is a noun rather than a scale word — `eine
    Million`, `deux millions` — so the lexicon spells it whole, in the singular and the
    plural.
    """

    style: str
    units: tuple[str, ...]
    tens: tuple[str, ...]
    scales: tuple[str, ...]
    scale_many: tuple[str, ...]
    million: tuple[str, str]
    scale_one: str
    joiner: str
    currency_unit: tuple[str, str]
    currency_fraction: tuple[str, str]


@dataclass(frozen=True, slots=True)
class Lexicon:
    """One language's half of every printed line."""

    language: str
    document_titles: Mapping[str, tuple[str, ...]]
    header_labels: Mapping[str, tuple[str, ...]]
    totals_labels: Mapping[str, tuple[str, ...]]
    charge_labels: Mapping[str, tuple[str, ...]]
    column_headers: Mapping[str, tuple[str, ...]]
    vat_summary_headers: Mapping[str, tuple[str, ...]]
    party_headings: Mapping[str, tuple[str, ...]]
    trap_labels: Mapping[str, tuple[str, ...]]
    carry_forward: Mapping[str, tuple[str, ...]]
    exemption_sentences: Mapping[str, tuple[str, ...]]
    page_numbering: tuple[str, ...]
    payment_terms: tuple[str, ...]
    legal_lines: tuple[str, ...]
    copy_stamps: tuple[str, ...]
    section_headings: tuple[str, ...]
    address_placeholders: tuple[str, ...]
    months: tuple[str, ...]
    month_abbreviations: tuple[str, ...]
    diacritics: str
    # Absent where the language's rules for spelling a number are not among the styles
    # above. A lexicon may not carry rules it does not follow, so the `amount_in_words`
    # knob prints nothing for such a language — the axis is one that document has not got.
    amount_in_words: AmountInWords | None


SYNONYM_MAPS: Mapping[str, tuple[str, ...]] = {
    "document_titles": TITLE_KINDS,
    "header_labels": HEADER_FIELDS,
    "totals_labels": TOTALS_FIELDS,
    "charge_labels": CHARGE_TYPE_NAMES,
    "column_headers": TABLE_COLUMNS,
    "vat_summary_headers": VAT_SUMMARY_COLUMNS,
    "party_headings": PARTY_KINDS,
    "trap_labels": TRAP_KINDS,
    "carry_forward": CARRY_KINDS,
    "exemption_sentences": EXEMPTION_KINDS,
}
