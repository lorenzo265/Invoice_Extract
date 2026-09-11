"""Everything below the table: the parties, the payment terms, the bank block, the footer.

Each function draws one block from the family's declaration and returns the y its next
neighbour starts at, the same way `render/header.py` stacks the blocks above the table.
A block the family declares as `None` draws nothing and returns the y it was given, which
is how `minimal` is `classic` with four blocks switched off rather than a layout of its own.

`payment_height` and `draw_payment` are two readings of one layout: the pagination has to
know how tall all of this is before a single row is placed. A test holds them together.
"""

from __future__ import annotations

from invoice_forge.layout.spec import CustomerVat, PartiesSpec, Weight
from invoice_forge.model import Document, Party
from invoice_forge.render import text as fmt
from invoice_forge.render.context import RenderContext
from invoice_forge.render.placement import Mark, field, noise, party_part
from invoice_forge.render.sheet import Sheet

NAME_TO_LINES_GAP = 4.0
FOOTER_RULE_GAP = 12.0
# Bank and IBAN, account holder, payment terms.
PAYMENT_LINES = 3
# Heading, terms, due date — two of them under the heading.
TERMS_LINES = 3
TERMS_VALUE_LINES = 2


def draw_parties(sheet: Sheet, context: RenderContext, y: float) -> float:
    """Bill-to and ship-to side by side, then the customer's VAT id under them."""
    spec = context.family.parties
    if spec is None:
        return y
    top = y + spec.gap_above
    bottoms = [
        _draw_party(sheet, context, spec, party, kind, spec.columns[index], top)
        for index, (kind, party) in enumerate(_party_columns(context.document))
        if index < len(spec.columns)
    ]
    return _draw_customer_vat(sheet, context, spec, max(bottoms, default=top)) + spec.gap_below


def draw_payment(sheet: Sheet, context: RenderContext, y: float) -> float:
    """The terms block where the family has one, then the bank block under it."""
    after_terms = _draw_terms_block(sheet, context, y)
    spec = context.family.payment
    if spec is None:
        return after_terms
    top = after_terms + spec.gap_above
    box_x = context.family.page.right - spec.box_width
    sheet.box(box_x, top - spec.size, spec.box_width, spec.box_height)
    lines = _payment_lines(context)
    for index, (line, mark) in enumerate(lines):
        sheet.draw(spec.x, top + spec.leading * index, line, spec.size, Weight.REGULAR, mark)
    return top + max(spec.leading * len(lines), spec.box_height)


def payment_height(context: RenderContext) -> float:
    """How much room the blocks under the totals need, counted before the table is placed."""
    terms = context.family.terms_block
    height = 0.0 if terms is None else terms.gap_above + terms.leading * TERMS_LINES
    spec = context.family.payment
    if spec is None:
        return height
    return height + spec.gap_above + max(spec.leading * PAYMENT_LINES, spec.box_height)


def draw_footer(sheet: Sheet, context: RenderContext) -> None:
    """The legal lines, on every page. They are noise, and the truth says where they are."""
    spec = context.family.footer
    if spec is None:
        return
    top = footer_top(context)
    sheet.rule(top)
    for index, line in enumerate(context.wording.legal_lines):
        baseline = top + FOOTER_RULE_GAP + spec.leading * index
        sheet.draw(spec.x, baseline, line, spec.size, Weight.REGULAR, noise("footer_legal"))


def footer_top(context: RenderContext) -> float:
    """The y no block may cross: the rule above the footer, or the bottom margin itself."""
    spec = context.family.footer
    height = 0.0 if spec is None else spec.height
    return context.family.page.bottom - height


def _payment_lines(context: RenderContext) -> tuple[tuple[str, Mark | None], ...]:
    """The bank, the holder, and the terms — unless the terms have a block of their own."""
    payment = context.document.payment
    label = context.wording.labels["payment_terms"]
    lines: list[tuple[str, Mark | None]] = [
        (f"{payment.bank_name} · IBAN {payment.iban} · BIC {payment.bic}", None),
        (payment.account_holder, None),
    ]
    if context.family.terms_block is None:
        lines.append((f"{label}: {payment.terms}", field("payment_terms", label)))
    return tuple(lines)


def _draw_terms_block(sheet: Sheet, context: RenderContext, y: float) -> float:
    """Payment terms with a heading of their own, a whole block away from the bank details."""
    spec = context.family.terms_block
    if spec is None:
        return y
    payment = context.document.payment
    label = context.wording.labels["payment_terms"]
    top = y + spec.gap_above
    sheet.draw(spec.x, top, label, spec.size, Weight.BOLD)
    baseline = top + spec.leading
    mark = field("payment_terms", label)
    sheet.draw(spec.x, baseline, payment.terms, spec.size, Weight.REGULAR, mark)
    wording = context.wording
    due = fmt.date_text(context.document.dates.due_date, wording.date_format, context.lexicon)
    printed = f"{wording.labels['due_date']}: {due}"
    sheet.draw(spec.x, baseline + spec.leading, printed, spec.size)
    return baseline + spec.leading * TERMS_VALUE_LINES


def _party_columns(document: Document) -> tuple[tuple[str, Party], ...]:
    named = [("bill_to", document.bill_to)]
    for kind, party in (("ship_to", document.ship_to), ("mail_to", document.mail_to)):
        if party is not None:
            named.append((kind, party))
    return tuple(named)


def _draw_party(
    sheet: Sheet,
    context: RenderContext,
    spec: PartiesSpec,
    party: Party,
    kind: str,
    x: float,
    y: float,
) -> float:
    sheet.draw(x, y, context.wording.parties[kind], spec.heading_size, Weight.BOLD)
    top = y + spec.leading + NAME_TO_LINES_GAP
    sheet.draw(x, top, party.name, spec.line_size, Weight.BOLD, party_part(kind, "name"))
    lines = party.lines if party.placeholder is None else (party.placeholder,)
    for index, line in enumerate(lines):
        baseline = top + spec.leading * (index + 1)
        mark = party_part(kind, "line") if party.placeholder is None else None
        sheet.draw(x, baseline, line, spec.line_size, Weight.REGULAR, mark)
    return top + spec.leading * (len(lines) + 1)


def _draw_customer_vat(sheet: Sheet, context: RenderContext, spec: PartiesSpec, y: float) -> float:
    """Under the bill-to block, unless the family prints it with the references instead."""
    vat_id = context.document.bill_to.vat_id
    if vat_id is None or context.family.customer_vat is CustomerVat.METADATA:
        return y
    label = context.wording.labels["customer_vat_id"]
    printed = f"{label}: {vat_id}"
    mark = field("customer_vat_id", label)
    sheet.draw(spec.columns[0], y, printed, spec.line_size, Weight.REGULAR, mark)
    return y + spec.leading
