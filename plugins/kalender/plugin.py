"""Standalone calendar plugin. Never reads employee, vacation or tenant files."""
from datetime import date
from pathlib import Path
from PySide6.QtCore import QDate, Qt, QLocale
from PySide6.QtGui import QColor, QTextCharFormat, QPalette
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QFormLayout, QLabel, QSpinBox, QComboBox,
    QCalendarWidget, QListWidget, QListWidgetItem, QPushButton, QFileDialog, QMessageBox,
)
from core import i18n
from core.calendar_data import year_days
from core.calendar_pdf import export_calendar
from core.holidays import get_region_from_settings, describe_region
from core.seasonal_options import edit_seasonal_options
from core.ui_layout import FlowLayout
from plugins.base_plugin import BasePlugin

PLUGIN_INFO = {"id": "kalender", "name": "Kalender", "version": "2.15.2", "author": "Rickard Längkvist"}


class CalendarView(QWidget):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self.formats = set()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel(i18n.t("calendar.title"))
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(i18n.t("calendar.description"))
        description.setWordWrap(True)
        description.setProperty("role", "muted")
        layout.addWidget(description)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.year = QSpinBox()
        self.year.setRange(2020, 2100)
        self.year.setValue(int(plugin.settings.get("year", date.today().year)))
        form.addRow(i18n.t("calendar.year"), self.year)
        self.per_page = QComboBox()
        self.per_page.addItems(["1", "2", "3"])
        self.per_page.setCurrentText(str(plugin.settings.get("months_per_page", 1)))
        form.addRow(i18n.t("calendar.per_page"), self.per_page)
        self.region_label = QLabel()
        form.addRow(i18n.t("calendar.region"), self.region_label)
        layout.addLayout(form)
        self.calendar = QCalendarWidget()
        self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.calendar.setMinimumDate(QDate(2020, 1, 1))
        self.calendar.setMaximumDate(QDate(2100, 12, 31))
        self.calendar.setGridVisible(True)
        self.calendar.setSelectedDate(QDate(self.year.value(), 1, 1))
        layout.addWidget(self.calendar)
        self.names = QLabel()
        self.names.setWordWrap(True)
        self.names.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.names)
        months_label = QLabel(i18n.t("calendar.months"))
        layout.addWidget(months_label)
        self.months = QListWidget()
        self.months.setMaximumHeight(130)
        selected = plugin.settings.get("months", list(range(1, 13)))
        for month in range(1, 13):
            item = QListWidgetItem(i18n.month_name(month), self.months)
            item.setData(Qt.ItemDataRole.UserRole, month)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if month in selected else Qt.CheckState.Unchecked)
        actions = FlowLayout()
        export = QPushButton(i18n.t("calendar.export"))
        export.setProperty("primary", True)
        export.clicked.connect(self._export)
        appearance = QPushButton(i18n.t("season.settings"))
        appearance.clicked.connect(self._appearance)
        all_months = QPushButton(i18n.t("calendar.all_months"))
        all_months.clicked.connect(self._select_all)
        layout.addWidget(self.months)
        for button in (export, appearance, all_months):
            actions.addWidget(button)
        layout.addStretch()
        layout.addLayout(actions)
        self.year.valueChanged.connect(self._year_changed)
        self.calendar.currentPageChanged.connect(self._page_changed)
        self.calendar.selectionChanged.connect(self.refresh)
        self.per_page.currentIndexChanged.connect(self._save)
        self.months.itemChanged.connect(self._save)
        QApplication.instance().paletteChanged.connect(self.refresh)
        self.translated_widgets = [(title, "calendar.title"), (description, "calendar.description"),
                                   (months_label, "calendar.months"), (export, "calendar.export"),
                                   (appearance, "season.settings"), (all_months, "calendar.all_months"),
                                   (form.labelForField(self.year), "calendar.year"),
                                   (form.labelForField(self.per_page), "calendar.per_page"),
                                   (form.labelForField(self.region_label), "calendar.region")]
        self.refresh()

    def _selected_months(self):
        return [self.months.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.months.count())
                if self.months.item(i).checkState() == Qt.CheckState.Checked]

    def _save(self, *_):
        self.plugin.settings.update(year=self.year.value(), months=self._selected_months(),
                                    months_per_page=int(self.per_page.currentText()))
        self.plugin.save_settings(self.plugin.settings)

    def _year_changed(self, year):
        self.calendar.setSelectedDate(QDate(year, self.calendar.monthShown(), 1))
        self.refresh()
        self._save()

    def _page_changed(self, year, month):
        self.year.blockSignals(True)
        self.year.setValue(year)
        self.year.blockSignals(False)
        self.refresh()
        self._save()

    def refresh(self, *_):
        for widget, key in getattr(self, "translated_widgets", []):
            widget.setText(i18n.t(key))
        region = get_region_from_settings(self.plugin._settings_manager)
        self.calendar.setLocale(QLocale(i18n.current_language()))
        header_format = QTextCharFormat()
        header_format.setForeground(self.palette().color(QPalette.ColorRole.Text))
        for weekday in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.calendar.setWeekdayTextFormat(weekday, header_format)
        self.months.blockSignals(True)
        for index in range(self.months.count()):
            self.months.item(index).setText(i18n.month_name(index + 1))
        self.months.blockSignals(False)
        self.region_label.setText(describe_region(region))
        for day in self.formats:
            self.calendar.setDateTextFormat(day, QTextCharFormat())
        self.formats.clear()
        days = year_days(self.year.value(), region)
        names = []
        for day, info in days.items():
            if day.month != self.calendar.monthShown():
                continue
            bg = {"holiday": "#FFE1E1", "sunday": "#FFE1E1", "saturday": "#E4EEF9", "halfday": "#E4F0D7"}.get(info.kind)
            if bg:
                fmt = QTextCharFormat()
                fmt.setBackground(QColor(bg))
                fmt.setForeground(QColor("#111111"))
                if info.holiday_key:
                    fmt.setToolTip(i18n.holiday_name(info.holiday_key))
                qdate = QDate(day.year, day.month, day.day)
                self.calendar.setDateTextFormat(qdate, fmt)
                self.formats.add(qdate)
            if info.holiday_key:
                names.append(f"{day.day}: {i18n.holiday_name(info.holiday_key)}")
        self.names.setText(" · ".join(names) if names else i18n.t("calendar.no_holidays"))

    def _select_all(self):
        for index in range(self.months.count()):
            self.months.item(index).setCheckState(Qt.CheckState.Checked)

    def _appearance(self):
        if edit_seasonal_options(self.plugin.settings, self):
            self._save()

    def _export(self):
        months = self._selected_months()
        if not months:
            QMessageBox.information(self, i18n.t("calendar.title"), i18n.t("calendar.select_months"))
            return
        filename, _ = QFileDialog.getSaveFileName(self, i18n.t("calendar.export"),
                str(Path.home() / f"kalender_{self.year.value()}.pdf"), "PDF (*.pdf)")
        if not filename:
            return
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        try:
            if export_calendar(filename, self.year.value(), months, int(self.per_page.currentText()),
                               get_region_from_settings(self.plugin._settings_manager), self.plugin.settings):
                QMessageBox.information(self, i18n.t("calendar.title"), i18n.t("calendar.saved", path=filename))
        except Exception as exc:
            QMessageBox.warning(self, i18n.t("calendar.title"), str(exc))


class Plugin(BasePlugin):
    NAME = "Kalender"
    VERSION: str = "2.15.2"
    AUTHOR = "Rickard Längkvist"
    TAB_ORDER = 0

    def __init__(self, event_bus, settings_manager):
        super().__init__(event_bus, settings_manager)
        self.settings = {"seasonal_pdf": True, **self.get_settings()}
        self.view = None
        self.subscribe("settings:changed", self._refresh)
        self.subscribe("language:changed", self._refresh)

    def _refresh(self, *_):
        if self.view is not None:
            self.view.refresh()

    def get_name(self):
        return self.NAME

    def get_version(self):
        return self.VERSION

    def get_tab_widget(self):
        if self.view is None:
            self.view = CalendarView(self)
        return self.view
