"""A separate, readable driver sheet; leaves monthly vehicle schedules unchanged."""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from core import i18n
from core.pdf_export import get_export_folder, save_document, open_pdf

FIELDS = ("vehicle", "driver", "time", "pickup", "destination", "notes")


def export_driver_sheet(day, values):
    target = Path(get_export_folder("Fordon")) / f"korblad_{day.isoformat()}.pdf"
    doc = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=36, leftMargin=36,
                            topMargin=36, bottomMargin=40, title=i18n.t("driver.title"))
    heading = ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=22, leading=27,
                             textColor=colors.HexColor("#143958"), spaceAfter=14)
    label = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=12, leading=16,
                           spaceBefore=14, spaceAfter=5)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=16, leading=22,
                          splitLongWords=True)
    elements = [Paragraph(escape(i18n.t("driver.title")), heading),
                Paragraph(day.isoformat(), body)]
    for key in FIELDS:
        elements.append(Paragraph(escape(i18n.t(f"driver.{key}")), label))
        text = str(values.get(key, "")).strip()
        if text:
            # Plain text only; no user HTML, no truncated addresses or notes.
            elements.append(Paragraph(escape(text).replace("\n", "<br/>"), body))
        else:
            elements.append(Spacer(1, 40 if key == "notes" else 24))
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(A4[0] - 36, 22, str(document.page))
        canvas.restoreState()
    return save_document(doc, elements, target, onFirstPage=footer, onLaterPages=footer)


def show_driver_sheet(parent, vehicles):
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox,
        QFormLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QVBoxLayout)
    dialog = QDialog(parent)
    dialog.setWindowTitle(i18n.t("driver.title"))
    dialog.resize(580, 640)
    layout = QVBoxLayout(dialog)
    hint = QLabel(i18n.t("driver.hint"))
    hint.setWordWrap(True)
    layout.addWidget(hint)
    form = QFormLayout()
    day = QDateEdit(QDate.currentDate())
    day.setCalendarPopup(True)
    day.setDisplayFormat("yyyy-MM-dd")
    form.addRow(i18n.t("driver.date"), day)
    widgets = {}
    for key in FIELDS:
        if key == "vehicle":
            widget = QComboBox()
            widget.addItems(vehicles)
            widget.setEditable(True)
            widget.lineEdit().setMaxLength(160)
        elif key == "notes":
            widget = QPlainTextEdit()
        else:
            widget = QLineEdit()
            widget.setMaxLength(1000)
        widgets[key] = widget
        form.addRow(i18n.t(f"driver.{key}"), widget)
    layout.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
    buttons.button(QDialogButtonBox.StandardButton.Save).setText(i18n.t("driver.export"))
    def export():
        values = {key: (widget.toPlainText() if key == "notes" else
                       widget.currentText() if key == "vehicle" else widget.text())
                  for key, widget in widgets.items()}
        try:
            path = export_driver_sheet(day.date().toPython(), values)
        except Exception as exc:
            QMessageBox.warning(dialog, i18n.t("driver.title"), str(exc))
            return
        open_pdf(path, dialog)
    buttons.accepted.connect(export)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
