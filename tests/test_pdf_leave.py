#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för lediga dagar i PDF:en (v2.11.0).

Kontrollerar att rader som ``Anna Andersson ; 18/12 - 7/1`` läses in, att rätt
celler markeras med × och att färgförklaringen har en ruta för lediga dagar.

    python -m unittest discover -s tests -v
    python tests/test_pdf_leave.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAVE_GUI = importlib.util.find_spec("reportlab") is not None
except Exception:  # pragma: no cover – miljö utan Qt/reportlab
    HAVE_GUI = False

PLUGIN_PATH = PROJECT_ROOT / "plugins" / "lista" / "plugin.py"


def _load_plugin_module():
    """Ladda plugins/lista/plugin.py utan att gå via PluginManager."""
    name = "plugins.lista.plugin"
    if name in sys.modules:
        return sys.modules[name]

    spec = importlib.util.spec_from_file_location(name, PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAVE_GUI, "PySide6/reportlab saknas")
class LeaveInPdfTests(unittest.TestCase):
    """Lediga dagar ska synas i tabellen och i förklaringen."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.app = QApplication.instance() or QApplication([])
        except Exception as exc:  # pragma: no cover – ingen skärm
            raise unittest.SkipTest(f"Qt kunde inte startas: {exc}")

        cls.module = _load_plugin_module()
        from core.event_bus import EventBus
        from core.settings_manager import SettingsManager

        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.outdir = base / "ut"
        cls.outdir.mkdir()

        cls.settings_manager = SettingsManager(str(base / "app"))
        cls.plugin = cls.module.Plugin(EventBus(), cls.settings_manager)
        cls.plugin.settings["auto_open_pdf"] = False
        cls.generator = cls.module.PDFGenerator(cls.plugin)

        cls._orig = {
            "information": cls.module.QMessageBox.information,
            "critical": cls.module.QMessageBox.critical,
            "warning": cls.module.QMessageBox.warning,
            "open": cls.module.webbrowser.open,
            "docs": cls.module.get_documents_folder,
            "table": cls.module.Table,
        }
        cls.messages = []
        cls.module.QMessageBox.information = staticmethod(
            lambda *args, **kwargs: cls.messages.append(("info", args))
        )
        cls.module.QMessageBox.critical = staticmethod(
            lambda *args, **kwargs: cls.messages.append(("critical", args))
        )
        cls.module.QMessageBox.warning = staticmethod(
            lambda *args, **kwargs: cls.messages.append(("warning", args))
        )
        cls.module.webbrowser.open = lambda *args, **kwargs: True
        cls.module.get_documents_folder = lambda: str(cls.outdir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.module.QMessageBox.information = cls._orig["information"]
        cls.module.QMessageBox.critical = cls._orig["critical"]
        cls.module.QMessageBox.warning = cls._orig["warning"]
        cls.module.webbrowser.open = cls._orig["open"]
        cls.module.get_documents_folder = cls._orig["docs"]
        cls.module.Table = cls._orig["table"]
        cls._tmp.cleanup()

    def setUp(self) -> None:
        # Fånga tabelldata genom att linda reportlabs Table
        real_table = self._orig["table"]
        captured = []

        class CapturingTable(real_table):
            def __init__(self, data, *args, **kwargs):
                captured.append(data)
                super().__init__(data, *args, **kwargs)

        self._captured = captured
        self.module.Table = CapturingTable

    def tearDown(self) -> None:
        self.module.Table = self._orig["table"]

    def _month_tables(self):
        """Tabeller som innehåller anställda (fler än tre rubrikrader)."""
        return [data for data in self._captured if len(data) > 3]

    def _generate(self, leave=None, start_month=None) -> None:
        for old in self.outdir.glob("*.pdf"):
            old.unlink()
        ok = self.generator._generate_pdf(
            data_list=["Anna Andersson", "Bertil Bengtsson"],
            year=2026,
            mode="Semesterlista",
            leave=leave,
            start_month=start_month,
        )
        self.assertTrue(ok)

    def _row(self, data, name: str):
        for row in data:
            if row and row[0] == name:
                return row
        raise AssertionError(f"Hittade ingen rad för {name}")

    def test_leave_cells_are_marked(self) -> None:
        from core.leave import LeaveCalendar

        calendar = LeaveCalendar.from_lines(
            ["Anna Andersson ; 18/12 - 7/1"], default_year=2026
        )
        self._generate(leave=calendar)

        december = next(
            data for data in self._month_tables() if "December 2026" in str(data[0][0])
        )
        anna = self._row(december, "Anna Andersson")
        # 21/12 är första lediga dagen, 31/12 den sista i månaden
        self.assertEqual(anna[1:21], [""] * 20, "dagar före 21/12 ska vara tomma")
        self.assertEqual(
            anna[21:32], [self.module.LEAVE_MARK] * 11, "21–31/12 ska vara markerade"
        )

        bertil = self._row(december, "Bertil Bengtsson")
        self.assertNotIn(self.module.LEAVE_MARK, bertil, "Bertil har ingen frånvaro")

    def test_leave_continues_into_january(self) -> None:
        from core.leave import LeaveCalendar

        calendar = LeaveCalendar.from_lines(
            ["Anna Andersson ; 18/12 - 7/1"], default_year=2026
        )
        # start_month=2 → feb 2026 – jan 2027, så januari 2027 finns med
        self._generate(leave=calendar, start_month=2)

        january = next(
            data for data in self._month_tables() if "Januari 2027" in str(data[0][0])
        )
        anna = self._row(january, "Anna Andersson")
        self.assertEqual(anna[1:5], [self.module.LEAVE_MARK] * 4, "1–4/1 ska vara lediga")
        self.assertEqual(anna[5:31], [""] * 26, "5/1 och framåt ska vara tomma")

    def test_without_leave_nothing_is_marked(self) -> None:
        from core.leave import LeaveCalendar

        self._generate(leave=LeaveCalendar())
        for data in self._month_tables():
            for row in data[3:]:
                self.assertNotIn(self.module.LEAVE_MARK, row)

    def test_legend_has_leave_entry(self) -> None:
        from core.leave import LeaveCalendar

        self._generate(leave=LeaveCalendar())
        legends = [data for data in self._captured if len(data) == 1]
        self.assertTrue(legends, "ingen färgförklaring hittades")
        legend = legends[0][0]
        self.assertIn(self.module.i18n.t("lista.pdf.legend.leave"), legend)
        self.assertEqual(len(legend), 10, "fyra färger + en för lediga dagar")

    def test_leave_mark_is_latin1(self) -> None:
        self.assertEqual(self.module.LEAVE_MARK, "\u00d7")
        self.module.LEAVE_MARK.encode("latin-1")


@unittest.skipUnless(HAVE_GUI, "PySide6/reportlab saknas")
class ReadListWithLeaveTests(unittest.TestCase):
    """Listfilen läses in med både namn och frånvaro."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.app = QApplication.instance() or QApplication([])
        except Exception as exc:  # pragma: no cover – ingen skärm
            raise unittest.SkipTest(f"Qt kunde inte startas: {exc}")

        cls.module = _load_plugin_module()
        from core.event_bus import EventBus
        from core.settings_manager import SettingsManager

        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.list_file = base / "Anställda.txt"
        cls.list_file.write_text(
            "Anna Andersson ; 18/12 - 7/1\n"
            "Bertil Bengtsson\n"
            "Cecilia Carlsson | 6/7 - 20/7\n"
            "# kommentar\n",
            encoding="utf-8",
        )

        cls._orig_critical = cls.module.QMessageBox.critical
        cls.module.QMessageBox.critical = staticmethod(lambda *a, **k: None)

        cls.settings_manager = SettingsManager(str(base / "app"))
        cls.plugin = cls.module.Plugin(EventBus(), cls.settings_manager)
        cls.generator = cls.module.PDFGenerator(cls.plugin)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.module.QMessageBox.critical = cls._orig_critical
        cls._tmp.cleanup()

    def test_names_are_clean(self) -> None:
        names = self.generator._read_list_from_file(str(self.list_file))
        self.assertEqual(
            names, ["Anna Andersson", "Bertil Bengtsson", "Cecilia Carlsson"]
        )

    def test_calendar_is_filled(self) -> None:
        from datetime import date

        self.generator._read_list_from_file(str(self.list_file))
        calendar = self.generator._leave_calendar
        self.assertEqual(len(calendar), 2)
        self.assertEqual(calendar.errors, [])

        ranges = calendar.ranges_for("Anna Andersson")
        self.assertEqual(len(ranges), 1)
        # 21/12 – 4/1 oavsett vilket år listan avser
        self.assertEqual((ranges[0].start.month, ranges[0].start.day), (12, 21))
        self.assertEqual((ranges[0].end.month, ranges[0].end.day), (1, 4))
        self.assertEqual(ranges[0].start.weekday(), 0, "start ska vara måndag")
        self.assertEqual(ranges[0].end.weekday(), 0, "slut ska vara måndag")

        self.assertTrue(calendar.is_off("Cecilia Carlsson", date(ranges[0].start.year, 7, 6)))
        self.assertFalse(calendar.is_off("Bertil Bengtsson", date(ranges[0].start.year, 7, 6)))

    def test_generate_uses_read_calendar(self) -> None:
        self.generator._read_list_from_file(str(self.list_file))
        self.assertIsNotNone(self.generator._leave_calendar.ranges_for("Anna Andersson"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
