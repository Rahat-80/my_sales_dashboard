import io
from datetime import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

TITLE = "Sales Report - DHAKA-1 (BSMMU) - HORMON"


def bd_number(value, decimals):
    """সংখ্যাকে PDF-এর মতো ভাগে সাজানো: 415792.8 -> 4,15,792.80"""
    if value is None or pd.isna(value):
        return ""
    s = f"{abs(value):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    sign = "-" if value < 0 else ""
    return sign + whole + ("." + frac if frac else "")


def english(name):
    """PDF-এ বাংলা অক্ষর আসে না, তাই শিরোনাম ইংরেজিতে"""
    return name.replace("(পরিমাণ)", "(Qty)").replace("(টাকা)", "(Value)")


def build_table(df, decimals_for, extra_codes):
    headers = [english(c) for c in df.columns]
    data = [headers]
    first_extra = None
    for i, row in df.iterrows():
        cells = [str(row.iloc[0]), str(row.iloc[1])]
        for col in df.columns[2:]:
            cells.append(bd_number(row[col], decimals_for(english(col))))
        data.append(cells)
        if first_extra is None and str(row.iloc[0]) in extra_codes:
            first_extra = len(data) - 1

    widths = [18 * mm, 58 * mm] + [28 * mm] * (len(df.columns) - 2)
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BBBBBB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F2F5F9")]),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 8),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#DDE5EE")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if first_extra is not None:
        style.append(("LINEABOVE", (0, first_extra), (-1, first_extra), 1.2, colors.black))
    t.setStyle(TableStyle(style))
    return t


def make_pdf(selected, qty_table, val_table, daily_table, prev_date, extra_codes, daily_note=None):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
        title=f"Sales Report {selected}",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(TITLE, styles["Title"]),
        Paragraph(f"Report date: <b>{selected}</b> &nbsp;&nbsp; (figures are month-to-date totals) "
                  f"&nbsp;&nbsp; Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
        Spacer(1, 6 * mm),
    ]

    if daily_table is not None:
        if daily_table is None and daily_note:
            story.append(Paragraph(f"<b>Daily sales:</b> {daily_note}", styles["Normal"]))
            story.append(Spacer(1, 6 * mm))
            story.append(KeepTogether([
                Paragraph(f"Daily sales ({prev_date} to {selected})", styles["Heading3"]),
                build_table(daily_table, lambda c: 0 if "Qty" in c else 2, extra_codes),
                Spacer(1, 6 * mm),
        ]))
    story.append(KeepTogether([
        Paragraph("Cumulative - Quantity", styles["Heading3"]),
        build_table(qty_table, lambda c: 0, extra_codes),
        Spacer(1, 6 * mm),
    ]))
    story.append(KeepTogether([
        Paragraph("Cumulative - Value", styles["Heading3"]),
        build_table(val_table, lambda c: 2, extra_codes),
    ]))

    def footer(canvas, doc_):
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 8 * mm, f"Page {doc_.page}")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()