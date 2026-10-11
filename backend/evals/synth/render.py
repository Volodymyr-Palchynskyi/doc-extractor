"""Render a SyntheticInvoice to PDF with reportlab. Three layouts, so an extractor cannot rely on positions."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from evals.synth.formats import format_date, format_money, format_number, format_quantity
from evals.synth.generate import SyntheticInvoice

FONTS = {  # layout -> (regular, bold); all are standard PDF fonts with Latin-1 + Euro
    "classic": ("Helvetica", "Helvetica-Bold"),
    "modern": ("Times-Roman", "Times-Bold"),
    "minimal": ("Courier", "Courier-Bold"),
}
ACCENT = {"classic": colors.HexColor("#2b2b2b"), "modern": colors.HexColor("#1f4e79"), "minimal": colors.black}


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


class _NumberedCanvas(canvas.Canvas):
    """Two-pass canvas so every page can say 'Page x of y'."""

    page_label = "Page"
    of_label = "of"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages: list[dict] = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.grey)
            self.drawRightString(A4[0] - 15 * mm, 10 * mm, f"{self.page_label} {self._pageNumber} {self.of_label} {total}")
            super().showPage()
        super().save()


def render_pdf(inv: SyntheticInvoice) -> bytes:
    loc, t, d = inv.loc, inv.truth, inv.distractors
    regular, bold = FONTS[inv.layout]
    accent = ACCENT[inv.layout]

    base = ParagraphStyle("base", fontName=regular, fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=base, fontSize=7.5, leading=10, textColor=colors.HexColor("#555555"))
    strong = ParagraphStyle("strong", parent=base, fontName=bold)
    right = ParagraphStyle("right", parent=base, alignment=TA_RIGHT)
    right_strong = ParagraphStyle("right_strong", parent=right, fontName=bold)
    title = ParagraphStyle("title", parent=base, fontName=bold, fontSize=22 if inv.layout != "minimal" else 14, leading=26, textColor=accent)

    def money(value: float) -> str:
        return format_money(value, t.currency, loc, inv.money_style)

    def date_text(value) -> str:
        return format_date(value, inv.date_format)

    def party_block(label_key: str, party) -> list:
        lines = [_p(loc.labels[label_key], ParagraphStyle("lbl", parent=small, fontName=bold)), _p(party.name, strong)]
        if party.address:
            lines.append(_p(party.address, base))
        if party.tax_id:
            printed = f"{loc.tax_id_label} {party.tax_id}" if loc.tax_id_label else party.tax_id
            lines.append(_p(printed, small))
        return lines

    story: list = []

    # --- header
    if inv.layout == "modern":
        header = Table(
            [[Paragraph(f'<font color="white">{escape(loc.labels["invoice"])}</font>', ParagraphStyle("h", parent=title, textColor=colors.white)),
              Paragraph(f'<font color="white">{escape(loc.labels["invoice_number"])}<br/><b>{escape(t.invoice_number)}</b></font>',
                        ParagraphStyle("hr", parent=right, textColor=colors.white))]],
            colWidths=[100 * mm, 80 * mm],
        )
        header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                    ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        story += [header, Spacer(1, 6 * mm)]
    elif inv.layout == "classic":
        story += [_p(loc.labels["invoice"], title), Spacer(1, 3 * mm)]
    else:
        story += [_p(loc.labels["invoice"], title), Spacer(1, 2 * mm)]

    # --- parties
    parties = Table([[party_block("from", t.vendor), party_block("bill_to", t.buyer)]], colWidths=[90 * mm, 90 * mm])
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [parties, Spacer(1, 5 * mm)]

    # --- meta (number, dates and the distractor identifiers that look like numbers)
    meta_rows = []
    if inv.layout != "modern":  # modern prints the number in its header band
        meta_rows.append([loc.labels["invoice_number"], t.invoice_number])
    meta_rows.append([loc.labels["issue_date"], date_text(t.issue_date)])
    if t.due_date:
        meta_rows.append([loc.labels["due_date"], date_text(t.due_date)])
    if d.po_number:
        meta_rows.append([loc.labels["po_number"], d.po_number])
    if d.customer_number:
        meta_rows.append([loc.labels["customer_number"], d.customer_number])
    meta = Table([[_p(k, small), _p(v, strong if k == loc.labels["invoice_number"] else base)] for k, v in meta_rows],
                 colWidths=[45 * mm, 60 * mm], hAlign="LEFT")
    meta.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    story += [meta, Spacer(1, 4 * mm)]

    if d.replaces:
        story += [_p(f"{loc.labels['replaces']} {d.replaces}.", small), Spacer(1, 3 * mm)]

    # --- line items (long invoices flow onto more pages and repeat the header row)
    head = [loc.labels[k] for k in ("description", "quantity", "unit_price", "amount")]
    rows = [[_p(h, ParagraphStyle("th", parent=strong if i == 0 else right_strong)) for i, h in enumerate(head)]]
    for item in t.line_items:
        rows.append([
            _p(item.description, base),
            _p(format_quantity(item.quantity, loc), right),
            _p(money(item.unit_price), right),
            _p(money(item.line_total), right),
        ])
    items = Table(rows, colWidths=[82 * mm, 20 * mm, 38 * mm, 40 * mm], repeatRows=1)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP")]
    if inv.layout == "classic":
        style += [("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6"))]
    elif inv.layout == "modern":
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce6f1")),
                  ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")])]
    else:
        style += [("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black)]
    items.setStyle(TableStyle(style))
    story += [items, Spacer(1, 4 * mm)]

    # --- totals
    tax_rate_text = format_number(inv.tax_rate, loc, decimals=2).rstrip("0").rstrip(loc.decimal)
    totals = [[_p(loc.labels["subtotal"], right), _p(money(t.subtotal), right)]]
    if t.discount_total:
        discount_rate = format_number(inv.discount_rate, loc, decimals=1).rstrip("0").rstrip(loc.decimal)
        totals.append([_p(f"{loc.labels['discount']} {discount_rate}%", right), _p("-" + money(t.discount_total), right)])
    totals.append([_p(f"{loc.labels['tax']} {tax_rate_text}%", right), _p(money(t.tax_total), right)])
    totals.append([_p(inv.total_label, right_strong), _p(money(t.total), right_strong)])
    totals_table = Table(totals, colWidths=[100 * mm, 40 * mm], hAlign="RIGHT")
    total_style = [("LINEABOVE", (0, -1), (-1, -1), 0.8, accent)]
    if inv.layout == "modern":
        total_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dce6f1")))
    totals_table.setStyle(TableStyle(total_style))
    story += [totals_table, Spacer(1, 8 * mm)]

    # --- footer material
    if d.iban:
        bank = f"{loc.labels['bank']}: IBAN {d.iban}" + (f"  BIC {d.bic}" if d.bic else "")
        story.append(_p(bank, small))
        story.append(Spacer(1, 2 * mm))
    if d.long_terms:
        story.append(_p(f"{loc.labels['terms']}: {loc.labels['terms_text']}", small))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"{t.invoice_number}", author=t.vendor.name, invariant=1,  # invariant: byte-identical reruns
    )
    canvas_class = type("Canvas", (_NumberedCanvas,), {"page_label": loc.labels["page"], "of_label": loc.labels["of"]})
    doc.build(story, canvasmaker=canvas_class)
    return buffer.getvalue()
