#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logotypväljare (v2.8.0)
=======================

Dialog som visar alla bilder som ligger i appens assets-mapp (även
undermappar) och låter användaren välja en logotyp till PDF-exporten.

    from core.logo_dialog import choose_logo

    vald, path = choose_logo(self, current=settings.get("logo_svg", ""))
    if vald:
        settings["logo_svg"] = path      # "" = ingen logotyp

Kan även användas fristående:
    LogoDialog(parent, current="assets/logotyper/foretag.svg").exec()

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple, Union

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.pdf_assets import AssetFile, assets_root, ensure_assets_dir, scan_assets

logger = logging.getLogger(__name__)

MODULE_VERSION: str = "2.9.0"

#: Data-roll för den valda sökvägen på listobjekt
_PATH_ROLE = Qt.ItemDataRole.UserRole

PREVIEW_WIDTH: int = 320
PREVIEW_HEIGHT: int = 200


class LogoDialog(QDialog):
    """
    Välj en logotyp från assets-mappen.

    Attribut:
        selected_path (str): vald sökväg, "" om ingen logotyp ska användas.
        cancelled     (bool): True om användaren avbröt.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        current: str = "",
        root: Optional[Union[str, Path]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(t("logo.dialog_title"))
        self.setMinimumSize(680, 440)

        # Samma appikon som huvudfönstret (v2.7.0)
        try:
            from core.app_icon import app_icon

            self.setWindowIcon(app_icon())
        except Exception:  # pragma: no cover – defensivt
            pass

        self._root = Path(root) if root is not None else assets_root()
        self._assets: List[AssetFile] = []
        self.selected_path: str = str(current or "")
        self.cancelled: bool = True

        self._preview_svg: Optional[QSvgWidget] = None
        self._build_ui()
        self._reload()
        self._select_current()

    # ──────────────────────────────────────────────────────
    # Bygge
    # ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(t("logo.dialog_title"))
        title.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        hint = QLabel(
            t("logo.dialog_hint") + "\n" + t("logo.folder", path=str(self._root))
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        content = QHBoxLayout()
        content.setSpacing(12)

        # Vänster: lista med bilder
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(QLabel(t("logo.assets")))

        self._list = QListWidget()
        self._list.setFixedWidth(280)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.currentItemChanged.connect(self._on_current_changed)
        self._list.itemDoubleClicked.connect(lambda _item: self._accept())
        left.addWidget(self._list, 1)

        browse = QPushButton(t("logo.browse"))
        browse.clicked.connect(self._browse)
        left.addWidget(browse)

        rescan = QPushButton(t("logo.rescan"))
        rescan.clicked.connect(self._reload)
        left.addWidget(rescan)

        content.addLayout(left)

        # Höger: förhandsgranskning
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(QLabel(t("logo.preview")))

        self._preview = QStackedWidget()
        self._preview.setMinimumSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        self._preview.setStyleSheet(
            "background: #ffffff; border: 1px solid #ccc; border-radius: 6px;"
        )

        self._empty_label = QLabel(t("logo.empty"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet("color: #888;")
        self._preview.addWidget(self._empty_label)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.addWidget(self._image_label)

        self._svg_holder = QWidget()
        svg_layout = QVBoxLayout(self._svg_holder)
        svg_layout.setContentsMargins(0, 0, 0, 0)
        self._preview.addWidget(self._svg_holder)

        right.addWidget(self._preview)
        content.addLayout(right, 1)

        layout.addLayout(content, 1)

        # Knapprad
        buttons = QHBoxLayout()
        self._clear_button = QPushButton(t("logo.clear"))
        self._clear_button.clicked.connect(self._clear)
        buttons.addWidget(self._clear_button)
        buttons.addStretch()

        box = QDialogButtonBox()
        self._ok_button = box.addButton(t("logo.ok"), QDialogButtonBox.ButtonRole.AcceptRole)
        self._cancel_button = box.addButton(
            t("logo.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        buttons.addWidget(box)
        layout.addLayout(buttons)

    # ──────────────────────────────────────────────────────
    # Innehåll
    # ──────────────────────────────────────────────────────

    def _reload(self) -> None:
        """Läs om assets-mappen och fyll listan."""
        if self._root.name.casefold() == "assets":
            ensure_assets_dir(self._root)
        self._assets = scan_assets(self._root)
        self._list.clear()

        for asset in self._assets:
            item = QListWidgetItem(asset.relative)
            item.setData(_PATH_ROLE, str(asset.path))
            item.setToolTip(str(asset.path))
            self._list.addItem(item)

        if not self._assets:
            self._current_asset = None
            self._show_empty()
        else:
            self._list.setCurrentRow(0)

    def _select_current(self) -> None:
        """Markera den logotyp som redan är vald."""
        if not self.selected_path:
            return

        target = Path(self.selected_path)
        for row in range(self._list.count()):
            item = self._list.item(row)
            if Path(str(item.data(_PATH_ROLE))) == target:
                self._list.setCurrentRow(row)
                return

        # Filen finns utanför assets – lägg till den tillfälligt i listan
        if target.exists():
            item = QListWidgetItem(f"{target.name}  ({t('logo.outside_assets')})")
            item.setData(_PATH_ROLE, str(target))
            item.setToolTip(str(target))
            self._list.addItem(item)
            self._list.setCurrentItem(item)

    def _on_current_changed(
        self, current: Optional[QListWidgetItem], _previous: Optional[QListWidgetItem] = None
    ) -> None:
        if current is None:
            self._show_empty()
            return

        path = Path(str(current.data(_PATH_ROLE)))
        if not path.exists():
            self._show_message(t("logo.missing", path=str(path)))
            return

        if path.suffix.lower() == ".svg":
            self._show_svg(path)
        else:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self._show_message(t("logo.error", error=path.name))
                return
            self._image_label.setPixmap(
                pixmap.scaled(
                    QSize(PREVIEW_WIDTH - 16, PREVIEW_HEIGHT - 16),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._preview.setCurrentWidget(self._image_label)

    def _show_svg(self, path: Path) -> None:
        """Visa SVG i en QSvgWidget (skapas på nytt per fil)."""
        if self._preview_svg is not None:
            self._preview_svg.deleteLater()
            self._preview_svg = None

        svg = QSvgWidget(str(path))
        svg.setMinimumSize(QSize(PREVIEW_WIDTH - 16, PREVIEW_HEIGHT - 16))
        layout = self._svg_holder.layout()
        if layout is not None:
            layout.addWidget(svg)
        self._preview_svg = svg
        self._preview.setCurrentWidget(self._svg_holder)

    def _show_empty(self) -> None:
        self._empty_label.setText(t("logo.empty"))
        self._preview.setCurrentWidget(self._empty_label)

    def _show_message(self, message: str) -> None:
        self._empty_label.setText(message)
        self._preview.setCurrentWidget(self._empty_label)

    # ──────────────────────────────────────────────────────
    # Åtgärder
    # ──────────────────────────────────────────────────────

    def _browse(self) -> None:
        """Välj en fil utanför assets-mappen."""
        filename, _filter = QFileDialog.getOpenFileName(
            self,
            t("logo.dialog_title"),
            str(self._root),
            "Bilder (*.svg *.png *.jpg *.jpeg);;SVG (*.svg)",
        )
        if not filename:
            return

        self.selected_path = filename

        # Markera i listan om filen redan finns där
        for row in range(self._list.count()):
            if str(self._list.item(row).data(_PATH_ROLE)) == filename:
                self._list.setCurrentRow(row)
                return

        item = QListWidgetItem(Path(filename).name)
        item.setData(_PATH_ROLE, filename)
        item.setToolTip(filename)
        self._list.addItem(item)
        self._list.setCurrentItem(item)

    def _clear(self) -> None:
        """Ingen logotyp ska användas."""
        self.selected_path = ""
        self._show_message(t("logo.no_logo"))
        self._ok_button.setFocus()

    def _accept(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self.selected_path = str(item.data(_PATH_ROLE))
        self.cancelled = False
        self.accept()


def choose_logo(
    parent: Optional[QWidget] = None,
    current: str = "",
    root: Optional[Union[str, Path]] = None,
) -> Tuple[bool, str]:
    """
    Visa logotypväljaren.

    Returns:
        (ändrad, sökväg). ändrad=False om användaren avbröt, annars den
        valda sökvägen – "" betyder "ingen logotyp".
    """
    dialog = LogoDialog(parent, current=current, root=root)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return (False, current)

    return (True, dialog.selected_path)


__all__ = ["LogoDialog", "choose_logo", "MODULE_VERSION"]
