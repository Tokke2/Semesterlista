"""Exact vacation selection, annual totals and persistence."""
from datetime import date
from pathlib import Path
import tempfile
import unittest
from core.leave import LeaveRange, LeaveCalendar, parse_leave, vacation_workdays
from core.roster import RosterFile


class VacationCalculationTests(unittest.TestCase):
    def test_exact_range_does_not_snap(self):
        days = parse_leave("=2026-07-07 - 2026-07-09")
        self.assertEqual(days, [LeaveRange(date(2026, 7, 7), date(2026, 7, 9))])
        self.assertEqual(vacation_workdays(days, 2026), 3)
        calendar = LeaveCalendar.from_lines(["Anna ; =2026-07-07 - 2026-07-09"])
        self.assertFalse(calendar.is_off("Anna", date(2026, 7, 6)))
        self.assertTrue(calendar.is_off("Anna", date(2026, 7, 7)))
        self.assertFalse(calendar.is_off("Anna", date(2026, 7, 10)))

    def test_legacy_ranges_still_snap(self):
        self.assertNotEqual(parse_leave("2026-07-07 - 2026-07-09")[0].start, date(2026, 7, 7))

    def test_overlaps_count_once_and_exclude_weekends(self):
        periods = parse_leave("=2026-07-06 - 2026-07-12, =2026-07-08 - 2026-07-10")
        self.assertEqual(vacation_workdays(periods, 2026), 5)

    def test_region_and_half_days(self):
        periods = [LeaveRange(date(2026, 7, 3), date(2026, 7, 3))]
        self.assertEqual(vacation_workdays(periods, 2026, "sv"), 1)
        self.assertEqual(vacation_workdays(periods, 2026, "us"), 0)
        self.assertEqual(vacation_workdays(parse_leave("=2026-12-24"), 2026, "sv"), 1)

    def test_year_boundary(self):
        periods = parse_leave("=2026-12-31 - 2027-01-04")
        self.assertEqual(vacation_workdays(periods, 2026), 1)
        self.assertEqual(vacation_workdays(periods, 2027), 1)

    def test_multiple_periods_save_beyond_name_length_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "employees.txt"
            path.write_text("Anna\n", encoding="utf-8")
            roster = RosterFile.load(path)
            text = "Anna ; " + ", ".join(f"=2026-{month:02}-01 - 2026-{month:02}-02" for month in range(1, 10))
            roster.section()[0] = text
            roster.save()
            self.assertEqual(RosterFile.load(path).section()[0], text)


try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QDate, Qt
    from core.vacation_dialog import VacationDialog
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "Qt missing")
class VacationDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "employees.txt"
        self.path.write_text("Anna\nBertil\n", encoding="utf-8")
        self.dialog = VacationDialog(self.path, 2026)
        self.addCleanup(self.dialog.deleteLater)

    def test_calendar_monday_and_exact_save(self):
        dialog = self.dialog
        self.assertEqual(dialog.start.firstDayOfWeek(), Qt.DayOfWeek.Monday)
        self.assertEqual(dialog.end.firstDayOfWeek(), Qt.DayOfWeek.Monday)
        dialog.start.setSelectedDate(QDate(2026, 7, 7))
        dialog.end.setSelectedDate(QDate(2026, 7, 9))
        dialog._add()
        self.assertEqual(dialog.table.item(0, 1).text(), "3")
        dialog._save()
        self.assertIn("=2026-07-07 - 2026-07-09", self.path.read_text())
        self.assertIn("Bertil", self.path.read_text())

    def test_cancel_leaves_original_unchanged(self):
        original = self.path.read_bytes()
        self.dialog._add()
        self.dialog.reject()
        self.assertEqual(self.path.read_bytes(), original)

    def test_external_changes_not_overwritten(self):
        from unittest.mock import patch
        self.path.write_text("Changed\n")
        with patch.object(QMessageBox, "warning") as warning:
            self.dialog._save()
            warning.assert_called_once()
        self.assertEqual(self.path.read_text(), "Changed\n")
