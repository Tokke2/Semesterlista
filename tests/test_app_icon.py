#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för appikonen (v2.7.0).

Kontrollerar att ikonfilerna finns i rätt storlekar (SVG, PNG, ICO) och
– om Qt finns – att de kan läsas som QIcon och sättas på applikationen.

    python -m unittest discover -s tests -v
    python tests/test_app_icon.py
"""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import app_icon as app_icon_module  # noqa: E402

ICON_DIR = PROJECT_ROOT / "assets" / "ikon"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(path: Path) -> tuple[int, int]:
    """Läs bredd/höjd ur en PNG (IHDR) utan externa beroenden."""
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise AssertionError(f"{path.name} är ingen PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def png_size_from_bytes(data: bytes) -> tuple[int, int]:
    """Läs bredd/höjd ur PNG-data i minnet."""
    if not data.startswith(PNG_SIGNATURE):
        raise AssertionError("Inte en PNG")
    return struct.unpack(">II", data[16:24])


def ico_sizes(path: Path) -> list[int]:
    """Läs vilka storlekar som finns i en .ico-fil."""
    data = path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    if reserved != 0 or kind != 1:
        raise AssertionError("Ogiltig ICO-header")

    sizes = []
    for index in range(count):
        offset = 6 + index * 16
        width, height = data[offset], data[offset + 1]
        sizes.append(256 if width == 0 else width)
        if height != width:
            raise AssertionError("ICO-posten är inte kvadratisk")
    return sizes


class IconFilesTests(unittest.TestCase):
    """Filerna på disk – kräver ingen Qt."""

    def test_svg_exists(self) -> None:
        svg = ICON_DIR / "appikon.svg"
        self.assertTrue(svg.exists())
        text = svg.read_text(encoding="utf-8")
        self.assertIn("<svg", text)
        self.assertIn(app_icon_module.ICON_BLUE, text)
        self.assertIn(app_icon_module.ICON_YELLOW, text)

    def test_png_sizes(self) -> None:
        for size in app_icon_module.APP_ICON_SIZES:
            with self.subTest(size=size):
                path = ICON_DIR / f"appikon-{size}.png"
                self.assertTrue(path.exists(), path.name)
                self.assertEqual(png_size(path), (size, size))

    def test_ico_has_all_sizes(self) -> None:
        path = ICON_DIR / "appikon.ico"
        self.assertTrue(path.exists())
        sizes = ico_sizes(path)
        self.assertEqual(sorted(set(sizes)), sorted(app_icon_module.APP_ICON_SIZES))

        # Alla poster ska vara PNG-baserade (Vista+)
        data = path.read_bytes()
        for index, _size in enumerate(sizes):
            # ICO-post: byte 8–11 = bildens storlek, 12–15 = offset
            length, offset = struct.unpack(
                "<II", data[6 + index * 16 + 8: 6 + index * 16 + 16]
            )
            blob = data[offset:offset + length]
            self.assertTrue(blob.startswith(PNG_SIGNATURE))
            self.assertEqual(png_size_from_bytes(blob), (_size, _size))

    def test_icon_files_order_and_content(self) -> None:
        files = app_icon_module.icon_files()
        names = [path.name for path in files]
        self.assertEqual(names[0], "appikon-16.png")
        self.assertIn("appikon.svg", names)
        self.assertIn("appikon.ico", names)
        self.assertEqual(len(files), len(app_icon_module.APP_ICON_SIZES) + 2)

    def test_icon_dir_points_into_app(self) -> None:
        self.assertEqual(app_icon_module.icon_dir(), ICON_DIR)

    def test_windows_app_id_is_only_windows(self) -> None:
        result = app_icon_module.set_windows_app_user_model_id()
        self.assertEqual(result, sys.platform == "win32")


class QtIconTests(unittest.TestCase):
    """QIcon-delen – hoppas över utan PySide6/skärm."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 saknas: {exc}")

        try:
            cls.app = QApplication.instance() or QApplication([])
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"Qt kunde inte startas: {exc}")

        cls.qt = True

    def setUp(self) -> None:
        app_icon_module.clear_cache()

    def tearDown(self) -> None:
        app_icon_module.clear_cache()

    def test_icon_loads_all_sizes(self) -> None:
        icon = app_icon_module.app_icon()
        self.assertFalse(icon.isNull())
        sizes = sorted({size.width() for size in icon.availableSizes()})
        expected = sorted(app_icon_module.APP_ICON_SIZES)
        self.assertTrue(set(expected).issubset(set(sizes)), sizes)

    def test_icon_is_cached(self) -> None:
        first = app_icon_module.app_icon()
        second = app_icon_module.app_icon()
        self.assertIs(first, second)
        self.assertIsNot(first, app_icon_module.app_icon(force_reload=True))

    def test_apply_sets_application_icon(self) -> None:
        icon = app_icon_module.apply_app_icon(self.app)
        self.assertFalse(icon.isNull())
        self.assertFalse(self.app.windowIcon().isNull())

    def test_fallback_when_files_missing(self) -> None:
        original = app_icon_module.icon_dir
        with tempfile.TemporaryDirectory() as tmp:
            app_icon_module.icon_dir = lambda: Path(tmp)  # type: ignore[assignment]
            try:
                app_icon_module.clear_cache()
                self.assertEqual(app_icon_module.icon_files(), [])
                icon = app_icon_module.app_icon()
                self.assertFalse(icon.isNull())
                self.assertIn(64, {size.width() for size in icon.availableSizes()})
            finally:
                app_icon_module.icon_dir = original  # type: ignore[assignment]
                app_icon_module.clear_cache()


if __name__ == "__main__":
    unittest.main(verbosity=2)
