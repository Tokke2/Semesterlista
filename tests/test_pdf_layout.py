#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för PDF-layouten – sidlayout och månader per blad (v2.6.0).

Kräver PySide6 + reportlab. Saknas de hoppas hela filen över, så att
testsviten fortfarande kan köras i en miljö utan GUI-beroenden.

    python -m unittest discover -s tests -v
    python tests/test_pdf_layout.py
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Offscreen krävs för att QApplication ska kunna skapas utan skärm
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    import reportlab  # noqa: F401

    HAVE_GUI = True
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


def _media_box(pdf_path: Path) -> tuple[tuple[float, float], int]:
    """Läs MediaBox (bredd, höjd) och antal sidor ur en PDF."""
    data = Path(pdf_path).read_bytes()
    match = re.search(
        rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]",
        data,
    )
    if match is None:  # pragma: no cover – borde inte hända
        raise AssertionError("Ingen MediaBox i PDF:en")
    width = float(match.group(3)) - float(match.group(1))
    height = float(match.group(4)) - float(match.group(2))
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    return (width, height), pages


@unittest.skipUnless(HAVE_GUI, "PySide6/reportlab saknas")
class PdfLayoutTestBase(unittest.TestCase):
    """Bas som laddar pluginet och ett QApplication."""

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
        cls.list_file.write_text("Anna Andersson\nBertil Bengtsson\n", encoding="utf-8")
        cls.outdir = base / "ut"
        cls.outdir.mkdir()

        cls.settings_manager = SettingsManager(str(base / "app"))
        cls.plugin = cls.module.Plugin(EventBus(), cls.settings_manager)
        cls.plugin.settings["auto_open_pdf"] = False
        cls.generator = cls.module.PDFGenerator(cls.plugin)

        # Ersätt dialoger/öppning under testerna
        cls._orig = {
            "information": cls.module.QMessageBox.information,
            "critical": cls.module.QMessageBox.critical,
            "warning": cls.module.QMessageBox.warning,
            "open": cls.module.webbrowser.open,
            "docs": cls.module.get_documents_folder,
        }
        cls.messages = []
        cls.module.QMessageBox.information = staticmethod(
            lambda *args, **kwargs: cls.messages.append(("info", args[2] if len(args) > 2 else ""))
        )
        cls.module.QMessageBox.critical = staticmethod(
            lambda *args, **kwargs: cls.messages.append(("critical", args[2] if len(args) > 2 else ""))
        )
        cls.module.QMessageBox.warning = staticmethod(
            lambda *args, **kwargs: cls.messages.append(("warning", args[2] if len(args) > 2 else ""))
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
        cls._tmp.cleanup()

    def _generate(self, **kwargs) -> Path:
        """Generera en PDF och returnera sökvägen."""
        for old in self.outdir.glob("*.pdf"):
            old.unlink()
        ok = self.generator._generate_pdf(
            data_list=["Anna Andersson", "Bertil Bengtsson"],
            year=2026,
            mode=kwargs.pop("mode", "Semesterlista"),
            **kwargs,
        )
        self.assertTrue(ok)
        files = sorted(self.outdir.glob("*.pdf"))
        self.assertEqual(len(files), 1, files)
        return files[0]


class OrientationTests(PdfLayoutTestBase):
    """Sidlayout – liggande/stående."""

    def test_default_is_landscape(self) -> None:
        self.assertEqual(self.module.DEFAULT_ORIENTATION, "Liggande")
        self.assertEqual(self.module.ORIENTATIONS, ["Liggande", "Stående"])

    def test_normalize_orientation(self) -> None:
        normalize = self.module.normalize_orientation
        self.assertEqual(normalize("Stående"), "Stående")
        self.assertEqual(normalize("Liggande"), "Liggande")
        self.assertEqual(normalize(""), "Liggande")
        self.assertEqual(normalize(None), "Liggande")
        self.assertEqual(normalize("Diagonal"), "Liggande")

    def test_page_geometry(self) -> None:
        module = self.module
        landscape_size, landscape_width = module.page_geometry("Liggande")
        portrait_size, portrait_width = module.page_geometry("Stående")

        self.assertGreater(landscape_size[0], landscape_size[1])
        self.assertLess(portrait_size[0], portrait_size[1])
        self.assertAlmostEqual(landscape_width, 270.0 * 72 / 25.4, places=1)
        self.assertAlmostEqual(portrait_width, 190.0 * 72 / 25.4, places=1)

    def test_orientation_labels_are_translated(self) -> None:
        from core import i18n

        old = i18n.current_language()
        try:
            i18n.set_language("sv")
            self.assertIn("Liggande", self.module.orientation_label("Liggande"))
            i18n.set_language("en")
            self.assertIn("Landscape", self.module.orientation_label("Liggande"))
            self.assertIn("Portrait", self.module.orientation_label("Stående"))
        finally:
            i18n.set_language(old)

    def test_landscape_pdf_is_wider_than_tall(self) -> None:
        pdf = self._generate(months_per_page=3, orientation="Liggande")
        (width, height), pages = _media_box(pdf)
        self.assertGreater(width, height)
        self.assertEqual(pages, 4)  # 12 månader / 3 per blad

    def test_portrait_pdf_is_taller_than_wide(self) -> None:
        pdf = self._generate(months_per_page=3, orientation="Stående")
        (width, height), pages = _media_box(pdf)
        self.assertGreater(height, width)
        self.assertEqual(pages, 4)

    def test_unknown_orientation_falls_back_to_landscape(self) -> None:
        pdf = self._generate(months_per_page=2, orientation="Diagonal")
        (width, height), _pages = _media_box(pdf)
        self.assertGreater(width, height)


class MonthsPerPageTests(PdfLayoutTestBase):
    """Månader per blad – 1, 2 eller 3."""

    def test_options(self) -> None:
        self.assertEqual(self.module.MONTHS_PER_PAGE_OPTIONS, [1, 2, 3])
        self.assertEqual(self.module.DEFAULT_MONTHS_PER_PAGE, 3)

    def test_chunking(self) -> None:
        module = self.module
        sequence = module.PDFGenerator._build_month_sequence(2026, None)
        self.assertEqual(len(sequence), 12)
        self.assertEqual(sequence[0], (2026, 1))
        self.assertEqual(sequence[-1], (2026, 12))

        for months in (1, 2, 3):
            pages = module.PDFGenerator._chunk_months(sequence, months)
            self.assertEqual(len(pages), -(-12 // months))
            self.assertEqual(sum(len(page) for page in pages), 12)

    def test_start_month_crosses_year(self) -> None:
        sequence = self.module.PDFGenerator._build_month_sequence(2026, 12)
        self.assertEqual(sequence[0], (2026, 12))
        self.assertEqual(sequence[-1], (2027, 11))

    def test_pdf_page_counts(self) -> None:
        for months, expected in ((1, 12), (2, 6), (3, 4)):
            with self.subTest(months=months):
                pdf = self._generate(months_per_page=months, orientation="Stående")
                _size, pages = _media_box(pdf)
                self.assertEqual(pages, expected)

    def test_invalid_months_rejected(self) -> None:
        errors = self.generator._validate_inputs(
            "2026", str(self.list_file), "Semesterlista", 4, "Liggande"
        )
        self.assertTrue(any("Månader per blad" in error for error in errors))

        self.messages.clear()
        ok = self.generator.generate(
            year_str="2026",
            file_path=str(self.list_file),
            mode="Semesterlista",
            months_per_page=4,
        )
        self.assertFalse(ok)
        self.assertTrue(self.messages)

    def test_invalid_orientation_rejected(self) -> None:
        errors = self.generator._validate_inputs(
            "2026", str(self.list_file), "Semesterlista", 2, "Diagonal"
        )
        self.assertTrue(any("Sidlayout" in error for error in errors))

    def test_settings_are_passed_to_view(self) -> None:
        self.plugin.settings["orientation"] = "Stående"
        self.plugin.settings["months_per_page"] = 1
        view = self.plugin.get_tab_widget()

        self.assertEqual(view.orientation_combo.currentData(), "Stående")
        self.assertEqual(
            view.months_per_page_combo.currentText(),
            "1",
        )
        labels = [view.months_per_page_combo.itemText(i)
                  for i in range(view.months_per_page_combo.count())]
        self.assertEqual(labels, ["1", "2", "3"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
