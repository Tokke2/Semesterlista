"""Shared pre-export readability confirmation."""
from PySide6.QtWidgets import QMessageBox
from core import i18n

def confirm_readability(font_sizes, months_per_page):
    """Warn once if any sheet's calendar text is below 6 points."""
    small_pages = [str(index + 1) for index, size in enumerate(font_sizes)
                   if size < 6.0 - 0.01]
    if not small_pages:
        return True
    answer = QMessageBox.question(
        None,
        i18n.t("lista.pdf.small_text.title"),
        i18n.t("lista.pdf.small_text.message",
               size=f"{min(font_sizes):.1f}", pages=", ".join(small_pages),
               months=months_per_page),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes
