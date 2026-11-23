"""Validate complete export periods before writing any PDF."""
from calendar import monthrange, isleap
from datetime import date


def validate_period(months):
    months = list(months)
    if not months or len(months) > 12 or len(set(months)) != len(months):
        raise ValueError('Expected 1–12 distinct months')
    if months != sorted(months):
        raise ValueError('Months must be chronological')
    for year, month in months:
        date(year, month, 1)
    first_year, first_month = months[0]
    last_year, last_month = months[-1]
    return (date(first_year, first_month, 1),
            date(last_year, last_month, monthrange(last_year, last_month)[1]),
            [year for year, month in months if month == 2 and isleap(year)])


def confirm_period(months, parent=None):
    from PySide6.QtWidgets import QMessageBox
    from core import i18n
    first, last, leap_years = validate_period(months)
    text = i18n.t("export.period", first=first.isoformat(), last=last.isoformat(),
                  count=len(months), leap=', '.join(map(str, leap_years)) or '—')
    return QMessageBox.question(parent, i18n.t("export.check"), text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes
