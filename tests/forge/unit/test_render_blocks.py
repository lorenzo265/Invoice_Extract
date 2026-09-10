"""What the renderer does with the blocks a family switches off, and with odd documents.

`classic` has every block, so the four bundled profiles never exercise a missing one.
These are the paths the simpler families will take in PR F5, and the documents the knobs
will produce — a single VAT rate, a party without a VAT id, a row with sub-items.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal
from pathlib import Path
from random import Random

import pytest

from invoice_forge.families import Family
from invoice_forge.layout.classic import CLASSIC, family_spec
from invoice_forge.layout.spec import FamilySpec, VatSummaryStyle
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.model import (
    Charge,
    ChargeType,
    Dates,
    Document,
    DocumentType,
    Identifiers,
    LineItem,
    Party,
    Payment,
    RoundingPolicy,
    SubItem,
)
from invoice_forge.profiles.loader import load_profile
from invoice_forge.render import blocks, table, totals
from invoice_forge.render.context import RenderContext
from invoice_forge.render.placement import Slot
from invoice_forge.render.renderer import RenderRequest, render
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.wording import choose_wording

RATE = Decimal("19")
BARE = dataclasses.replace(CLASSIC, parties=None, payment=None, vat_summary=None)
UNRULED = dataclasses.replace(CLASSIC, items=dataclasses.replace(CLASSIC.items, ruled=False))
NO_SUMMARY = dataclasses.replace(
    CLASSIC, vat_summary=dataclasses.replace(CLASSIC.vat_summary, style=VatSummaryStyle.NONE)
)


def item(pos: int = 1, rate: Decimal = RATE, subs: tuple[SubItem, ...] = ()) -> LineItem:
    return LineItem(
        pos=pos,
        sku=f"SKU-{pos}",
        description="A thing that is sold",
        quantity=Decimal("2"),
        unit="ea",
        unit_price=Decimal("10.00"),
        vat_rate=rate,
        sub_items=subs,
    )


def document(**changes: object) -> Document:
    party = Party("A Vendor Ltd", ("1 A Street", "AB1 2CD"), "GB123456789")
    base = Document(
        type=DocumentType.INVOICE,
        profile_id="en-GB",
        language="en",
        currency="GBP",
        supplier=party,
        bill_to=party,
        identifiers=Identifiers("INV-1", "PO-1", "C-1"),
        dates=Dates(date(2024, 3, 15), date(2024, 4, 14)),
        items=(item(),),
        charges=(),
        payment=Payment("GB00 X", "ABCDGB2L001", "A Bank", "A Vendor Ltd", "Net 30"),
        rounding=RoundingPolicy.PER_LINE,
    )
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]  # kwargs are field names


def context_for(family: FamilySpec, drawn: Document | None = None) -> RenderContext:
    profile = load_profile("en-GB")
    lexicon = load_lexicon(profile.lexicon)
    subject = document() if drawn is None else drawn
    wording = choose_wording(subject, profile, lexicon, Random(1))
    return RenderContext(subject, profile, lexicon, family, wording)


def sheet_for(context: RenderContext) -> Sheet:
    sheet = Sheet(context.family.page, context.profile.fonts)
    sheet.new_page()
    return sheet


def test_a_family_without_parties_draws_nothing_where_they_would_go() -> None:
    context = context_for(BARE)
    sheet = sheet_for(context)
    assert blocks.draw_parties(sheet, context, 200.0) == 200.0
    assert not [p for p in sheet.placements if p.mark.slot is Slot.PARTY]


def test_a_family_without_a_payment_block_needs_no_room_for_one() -> None:
    context = context_for(BARE)
    sheet = sheet_for(context)
    assert blocks.payment_height(context) == 0.0
    assert blocks.draw_payment(sheet, context, 400.0) == 400.0


def test_a_family_without_a_vat_summary_draws_none() -> None:
    for family in (BARE, NO_SUMMARY):
        context = context_for(family)
        sheet = sheet_for(context)
        totals.draw_totals(sheet, context, 400.0)
        assert not [p for p in sheet.placements if p.mark.slot is Slot.VAT_LINE], family.family


def test_a_customer_without_a_vat_id_has_no_line_for_one() -> None:
    anonymous = Party("A Buyer Ltd", ("2 B Street",), None)
    context = context_for(CLASSIC, document(bill_to=anonymous))
    sheet = sheet_for(context)
    blocks.draw_parties(sheet, context, 200.0)
    assert not [p for p in sheet.placements if p.mark.name == "customer_vat_id"]


def test_a_supplier_without_a_vat_id_has_no_line_for_one() -> None:
    anonymous = Party("A Vendor Ltd", ("1 A Street",), None)
    context = context_for(CLASSIC, document(supplier=anonymous))
    sheet = sheet_for(context)
    blocks.draw_header(sheet, context)
    assert not [p for p in sheet.placements if p.mark.name == "supplier_vat_id"]


def test_a_document_at_one_rate_states_that_rate_in_its_totals() -> None:
    context = context_for(CLASSIC)
    names = [name for name, _, _ in totals.total_rows(context)]
    assert "vat_rate" in names


def test_a_document_at_two_rates_states_none_of_them_as_the_rate() -> None:
    two = document(items=(item(1, RATE), item(2, Decimal("5"))))
    context = context_for(CLASSIC, two)
    names = [name for name, _, _ in totals.total_rows(context)]
    assert "vat_rate" not in names


def test_the_headline_rate_of_a_document_with_no_rows_is_nothing() -> None:
    assert totals.headline_rate(document(items=()).totals) is None


def test_the_headline_rate_is_the_one_the_document_is_mostly_at() -> None:
    mixed = document(items=(item(1, RATE), item(2, Decimal("5")), item(3, Decimal("5"))))
    assert totals.headline_rate(mixed.totals) == Decimal("5")


def test_an_undeclared_charge_is_in_no_totals_row() -> None:
    hidden = Charge(ChargeType.SHIPPING, Decimal("10.00"), RATE, declared=False)
    context = context_for(CLASSIC, document(charges=(hidden,)))
    labels = [label for _, label, _ in totals.total_rows(context)]
    assert context.wording.charges["SHIPPING"] not in labels


def test_an_unruled_table_draws_no_rules_but_the_same_values() -> None:
    ruled = context_for(CLASSIC)
    unruled = context_for(UNRULED)
    drawn = []
    for context in (ruled, unruled):
        sheet = sheet_for(context)
        rows = table.measure_rows(sheet, context.document, context.family.items)
        y = table.draw_header(sheet, context.family.items, context.wording, 300.0)
        table.draw_row(sheet, rows[0], context.family.items, context.wording, y)
        drawn.append([(p.mark.name, p.text) for p in sheet.placements])
    assert drawn[0] == drawn[1]


def test_a_column_the_table_has_no_value_for_is_refused() -> None:
    context = context_for(CLASSIC)
    with pytest.raises(ValueError, match="no value for table column"):
        table.draw_row(
            Sheet(CLASSIC.page, context.profile.fonts),
            table.MeasuredRow(item(), ("A thing",), 20.0),
            dataclasses.replace(
                CLASSIC.items, columns=(dataclasses.replace(CLASSIC.items.columns[0], name="wat"),)
            ),
            context.wording,
            300.0,
        )


def test_a_family_that_is_declared_but_not_built_says_so() -> None:
    with pytest.raises(ValueError, match="not built yet"):
        family_spec(Family.SAAS)
    assert family_spec(Family.CLASSIC) is CLASSIC


def test_a_row_with_sub_items_carries_them_into_the_truth(tmp_path: Path) -> None:
    from invoice_forge.truth.values import item_row

    parts = (SubItem("A part", Decimal("1"), Decimal("2.00")), SubItem("Another part"))
    row = item_row(item(1, RATE, parts), {})
    assert row["sub_items"] == [
        {"description": "A part", "quantity": "1", "unit_price": "2.00"},
        {"description": "Another part", "quantity": None, "unit_price": None},
    ]


def test_a_document_with_no_rows_still_renders(tmp_path: Path) -> None:
    profile = load_profile("en-GB")
    lexicon = load_lexicon(profile.lexicon)
    empty = document(items=())
    request = RenderRequest(empty, profile, lexicon, Family.CLASSIC, 1)
    result = render(request, tmp_path / "empty.pdf")
    assert result.pages == 1


def test_an_unruled_table_still_carries_a_subtotal_across_a_break() -> None:
    context = context_for(UNRULED)
    sheet = sheet_for(context)
    after = table.draw_carry(sheet, context.family.items, "Carried", "1.00", 300.0)
    assert after == 300.0 + table.CARRY_HEIGHT


def test_an_unruled_family_draws_its_totals_the_same_way() -> None:
    context = context_for(UNRULED)
    sheet = sheet_for(context)
    totals.draw_totals(sheet, context, 400.0)
    assert [p.mark.name for p in sheet.placements if p.mark.slot is Slot.FIELD]
