"""A layout per vendor profile, built from the same profile and lexicon that printed it.

The extractor needs a layout — labels, separators, date formats — the way a deployment
needs one per vendor. Guessing labels is not what is being measured here, so the layout
is given rather than guessed, and it is given generously: **every** synonym the lexicon
offers for a field, not the one the document happened to draw. What is left to measure
is the engine — finding the value beside the label, reading it, judging it, choosing
between candidates, and parsing the table.

Two things the layout cannot be generous about, because the format cannot say them:

- A profile draws its thousands separator per document, and a layout names one. The
  vendor's usual one is declared, which is the first the profile lists, so a document
  that drew the other is a number written a way its own layout does not describe.
- A date format that spells the month is declared as `%B`, and `datetime.strptime`
  reads month names in the C locale — that is, in English. The numeric formats are
  declared first so they are tried first; the spelled ones are declared honestly and
  will fail for every language but English.

Both are real limits, and the benchmark reports what they cost rather than hiding them.
"""

from __future__ import annotations

from collections.abc import Mapping

from invoice_extractor.document.reader import Zone
from invoice_extractor.layout.schema import (
    FIELD_NAMES,
    LINE_ITEM_COLUMNS,
    FieldLayout,
    Layout,
    LineItemsLayout,
)
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.lexicon.schema import TOTALS_FIELDS, Lexicon
from invoice_forge.profiles.loader import load_profile
from invoice_forge.profiles.schema import DateFormat, VendorProfile

# Where the `classic` family prints each field. Zones only break ties between candidates
# — a strategy that finds nothing inside them searches the whole page — so a family that
# puts a block somewhere else costs nothing but the tie-break.
ZONES: Mapping[str, tuple[Zone, ...]] = {
    "invoice_number": (Zone.TOP_RIGHT, Zone.TOP_CENTER),
    "invoice_date": (Zone.TOP_RIGHT, Zone.TOP_CENTER),
    "due_date": (Zone.TOP_RIGHT, Zone.TOP_CENTER),
    "supplier_vat_id": (Zone.TOP_LEFT,),
    "customer_vat_id": (Zone.MIDDLE_LEFT, Zone.TOP_CENTER),
    "currency": (Zone.TOP_RIGHT, Zone.TOP_CENTER),
    "vat_rate": (Zone.BOTTOM_RIGHT, Zone.MIDDLE_RIGHT),
    "subtotal": (Zone.BOTTOM_RIGHT, Zone.MIDDLE_RIGHT),
    "vat_amount": (Zone.BOTTOM_RIGHT, Zone.MIDDLE_RIGHT),
    "total_amount": (Zone.BOTTOM_RIGHT, Zone.MIDDLE_RIGHT),
}

# `strptime` patterns for the five ways a profile may print a date. The two that spell a
# month sort last, because a format that cannot read the text should not be tried first.
PATTERNS: Mapping[DateFormat, str] = {
    DateFormat.ISO: "%Y-%m-%d",
    DateFormat.DAY_DOT_MONTH: "%d.%m.%Y",
    DateFormat.DAY_SLASH_MONTH: "%d/%m/%Y",
    DateFormat.DAY_MONTH_NAME: "%d %B %Y",
    DateFormat.DAY_MONTH_ABBREVIATION: "%d-%b-%Y",
}
SPELLED = (DateFormat.DAY_MONTH_NAME, DateFormat.DAY_MONTH_ABBREVIATION)


def layout_for(profile_id: str) -> Layout:
    """The layout a deployment would write for this vendor, from the vendor's own words."""
    profile = load_profile(profile_id)
    lexicon = load_lexicon(profile.lexicon)
    return Layout(
        id=profile.id,
        language=profile.language,
        decimal_separator=profile.decimal_separator,
        thousands_separator=profile.thousands_separators[0],
        date_formats=_date_formats(profile),
        currency_symbols={},
        fields={name: _field(name, lexicon) for name in FIELD_NAMES},
        line_items=LineItemsLayout(
            header_labels={name: lexicon.column_headers[name] for name in LINE_ITEM_COLUMNS},
            stop_labels=lexicon.totals_labels["subtotal"],
        ),
    )


def _field(name: str, lexicon: Lexicon) -> FieldLayout:
    """Every label the language uses for this field, and where the classic family puts it."""
    labels = lexicon.totals_labels if name in TOTALS_FIELDS else lexicon.header_labels
    return FieldLayout(labels=labels[name], zones=ZONES[name])


def _date_formats(profile: VendorProfile) -> tuple[str, ...]:
    """The profile's own formats, the ones that read numbers before the ones that read words."""
    ordered = sorted(profile.date_formats, key=lambda declared: declared in SPELLED)
    return tuple(PATTERNS[declared] for declared in ordered)
