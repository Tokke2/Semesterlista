#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bygg appikonerna från assets/ikon/appikon.svg (v2.7.0)
======================================================

Körs när SVG-filen ändrats:

    python tools/make_icons.py

Skriptet skapar:
    assets/ikon/appikon-16.png … appikon-256.png   (Qt, QSvgRenderer)
    assets/ikon/appikon.ico                         (multi-size, PNG-baserad)

Kräver PySide6 (samma beroende som appen). Inga andra verktyg behövs.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "ikon"
SVG_FILE = ICON_DIR / "appikon.svg"
ICO_FILE = ICON_DIR / "appikon.ico"

#: Storlekar som rasteriseras (Windows-ikoner + HiDPI)
SIZES = (16, 24, 32, 48, 64, 128, 256)

#: Storlekar som bäddas in i .ico
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_pngs() -> None:
    """Rendera SVG:n till PNG i alla storlekar."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(SVG_FILE))
    if not renderer.isValid():
        raise SystemExit(f"Ogiltig SVG: {SVG_FILE}")

    for size in SIZES:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            renderer.render(painter)
        finally:
            painter.end()

        target = ICON_DIR / f"appikon-{size}.png"
        if not image.save(str(target), "PNG"):
            raise SystemExit(f"Kunde inte spara {target}")
        print(f"  {target.name}  ({size}×{size})")


def build_ico() -> None:
    """Bygg en multi-size .ico med PNG-bilder (Vista+)."""
    entries = []
    payload = b""

    for size in ICO_SIZES:
        png = (ICON_DIR / f"appikon-{size}.png").read_bytes()
        width = 0 if size >= 256 else size
        height = 0 if size >= 256 else size
        offset = 6 + 16 * len(ICO_SIZES) + len(payload)
        entries.append(struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32,
                                   len(png), offset))
        payload += png

    header = struct.pack("<HHH", 0, 1, len(ICO_SIZES))
    ICO_FILE.write_bytes(header + b"".join(entries) + payload)
    print(f"  {ICO_FILE.name}  ({len(ICO_SIZES)} storlekar, "
          f"{ICO_FILE.stat().st_size} byte)")


def main() -> int:
    if not SVG_FILE.exists():
        raise SystemExit(f"Saknar {SVG_FILE}")

    print(f"Bygger ikoner från {SVG_FILE.relative_to(ROOT)}")
    render_pngs()
    build_ico()
    print("Klart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
