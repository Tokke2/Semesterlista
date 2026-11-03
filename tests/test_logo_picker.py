#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för core/logo_picker.py – dropdown-logotypen (v2.10.0).

Kontrollerar att listan fylls med bilderna i ``assets/`` **och dess
undermappar**, att valet sparas via ``changed``-signalen och att
förhandsgranskningen skalas automatiskt utan att proportionerna ändras.

Kräver PySide6 och körs offscreen. Saknas Qt hoppas filen över.

    python -m unittest discover -s tests -v
    python tests/test_logo_picker.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAVE_QT = True
except Exception:  # pragma: no cover – miljö utan PySide6
    HAVE_QT = False

from core.pdf_assets import LOGO_SCALE_MAX, LOGO_SCALE_MIN  # noqa: E402

SVG_200x100 = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"'
    ' viewBox="0 0 200 100">\n'
    '  <rect x="0" y="0" width="200" height="100" fill="#1f4e79"/>\n'
    "</svg>\n"
)


def _write_svg(path: Path, content: str = SVG_200x100) -> None:
    """Skriv en liten SVG-fil till testmappen."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@unittest.skipUnless(HAVE_QT, "PySide6 saknas")
class LogoPickerTests(unittest.TestCase):
    """LogoPicker – dropdown, signaler och förhandsgranskning."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

        from core import i18n

        cls.i18n = i18n
        i18n.init(None)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "assets"
        self.root.mkdir(parents=True, exist_ok=True)
        self.svg = self.root / "logotyper" / "foretag.svg"
        _write_svg(self.svg)

        # Andra bildformat får finnas i mappen men ska inte listas (v2.10.0)
        (self.root / "logotyper" / "bild.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.root / "foto.jpg").write_bytes(b"\xff\xd8\xff")

        from core.logo_picker import LogoPicker

        self.LogoPicker = LogoPicker

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _picker(self, **kwargs):
        picker = self.LogoPicker(root=self.root, **kwargs)
        picker.resize(420, 120)
        picker.show()
        self.app.processEvents()
        return picker

    # ── listan ────────────────────────────────────────────

    def test_first_item_is_no_logo(self) -> None:
        picker = self._picker()
        self.assertEqual(picker.combo.count(), 2)
        self.assertEqual(picker.combo.itemData(0), "")
        self.assertEqual(picker.combo.currentIndex(), 0)
        self.assertEqual(picker.current_path(), "")
        picker.deleteLater()

    def test_lists_assets_and_subfolders(self) -> None:
        picker = self._picker()
        items = [picker.combo.itemData(i) for i in range(1, picker.combo.count())]
        self.assertEqual(items, [str(self.svg)])
        # Texten är den relativa sökvägen inuti assets/
        self.assertEqual(picker.combo.itemText(1), "logotyper/foretag.svg")
        self.assertEqual([a.path for a in picker.assets()], [self.svg])
        picker.deleteLater()

    def test_only_svg_is_listed(self) -> None:
        """PNG/JPG i assets-mappen ska inte dyka upp i dropdownen (v2.10.0)."""
        picker = self._picker()
        texts = [picker.combo.itemText(i) for i in range(picker.combo.count())]
        self.assertFalse([t for t in texts if t.lower().endswith((".png", ".jpg", ".jpeg"))])
        self.assertTrue(all(a.suffix == ".svg" for a in picker.assets()))
        picker.deleteLater()

    def test_svg_deep_in_subfolders_is_listed(self) -> None:
        _write_svg(self.root / "kunder" / "2026" / "acme.svg")
        picker = self._picker()
        texts = [picker.combo.itemText(i) for i in range(1, picker.combo.count())]
        self.assertIn("kunder/2026/acme.svg", texts)
        picker.deleteLater()

    def test_missing_assets_folder_gives_only_no_logo(self) -> None:
        picker = self.LogoPicker(root=Path(self._tmp.name) / "finns-inte")
        self.assertEqual(picker.combo.count(), 1)
        self.assertEqual(picker.current_path(), "")
        picker.deleteLater()

    # ── val och signal ────────────────────────────────────

    def test_selecting_emits_changed(self) -> None:
        picker = self._picker()
        seen = []
        picker.changed.connect(seen.append)

        picker.combo.setCurrentIndex(1)
        self.app.processEvents()

        self.assertEqual(seen, [str(self.svg)])
        self.assertEqual(picker.current_path(), str(self.svg))
        picker.deleteLater()

    def test_start_value_is_selected(self) -> None:
        picker = self.LogoPicker(root=self.root, current=str(self.svg))
        self.assertEqual(picker.current_path(), str(self.svg))
        self.assertEqual(Path(picker.combo.currentData()), self.svg)
        picker.deleteLater()

    def test_clear_returns_to_no_logo(self) -> None:
        picker = self._picker()
        seen = []
        picker.changed.connect(seen.append)
        picker.combo.setCurrentIndex(1)

        picker.clear()

        self.assertEqual(picker.current_path(), "")
        self.assertEqual(picker.combo.currentIndex(), 0)
        self.assertEqual(seen[-1], "")
        picker.deleteLater()

    def test_refresh_keeps_selection(self) -> None:
        picker = self._picker()
        picker.combo.setCurrentIndex(1)

        # Ny bild i mappen → listan byggs om men valet ligger kvar
        _write_svg(self.root / "ny.svg", SVG_200x100.replace("100", "100"))

        picker.refresh()

        # endast SVG räknas (post 0 + två SVG-filer)
        self.assertEqual(picker.combo.count(), 3)
        self.assertEqual(picker.current_path(), str(self.svg))
        self.assertEqual(Path(picker.combo.currentData()), self.svg)
        picker.deleteLater()

    def test_file_outside_assets_is_added_to_list(self) -> None:
        outside = Path(self._tmp.name) / "extern.svg"
        _write_svg(outside)

        picker = self._picker()
        picker.set_current(str(outside), emit=False)

        self.assertEqual(picker.current_path(), str(outside))
        self.assertEqual(Path(picker.combo.currentData()), outside)
        self.assertIn(self.i18n.t("logo.outside_assets"), picker.combo.currentText())
        picker.deleteLater()

    def test_missing_file_falls_back_to_no_logo(self) -> None:
        picker = self._picker()
        picker.set_current(str(self.root / "saknas.svg"), emit=False)
        self.assertEqual(picker.current_path(), "")
        self.assertEqual(picker.combo.currentIndex(), 0)
        picker.deleteLater()

    # ── förhandsgranskning ────────────────────────────────

    def test_preview_scales_without_distortion(self) -> None:
        picker = self._picker()
        picker.combo.setCurrentIndex(1)
        self.app.processEvents()

        pixmap = picker.preview.pixmap()
        self.assertFalse(pixmap.isNull(), "förhandsgranskningen ska vara renderad")

        width, height = pixmap.width(), pixmap.height()
        box = picker._preview_box()
        self.assertLessEqual(width, box.width())
        self.assertLessEqual(height, box.height())
        # 200 × 100 = proportionerna 2.0 ska behållas
        self.assertAlmostEqual(width / height, 2.0, delta=0.1)
        picker.deleteLater()

    def test_preview_fills_the_available_height(self) -> None:
        # Förhandsgranskningen är högst PREVIEW_HEIGHT hög – en liggande
        # logotyp begränsas därför av höjden, inte av fönstrets bredd.
        from core.logo_picker import PREVIEW_HEIGHT

        picker = self._picker()
        picker.combo.setCurrentIndex(1)
        self.app.processEvents()

        box = picker._preview_box()
        pixmap = picker.preview.pixmap()
        self.assertGreaterEqual(PREVIEW_HEIGHT, 24)
        self.assertAlmostEqual(pixmap.height(), box.height(), delta=2)
        picker.deleteLater()

    def test_wide_preview_is_limited_by_width(self) -> None:
        # En mycket bred logotyp (600 × 60) ska begränsas av bredden.
        _write_svg(
            self.root / "bred.svg",
            SVG_200x100.replace('width="200" height="100"', 'width="600" height="60"'),
        )

        picker = self._picker()
        index = picker.combo.findData(str(self.root / "bred.svg"))
        self.assertGreater(index, 0)
        picker.combo.setCurrentIndex(index)
        self.app.processEvents()

        box = picker._preview_box()
        pixmap = picker.preview.pixmap()
        self.assertAlmostEqual(pixmap.width(), box.width(), delta=2)
        self.assertAlmostEqual(pixmap.width() / pixmap.height(), 10.0, delta=0.2)
        picker.deleteLater()

    def test_preview_can_be_hidden(self) -> None:
        picker = self._picker(show_preview=False)
        self.assertFalse(picker.preview.isVisible())
        picker.deleteLater()

    def test_preview_shows_error_for_broken_file(self) -> None:
        broken = self.root / "trasig.svg"
        broken.write_text("inte en svg alls", encoding="utf-8")

        picker = self._picker()
        picker.set_current(str(broken), emit=False)
        self.app.processEvents()

        self.assertEqual(picker.current_path(), str(broken))
        self.assertTrue(picker._pixmap is None)
        self.assertIn(broken.name, picker.preview.text())
        picker.deleteLater()

    # ── import och storlek (v2.11.0) ──────────────────────

    def test_file_filter_offers_svg_eps_and_pdf(self) -> None:
        picker = self._picker()
        text = picker.file_filter()
        for pattern in ("*.svg", "*.eps", "*.pdf", "*.png", "*.jpg"):
            self.assertIn(pattern, text)
        picker.deleteLater()

    def test_insert_button_accepts_more_than_svg(self) -> None:
        picker = self._picker()
        self.assertIn("logotyp", picker.insert_button.text().lower())
        picker.deleteLater()

    def test_size_default_is_100_percent(self) -> None:
        picker = self._picker()
        self.assertEqual(picker.scale(), 100)
        self.assertEqual(picker.size_spin.value(), 100)
        self.assertEqual(picker.size_spin.suffix().strip(), "%")
        self.assertEqual(picker.size_spin.minimum(), LOGO_SCALE_MIN)
        self.assertEqual(picker.size_spin.maximum(), LOGO_SCALE_MAX)
        picker.deleteLater()

    def test_size_is_clamped_and_emitted(self) -> None:
        picker = self._picker()
        seen = []
        picker.scale_changed.connect(seen.append)

        picker.set_scale(150, emit=True)
        self.assertEqual(picker.scale(), 150)
        self.assertEqual(seen, [150])

        picker.set_scale(150, emit=True)          # oförändrat ger ingen signal
        self.assertEqual(seen, [150])

        picker.set_scale(1, emit=True)            # för litet → minsta
        self.assertEqual(picker.scale(), LOGO_SCALE_MIN)
        picker.set_scale(9999, emit=True)         # för stort → största
        self.assertEqual(picker.scale(), LOGO_SCALE_MAX)
        picker.deleteLater()

    def test_size_can_be_given_in_the_constructor(self) -> None:
        picker = self._picker(scale=80)
        self.assertEqual(picker.scale(), 80)
        self.assertEqual(picker.size_spin.value(), 80)
        picker.deleteLater()

    def test_preview_shrinks_with_the_size(self) -> None:
        picker = self._picker()
        picker.set_current(str(self.svg), emit=False)
        self.app.processEvents()
        wide = picker.preview.pixmap().width()

        picker.set_scale(50)
        self.app.processEvents()
        small = picker.preview.pixmap().width()

        self.assertGreater(wide, 0)
        self.assertLess(small, wide)
        picker.deleteLater()

    def test_eps_without_ghostscript_shows_a_hint(self) -> None:
        eps = self.root / "logotyper" / "gammal.eps"
        eps.write_text(
            "%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n",
            encoding="latin-1",
        )

        picker = self._picker()
        import core.pdf_assets as pdf_assets

        with mock.patch.object(pdf_assets, "find_ghostscript", return_value=None):
            picker.set_current(str(eps), emit=False)
            self.app.processEvents()

        self.assertIsNone(picker._pixmap)
        self.assertIn("Ghostscript", picker.preview.text())
        picker.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
