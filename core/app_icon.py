#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Appikon – samma ikon överallt (v2.7.0)
=======================================

Ikonen finns som SVG, PNG (16–256 px) och ICO i ``assets/ikon/`` och
används av:

    - huvudfönstret               (setWindowIcon)
    - systemfältet / tray         (QSystemTrayIcon)
    - aktivitetsfältet (Windows)  (AppUserModelID + ikon → rätt ikon i
                                   aktivitetshanteraren och på aktivitetsfältet)
    - dialoger (Listredigeraren, logotypväljaren, inställningar)
    - meddelanderutor             (ärver applikationens ikon)

Exempel:
    from core.app_icon import app_icon, apply_app_icon

    apply_app_icon(app)            # sätter applikationens ikon
    my_window.setWindowIcon(app_icon())

Saknas bildfilerna ritas ikonen programmatiskt (samma form och färger),
så appen aldrig visas utan ikon.

Bygg om PNG/ICO efter ändring i SVG:n:

    python tools/make_icons.py

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

MODULE_VERSION: str = "2.13.2"

#: Filnamn (utan ändelse) för ikonen i assets/ikon/
APP_ICON_STEM: str = "appikon"

#: Mapp med ikonerna, relativt appens rot
APP_ICON_DIR: str = "assets/ikon"

#: Storlekar som finns som PNG
APP_ICON_SIZES: tuple = (16, 24, 32, 48, 64, 128, 256)

#: Windows AppUserModelID – grupperar fönster och ger rätt ikon i
#: aktivitetsfältet/aktivitetshanteraren i stället för Python-ikonen.
WINDOWS_APP_ID: str = "Tokke2.Semesterlista"

#: Färger (samma som assets/ikon/appikon.svg)
ICON_BLUE: str = "#14507d"
ICON_YELLOW: str = "#f2b705"
ICON_WHITE: str = "#ffffff"

_cache: Optional[Any] = None


# ══════════════════════════════════════════════════════════
# FILER
# ══════════════════════════════════════════════════════════

def icon_dir() -> Path:
    """Sökväg till mappen med ikonerna (assets/ikon)."""
    from core.roster import resolve_path

    return resolve_path(APP_ICON_DIR)


def icon_files() -> List[Path]:
    """
    Alla befintliga ikonfiler, minsta PNG först.

    Ordningen är viktig: Qt väljer den bild som passar bäst för varje
    storlek, men SVG/ICO läggs sist eftersom de kan saknas.
    """
    folder = icon_dir()
    files: List[Path] = []

    for size in APP_ICON_SIZES:
        candidate = folder / f"{APP_ICON_STEM}-{size}.png"
        if candidate.exists():
            files.append(candidate)

    ico = folder / f"{APP_ICON_STEM}.ico"
    if ico.exists():
        files.append(ico)

    svg = folder / f"{APP_ICON_STEM}.svg"
    if svg.exists():
        files.append(svg)

    return files


# ══════════════════════════════════════════════════════════
# IKON
# ══════════════════════════════════════════════════════════

def fallback_icon() -> Any:
    """
    Rita ikonen programmatiskt (används om bildfilerna saknas).

    Returns:
        QIcon, eller en tom QIcon om Qt inte kan rita (t.ex. utan skärm).
    """
    try:
        from PySide6.QtCore import QPointF, QRectF, Qt
        from PySide6.QtGui import (
            QColor,
            QIcon,
            QPainter,
            QPen,
            QPixmap,
            QPolygonF,
        )

        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        # Blå platta
        painter.setBrush(QColor(ICON_BLUE))
        painter.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)

        # Vit kalender
        painter.setBrush(QColor(ICON_WHITE))
        painter.drawRoundedRect(QRectF(13, 17, 38, 34), 5, 5)

        # Gul rubrik
        painter.setBrush(QColor(ICON_YELLOW))
        painter.drawRect(QRectF(13, 22, 38, 4))

        # Gul bock
        pen = QPen(QColor(ICON_YELLOW), 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(QPolygonF([
            QPointF(24, 37), QPointF(30, 43), QPointF(41, 30),
        ]))
        painter.end()

        return QIcon(pixmap)

    except Exception as exc:  # pragma: no cover – Qt saknas
        logger.warning(f"Kunde inte rita reservikon: {exc}")
        return _empty_icon()


def _empty_icon() -> Any:
    """Tom QIcon (eller None om Qt saknas helt)."""
    try:
        from PySide6.QtGui import QIcon

        return QIcon()
    except Exception:  # pragma: no cover
        return None


def app_icon(force_reload: bool = False) -> Any:
    """
    Applikationens ikon i alla tillgängliga storlekar.

    Args:
        force_reload: Bygg om ikonen (används av tester).

    Returns:
        QIcon med PNG:er/ICO/SVG, annars en programmatiskt ritad ikon.
    """
    global _cache

    if _cache is not None and not force_reload:
        return _cache

    try:
        from PySide6.QtGui import QIcon
    except Exception:  # pragma: no cover – Qt saknas
        return _empty_icon()

    files = icon_files()
    if not files:
        logger.debug("Inga ikonfiler hittades – använder ritad ikon")
        _cache = fallback_icon()
        return _cache

    icon = QIcon()
    for path in files:
        icon.addFile(str(path))

    if icon.isNull() or not icon.availableSizes():
        logger.warning("Ikonfilerna kunde inte läsas – använder ritad ikon")
        _cache = fallback_icon()
        return _cache

    logger.debug(f"Appikon laddad från {len(files)} fil(er)")
    _cache = icon
    return _cache


def apply_app_icon(app: Optional[Any] = None) -> Any:
    """
    Sätt applikationens ikon (påverkar alla fönster och dialoger).

    Args:
        app: QApplication (annars hämtas den aktiva instansen).

    Returns:
        Den ikon som sattes.
    """
    icon = app_icon()

    try:
        from PySide6.QtWidgets import QApplication

        target = app if app is not None else QApplication.instance()
        if target is not None and icon is not None and not icon.isNull():
            target.setWindowIcon(icon)

        # Linux/wayland: koppla ikonen till .desktop-filen
        if sys.platform.startswith("linux"):
            try:
                target.setDesktopFileName("semesterlista")  # type: ignore[union-attr]
            except Exception:
                pass

    except Exception as exc:  # pragma: no cover – defensivt
        logger.warning(f"Kunde inte sätta appikon: {exc}")

    return icon


def set_windows_app_user_model_id(app_id: str = WINDOWS_APP_ID) -> bool:
    """
    Sätt AppUserModelID så att Windows visar rätt ikon i aktivitetsfältet
    och grupperar fönstret under appen (inte under python.exe).

    Anropas innan fönstret skapas; gör inget på andra plattformar.

    Returns:
        True om ID:t sattes.
    """
    if sys.platform != "win32":
        return False

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        logger.debug(f"AppUserModelID satt till {app_id}")
        return True
    except Exception as exc:  # pragma: no cover – endast Windows
        logger.warning(f"Kunde inte sätta AppUserModelID: {exc}")
        return False


def clear_cache() -> None:
    """Glöm cachelagrad ikon (används av tester)."""
    global _cache
    _cache = None


__all__ = [
    "APP_ICON_STEM",
    "APP_ICON_DIR",
    "APP_ICON_SIZES",
    "WINDOWS_APP_ID",
    "app_icon",
    "apply_app_icon",
    "clear_cache",
    "fallback_icon",
    "icon_dir",
    "icon_files",
    "set_windows_app_user_model_id",
    "MODULE_VERSION",
]
