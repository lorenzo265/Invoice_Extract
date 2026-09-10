"""First rendered example for the synthetic invoice generator (`invoice_forge`).

One German B2B invoice, `classic` template family, two pages: header blocks, a line-item
table that breaks across pages with a carry-forward line, VAT summary, totals with a
declared shipping charge, a dual-currency echo, and a footer with bank details.

Everything drawn here is also written to a ground-truth JSON with the bbox of every value,
read back from the produced PDF — the contract the real generator will keep.

Run: python forge_prototype.py <directory holding the Liberation TTF files>
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import fitz

HERE = Path(__file__).parent
OUT = HERE / "out"
FONT_CANDIDATES = {
    "regular": [
        Path(sys.argv[1]) / "LiberationSans-Regular.ttf" if len(sys.argv) > 1 else None,
    ],
    "bold": [
        Path(sys.argv[1]) / "LiberationSans-Bold.ttf" if len(sys.argv) > 1 else None,
    ],
}
PAGE_W, PAGE_H = 595.0, 842.0
MARGIN_L, MARGIN_R, MARGIN_TOP, MARGIN_BOTTOM = 50.0, 545.0, 50.0, 790.0
CENT = Decimal("0.01")


# ── document model ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Party:
    name: str
    lines: tuple[str, ...]
    vat_id: str


@dataclass(frozen=True)
class LineItem:
    pos: int
    part_number: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal

    @property
    def net_amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(CENT, ROUND_HALF_UP)


@dataclass(frozen=True)
class Charge:
    label: str
    amount: Decimal
    vat_rate: Decimal


@dataclass
class Invoice:
    supplier: Party
    customer: Party
    ship_to: Party
    number: str
    order_number: str
    customer_number: str
    invoice_date: date
    supply_date: date
    due_date: date
    currency: str
    secondary_currency: str
    exchange_rate: Decimal
    items: list[LineItem]
    charges: list[Charge]
    iban: str
    bic: str
    vat_lines: dict[Decimal, tuple[Decimal, Decimal]] = field(default_factory=dict)

    def compute(self) -> None:
        by_rate: dict[Decimal, Decimal] = {}
        for it in self.items:
            by_rate[it.vat_rate] = by_rate.get(it.vat_rate, Decimal(0)) + it.net_amount
        for ch in self.charges:
            by_rate[ch.vat_rate] = by_rate.get(ch.vat_rate, Decimal(0)) + ch.amount
        self.vat_lines = {
            rate: (base, (base * rate / 100).quantize(CENT, ROUND_HALF_UP))
            for rate, base in sorted(by_rate.items())
        }

    @property
    def subtotal(self) -> Decimal:
        return sum((it.net_amount for it in self.items), Decimal(0))

    @property
    def charges_total(self) -> Decimal:
        return sum((c.amount for c in self.charges), Decimal(0))

    @property
    def vat_total(self) -> Decimal:
        return sum((v for _, v in self.vat_lines.values()), Decimal(0))

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.charges_total + self.vat_total


# ── content sampler (German locale) ─────────────────────────────────────────

CATALOG = [
    ("HX-M8-040", "Sechskantschraube M8 x 40, verzinkt, DIN 933", "1.5", "0.12"),
    ("BRG-6204", "Rillenkugellager 6204-2RS, beidseitig gedichtet", "1", "3.85"),
    ("BRK-ST-3", "Stahlwinkel 3 mm, 60 x 60 x 40, roh", "1", "2.30"),
    ("CBL-H07-25", "Leitung H07V-K 2,5 mm², schwarz, Ring 100 m", "1", "48.90"),
    ("FLT-P-200", "Filterpatrone P-200, Zellulose, 10 µm", "1", "17.40"),
    ("SW-LIC-PRO", "Softwarelizenz ProSuite, 1 Arbeitsplatz, 12 Monate", "1", "349.00"),
    ("SRV-INST-H", "Installationsservice vor Ort, pro Stunde", "1", "95.00"),
    ("PLT-AL-2", "Aluminiumblech 2 mm, 1000 x 500, EN AW-5754", "1", "31.20"),
    ("NUT-M8", "Sechskantmutter M8, verzinkt, DIN 934 (VE 200)", "1", "4.60"),
    ("WSH-M8", "Unterlegscheibe M8, DIN 125 (VE 500)", "1", "6.10"),
    ("SNS-T-PT1", "Temperatursensor PT100, 3-Leiter, -50…+200 °C", "1", "22.75"),
    ("HSE-12-2", "Hydraulikschlauch 12 mm, 2 m, mit Pressarmatur", "1", "38.00"),
    ("ENC-IP65", "Verteilerkasten IP65, 300 x 200 x 120", "1", "45.50"),
    ("REL-24V", "Koppelrelais 24 V DC, 1 Wechsler", "1", "7.95"),
]


def sample_invoice(seed: int) -> Invoice:
    rng = random.Random(seed)
    items = []
    for pos, (pn, desc, _, price) in enumerate(rng.sample(CATALOG, 13), start=1):
        qty = Decimal(rng.choice([1, 2, 4, 5, 10, 12, 25, 50, 100]))
        rate = Decimal("7") if pn.startswith("SW-") else Decimal("19")
        items.append(LineItem(pos, pn, desc, qty, Decimal(price), rate))
    inv_date = date(2024, 3, 15)
    inv = Invoice(
        supplier=Party("Rheinwerk Industriebedarf GmbH",
                       ("Am Hafen 27", "47119 Duisburg", "Deutschland"), "DE811234567"),
        customer=Party("Nordwind Logistik GmbH",
                       ("Friedrichstraße 88", "20095 Hamburg", "Deutschland"), "DE123456789"),
        ship_to=Party("Nordwind Logistik GmbH – Lager Nord",
                      ("Industrieweg 4", "21079 Hamburg", "Deutschland"), "DE123456789"),
        number="RE-2024-004217", order_number="PO-88-13092", customer_number="K-104233",
        invoice_date=inv_date, supply_date=inv_date - timedelta(days=3),
        due_date=inv_date + timedelta(days=30),
        currency="EUR", secondary_currency="USD", exchange_rate=Decimal("1.0873"),
        items=items, charges=[Charge("Versandkosten", Decimal("24.90"), Decimal("19"))],
        iban="DE89 3704 0044 0532 0130 00", bic="HABADEDDXXX",
    )
    inv.compute()
    return inv


# ── German formatting ───────────────────────────────────────────────────────


def money(v: Decimal) -> str:
    q = v.quantize(CENT, ROUND_HALF_UP)
    whole, frac = f"{abs(q):.2f}".split(".")
    whole = f"{int(whole):,}".replace(",", ".")
    return f"{'-' if q < 0 else ''}{whole},{frac}"


def qty(v: Decimal) -> str:
    return str(int(v)) if v == v.to_integral_value() else money(v)


def dmy(d: date) -> str:
    return d.strftime("%d.%m.%Y")


# ── renderer (classic family) ───────────────────────────────────────────────


class Canvas:
    """One page with a registered font pair and a running cursor."""

    def __init__(self, doc: fitz.Document, fonts: dict[str, Path], page_no: int, total_pages_slot: list[int]):
        self.page = doc.new_page(width=PAGE_W, height=PAGE_H)
        self.page.insert_font(fontname="F", fontfile=str(fonts["regular"]))
        self.page.insert_font(fontname="FB", fontfile=str(fonts["bold"]))
        self.font = {"F": fitz.Font(fontfile=str(fonts["regular"])), "FB": fitz.Font(fontfile=str(fonts["bold"]))}
        self.y = MARGIN_TOP
        self.page_no = page_no
        self.drawn: list[tuple[str, str]] = []  # (role, text) for ground truth lookup

    def width(self, text: str, size: float, font: str = "F") -> float:
        return self.font[font].text_length(text, fontsize=size)

    def text(self, x: float, y: float, s: str, size: float = 9, font: str = "F", role: str = "") -> None:
        self.page.insert_text(fitz.Point(x, y), s, fontsize=size, fontname=font)
        if role:
            self.drawn.append((role, s))

    def text_right(self, x_right: float, y: float, s: str, size: float = 9, font: str = "F", role: str = "") -> None:
        self.text(x_right - self.width(s, size, font), y, s, size, font, role)

    def hline(self, y: float, x0: float = MARGIN_L, x1: float = MARGIN_R, width: float = 0.6) -> None:
        self.page.draw_line(fitz.Point(x0, y), fitz.Point(x1, y), width=width, color=(0.3, 0.3, 0.3))


COLS = {  # x positions of the classic table (left edge; amounts are right-aligned to x_right)
    "pos": 50, "part": 72, "desc": 140, "qty_r": 372, "price_r": 432, "vat_r": 470, "amount_r": 545,
}


def draw_header(c: Canvas, inv: Invoice, total_pages: int) -> None:
    c.text(MARGIN_L, 62, inv.supplier.name, 13, "FB", "supplier_name")
    y = 78
    for line in inv.supplier.lines:
        c.text(MARGIN_L, y, line, 9); y += 12
    c.text(MARGIN_L, y + 2, f"USt-IdNr.: {inv.supplier.vat_id}", 9, role="supplier_vat_line")
    # metadata block, right, as label/value pairs
    c.text(360, 62, "RECHNUNG", 13, "FB", "doc_type")
    rows = [("Rechnungsnummer", inv.number, "invoice_number"), ("Rechnungsdatum", dmy(inv.invoice_date), "invoice_date"),
            ("Leistungsdatum", dmy(inv.supply_date), "supply_date"), ("Fällig am", dmy(inv.due_date), "due_date"),
            ("Kundennummer", inv.customer_number, "customer_number"), ("Bestellnummer", inv.order_number, "order_number"),
            ("Seite", f"{c.page_no} von {total_pages}", "")]
    y = 80
    for label, value, role in rows:
        c.text(360, y, f"{label}:", 9)
        c.text_right(MARGIN_R, y, value, 9, "F", role); y += 12
    c.hline(172)


def draw_parties(c: Canvas, inv: Invoice) -> None:
    c.text(MARGIN_L, 190, "Rechnungsempfänger", 8, "FB")
    c.text(320, 190, "Lieferanschrift", 8, "FB")
    y = 204
    for party, x, role in ((inv.customer, MARGIN_L, "bill_to"), (inv.ship_to, 320, "ship_to")):
        yy = y
        c.text(x, yy, party.name, 9, "FB", f"{role}_name"); yy += 12
        for line in party.lines:
            c.text(x, yy, line, 9); yy += 12
    c.text(MARGIN_L, 264, f"USt-IdNr. des Kunden: {inv.customer.vat_id}", 9, role="customer_vat_line")
    c.y = 290


def draw_table_header(c: Canvas) -> None:
    y = c.y
    c.hline(y - 10, width=0.8)
    for label, key, right in (("Pos.", "pos", False), ("Artikel-Nr.", "part", False), ("Beschreibung", "desc", False),
                              ("Menge", "qty_r", True), ("Einzelpreis", "price_r", True), ("USt %", "vat_r", True),
                              ("Betrag EUR", "amount_r", True)):
        (c.text_right if right else c.text)(COLS[key], y, label, 8, "FB")
    c.hline(y + 4, width=0.8)
    c.y = y + 18


def wrap(c: Canvas, s: str, max_w: float, size: float) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if c.width(trial, size) <= max_w:
            cur = trial
        else:
            lines.append(cur); cur = w
    return lines + [cur]


def draw_row(c: Canvas, it: LineItem) -> None:
    desc_lines = wrap(c, it.description, COLS["qty_r"] - 40 - COLS["desc"], 9)
    y = c.y
    c.text(COLS["pos"], y, str(it.pos), 9)
    c.text(COLS["part"], y, it.part_number, 9, role=f"item{it.pos}_part")
    for i, line in enumerate(desc_lines):
        c.text(COLS["desc"], y + 11 * i, line, 9, role=f"item{it.pos}_desc{i}")
    c.text_right(COLS["qty_r"], y, qty(it.quantity), 9, role=f"item{it.pos}_qty")
    c.text_right(COLS["price_r"], y, money(it.unit_price), 9, role=f"item{it.pos}_price")
    c.text_right(COLS["vat_r"], y, f"{int(it.vat_rate)}", 9)
    c.text_right(COLS["amount_r"], y, money(it.net_amount), 9, role=f"item{it.pos}_net")
    c.y = y + 11 * len(desc_lines) + 6


def draw_carry(c: Canvas, carried: Decimal, incoming: bool) -> None:
    label = "Übertrag von Vorseite" if incoming else "Zwischensumme / Übertrag"
    c.hline(c.y - 9)
    c.text(COLS["desc"], c.y, label, 9, "FB")
    c.text_right(COLS["amount_r"], c.y, money(carried), 9, "FB", "carry_in" if incoming else "carry_out")
    c.y += 18


def draw_totals(c: Canvas, inv: Invoice) -> None:
    y = c.y + 6
    c.text(MARGIN_L, y, "Umsatzsteuer", 8, "FB"); y += 12
    for label, key, right in (("Satz", 50, False), ("Netto", 200, True), ("USt", 280, True)):
        (c.text_right if right else c.text)(key, y, label, 8, "FB")
    y += 12
    for rate, (base, vat) in inv.vat_lines.items():
        c.text(50, y, f"{int(rate)} %", 9, role=f"vat_rate_{int(rate)}")
        c.text_right(200, y, money(base), 9, role=f"vat_base_{int(rate)}")
        c.text_right(280, y, money(vat), 9, role=f"vat_amount_{int(rate)}"); y += 12
    # totals block, right
    ty = c.y + 6
    rows = [("Nettosumme", inv.subtotal, "subtotal")]
    rows += [(ch.label, ch.amount, "shipping") for ch in inv.charges]
    rows += [("Umsatzsteuer gesamt", inv.vat_total, "vat_amount"), ("Rechnungsbetrag", inv.total, "total_amount")]
    for label, value, role in rows:
        bold = "FB" if role == "total_amount" else "F"
        if role == "total_amount":
            c.hline(ty - 10, 340, MARGIN_R)
        c.text(340, ty, f"{label}:", 9, bold)
        c.text_right(MARGIN_R, ty, f"{money(value)} EUR", 9, bold, role); ty += 13
    usd = (inv.total * inv.exchange_rate).quantize(CENT, ROUND_HALF_UP)
    c.text(340, ty + 4, f"Gegenwert: {money(usd)} USD (Kurs 1 EUR = {inv.exchange_rate} USD)", 8, role="secondary_echo")
    c.y = max(y, ty + 30)


def draw_footer(c: Canvas, inv: Invoice) -> None:
    c.hline(MARGIN_BOTTOM - 40, width=0.4)
    lines = [
        f"Zahlbar bis {dmy(inv.due_date)} ohne Abzug. Bankverbindung: Hansebank Duisburg · IBAN {inv.iban} · BIC {inv.bic}",
        "Rheinwerk Industriebedarf GmbH · Amtsgericht Duisburg HRB 21877 · Geschäftsführer: Dr. Anke Voss · Steuernummer 134/5804/0912",
        "Es gelten unsere Allgemeinen Geschäftsbedingungen. Die Ware bleibt bis zur vollständigen Bezahlung unser Eigentum.",
    ]
    y = MARGIN_BOTTOM - 28
    for i, line in enumerate(lines):
        c.text(MARGIN_L, y, line, 7, role="iban_line" if i == 0 else ""); y += 10


def render(inv: Invoice, fonts: dict[str, Path], pdf_path: Path) -> list[Canvas]:
    doc = fitz.open()
    pages: list[Canvas] = []
    rows_first, rows_next = 8, 12  # deliberately low so the example breaks across pages
    chunks = [inv.items[:rows_first]] + [inv.items[i:i + rows_next] for i in range(rows_first, len(inv.items), rows_next)]
    total_pages = len(chunks)
    carried = Decimal(0)
    for idx, chunk in enumerate(chunks):
        c = Canvas(doc, fonts, idx + 1, [total_pages])
        draw_header(c, inv, total_pages)
        if idx == 0:
            draw_parties(c, inv)
        else:
            c.y = 200
        draw_table_header(c)
        if idx > 0:
            draw_carry(c, carried, incoming=True)
        for it in chunk:
            draw_row(c, it)
        carried += sum((it.net_amount for it in chunk), Decimal(0))
        if idx < total_pages - 1:
            draw_carry(c, carried, incoming=False)
        else:
            c.hline(c.y - 9, width=0.8)
            draw_totals(c, inv)
        draw_footer(c, inv)
        pages.append(c)
    doc.set_metadata({"producer": "invoice_forge prototype", "creator": "forge_prototype.py",
                      "title": inv.number, "creationDate": "D:20240101000000Z", "modDate": "D:20240101000000Z"})
    doc.save(str(pdf_path), garbage=4, deflate=True, no_new_id=True)
    doc.close()
    return pages


# ── ground truth, read back from the PDF ────────────────────────────────────


def ground_truth(inv: Invoice, pages: list[Canvas], pdf_path: Path) -> dict:
    doc = fitz.open(str(pdf_path))
    located: dict[str, dict] = {}
    missing: list[str] = []
    for c in pages:
        page = doc[c.page_no - 1]
        for role, text in c.drawn:
            hits = page.search_for(text)
            if not hits:
                missing.append(f"{role}:{text}"); continue
            r = hits[0]
            located[role] = {"page": c.page_no, "text": text,
                             "bbox": [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]}
    doc.close()
    fields = {
        "invoice_number": inv.number, "invoice_date": inv.invoice_date.isoformat(),
        "supply_date": inv.supply_date.isoformat(), "due_date": inv.due_date.isoformat(),
        "customer_number": inv.customer_number, "order_number": inv.order_number,
        "supplier_vat_id": inv.supplier.vat_id, "customer_vat_id": inv.customer.vat_id,
        "currency": inv.currency, "secondary_currency": inv.secondary_currency,
        "exchange_rate": str(inv.exchange_rate), "subtotal": str(inv.subtotal),
        "charges": [{"type": "SHIPPING", "label": ch.label, "amount": str(ch.amount), "declared": True} for ch in inv.charges],
        "vat_summary": [{"rate": str(r), "base": str(b), "vat": str(v)} for r, (b, v) in inv.vat_lines.items()],
        "vat_amount": str(inv.vat_total), "total_amount": str(inv.total), "iban": inv.iban,
        "document_type": "invoice", "pages": len(pages),
    }
    items = [{"pos": it.pos, "part_number": it.part_number, "description": it.description,
              "quantity": str(it.quantity), "unit_price": str(it.unit_price), "vat_rate": str(it.vat_rate),
              "net_amount": str(it.net_amount)} for it in inv.items]
    return {"schema": "forge-ground-truth/0-prototype", "profile": "de-classic", "seed": 7,
            "fields": fields, "line_items": items, "evidence": located, "unlocated": missing}


def main() -> None:
    fonts = {}
    for kind, candidates in FONT_CANDIDATES.items():
        fonts[kind] = next(p for p in candidates if p and p.exists())
    OUT.mkdir(exist_ok=True)
    inv = sample_invoice(seed=7)
    pdf_path = OUT / "de_classic_example.pdf"
    pages = render(inv, fonts, pdf_path)
    truth = ground_truth(inv, pages, pdf_path)
    (OUT / "de_classic_example.truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = fitz.open(str(pdf_path))
    for i, page in enumerate(doc, start=1):
        page.get_pixmap(dpi=110).save(str(OUT / f"de_classic_example_p{i}.png"))
    print(f"font: {fonts['regular'].name} | pages: {len(pages)} | total: {money(inv.total)} EUR | "
          f"evidence located: {len(truth['evidence'])} | unlocated: {len(truth['unlocated'])}")


if __name__ == "__main__":
    main()
