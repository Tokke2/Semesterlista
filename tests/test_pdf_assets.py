#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för core/pdf_assets.py – logotyper från assets-mappen till PDF.

Körs utan nätverk. Delar som kräver reportlab (PDF-ritning) hoppas över
automatiskt om reportlab inte är installerat, och SVG-rendering hoppas
över om varken svglib eller Qt kan användas i miljön.

    python -m unittest discover -s tests -v
    python tests/test_pdf_assets.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.pdf_assets import (  # noqa: E402
    ASSET_DIR_NAME,
    AUTO_HEIGHT_RATIO,
    AUTO_MAX_HEIGHT_MM,
    AUTO_MAX_WIDTH_MM,
    AUTO_MIN_HEIGHT_PT,
    AUTO_MIN_WIDTH_PT,
    AUTO_WIDTH_RATIO,
    MM,
    AssetError,
    AssetFile,
    GHOSTSCRIPT_ENV,
    LOGO_SCALE_MAX,
    LOGO_SCALE_MIN,
    PdfLogo,
    SCALE_MAX_HEIGHT_RATIO,
    SCALE_MAX_WIDTH_RATIO,
    assets_root,
    convert_eps_to_png,
    convert_pdf_to_png,
    find_ghostscript,
    ghostscript_hint,
    ensure_assets_dir,
    find_asset,
    logo_for_settings,
    make_logo_canvas,
    make_page_logo_drawer,
    scan_assets,
)

#: A4 i punkter (liggande = 842 × 595)
A4_LANDSCAPE_W = 842.0
A4_LANDSCAPE_H = 595.0
A4_H = 842.0

try:  # reportlab är en vanlig beroende men kan saknas i testmiljö
    import importlib.util

    from reportlab.lib.pagesizes import A4

    HAVE_REPORTLAB = importlib.util.find_spec("reportlab") is not None
except Exception:  # pragma: no cover
    HAVE_REPORTLAB = False
    A4 = (595.0, 842.0)

def _write_png(path: Path, width: int, height: int, rgb: tuple = (31, 78, 121)) -> None:
    """Skriv en enfärgad PNG utan externa beroenden (för rastertesterna)."""
    import struct
    import zlib

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


SVG_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60" viewBox="0 0 120 60">
  <rect x="0" y="0" width="120" height="60" fill="#1f4e79"/>
  <circle cx="30" cy="30" r="20" fill="#f2b705"/>
</svg>
"""


class AssetsFixture(unittest.TestCase):
    """Bastest som skapar en temporär assets-mapp med undermappar."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / ASSET_DIR_NAME
        self.root.mkdir(parents=True)
        (self.root / "foretag.svg").write_text(SVG_SAMPLE, encoding="utf-8")
        sub = self.root / "logotyper"
        sub.mkdir()
        (sub / "avdelning.svg").write_text(SVG_SAMPLE, encoding="utf-8")
        (sub / "anteckning.txt").write_text("inte en bild", encoding="utf-8")
        hidden = self.root / ".cache"
        hidden.mkdir()
        (hidden / "dold.svg").write_text(SVG_SAMPLE, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()


class ScanAssetsTests(AssetsFixture):
    """scan_assets / find_asset."""

    def test_finds_files_recursively(self) -> None:
        found = scan_assets(self.root)
        names = [asset.relative for asset in found]
        self.assertEqual(names, ["foretag.svg", "logotyper/avdelning.svg"])

    def test_ignores_hidden_and_other_suffixes(self) -> None:
        found = scan_assets(self.root)
        relatives = {asset.relative for asset in found}
        self.assertNotIn(".cache/dold.svg", relatives)
        self.assertNotIn("logotyper/anteckning.txt", relatives)

    def test_non_recursive(self) -> None:
        found = scan_assets(self.root, recursive=False)
        self.assertEqual([asset.relative for asset in found], ["foretag.svg"])

    def test_only_svg(self) -> None:
        found = scan_assets(self.root, suffixes=(".svg",))
        self.assertEqual(len(found), 2)
        self.assertTrue(all(asset.is_svg for asset in found))

    def test_ignores_app_icon_folder(self) -> None:
        """Appikonen i assets/ikon ska inte erbjudas som logotyp (v2.7.0)."""
        icon_dir = self.root / "ikon"
        icon_dir.mkdir()
        (icon_dir / "appikon-64.png").write_text("x", encoding="utf-8")
        (icon_dir / "appikon.svg").write_text(SVG_SAMPLE, encoding="utf-8")

        found = scan_assets(self.root)
        relatives = {asset.relative for asset in found}
        self.assertNotIn("ikon/appikon.svg", relatives)
        self.assertNotIn("ikon/appikon-64.png", relatives)
        self.assertIn("foretag.svg", relatives)

        # Går att tvinga fram om man verkligen vill
        forced = scan_assets(self.root, exclude_dirs=())
        self.assertIn("ikon/appikon.svg", {asset.relative for asset in forced})

    def test_missing_folder_returns_empty(self) -> None:
        self.assertEqual(scan_assets(Path(self._tmp.name) / "finns-inte"), [])

    def test_asset_properties(self) -> None:
        found = scan_assets(self.root)
        sub = found[1]
        self.assertEqual(sub.name, "avdelning")
        self.assertEqual(sub.folder, "logotyper")
        self.assertEqual(sub.suffix, ".svg")
        self.assertTrue(sub.is_svg)
        self.assertIsInstance(sub, AssetFile)

    def test_find_asset_by_relative_path(self) -> None:
        asset = find_asset("logotyper/avdelning.svg", self.root)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.name, "avdelning")

    def test_find_asset_by_name_and_stem(self) -> None:
        self.assertIsNotNone(find_asset("foretag.svg", self.root))
        self.assertIsNotNone(find_asset("foretag", self.root))
        self.assertIsNone(find_asset("saknas.svg", self.root))

    def test_assets_root_and_ensure(self) -> None:
        self.assertEqual(assets_root(), PROJECT_ROOT / ASSET_DIR_NAME)
        created = ensure_assets_dir(Path(self._tmp.name) / "ny")
        self.assertTrue(created.is_dir())
        self.assertEqual(created.name, ASSET_DIR_NAME)


class PdfLogoTests(AssetsFixture):
    """PdfLogo och logotypinställningar."""

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(AssetError):
            PdfLogo.load(self.root / "finns-inte.svg")

    def test_empty_settings_give_none(self) -> None:
        self.assertIsNone(logo_for_settings({}))
        self.assertIsNone(logo_for_settings({"logo_svg": ""}))
        self.assertIsNone(logo_for_settings(None))

    def test_settings_pointing_to_missing_file_raises(self) -> None:
        with self.assertRaises(AssetError):
            logo_for_settings({"logo_svg": "assets/saknas.svg"})

    def test_svg_loads_and_is_scaled(self) -> None:
        try:
            logo = PdfLogo.load(self.root / "foretag.svg", max_width_mm=35, max_height_mm=16)
        except AssetError as exc:  # pragma: no cover – miljöberoende
            self.skipTest(f"SVG kunde inte renderas här: {exc}")

        max_w = 35 / 25.4 * 72
        max_h = 16 / 25.4 * 72
        self.assertLessEqual(logo.width, max_w + 0.5)
        self.assertLessEqual(logo.height, max_h + 0.5)
        # Proportionerna 120×60 ska behållas
        self.assertAlmostEqual(logo.width / logo.height, 2.0, places=2)

    @unittest.skipUnless(HAVE_REPORTLAB, "reportlab saknas")
    def test_raster_load_and_draw(self) -> None:
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas as rl_canvas

        png = self.root / "ruta.png"
        _write_png(png, 200, 100)
        self.assertTrue(png.exists())

        logo = PdfLogo.load(png, max_width_mm=35, max_height_mm=16)
        self.assertAlmostEqual(logo.width / logo.height, 2.0, places=2)

        out = Path(self._tmp.name) / "logo.pdf"
        canv = rl_canvas.Canvas(str(out), pagesize=A4)
        logo.draw_on(canv, 100, 500)
        canv.showPage()
        canv.save()

        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 500)
        self.assertEqual(ImageReader(str(png)).getSize(), (200, 100))

    def test_helpers_none_without_logo(self) -> None:
        self.assertIsNone(make_page_logo_drawer(None))
        self.assertIsNone(make_logo_canvas(None))

    @unittest.skipUnless(HAVE_REPORTLAB, "reportlab saknas")
    def test_canvas_draws_logo_on_every_page(self) -> None:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

        calls = []

        class _FakeLogo:
            width = 20.0
            height = 10.0

            def draw_corner(self, canvas, doc, margin_mm=8.0, corner="right"):
                calls.append((margin_mm, corner))

        maker = make_logo_canvas(_FakeLogo(), margin_mm=8.0)
        self.assertIsNotNone(maker)

        out = Path(self._tmp.name) / "sidor.pdf"
        style = getSampleStyleSheet()["Normal"]
        story = [Paragraph("Sida 1", style), PageBreak(), Paragraph("Sida 2", style)]
        doc = SimpleDocTemplate(str(out), pagesize=A4)
        doc.build(story, canvasmaker=maker)

        self.assertTrue(out.exists())
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(calls[0], (8.0, "right"))


class PdfLogoAutoSizeTests(unittest.TestCase):
    """Automatisk storlek på logotypen i PDF:en (v2.10.0)."""

    def _logo(self, width: float, height: float) -> PdfLogo:
        """PdfLogo med given naturlig storlek (utan att läsa någon fil)."""
        logo = PdfLogo.__new__(PdfLogo)
        logo.width = width
        logo.height = height
        return logo

    def _box(self, page_w: float, page_h: float) -> tuple:
        box_w = max(min(page_w * float(AUTO_WIDTH_RATIO), AUTO_MAX_WIDTH_MM * MM),
                    AUTO_MIN_WIDTH_PT)
        box_h = max(min(page_h * float(AUTO_HEIGHT_RATIO), AUTO_MAX_HEIGHT_MM * MM),
                    AUTO_MIN_HEIGHT_PT)
        return box_w, box_h

    def test_landscape_and_portrait_fit_the_page(self) -> None:
        logo = self._logo(200.0, 80.0)  # proportion 2.5

        for page_w, page_h in ((A4_LANDSCAPE_W, A4_LANDSCAPE_H), (A4_LANDSCAPE_H, A4_H)):
            width, height = logo.auto_size(page_w, page_h)
            box_w, box_h = self._box(page_w, page_h)
            self.assertLessEqual(width, box_w + 0.01)
            self.assertLessEqual(height, box_h + 0.01)
            self.assertGreater(width, 0.0)
            self.assertAlmostEqual(width / height, 2.5, places=3)

    def test_landscape_logo_is_wider_than_portrait(self) -> None:
        logo = self._logo(200.0, 80.0)
        land_w, land_h = logo.auto_size(A4_LANDSCAPE_W, A4_LANDSCAPE_H)
        port_w, port_h = logo.auto_size(A4_LANDSCAPE_H, A4_H)
        self.assertGreater(land_w, port_w)
        self.assertGreater(land_h, port_h)

    def test_proportions_are_kept_for_extreme_shapes(self) -> None:
        for natural_w, natural_h in ((240.0, 20.0), (20.0, 160.0), (50.0, 50.0), (8.0, 6.0)):
            logo = self._logo(natural_w, natural_h)
            for page_w, page_h in ((A4_LANDSCAPE_W, A4_LANDSCAPE_H),
                                   (A4_LANDSCAPE_H, A4_H),
                                   (200.0, 200.0)):
                width, height = logo.auto_size(page_w, page_h)
                box_w, box_h = self._box(page_w, page_h)
                self.assertAlmostEqual(
                    width / height, natural_w / natural_h, places=3,
                    msg=f"{natural_w}x{natural_h} på {page_w}x{page_h}",
                )
                self.assertLessEqual(width, box_w + 0.01)
                self.assertLessEqual(height, box_h + 0.01)

    def test_never_larger_than_the_caps(self) -> None:
        logo = self._logo(100.0, 50.0)
        width, height = logo.auto_size(6000.0, 6000.0)
        self.assertLessEqual(width, AUTO_MAX_WIDTH_MM * MM + 0.01)
        self.assertLessEqual(height, AUTO_MAX_HEIGHT_MM * MM + 0.01)
        self.assertAlmostEqual(width / height, 2.0, places=3)

    def test_tiny_page_is_bounded_by_the_minimum_box(self) -> None:
        # Även en liten sida ger en ruta på minst 36 × 12 pt – logotypen
        # ryms alltid i den och förvrängs aldrig.
        logo = self._logo(100.0, 50.0)
        width, height = logo.auto_size(10.0, 10.0)
        self.assertLessEqual(width, AUTO_MIN_WIDTH_PT + 0.01)
        self.assertLessEqual(height, AUTO_MIN_HEIGHT_PT + 0.01)
        self.assertAlmostEqual(width / height, 2.0, places=3)
        self.assertGreater(width, 0.0)

    def test_natural_size_is_kept_when_disabled(self) -> None:
        logo = self._logo(100.0, 50.0)
        drawn = []

        def _fake_draw(_canvas, _x, _y, width=None, height=None):
            drawn.append((width, height))

        logo.draw_on = _fake_draw  # type: ignore[method-assign]

        class _Canvas:
            _pagesize = (A4_LANDSCAPE_W, A4_LANDSCAPE_H)

        class _Doc:
            pagesize = (A4_LANDSCAPE_W, A4_LANDSCAPE_H)

        canvas = _Canvas()
        canvas.saveState = canvas.restoreState = lambda: None

        logo.draw_corner(canvas, _Doc(), margin_mm=8.0, auto_size=False)
        self.assertEqual(drawn[-1], (logo.width, logo.height))

        logo.draw_corner(canvas, _Doc(), margin_mm=8.0, auto_size=True)
        expected = logo.auto_size(A4_LANDSCAPE_W, A4_LANDSCAPE_H)
        self.assertAlmostEqual(drawn[-1][0], expected[0], places=3)
        self.assertAlmostEqual(drawn[-1][1], expected[1], places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)


@unittest.skipIf(os.name == "nt", "fejkat Ghostscript kräver ett skal")
class EpsImportTests(unittest.TestCase):
    """EPS-logotyper konverteras med Ghostscript (v2.11.0)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.eps = self.tmp / "logo.eps"
        self.eps.write_text(
            "%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 200 100\nshowpage\n",
            encoding="latin-1",
        )
        self.png = self.tmp / "fixture.png"
        _write_png(self.png, 400, 200)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_gs(self, body: str) -> Path:
        """Skapa ett litet skal som beter sig som Ghostscript."""
        script = self.tmp / "fake-gs"
        script.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        script.chmod(0o755)
        return script

    def _copy_gs(self) -> Path:
        return self._fake_gs(
            'out=""\n'
            'for a in "$@"; do\n'
            '  case "$a" in -sOutputFile=*) out="${a#-sOutputFile=}" ;; esac\n'
            "done\n"
            f'cp "{self.png}" "$out"'
        )

    def test_environment_variable_wins(self) -> None:
        script = self._copy_gs()
        with mock.patch.dict(os.environ, {GHOSTSCRIPT_ENV: str(script)}):
            self.assertEqual(find_ghostscript(), str(script))

    def test_environment_variable_pointing_nowhere_is_ignored(self) -> None:
        missing = self.tmp / "finns-inte"
        with mock.patch.dict(os.environ, {GHOSTSCRIPT_ENV: str(missing)}):
            self.assertIsNone(find_ghostscript())

    def test_missing_ghostscript_gives_a_hint(self) -> None:
        with mock.patch.object(
            sys.modules["core.pdf_assets"], "find_ghostscript", return_value=None
        ):
            with self.assertRaises(AssetError) as ctx:
                convert_eps_to_png(self.eps)
        self.assertIn("Ghostscript", str(ctx.exception))
        self.assertIn("Ghostscript", ghostscript_hint())

    def test_eps_is_converted_to_png(self) -> None:
        script = self._copy_gs()
        with mock.patch.dict(os.environ, {GHOSTSCRIPT_ENV: str(script)}):
            result = convert_eps_to_png(self.eps)
            self.assertTrue(result.exists())
            self.assertEqual(result.suffix, ".png")
            self.assertEqual(result.read_bytes()[:4], b"\x89PNG")
            # Andra anropet använder cachen (inget nytt Ghostscript-anrop)
            again = convert_eps_to_png(self.eps)
            self.assertEqual(again, result)

    def test_eps_logo_keeps_the_original_path(self) -> None:
        script = self._copy_gs()
        with mock.patch.dict(os.environ, {GHOSTSCRIPT_ENV: str(script)}):
            logo = PdfLogo.load(self.eps)
        self.assertEqual(logo.path, self.eps, "originalfilen ska visas i listan")
        self.assertFalse(logo.vector)
        self.assertAlmostEqual(logo.width / logo.height, 2.0, places=2)

    def test_failed_conversion_reports_the_error(self) -> None:
        script = self._fake_gs('echo "boom" 1>&2\nexit 1')
        with mock.patch.dict(os.environ, {GHOSTSCRIPT_ENV: str(script)}):
            with self.assertRaises(AssetError) as ctx:
                convert_eps_to_png(self.eps)
        self.assertIn("logo.eps", str(ctx.exception))
        self.assertIn("boom", str(ctx.exception))


@unittest.skipUnless(HAVE_REPORTLAB, "reportlab saknas")
class PdfImportTests(unittest.TestCase):
    """PDF-logotyper rastreras med PyMuPDF (v2.11.0)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.pdf = self.tmp / "logo.pdf"
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas

        page = rl_canvas.Canvas(str(self.pdf), pagesize=A4)
        page.rect(0, 0, 200, 100, stroke=0, fill=1)
        page.showPage()
        page.save()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_page_is_rasterized(self) -> None:
        png = convert_pdf_to_png(self.pdf, dpi=72)
        self.assertTrue(png.exists())
        self.assertEqual(png.read_bytes()[:4], b"\x89PNG")
        # Cachen återanvänds
        self.assertEqual(convert_pdf_to_png(self.pdf, dpi=72), png)

    def test_pdf_logo_is_loaded_as_image(self) -> None:
        logo = PdfLogo.load(self.pdf)
        self.assertFalse(logo.vector)
        self.assertEqual(logo.path, self.pdf)
        self.assertLessEqual(logo.width, 35.0 * MM + 0.01)
        self.assertLessEqual(logo.height, 16.0 * MM + 0.01)

    def test_missing_pdf_raises(self) -> None:
        with self.assertRaises(AssetError):
            convert_pdf_to_png(self.tmp / "saknas.pdf")


class LogoScaleTests(unittest.TestCase):
    """Storleksreglaget 25–300 % (v2.11.0)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.png = self.tmp / "logo.png"
        _write_png(self.png, 400, 200)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scale_is_stored_on_the_logo(self) -> None:
        logo = PdfLogo.load(self.png, scale=1.5)
        self.assertAlmostEqual(logo.scale, 1.5, places=3)

    def test_scale_changes_the_loaded_size(self) -> None:
        small = PdfLogo.load(self.png, max_width_mm=10, max_height_mm=10)
        large = PdfLogo.load(self.png, max_width_mm=10, max_height_mm=10, scale=2.0)
        self.assertAlmostEqual(large.width / small.width, 2.0, places=2)
        self.assertAlmostEqual(large.height / small.height, 2.0, places=2)

    def test_auto_size_follows_the_scale(self) -> None:
        logo = PdfLogo.load(self.png, scale=0.5)
        width, height = logo.auto_size(842.0, 595.0)
        plain = PdfLogo.load(self.png, max_width_mm=35, max_height_mm=16)
        full_w, full_h = plain.auto_size(842.0, 595.0)
        self.assertAlmostEqual(width, full_w * 0.5, places=2)
        self.assertAlmostEqual(height, full_h * 0.5, places=2)

    def test_auto_size_never_leaves_the_page(self) -> None:
        logo = PdfLogo.load(self.png, scale=5.0)
        width, height = logo.auto_size(200.0, 100.0)
        self.assertLess(width, 200.0)
        self.assertLess(height, 100.0)

    def test_auto_size_is_capped_so_the_legend_stays_visible(self) -> None:
        """Även 300 % får plats ovanför färgförklaringen (v2.11.0)."""
        logo = PdfLogo.load(self.png, scale=3.0)
        width, height = logo.auto_size(842.0, 595.0)
        self.assertLessEqual(height, 595.0 * SCALE_MAX_HEIGHT_RATIO + 0.01)
        self.assertLessEqual(width, 842.0 * SCALE_MAX_WIDTH_RATIO + 0.01)

    def test_logo_for_settings_reads_the_percentage(self) -> None:
        logo = logo_for_settings({"logo_svg": str(self.png), "logo_scale": 200})
        self.assertIsNotNone(logo)
        self.assertAlmostEqual(logo.scale, 2.0, places=3)

    def test_logo_for_settings_defaults_to_100(self) -> None:
        for value in (None, "", "abc", 0.5):
            settings = {"logo_svg": str(self.png)}
            if value is not None:
                settings["logo_scale"] = value
            logo = logo_for_settings(settings)
            self.assertIsNotNone(logo)
            self.assertGreaterEqual(logo.scale, LOGO_SCALE_MIN / 100.0)
            self.assertLessEqual(logo.scale, LOGO_SCALE_MAX / 100.0)

    def test_logo_for_settings_clamps_extremes(self) -> None:
        low = logo_for_settings({"logo_svg": str(self.png), "logo_scale": 1})
        high = logo_for_settings({"logo_svg": str(self.png), "logo_scale": 9999})
        self.assertAlmostEqual(low.scale, LOGO_SCALE_MIN / 100.0, places=3)
        self.assertAlmostEqual(high.scale, LOGO_SCALE_MAX / 100.0, places=3)
