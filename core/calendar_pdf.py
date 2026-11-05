"""Standalone calendar PDF: Monday-first, regional holidays, no vacation data."""
from io import BytesIO
from pathlib import Path
import tempfile
import os
from math import ceil
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepInFrame
from core import i18n
from core.calendar_data import month_weeks, day_labels, calendar_background
from core.pdf_readability import confirm_readability
from core.seasonal_pdf import seasonal_header, print_canvas


def export_calendar(path, year, months, per_page, region, settings):
    months = sorted(set(months))
    if not months or any(month not in range(1, 13) for month in months) or per_page not in (1, 2, 3):
        raise ValueError(i18n.t("calendar.select_months"))
    pagesize = landscape(A4)
    width = pagesize[0] - 24 * mm - 12
    height = pagesize[1] - 28 * mm - 20
    title = ParagraphStyle("month", fontSize=12 if per_page == 3 else 15,
                           leading=14 if per_page == 3 else 18,
                           spaceAfter=3 if per_page == 3 else 5, alignment=1)
    cell = ParagraphStyle("day", fontSize=14 if per_page == 1 else 8,
                          leading=16 if per_page == 1 else 8)
    small = ParagraphStyle("name", fontSize=7, leading=8)
    story, sizes = [], []
    measuring = Canvas(BytesIO(), pagesize=pagesize)
    for offset in range(0, len(months), per_page):
        content = []
        note_height = 0
        if region in ("sv", "us"):
            note_key = "calendar.observance_note_sv" if region == "sv" else "calendar.observance_note"
            note = Paragraph(escape(i18n.t(note_key)), small)
            note_height = note.wrapOn(measuring, width, height)[1] + 4
            content.extend([note, Spacer(1, 4)])
        page_months = months[offset:offset + per_page]
        gap = 8
        slot_height = (height - note_height - gap * (len(page_months) - 1)) / len(page_months)
        for index, month in enumerate(page_months):
            header = seasonal_header(month, settings, width)
            header.append(Paragraph(f"{escape(i18n.month_name(month))} {year}", title))
            # Only actual header content consumes space: no empty image slot.
            header_height = sum(flow.wrapOn(measuring, width, height)[1]
                                + flow.getSpaceBefore() + flow.getSpaceAfter()
                                for flow in header)
            content.extend(header)
            data = [[i18n.t("calendar.week")] + list(i18n.weekday_short_names())]
            commands = [("GRID", (0, 0), (-1, -1), .35, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                        ("FONTSIZE", (0, 0), (-1, -1), 8)]
            for row, week in enumerate(month_weeks(year, month, region), 1):
                first = next(day for day in week if day is not None)
                cells = [str(first.date.isocalendar().week)]
                for column, day in enumerate(week, 1):
                    if day is None:
                        cells.append("")
                        continue
                    parts = [Paragraph(str(day.date.day), cell)]
                    for label in day_labels(day):
                        parts.append(Paragraph(escape(label), small))
                    cells.append(parts)
                    bg = calendar_background(day)
                    if bg:
                        commands.append(("BACKGROUND", (column, row), (column, row), colors.HexColor(bg)))
                data.append(cells)
            table = Table(data, colWidths=[32] + [(width - 32) / 7] * 7, rowHeights=[18] + [None] * (len(data) - 1))
            # Let long translated holiday names expand rows rather than clip them.
            padding = 1 if per_page == 3 else 2
            commands += [("TOPPADDING", (0, 1), (-1, -1), padding),
                         ("BOTTOMPADDING", (0, 1), (-1, -1), padding)]
            table.setStyle(TableStyle(commands))
            _, natural_height = table.wrapOn(measuring, width, height)
            extra = max(0, slot_height - header_height - natural_height)
            row_heights = [table._rowHeights[0]] + [
                row_height + extra / (len(data) - 1) for row_height in table._rowHeights[1:]]
            table = Table(data, colWidths=[32] + [(width - 32) / 7] * 7,
                          rowHeights=row_heights)
            table.setStyle(TableStyle(commands))
            content.append(table)
            if index + 1 < len(page_months):
                content.append(Spacer(1, gap))
        group = KeepInFrame(width, height, content, mode="shrink")
        group.wrapOn(measuring, width, height)
        sizes.append(7.0 / max(1.0, float(getattr(group, "_scale", 1.0))))
        story.append(group)
        if offset + per_page < len(months):
            story.append(PageBreak())
    if not confirm_readability(sizes, per_page):
        return False
    destination = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".calendar-", suffix=".pdf", dir=destination.parent)
    os.close(descriptor)
    document = SimpleDocTemplate(temporary, pagesize=pagesize, leftMargin=12 * mm, rightMargin=12 * mm,
                                 topMargin=14 * mm, bottomMargin=14 * mm)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(pagesize[0] - 12 * mm, 7 * mm,
                               i18n.t("calendar.page", page=doc.page, total=ceil(len(months) / per_page)))
        canvas.restoreState()

    try:
        document.build(story, canvasmaker=print_canvas(monochrome=settings.get("pdf_monochrome", False)),
                       onFirstPage=footer, onLaterPages=footer)
        Path(temporary).replace(destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True
