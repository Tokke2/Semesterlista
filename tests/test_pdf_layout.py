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
    from PySide6.QtWidgets import QApplication  # noqa: F401

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


def _paragraph_texts(value) -> list:
    """Plocka ut texterna ur allehanda cell- och tabellstrukturer."""
    texts = []

    def walk(item) -> None:
        if hasattr(item, "text"):
            texts.append(item.text)
        elif hasattr(item, "_cellvalues"):
            for row in item._cellvalues:
                for cell in row:
                    walk(cell)
        elif isinstance(item, (tuple, list)):
            for sub in item:
                walk(sub)

    walk(value)
    return texts


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
        from plugins.lista import pdf
        cls.pdf_module = pdf
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
            "docs": cls.pdf_module.get_documents_folder,
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
        cls.pdf_module.get_documents_folder = lambda: str(cls.outdir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.module.QMessageBox.information = cls._orig["information"]
        cls.module.QMessageBox.critical = cls._orig["critical"]
        cls.module.QMessageBox.warning = cls._orig["warning"]
        cls.module.webbrowser.open = cls._orig["open"]
        cls.pdf_module.get_documents_folder = cls._orig["docs"]
        cls._tmp.cleanup()

    def _generate(self, names=None, **kwargs) -> Path:
        """Generera en PDF och returnera sökvägen."""
        for old in self.outdir.glob("*.pdf"):
            old.unlink()
        ok = self.generator._generate_pdf(
            data_list=names or ["Anna Andersson", "Bertil Bengtsson"],
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
        pdf = self._generate(months_per_page=1, orientation="Liggande")
        (width, height), pages = _media_box(pdf)
        self.assertGreater(height, width)
        self.assertEqual(pages, 12)

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


class AdaptiveLayoutTests(PdfLayoutTestBase):
    """Layouten anpassas till listans längd (v2.11.0)."""

    def test_three_months_fit_with_six_names(self) -> None:
        names = [f"Person {i}" for i in range(6)]
        pdf = self._generate(names=names, start_month=10, months_per_page=3)
        _, pages = _media_box(pdf)
        self.assertEqual(pages, 4, "12 månader / 3 per blad = 4 sidor")

    def test_short_list_keeps_three_months(self) -> None:
        count, padding, gap = self.generator._fit_layout(
            months_per_page=3,
            rows=8,
            title_prefix="Semesterlista",
            months=[(2026, 10)],
            styles=self.module.getSampleStyleSheet(),
            table_width_pt=self.module.TABLE_WIDTH_PT,
            available_height=527.0,
        )
        self.assertEqual(count, 3)
        self.assertGreaterEqual(padding, 1)
        self.assertGreaterEqual(gap, 4)

    def test_long_list_preserves_months_per_page(self) -> None:
        count, _padding, _gap = self.generator._fit_layout(
            months_per_page=3,
            rows=17,
            title_prefix="Semesterlista",
            months=[(2026, 10)],
            styles=self.module.getSampleStyleSheet(),
            table_width_pt=self.module.TABLE_WIDTH_PT,
            available_height=527.0,
        )
        self.assertEqual(count, 3)

    def test_very_long_list_preserves_months_per_page(self) -> None:
        count, _padding, _gap = self.generator._fit_layout(
            months_per_page=3,
            rows=40,
            title_prefix="Semesterlista",
            months=[(2026, 10)],
            styles=self.module.getSampleStyleSheet(),
            table_width_pt=self.module.TABLE_WIDTH_PT,
            available_height=527.0,
        )
        self.assertEqual(count, 3)

    def test_month_height_grows_with_rows(self) -> None:
        small = self.generator._estimate_month_height(
            8, 31, self.module.ROW_PADDING, self.module.TABLE_WIDTH_PT
        )
        large = self.generator._estimate_month_height(
            20, 31, self.module.ROW_PADDING, self.module.TABLE_WIDTH_PT
        )
        self.assertGreater(large, small)

    def test_month_height_shrinks_with_padding(self) -> None:
        loose = self.generator._estimate_month_height(
            10, 31, 2, self.module.TABLE_WIDTH_PT
        )
        tight = self.generator._estimate_month_height(
            10, 31, 0, self.module.TABLE_WIDTH_PT
        )
        self.assertGreater(loose, tight)

    def test_long_list_does_not_clip_the_tables(self) -> None:
        """Även 16 anställda ska ge kompletta sidor (4, tre månader per blad)."""
        names = [f"Person {i}" for i in range(16)]
        pdf = self._generate(names=names, start_month=10, months_per_page=3)
        _, pages = _media_box(pdf)
        self.assertEqual(pages, 4)

    def test_legend_labels_are_complete(self) -> None:
        from core import i18n

        old_language = i18n.current_language()
        try:
            i18n.set_language("sv")
            legend = self.generator._create_legend_with_colors()
            legend.wrap(self.module.TABLE_WIDTH_PT, 10 ** 6)
            labels = _paragraph_texts(legend)
            self.assertEqual(labels, [i18n.t(key) for _c, key in self.module.LEGEND_ITEMS])
            self.assertIn("m.fl.)", " ".join(labels))
        finally:
            i18n.set_language(old_language)

    def test_legend_fills_the_full_width(self) -> None:
        legend = self.generator._create_legend_with_colors()
        width, _height = legend.wrap(self.module.TABLE_WIDTH_PT, 10 ** 6)
        self.assertAlmostEqual(width, self.module.TABLE_WIDTH_PT, places=0)
