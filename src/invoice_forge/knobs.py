"""The closed vocabulary of difficulty knobs.

A knob is one axis of variation from `docs/VARIATION_CATALOG.md`. It affects the sampler
(what content), the family (which blocks) or the renderer (how), and the truth records
which knobs were on. Knobs carry no free parameters: a variant that needs a parameter is
a second knob.

Unlike the extractor's enums, every member's value is the name the catalog prints. That
string is the contract — it is what a truth file records and what `--knobs` accepts — so
it is written out rather than generated.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum


class Knob(Enum):
    """One axis of variation, named exactly as `docs/VARIATION_CATALOG.md` names it."""

    # Language and locale
    THOUSANDS_VARIANT = "thousands_variant"
    DUAL_CURRENCY_ECHO = "dual_currency_echo"
    # Document type and structure
    CREDIT_NOTE = "credit_note"
    MULTI_PAGE = "multi_page"
    CARRY_FORWARD = "carry_forward"
    PAGE_NUMBERING = "page_numbering"
    STAMP_COPY = "stamp_copy"
    # Header and parties
    SUPPLY_DATE = "supply_date"
    EXTRA_REFERENCES = "extra_references"
    TRAP_LABELS = "trap_labels"
    PARTY_BLOCKS = "party_blocks"
    PLACEHOLDER_ADDRESSES = "placeholder_addresses"
    CUSTOMER_VAT_POSITION = "customer_vat_position"
    # Line-item table
    COLUMN_SET = "column_set"
    WRAPPED_DESCRIPTION = "wrapped_description"
    SUB_ITEMS = "sub_items"
    SECTION_SUBTOTALS = "section_subtotals"
    DISCOUNT = "discount"
    # Totals and tax
    CHARGES = "charges"
    DECLARED_CHARGE = "declared_charge"
    UNDECLARED_CHARGE = "undeclared_charge"
    MULTI_RATE = "multi_rate"
    VAT_SUMMARY_TABLE = "vat_summary_table"
    EXEMPTION_VERBIAGE = "exemption_verbiage"
    ROUNDING_PER_LINE = "rounding_per_line"
    ROUNDING_TOTAL = "rounding_total"
    AMOUNT_IN_WORDS = "amount_in_words"
    # Footer and noise
    BANK_FOOTER = "bank_footer"
    NOISE_FOOTER = "noise_footer"
    PAYMENT_TERMS_BLOCK = "payment_terms_block"
    REPEAT_LETTERHEAD = "repeat_letterhead"


KNOB_NAMES: tuple[str, ...] = tuple(knob.value for knob in Knob)

# Two knobs that name the two values of one axis cannot both be on. The catalog gives the
# rounding policy two rows because it counts documents of each kind, and a document is
# rounded one way or the other — so a cell that asks for both is a plan to fix, not a
# document to render.
EXCLUSIVE: tuple[tuple[Knob, Knob], ...] = ((Knob.ROUNDING_PER_LINE, Knob.ROUNDING_TOTAL),)


def check_knobs(knobs: Iterable[Knob]) -> None:
    """Refuse a combination no document could be. Raises `ValueError` naming both knobs."""
    turned = set(knobs)
    for first, second in EXCLUSIVE:
        if first in turned and second in turned:
            raise ValueError(
                f"{first.value} and {second.value} are the two values of one axis; "
                "a document can only be one of them"
            )


def parse_knobs(names: Iterable[str]) -> tuple[Knob, ...]:
    """Resolve knob names, in the order given. Raises `ValueError` naming the bad one."""
    by_name = {knob.value: knob for knob in Knob}
    resolved: list[Knob] = []
    for name in names:
        knob = by_name.get(name)
        if knob is None:
            raise ValueError(f"unknown knob: {name} (known: {', '.join(KNOB_NAMES)})")
        resolved.append(knob)
    return tuple(resolved)


def split_knobs(argument: str) -> tuple[Knob, ...]:
    """Resolve a comma-separated `--knobs` argument; an empty string is no knobs."""
    return parse_knobs(name.strip() for name in argument.split(",") if name.strip())
