"""Do the document's values agree with each other? The seven checks of `ENGINE_SPEC.md` §7.

The invariants ask whether the arithmetic adds up. These ask the other kind of question:
whether the dates run in the order dates run in, whether the VAT id carries the prefix
this vendor's country uses, whether a credit note says what it credits. Nothing here
re-reads the page, and nothing here is fatal on its own — a document can be perfectly
readable and still say something odd about itself.

Each returns the same `Verdict` as an invariant, so stage 6 runs both kinds in one loop.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from pathlib import Path

from invoice_extractor.domain.findings import Severity
from invoice_extractor.validation.facts import Facts, Verdict, fails, holds, missing

Check = Callable[[Facts], Verdict]
CREDIT_NOTE = "credit_note"
# What a filename has to carry before it is claiming to name a document: a run long
# enough to be an identifier, with a digit in it. `0001_fr-FR_classic_s7` has no such
# token, and a file named after nothing in particular contradicts nothing.
CLAIM = re.compile(r"[A-Za-z0-9][A-Za-z0-9/-]{5,}")
NOT_ALNUM = re.compile(r"[^A-Za-z0-9]")
# The dates a document may print, in the order they happen.
IN_ORDER = ("supply_date", "invoice_date", "due_date")


def invoice_number_in_filename(facts: Facts) -> Verdict:
    """Where the file is named after a document, it should be named after this one.

    A filename is a claim about what is inside, and a claim that disagrees with the page
    is worth saying out loud. A name that carries no identifier at all — most of them —
    claims nothing, and is not a disagreement.
    """
    names = ("invoice_number",)
    number = facts.text("invoice_number")
    if number is None:
        return missing(names, "invoice_number")
    claimed = [token for token in _tokens(facts.source_path) if _claims(token)]
    if not claimed:
        return Verdict(None, names, "the file name claims no document")
    wanted = _canonical(number)
    if any(_canonical(token) == wanted for token in claimed):
        return holds(names, f"the file is named after {number}")
    return fails(names, f"the file is named after {claimed[0]}, not {number}", Severity.WARNING)


def vat_prefix_matches_country(facts: Facts) -> Verdict:
    """The supplier's VAT id should carry the prefix its country's ids are written with."""
    names = ("supplier_vat_id",)
    found = facts.text("supplier_vat_id")
    prefix = facts.profile.vat.id_prefix
    if found is None:
        return missing(names, "supplier_vat_id")
    if found.upper().startswith(prefix.upper()):
        return holds(names, f"{found} is a {prefix} registration")
    return fails(names, f"{found} does not begin with {prefix}")


def dates_in_order(facts: Facts) -> Verdict:
    """What was supplied, then what was invoiced, then what is due. In that order."""
    names = IN_ORDER
    printed = [(name, _date(facts, name)) for name in IN_ORDER]
    known = [(name, value) for name, value in printed if value is not None]
    if len(known) < _A_PAIR:
        return missing(names, "two of the three dates")
    out_of_order = [
        (known[index], known[index + 1])
        for index in range(len(known) - 1)
        if known[index][1] > known[index + 1][1]
    ]
    if not out_of_order:
        return holds(names, " <= ".join(f"{value}" for _, value in known))
    (first, earlier), (second, later) = out_of_order[0]
    return fails(names, f"{first} {earlier} is after {second} {later}", Severity.WARNING)


def currency_agrees_across_families(facts: Facts) -> Verdict:
    """The currency the fields say should be the one the amounts add up in.

    A document that echoes its total in another currency prints two, and stage 5 says
    which one the arithmetic closed in. Where it could not say, there is nothing to
    disagree with.
    """
    names = ("currency",)
    found = facts.text("currency")
    basis = facts.currency_basis
    if found is None:
        return missing(names, "currency")
    if basis is None:
        return Verdict(None, names, "no currency was settled on by the arithmetic")
    if basis == found:
        return holds(names, f"the amounts add up in {found}")
    return fails(names, f"the amounts add up in {basis}, not {found}")


def customer_vat_differs_from_supplier(facts: Facts) -> Verdict:
    """An invoice is between two parties, and one registration cannot be both of them."""
    names = ("customer_vat_id", "supplier_vat_id")
    customer, supplier = facts.text("customer_vat_id"), facts.text("supplier_vat_id")
    if customer is None or supplier is None:
        return missing(names, "customer_vat_id" if customer is None else "supplier_vat_id")
    if _canonical(customer) != _canonical(supplier):
        return holds(names, f"{customer} is not {supplier}")
    return fails(names, f"the customer and the supplier are both {supplier}")


def bill_to_country_matches_customer_vat(facts: Facts) -> Verdict:
    """A customer registered where the vendor is should be billed at an address there.

    Nothing here holds a table of countries — a profile knows one country, its own — so
    this is asked only of a customer whose VAT id carries the vendor's own prefix: the
    block that bills them should name the country the vendor's own address ends in.
    """
    names = ("bill_to", "customer_vat_id")
    customer, party = facts.text("customer_vat_id"), facts.parties.get("bill_to")
    country = _country(facts)
    if customer is None or party is None or country is None:
        return missing(names, "customer_vat_id" if customer is None else "bill_to")
    if not customer.upper().startswith(facts.profile.vat.id_prefix.upper()):
        return Verdict(None, names, "the customer is not registered in the vendor's country")
    if any(line.casefold() == country.casefold() for line in party.lines):
        return holds(names, f"billed in {country}")
    return fails(names, f"a {facts.profile.vat.id_prefix} customer not billed in {country}")


def credit_note_references_invoice(facts: Facts) -> Verdict:
    """A credit note credits something, and a credit note that says what is worth more."""
    names = ("credit_reference",)
    if facts.document_type != CREDIT_NOTE:
        return Verdict(None, names, "the document is not a credit note")
    reference = facts.text("credit_reference")
    if reference is None:
        return fails(names, "the credit note names no invoice", Severity.WARNING)
    return holds(names, f"credits {reference}")


CHECKS: tuple[Check, ...] = (
    invoice_number_in_filename,
    vat_prefix_matches_country,
    dates_in_order,
    currency_agrees_across_families,
    customer_vat_differs_from_supplier,
    bill_to_country_matches_customer_vat,
    credit_note_references_invoice,
)
CHECK_NAMES: tuple[str, ...] = tuple(check.__name__ for check in CHECKS)

# Two dates are the fewest that can be in the wrong order.
_A_PAIR = 2


def _date(facts: Facts, name: str) -> date | None:
    found = facts.fields.get(name)
    value = None if found is None else found.value
    return value if isinstance(value, date) else None


def _tokens(source_path: str) -> list[str]:
    return [token for token in re.split(r"[^A-Za-z0-9/-]+", Path(source_path).stem) if token]


def _claims(token: str) -> bool:
    return CLAIM.fullmatch(token) is not None and any(character.isdigit() for character in token)


def _canonical(text: str) -> str:
    return NOT_ALNUM.sub("", text).upper()


def _country(facts: Facts) -> str | None:
    """The country the vendor's own address ends in, where it prints one."""
    lines = facts.profile.supplier.address_lines
    return lines[-1] if lines else None
