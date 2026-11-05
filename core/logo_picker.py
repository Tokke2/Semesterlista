#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logotypväljare med dropdown (v2.10.0)
=====================================

En liten widget som låter användaren infoga en logotyp till PDF-exporten:

    ┌──────────────────────────────────────────────────────────┐
    │ [logotyper/foretag.svg        ▼]  [Infoga SVG…] [Uppdatera] │
    │ ┌──────────────────────────────────────────────────────┐ │
    │ │              förhandsgranskning (skalas)             │ │
    │ └──────────────────────────────────────────────────────┘ │
    └──────────────────────────────────────────────────────────┘

* Dropdown-listan visar alla **SVG-logotyper** i appens mapp ``assets/``
  **och dess undermappar** (samma sökning som ``core/pdf_assets.py``).
* **Infoga logotyp…** låter användaren välja en fil utanför assets-mappen –
  **SVG, EPS, PDF, PNG eller JPG**.
* **EPS** konverteras med Ghostscript och **PDF** rastreras med PyMuPDF
  (v2.11.0); saknas Ghostscript visas en förklaring i förhandsgranskningen.
* **Storleksreglaget** (25–300 %) anpassar logotypens storlek i PDF:en –
  proportionerna behålls alltid.
* Förhandsgranskningen **anpassar storleken automatiskt** – bilden skalas
  alltid till att passa ytan och behåller sina proportioner.
* I den genererade PDF:en anpassas logotypen automatiskt efter sidans
  storlek (se ``PdfLogo.auto_size()`` i ``core/pdf_assets.py``).

Användning:

    from core.logo_picker import LogoPicker

    self.logo_picker = LogoPicker(current=settings.get("logo_svg", ""), parent=self)
    self.logo_picker.changed.connect(self._on_logo_changed)   # (str) → ny sökväg

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.pdf_assets import (
    EPS_SUFFIXES,
    LOGO_SCALE_DEFAULT,
    LOGO_SCALE_MAX,
    LOGO_SCALE_MIN,
    PDF_SUFFIXES,
    SVG_SUFFIXES,
    AssetError,
    AssetFile,
    assets_root,
    convert_eps_to_png,
    convert_pdf_to_png,
    scan_assets,
)

logger = logging.getLogger(__name__)

MODULE_VERSION: str = "2.15.0"

#: Höjd på förhandsgranskningen (px) – bredden följer fönstret
PREVIEW_HEIGHT: int = 56

#: Minsta storlek innan förhandsgranskningen ritas om
PREVIEW_MIN_SIZE: QSize = QSize(40, 24)


class LogoPicker(QWidget):
    """
    Dropdown + knappar + automatisk förhandsgranskning för PDF-logotypen.

    Signaler:
        changed (str): ny sökväg ("" = ingen logotyp).
    """

    changed = Signal(str)
    #: Ny storlek i procent (v2.11.0)
    scale_changed = Signal(int)

    def __init__(
        self,
        current: str = "",
        root: Optional[Union[str, Path]] = None,
        parent: Optional[QWidget] = None,
        show_preview: bool = True,
        scale: int = LOGO_SCALE_DEFAULT,
    ):
        super().__init__(parent)

        self._root = Path(root) if root is not None else assets_root()
        self._current = str(current or "")
        self._assets: List[AssetFile] = []
        self._pixmap: Optional[QPixmap] = None
        self._show_preview = show_preview
        self._scale = self._clamp_scale(scale)

        self._build_ui()
        self.refresh(emit=False)
        self.set_current(self._current, emit=False)

    # ──────────────────────────────────────────────────────
    # Bygge
    # ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        from core.ui_layout import FlowLayout
        row = FlowLayout()
        row.setSpacing(6)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(220)
        self.combo.setToolTip(t("logo.dialog_hint"))
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        row.addWidget(self.combo)

        self.insert_button = QPushButton("🖼️ " + t("logo.insert"))
        self.insert_button.setToolTip(t("logo.insert_tooltip"))
        self.insert_button.clicked.connect(self._insert_file)
        row.addWidget(self.insert_button)

        self.rescan_button = QPushButton(t("logo.rescan"))
        self.rescan_button.setToolTip(t("logo.rescan_tooltip"))
        self.rescan_button.clicked.connect(lambda: self.refresh(emit=True))
        row.addWidget(self.rescan_button)

        layout.addLayout(row)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(PREVIEW_HEIGHT)
        self.preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.preview.setStyleSheet(self._preview_style())
        self.preview.setToolTip(t("logo.auto_size"))
        self.preview.setVisible(self._show_preview)
        layout.addWidget(self.preview)

        # Storleksreglage (v2.11.0) – proportionerna låses, bara skalan ändras
        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        self.size_label = QLabel(t("logo.size_label"))
        size_row.addWidget(self.size_label)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(LOGO_SCALE_MIN, LOGO_SCALE_MAX)
        self.size_spin.setSingleStep(5)
        self.size_spin.setSuffix(" %")
        self.size_spin.setValue(self._scale)
        self.size_spin.setToolTip(t("logo.size_tooltip"))
        self.size_spin.valueChanged.connect(self._on_scale_changed)
        size_row.addWidget(self.size_spin)

        self.size_hint = QLabel(t("logo.size_hint"))
        self.size_hint.setProperty("role", "muted")
        size_row.addWidget(self.size_hint, 1)
        layout.addLayout(size_row)

    # ──────────────────────────────────────────────────────
    # Listan
    # ──────────────────────────────────────────────────────

    def refresh(self, emit: bool = False) -> None:
        """
        Läs om assets-mappen och fyll dropdown-listan.

        v2.10.0: endast SVG-logotyper listas (``SVG_SUFFIXES``) – appens
        undermappar genomsöks rekursivt. Andra bildformat kan fortfarande
        infogas med *Infoga SVG…* och ritas då som vanligt i PDF:en.
        """
        try:
            self._assets = scan_assets(self._root, suffixes=SVG_SUFFIXES)
        except Exception as exc:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte läsa logotyper: {exc}")
            self._assets = []

        previous = self._current
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(t("logo.no_logo"), "")

        for asset in self._assets:
            self.combo.addItem(asset.relative, str(asset.path))

        self.combo.blockSignals(False)

        # Behåll (eller lägg till) det som redan är valt
        self.set_current(previous, emit=False, add_missing=True)
        if emit:
            self.changed.emit(self._current)

    def assets(self) -> List[AssetFile]:
        """Alla SVG-logotyper som hittades vid senaste genomsökningen."""
        return list(self._assets)

    # ──────────────────────────────────────────────────────
    # Val
    # ──────────────────────────────────────────────────────

    def current_path(self) -> str:
        """Vald sökväg ("" om ingen logotyp)."""
        return self._current

    def set_current(
        self,
        path: str,
        emit: bool = True,
        add_missing: bool = True,
    ) -> None:
        """
        Markera en sökväg i listan och visa den i förhandsgranskningen.

        Args:
            path:        Sökväg till logotypen ("" = ingen).
            emit:        Skicka ``changed``-signalen.
            add_missing: Lägg till filen i listan om den ligger utanför
                         assets-mappen.
        """
        path = str(path or "")
        index = self._index_of(path)

        if index < 0 and path and add_missing and Path(path).exists():
            target = Path(path)
            label = target.name if target.name else str(target)
            if not self._is_inside_assets(target):
                label = f"{label}  ({t('logo.outside_assets')})"
            self.combo.blockSignals(True)
            self.combo.addItem(label, path)
            self.combo.blockSignals(False)
            index = self.combo.count() - 1

        if index < 0:
            index = 0
            path = ""

        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)

        self._current = path
        self._load_preview(path)

        if emit:
            self.changed.emit(self._current)

    def clear(self) -> None:
        """Ta bort logotypen."""
        self.set_current("", emit=True)

    # ──────────────────────────────────────────────────────
    # Storlek (v2.11.0)
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _clamp_scale(scale: int) -> int:
        """Håll reglaget inom tillåtna gränser."""
        try:
            value = int(scale)
        except (TypeError, ValueError):
            value = LOGO_SCALE_DEFAULT
        return max(LOGO_SCALE_MIN, min(value, LOGO_SCALE_MAX))

    def scale(self) -> int:
        """Storleken i procent (100 = automatisk storlek)."""
        return self._scale

    def set_scale(self, scale: int, emit: bool = False) -> None:
        """
        Ställ in storleken i procent.

        Args:
            scale: 25–300 (100 = automatisk storlek).
            emit:  Skicka ``scale_changed``.
        """
        value = self._clamp_scale(scale)
        if value != self.size_spin.value():
            self.size_spin.blockSignals(True)
            self.size_spin.setValue(value)
            self.size_spin.blockSignals(False)
        changed = value != self._scale
        self._scale = value
        self._apply_preview()
        if emit and changed:
            self.scale_changed.emit(value)

    def _on_scale_changed(self, value: int) -> None:
        self._scale = self._clamp_scale(value)
        self._apply_preview()
        self.scale_changed.emit(self._scale)

    # ──────────────────────────────────────────────────────
    # Infoga
    # ──────────────────────────────────────────────────────

    def file_filter(self) -> str:
        """Filtersträngen som *Infoga logotyp…* använder."""
        return (
            f"{t('logo.filter_all')} (*.svg *.eps *.pdf *.png *.jpg *.jpeg);;"
            f"SVG (*.svg);;EPS (*.eps);;PDF (*.pdf);;"
            f"{t('logo.filter_images')} (*.png *.jpg *.jpeg);;"
            f"{t('logo.filter_any')} (*)"
        )

    def _index_of(self, path: str) -> int:
        if not path:
            return 0 if self.combo.count() else -1

        target = Path(path)
        for index in range(self.combo.count()):
            data = str(self.combo.itemData(index) or "")
            if not data:
                continue
            if Path(data) == target:
                return index
        return -1

    def _is_inside_assets(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._root.resolve())
            return True
        except (ValueError, OSError):
            return False

    # ──────────────────────────────────────────────────────
    # Åtgärder
    # ──────────────────────────────────────────────────────

    def _on_combo_changed(self, index: int) -> None:
        path = str(self.combo.itemData(index) or "")
        self._current = path
        self._load_preview(path)
        self.changed.emit(path)

    def _insert_file(self) -> None:
        """Infoga SVG/EPS/PDF/PNG/JPG som ligger utanför assets-mappen."""
        start = str(self._root)
        current = self._current
        if current and Path(current).parent.exists():
            start = str(Path(current).parent)

        filename, _selected = QFileDialog.getOpenFileName(
            self,
            t("logo.dialog_title"),
            start,
            self.file_filter(),
        )
        if not filename:
            return

        logger.info(f"Logotyp infogad: {filename}")
        self.set_current(filename, emit=True, add_missing=True)

    # ──────────────────────────────────────────────────────
    # Förhandsgranskning (skalas automatiskt)
    # ──────────────────────────────────────────────────────

    def _load_preview(self, path: str) -> None:
        """Ladda bilden och rita den i den storlek som ytan har."""
        self._pixmap = None

        if not path:
            self.preview.clear()
            self.preview.setStyleSheet(self._preview_style())
            self.preview.setToolTip(t("logo.no_logo"))
            return

        target = Path(path)
        if not target.exists():
            self.preview.clear()
            self.preview.setText(t("logo.missing_file", path=target.name))
            self.preview.setStyleSheet("color: #c0392b; font-size: 11px;")
            return

        self.preview.setStyleSheet(self._preview_style())

        try:
            pixmap = self._pixmap_for(target)
            self._pixmap = None if pixmap.isNull() else pixmap
        except AssetError as exc:
            logger.warning(f"Kunde inte läsa logotypen: {exc}")
            self._pixmap = None
            self.preview.setPixmap(QPixmap())
            self.preview.setStyleSheet("color: #c0392b; font-size: 10px;")
            self.preview.setWordWrap(True)
            self.preview.setText(str(exc))
            return
        except Exception as exc:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte läsa logotypen: {exc}")
            self._pixmap = None

        if self._pixmap is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(t("logo.error", error=target.name))
            return

        self.preview.setText("")
        self._apply_preview()

    def _pixmap_for(self, target: Path) -> QPixmap:
        """
        Läs en logotyp som QPixmap, oavsett format (v2.11.0).

        EPS konverteras med Ghostscript och PDF rastreras med PyMuPDF –
        samma väg som PDF-exporten använder, så förhandsgranskningen visar
        det användaren faktiskt får.
        """
        suffix = target.suffix.lower()
        if suffix in SVG_SUFFIXES:
            return _render_svg(target, self._preview_box())
        if suffix in EPS_SUFFIXES:
            return QPixmap(str(convert_eps_to_png(target)))
        if suffix in PDF_SUFFIXES:
            return QPixmap(str(convert_pdf_to_png(target)))
        return QPixmap(str(target))

    def _preview_style(self) -> str:
        """Ram runt förhandsgranskningen (transparent när den är avstängd)."""
        if not self._show_preview:
            return "background: transparent;"
        return "background: #ffffff; border: 1px solid #ccc; border-radius: 4px;"

    def _preview_box(self) -> QSize:
        """Ytan som förhandsgranskningen får plats i."""
        width = max(self.preview.width() - 8, PREVIEW_MIN_SIZE.width())
        height = max(self.preview.height() - 4, PREVIEW_MIN_SIZE.height())
        return QSize(width, height)

    def _apply_preview(self) -> None:
        """
        Skala bilden så att den passar ytan (behåller proportioner).

        Storleksreglaget syns direkt: 50 % ger en halv så stor logotyp i
        rutan, 200 % fyller rutan helt (v2.11.0).
        """
        if self._pixmap is None:
            return

        box = self._preview_box()
        # 100 % = hela rutan (den automatiska storleken), 50 % = halva rutan,
        # över 100 % kan aldrig bli större än rutan
        factor = min(self._scale / 100.0, 1.0)
        target = QSize(
            max(1, int(round(box.width() * factor))),
            max(1, int(round(box.height() * factor))),
        )

        scaled = self._pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # noqa: N802 – Qt-API
        super().resizeEvent(event)
        self._apply_preview()

    def showEvent(self, event) -> None:  # noqa: N802 – Qt-API
        super().showEvent(event)
        self._apply_preview()


def _render_svg(path: Path, target: QSize) -> QPixmap:
    """Rendera en SVG till en QPixmap som passar i ``target``."""
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return QPixmap()

    size = renderer.defaultSize()
    if size.isEmpty():
        size = target

    # Rendera i ytans storlek men behåll proportionerna
    scaled = size.scaled(target, Qt.AspectRatioMode.KeepAspectRatio)
    if scaled.isEmpty():
        scaled = target

    pixmap = QPixmap(scaled)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    try:
        renderer.render(painter)
    finally:
        painter.end()

    return pixmap


__all__ = ["LogoPicker", "PREVIEW_HEIGHT", "MODULE_VERSION"]
