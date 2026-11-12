#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Appikon – samma ikon överallt (v2.7.0)
=======================================

Ikonen finns som SVG, PNG (16–256 px) och ICO i ``assets/ikon/`` och
används av:

    - huvudfönstret               (setWindowIcon)
    - systemfältet / tray         (QSystemTrayIcon)
    - aktivitetsfältet (Windows)  (AppUserModelID + ikon för aktivitetsfältet;
                                   processdetaljer kan fortfarande visa Python)
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

MODULE_VERSION: str = "2.21.1"

#: Filnamn (utan ändelse) för ikonen i assets/ikon/
APP_ICON_STEM: str = "appikon"

#: Mapp med ikonerna, relativt appens rot
APP_ICON_DIR: str = "assets/ikon"

#: Storlekar som finns som PNG
APP_ICON_SIZES: tuple = (16, 24, 32, 48, 64, 128, 256)

#: Windows AppUserModelID – grupperar fönster och ger rätt ikon i
#: aktivitetsfältet. Ändrar inte pythonw.exe:s inbyggda processikon.
WINDOWS_APP_ID: str = "Tokke2.Semesterlista"

#: Färger (samma som assets/ikon/appikon.svg)
ICON_BLUE: str = "#16324f"
ICON_YELLOW: str = "#36d6be"
ICON_WHITE: str = "#ffffff"

ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">\n  <defs>\n    <linearGradient id="icon-base" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#16324f"/><stop offset="0.55" stop-color="#4231a5"/><stop offset="1" stop-color="#7656ee"/></linearGradient>\n    <linearGradient id="icon-edge" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#75e8ff"/><stop offset="1" stop-color="#a68aff"/></linearGradient>\n    <linearGradient id="icon-page" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#e5f3ff"/></linearGradient>\n    <linearGradient id="icon-header" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#409cff"/><stop offset="1" stop-color="#8561ff"/></linearGradient>\n    <linearGradient id="icon-badge" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#a5ffe0"/><stop offset="0.5" stop-color="#36d6be"/><stop offset="1" stop-color="#3bd3ff"/></linearGradient>\n  </defs>\n  <rect x="2" y="2" width="60" height="60" rx="17" fill="url(#icon-base)" stroke="url(#icon-edge)" stroke-width="1.2"/>\n  <path d="M19 3h25c8 0 14 6 16 14L4 37V19C4 10 10 3 19 3z" fill="#ffffff" opacity="0.12"/>\n  <g transform="rotate(-8 30 32)">\n    <rect x="12" y="17" width="36" height="35" rx="5" fill="#16324f" opacity="0.24"/>\n    <rect x="11" y="14" width="36" height="35" rx="5" fill="url(#icon-page)"/>\n    <path d="M16 14h26a5 5 0 0 1 5 5v7H11v-7a5 5 0 0 1 5-5z" fill="url(#icon-header)"/>\n    <path d="M20 11v8m18-8v8" stroke="#ffffff" stroke-width="3.8" stroke-linecap="round"/>\n    <rect x="18" y="31" width="5" height="5" rx="1.4" fill="#6556ed"/>\n    <rect x="27" y="31" width="5" height="5" rx="1.4" fill="#6556ed"/>\n    <rect x="18" y="40" width="5" height="5" rx="1.4" fill="#16324f"/>\n  </g>\n  <circle cx="46" cy="47" r="12" fill="url(#icon-badge)" stroke="#ffffff" stroke-width="1.3"/>\n  <path d="M40 47l4 4 8-9" fill="none" stroke="#16324f" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>\n  <path d="M52 7l1.7 4.3L58 13l-4.3 1.7L52 19l-1.7-4.3L46 13l4.3-1.7z" fill="#ffcb77"/>\n</svg>\n'

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
        from PySide6.QtCore import QByteArray, Qt
        from PySide6.QtGui import QIcon, QPainter, QPixmap
        from PySide6.QtSvg import QSvgRenderer
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            QSvgRenderer(QByteArray(ICON_SVG.encode('utf-8'))).render(painter)
        finally:
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

        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        if setter(app_id) != 0:
            return False
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
