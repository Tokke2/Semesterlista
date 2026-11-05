"""Semesterperioder med exakta kalenderdatum och årsöversikt."""
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCalendarWidget, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QScrollArea, QWidget, QLayout,
)
from core import i18n
from core.leave import LeaveError, parse_leave, split_entry, vacation_workdays
from core.roster import RosterFile, RosterError


class VacationDialog(QDialog):
    def __init__(self, path, year, region="sv", parent=None):
        super().__init__(parent)
        self.roster = RosterFile.load(path)
        self.original = self.roster.path.read_bytes()
        self.region = region
        self.setWindowTitle(i18n.t("vacation.title"))
        self.resize(760, 680)
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        area = self.screen().availableGeometry()
        self.resize(min(780, area.width() - 48), min(760, area.height() - 80))
        self.year = QSpinBox()
        self.year.setRange(1900, 2200)
        self.year.setValue(year)
        layout.addWidget(QLabel(i18n.t("vacation.year")))
        layout.addWidget(self.year)
        self.table = QTableWidget(len(self.roster.section()), 2)
        self.table.setHorizontalHeaderLabels([i18n.t("vacation.person"), i18n.t("vacation.total")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.periods = QListWidget()
        layout.addWidget(self.periods)
        dates = QHBoxLayout()
        self.start = QCalendarWidget()
        self.end = QCalendarWidget()
        for calendar, label in [(self.start, "vacation.start"), (self.end, "vacation.end")]:
            column = QVBoxLayout()
            column.addWidget(QLabel(i18n.t(label)))
            calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
            calendar.setSelectedDate(QDate(year, 1, 1))
            column.addWidget(calendar)
            dates.addLayout(column)
        layout.addLayout(dates)
        buttons = QHBoxLayout()
        add = QPushButton(i18n.t("vacation.add"))
        add.clicked.connect(self._add)
        remove = QPushButton(i18n.t("vacation.remove"))
        remove.clicked.connect(self._remove)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout.addLayout(buttons)
        note = QLabel(i18n.t("vacation.note"))
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(self._save)
        actions.rejected.connect(self.reject)
        outer.addWidget(actions)
        self.table.currentCellChanged.connect(self._select)
        self.year.valueChanged.connect(self._change_year)
        self._refresh()
        if self.table.rowCount():
            self.table.setCurrentCell(0, 0)

    def _change_year(self, year):
        for calendar in (self.start, self.end):
            calendar.setSelectedDate(QDate(year, 1, 1))
        self._refresh()

    def _ranges(self, row):
        return parse_leave(split_entry(self.roster.section()[row])[1], self.year.value())

    def _refresh(self, *_):
        for row, entry in enumerate(self.roster.section()):
            name, _ = split_entry(entry)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            try:
                total = str(vacation_workdays(self._ranges(row), self.year.value(), self.region))
            except LeaveError:
                total = "?"
            self.table.setItem(row, 1, QTableWidgetItem(total))
        self._select()

    def _select(self, *_):
        self.periods.clear()
        row = self.table.currentRow()
        if row < 0:
            return
        try:
            self.periods.addItems([str(period) for period in self._ranges(row)])
        except LeaveError as exc:
            self.periods.addItem(str(exc))

    def _store(self, row, ranges):
        name, _ = split_entry(self.roster.section()[row])
        # '=' records exact calendar choices without legacy whole-week snapping.
        text = ", ".join(f"={period.start.isoformat()} - {period.end.isoformat()}" for period in ranges)
        self.roster.section()[row] = name + (" ; " + text if text else "")
        self._refresh()

    def _add(self):
        from core.leave import LeaveRange
        row = self.table.currentRow()
        if row < 0:
            return
        try:
            first = self.start.selectedDate().toPython()
            last = self.end.selectedDate().toPython()
            if last < first:
                raise LeaveError(i18n.t("vacation.invalid_dates"))
            ranges = self._ranges(row)
            period = LeaveRange(first, last)
            if period not in ranges:
                ranges.append(period)
            self._store(row, sorted(ranges))
        except LeaveError as exc:
            QMessageBox.warning(self, i18n.t("vacation.title"), str(exc))

    def _remove(self):
        row, selected = self.table.currentRow(), self.periods.currentRow()
        if row < 0 or selected < 0:
            return
        try:
            ranges = self._ranges(row)
            del ranges[selected]
            self._store(row, ranges)
        except (LeaveError, IndexError) as exc:
            QMessageBox.warning(self, i18n.t("vacation.title"), str(exc))

    def _save(self):
        try:
            if self.roster.path.read_bytes() != self.original:
                raise RosterError(i18n.t("vacation.changed"))
            self.roster.save()
        except (OSError, RosterError) as exc:
            QMessageBox.warning(self, i18n.t("vacation.title"), str(exc))
            return
        self.accept()
