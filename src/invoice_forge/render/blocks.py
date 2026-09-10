"""The blocks around the table: letterhead, title, metadata, parties, payment, footer.

Each function draws one block from the family's declaration and returns the y its next
neighbour starts at, so the page is stacked rather than laid out at fixed offsets. That
is what lets a profile with three extra reference lines push the table down instead of
printing over it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from invoice_forge.layout.spec import PartiesSpec, Weight
from invoice_forge.model import Document, Party
from invoice_forge.render import text as fmt
from invoice_forge.render.context import RenderContext
from invoice_forge.render.placement import field, noise, party_part
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.wording import page_line

RULE_BELOW_HEADER = 20.0
# The page count is the last row of the reference block; the rule goes under it.
PAGE_LINE_GAP = 4.0
NAME_TO_LINES_GAP = 4.0
VAT_LINE_GAP = 2.0
FOOTER_RULE_GAP = 12.0
# Bank and IBAN, account holder, payment terms.
PAYMENT_LINES = 3

# Every reference the header block can print, in the order a European invoice prints them.
METADATA_ORDER: tuple[str, ...] = (
    "invoice_number",
    "invoice_date",
    "supply_date",
    "due_date",
    "customer_number",
    "order_number",
    "contract_number",
    "our_reference",
    "your_reference",
    "currency",
)


@dataclass(frozen=True, slots=True)
class HeaderExtent:
    """Where the header block ended, and where its last line — the page count — goes."""

    bottom: float
    page_line_y: float


def draw_header(sheet: Sheet, context: RenderContext) -> HeaderExtent:
    """Letterhead on the left, title and reference list on the right, one rule under both."""
    left = _draw_letterhead(sheet, context)
    _draw_title(sheet, context)
    page_line_y = _draw_metadata(sheet, context)
    bottom = max(left, page_line_y)
    sheet.rule(bottom + PAGE_LINE_GAP)
    return HeaderExtent(bottom=bottom + PAGE_LINE_GAP + RULE_BELOW_HEADER, page_line_y=page_line_y)


def draw_page_line(sheet: Sheet, context: RenderContext, page: int, pages: int, y: float) -> None:
    """Drawn last, on a page long since left: the count is not known until the end."""
    spec = context.family.metadata
    printed = page_line(context.wording, page, pages)
    sheet.draw_right(spec.value_x, y, printed, spec.size, Weight.REGULAR, page=page)


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
    """The bank block, with an empty square where a payment QR code would be printed."""
    spec = context.family.payment
    if spec is None:
        return y
    payment = context.document.payment
    terms_label = context.wording.labels["payment_terms"]
    top = y + spec.gap_above
    box_x = context.family.page.right - spec.box_width
    sheet.box(box_x, top - spec.size, spec.box_width, spec.box_height)
    lines = (
        (f"{payment.bank_name} · IBAN {payment.iban} · BIC {payment.bic}", None),
        (payment.account_holder, None),
        (f"{terms_label}: {payment.terms}", field("payment_terms", terms_label)),
    )
    for index, (line, mark) in enumerate(lines):
        sheet.draw(spec.x, top + spec.leading * index, line, spec.size, Weight.REGULAR, mark)
    return top + max(spec.leading * len(lines), spec.box_height)


def payment_height(context: RenderContext) -> float:
    """How much room the bank block needs, counted before the table is placed."""
    spec = context.family.payment
    if spec is None:
        return 0.0
    return spec.gap_above + max(spec.leading * PAYMENT_LINES, spec.box_height)


def draw_footer(sheet: Sheet, context: RenderContext) -> None:
    """The legal lines, on every page. They are noise, and the truth says where they are."""
    spec = context.family.footer
    top = footer_top(context)
    sheet.rule(top)
    for index, line in enumerate(context.wording.legal_lines):
        baseline = top + FOOTER_RULE_GAP + spec.leading * index
        sheet.draw(spec.x, baseline, line, spec.size, Weight.REGULAR, noise("footer_legal"))


def footer_top(context: RenderContext) -> float:
    """The y no block may cross: the rule above the footer."""
    return context.family.page.bottom - context.family.footer.height


def _draw_letterhead(sheet: Sheet, context: RenderContext) -> float:
    spec = context.family.letterhead
    supplier = context.document.supplier
    name_mark = party_part("supplier", "name")
    sheet.draw(spec.x, spec.top, supplier.name, spec.name_size, Weight.BOLD, name_mark)
    top = spec.top + spec.leading + NAME_TO_LINES_GAP
    for index, line in enumerate(supplier.lines):
        baseline = top + spec.leading * index
        sheet.draw(
            spec.x, baseline, line, spec.line_size, Weight.REGULAR, party_part("supplier", "line")
        )
    y = top + spec.leading * len(supplier.lines) + VAT_LINE_GAP
    if supplier.vat_id is None:
        return y
    label = context.wording.labels["supplier_vat_id"]
    printed = f"{label}: {supplier.vat_id}"
    sheet.draw(spec.x, y, printed, spec.line_size, Weight.REGULAR, field("supplier_vat_id", label))
    return y


def _draw_title(sheet: Sheet, context: RenderContext) -> None:
    spec = context.family.title
    title = context.wording.title
    printed = title.upper() if spec.upper_case else title
    sheet.draw(spec.x, spec.top, printed, spec.size, Weight.BOLD)


def _draw_metadata(sheet: Sheet, context: RenderContext) -> float:
    """Label on the left of the block, value flushed to the right margin, one row each."""
    spec = context.family.metadata
    rows = _metadata_rows(context)
    for index, (name, label, printed) in enumerate(rows):
        y = spec.top + spec.leading * index
        sheet.draw(spec.label_x, y, f"{label}:", spec.size)
        sheet.draw_right(spec.value_x, y, printed, spec.size, Weight.REGULAR, field(name, label))
    return spec.top + spec.leading * len(rows)


def _metadata_rows(context: RenderContext) -> tuple[tuple[str, str, str], ...]:
    """`(field name, label, printed value)` for every reference this document prints."""
    labels = context.wording.labels
    printed = _metadata_values(context)
    return tuple((name, labels[name], printed[name]) for name in METADATA_ORDER if printed[name])


def _metadata_values(context: RenderContext) -> dict[str, str]:
    document = context.document
    dates = document.dates
    identifiers = document.identifiers

    def written(value: date | None) -> str:
        if value is None:
            return ""
        return fmt.date_text(value, context.wording.date_format, context.lexicon)

    return {
        "invoice_number": identifiers.invoice_number,
        "invoice_date": written(dates.invoice_date),
        "supply_date": written(dates.supply_date),
        "due_date": written(dates.due_date),
        "customer_number": identifiers.customer_number,
        "order_number": identifiers.order_number,
        "contract_number": identifiers.contract_number or "",
        "our_reference": identifiers.our_reference or "",
        "your_reference": identifiers.your_reference or "",
        "currency": document.currency,
    }


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
    for index, line in enumerate(party.lines):
        baseline = top + spec.leading * (index + 1)
        sheet.draw(x, baseline, line, spec.line_size, Weight.REGULAR, party_part(kind, "line"))
    return top + spec.leading * (len(party.lines) + 1)


def _draw_customer_vat(sheet: Sheet, context: RenderContext, spec: PartiesSpec, y: float) -> float:
    vat_id = context.document.bill_to.vat_id
    if vat_id is None:
        return y
    label = context.wording.labels["customer_vat_id"]
    printed = f"{label}: {vat_id}"
    mark = field("customer_vat_id", label)
    sheet.draw(spec.columns[0], y, printed, spec.line_size, Weight.REGULAR, mark)
    return y + spec.leading
