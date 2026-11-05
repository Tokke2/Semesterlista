#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Listredigerare (PySide6) – anställda, fordon och hyresgäster.
v2.8.0
=============================================================

En gemensam dialog för att redigera appens textlistor direkt i programmet
i stället för att öppna txt-filen i en extern editor:

    ┌──────────────────────────────────────────────┐
    │ Hantera Anställda                            │
    │ Fil: /sökväg/Anställda.txt      8 poster     │
    │ ┌──────────────────────────────────────────┐ │
    │ │ Anna Andersson                           │ │
    │ │ Bertil Bengtsson                         │ │
    │ │ …                                        │ │
    │ └──────────────────────────────────────────┘ │
    │ [Lägg till] [Ändra] [Ta bort] [Upp] [Ner]    │
    │ [Klistra in flera…] [Sortera A–Ö]            │
    │                        [Öppna i textredigerare]│
    │                        [Spara] [Avbryt]      │
    └──────────────────────────────────────────────┘

För Hyresgäster.txt visas två flikar (månad/kvartal).

All läsning, validering och skrivning sker i core/roster.py – dialogen
håller bara redigeringsytan.

Användning:
    from core.list_editor_dialog import ListEditorDialog

    if ListEditorDialog.edit("Anställda.txt", name="Anställda", parent=self):
        ...  # listan är sparad
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Sequence, Union

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import i18n
from core.roster import (
    MAX_ENTRY_LENGTH,
    RosterError,
    RosterFile,
    resolve_path,
    sort_key,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.16.0"


# ══════════════════════════════════════════════════════════
# REDIGERING AV EN SEKTION
# ══════════════════════════════════════════════════════════

class SectionEditor(QWidget):
    """
    Lista + knappar för en sektion (t.ex. "Anställda").

    Signaler:
        changed: emitteras när innehållet ändrats.
    """

    changed = Signal()

    def __init__(
        self,
        entries: Optional[Sequence[str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._build_ui()
        self.set_entries(entries or [])
        self._update_buttons()

    # ──────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Hjälptext: så skrivs lediga dagar (v2.11.0)
        self.leave_hint = QLabel(i18n.t("roster.leave.hint"))
        self.leave_hint.setWordWrap(True)
        self.leave_hint.setProperty("role", "muted")
        layout.addWidget(self.leave_hint)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setMinimumHeight(240)
        self.list_widget.itemDoubleClicked.connect(
            lambda _item: self._on_edit()
        )
        self.list_widget.itemSelectionChanged.connect(self._update_buttons)
        self.list_widget.model().rowsMoved.connect(self._on_changed)
        layout.addWidget(self.list_widget, stretch=1)

        # ── Rad 1: lägg till / ändra / ta bort ───────────
        row_one = QHBoxLayout()
        row_one.setSpacing(6)

        self.add_button = QPushButton("＋ " + i18n.t("roster.button.add"))
        self.add_button.clicked.connect(self._on_add)
        row_one.addWidget(self.add_button)

        self.edit_button = QPushButton(i18n.t("roster.button.edit"))
        self.edit_button.clicked.connect(self._on_edit)
        row_one.addWidget(self.edit_button)

        self.remove_button = QPushButton(i18n.t("roster.button.remove"))
        self.remove_button.clicked.connect(self._on_remove)
        row_one.addWidget(self.remove_button)

        row_one.addStretch(1)

        self.up_button = QPushButton("↑ " + i18n.t("roster.button.up"))
        self.up_button.setToolTip(i18n.t("roster.button.up.tooltip"))
        self.up_button.clicked.connect(lambda: self._on_move(-1))
        row_one.addWidget(self.up_button)

        self.down_button = QPushButton("↓ " + i18n.t("roster.button.down"))
        self.down_button.setToolTip(i18n.t("roster.button.down.tooltip"))
        self.down_button.clicked.connect(lambda: self._on_move(1))
        row_one.addWidget(self.down_button)

        layout.addLayout(row_one)

        # ── Rad 2: klistra in / sortera ──────────────────
        row_two = QHBoxLayout()
        row_two.setSpacing(6)

        self.paste_button = QPushButton(i18n.t("roster.button.paste"))
        self.paste_button.setToolTip(i18n.t("roster.button.paste.tooltip"))
        self.paste_button.clicked.connect(self._on_paste)
        row_two.addWidget(self.paste_button)

        self.sort_button = QPushButton(i18n.t("roster.button.sort"))
        self.sort_button.setToolTip(i18n.t("roster.button.sort.tooltip"))
        self.sort_button.clicked.connect(self._on_sort)
        row_two.addWidget(self.sort_button)

        row_two.addStretch(1)
        layout.addLayout(row_two)

    # ──────────────────────────────────────────────────────
    # Innehåll
    # ──────────────────────────────────────────────────────

    def set_entries(self, entries: Sequence[str]) -> None:
        """Fyll listan med poster."""
        self.list_widget.clear()
        for entry in entries:
            self.list_widget.addItem(QListWidgetItem(entry))
        self._update_buttons()

    def entries(self) -> List[str]:
        """Alla poster i listan, i visad ordning."""
        return [
            self.list_widget.item(row).text().strip()
            for row in range(self.list_widget.count())
        ]

    def _update_buttons(self) -> None:
        """Aktivera/avaktivera knappar utifrån markering."""
        selected = self.list_widget.selectedItems()
        has_selection = bool(selected)
        self.edit_button.setEnabled(len(selected) == 1)
        self.remove_button.setEnabled(has_selection)
        self.up_button.setEnabled(len(selected) == 1)
        self.down_button.setEnabled(len(selected) == 1)
        self.sort_button.setEnabled(self.list_widget.count() > 1)

    def _on_changed(self, *_: Any) -> None:
        """Vidarebefordra ändringar till dialogen."""
        self._update_buttons()
        self.changed.emit()

    # ──────────────────────────────────────────────────────
    # Åtgärder
    # ──────────────────────────────────────────────────────

    def _existing(self) -> List[str]:
        """Poster i listan, skiftlägesfolds för dubblettkontroll."""
        return [entry.casefold() for entry in self.entries()]

    def _on_add(self) -> None:
        """Lägg till en post."""
        text, ok = QInputDialog.getText(
            self,
            i18n.t("roster.add.title"),
            i18n.t("roster.add.prompt", max=MAX_ENTRY_LENGTH),
        )
        if not ok:
            return

        value = " ".join(str(text).split())
        if not value:
            return
        if len(value) > MAX_ENTRY_LENGTH:
            QMessageBox.warning(
                self,
                i18n.t("roster.error.title"),
                i18n.t("roster.error.too_long", max=MAX_ENTRY_LENGTH),
            )
            return
        if value.casefold() in self._existing():
            QMessageBox.warning(
                self,
                i18n.t("roster.error.title"),
                i18n.t("roster.error.duplicate", entry=value),
            )
            return

        self.list_widget.addItem(QListWidgetItem(value))
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        self._on_changed()

    def _on_edit(self) -> None:
        """Ändra markerad post."""
        item = self.list_widget.currentItem()
        if item is None:
            return

        text, ok = QInputDialog.getText(
            self,
            i18n.t("roster.edit.title"),
            i18n.t("roster.edit.prompt", max=MAX_ENTRY_LENGTH),
            text=item.text(),
        )
        if not ok:
            return

        value = " ".join(str(text).split())
        if not value:
            return
        if len(value) > MAX_ENTRY_LENGTH:
            QMessageBox.warning(
                self,
                i18n.t("roster.error.title"),
                i18n.t("roster.error.too_long", max=MAX_ENTRY_LENGTH),
            )
            return

        others = [
            entry.casefold()
            for row, entry in enumerate(self.entries())
            if row != self.list_widget.currentRow()
        ]
        if value.casefold() in others:
            QMessageBox.warning(
                self,
                i18n.t("roster.error.title"),
                i18n.t("roster.error.duplicate", entry=value),
            )
            return

        item.setText(value)
        self._on_changed()

    def _on_remove(self) -> None:
        """Ta bort markerade poster."""
        selected = self.list_widget.selectedItems()
        if not selected:
            return

        if len(selected) > 1:
            answer = QMessageBox.question(
                self,
                i18n.t("roster.button.remove"),
                i18n.t("roster.remove.question", count=len(selected)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        for item in selected:
            self.list_widget.takeItem(self.list_widget.row(item))
        self._on_changed()

    def _on_move(self, delta: int) -> None:
        """Flytta markerad post uppåt eller nedåt."""
        row = self.list_widget.currentRow()
        if row < 0:
            return

        new_row = max(0, min(self.list_widget.count() - 1, row + delta))
        if new_row == row:
            return

        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(new_row, item)
        self.list_widget.setCurrentRow(new_row)
        self._on_changed()

    def _on_paste(self) -> None:
        """Klistra in flera poster samtidigt (en per rad)."""
        text, ok = QInputDialog.getMultiLineText(
            self,
            i18n.t("roster.paste.title"),
            i18n.t("roster.paste.prompt"),
            "",
        )
        if not ok or not text.strip():
            return

        existing = set(self._existing())
        added = 0
        skipped = 0

        for line in text.splitlines():
            value = " ".join(line.split())
            if not value or len(value) > MAX_ENTRY_LENGTH:
                skipped += 1
                continue
            if value.casefold() in existing:
                skipped += 1
                continue
            self.list_widget.addItem(QListWidgetItem(value))
            existing.add(value.casefold())
            added += 1

        if added:
            self._on_changed()

        QMessageBox.information(
            self,
            i18n.t("roster.paste.title"),
            i18n.t("roster.paste.result", added=added, skipped=skipped),
        )

    def _on_sort(self) -> None:
        """Sortera listan alfabetiskt (Å, Ä, Ö efter Z)."""
        entries = sorted(self.entries(), key=sort_key)
        self.set_entries(entries)
        self._on_changed()


# ══════════════════════════════════════════════════════════
# DIALOGEN
# ══════════════════════════════════════════════════════════

class ListEditorDialog(QDialog):
    """
    Dialog för att redigera en lista (en eller flera sektioner).

    Efter Spara finns den sparade listan i `self.roster`.
    """

    def __init__(
        self,
        path: Union[str, Path],
        name: str = "",
        parent: Optional[QWidget] = None,
        section_titles: Optional[Sequence[str]] = None,
        base: Optional[Path] = None,
        create: bool = True,
    ):
        """
        Args:
            path:           Sökväg till txt-filen (relativ = appens rotmapp).
            name:           Visningsnamn, t.ex. "Anställda".
            parent:         Förälderfönster.
            section_titles: Fliknamn när filen har flera sektioner
                            (t.ex. ["Månadshyresgäster", "Kvartalshyresgäster"]).
            base:           Basmapp för relativa sökvägar.
            create:         Skapa filen om den saknas.
        """
        super().__init__(parent)

        # Samma appikon som huvudfönstret (v2.7.0)
        try:
            from core.app_icon import app_icon

            self.setWindowIcon(app_icon())
        except Exception:  # pragma: no cover – defensivt
            pass

        self._created = False
        self._dirty = False
        self._editors: List[SectionEditor] = []

        target = resolve_path(path, base)
        existed_before = target.exists()

        try:
            self.roster = RosterFile.load(
                path, name=name, base=base, create=create
            )
            self._created = create and not existed_before
        except RosterError as exc:
            logger.warning(f"Kunde inte läsa listan {path}: {exc}")
            QMessageBox.warning(
                self,
                i18n.t("roster.error.title"),
                i18n.t("roster.error.read", error=exc),
            )
            self.roster = RosterFile(path=resolve_path(path, base), name=name)

        self._section_titles = list(section_titles or [])
        self._build_ui()
        self._update_status()

    # ──────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────

    def _display_name(self) -> str:
        """Listans visningsnamn (t.ex. "Anställda")."""
        return self.roster.name or self.roster.path.stem

    def _build_ui(self) -> None:
        """Bygg dialogens innehåll."""
        self.setWindowTitle(i18n.t("roster.dialog.title", name=self._display_name()))
        self.setMinimumSize(620, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)

        header = QLabel(
            i18n.t("roster.header", path=str(self.roster.path))
        )
        header.setWordWrap(True)
        header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(header)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # ── En eller flera sektioner ─────────────────────
        self._tabs: Optional[QTabWidget] = None

        if self.roster.section_count > 1:
            self._tabs = QTabWidget()
            for index in range(self.roster.section_count):
                editor = SectionEditor(self.roster.section(index), self._tabs)
                editor.changed.connect(self._on_changed)
                title = (
                    self._section_titles[index]
                    if index < len(self._section_titles)
                    else i18n.t("roster.section.number", number=index + 1)
                )
                self._tabs.addTab(editor, title)
                self._editors.append(editor)
            layout.addWidget(self._tabs, stretch=1)
        else:
            editor = SectionEditor(self.roster.entries, self)
            editor.changed.connect(self._on_changed)
            self._editors.append(editor)
            layout.addWidget(editor, stretch=1)

        # ── Knapprad ─────────────────────────────────────
        button_row = QHBoxLayout()

        self._open_text_button = QPushButton(i18n.t("roster.button.open_text"))
        self._open_text_button.setToolTip(i18n.t("roster.button.open_text.tooltip"))
        self._open_text_button.clicked.connect(self._on_open_in_editor)
        button_row.addWidget(self._open_text_button)

        button_row.addStretch(1)

        self._cancel_button = QPushButton(i18n.t("roster.button.cancel"))
        self._cancel_button.clicked.connect(self._on_cancel)
        button_row.addWidget(self._cancel_button)

        self._save_button = QPushButton(i18n.t("roster.button.save"))
        self._save_button.setDefault(True)
        self._save_button.clicked.connect(self._on_save)
        button_row.addWidget(self._save_button)

        layout.addLayout(button_row)

    def _update_status(self) -> None:
        """Visa antal poster (och att filen nyss skapades) i statusraden."""
        count = sum(len(editor.entries()) for editor in self._editors)
        text = i18n.t("roster.count", count=count)
        if self._created:
            text = i18n.t("roster.info.created", path=str(self.roster.path)) + " · " + text
        self._status_label.setText(text)

        if hasattr(self, "_save_button"):
            self._save_button.setEnabled(True)

    # ──────────────────────────────────────────────────────
    # Ändringar
    # ──────────────────────────────────────────────────────

    def _on_changed(self) -> None:
        """Markera dialogen som ändrad."""
        self._dirty = True
        self._update_status()

    def _collect(self) -> List[List[str]]:
        """Hämta alla sektioner från redigerarna."""
        return [editor.entries() for editor in self._editors]

    # ──────────────────────────────────────────────────────
    # Spara
    # ──────────────────────────────────────────────────────

    def _on_save(self) -> None:
        """Validera och spara listan."""
        sections = self._collect()

        while len(self.roster.sections) < len(sections):
            self.roster.sections.append([])
        for index, entries in enumerate(sections):
            self.roster.set_entries(entries, index)

        issues = self.roster.validate()

        warnings = [
            issue for issue in issues
            if issue.is_warning and issue.entry
        ]
        if warnings:
            answer = QMessageBox.question(
                self,
                i18n.t("roster.warning.title"),
                i18n.t("roster.warning.body", issues="\n• ".join(
                    issue.message for issue in warnings
                )),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        try:
            path = self.roster.save()
        except RosterError as exc:
            QMessageBox.critical(
                self,
                i18n.t("roster.error.title"),
                str(exc),
            )
            return

        self._dirty = False
        self._created = False
        logger.info(f"Sparade {self.roster.entry_count()} poster i {path}")

        self.accept()

    def _on_cancel(self) -> None:
        """Stäng utan att spara (fråga om osparade ändringar)."""
        self.reject()

    def _on_open_in_editor(self) -> None:
        """Öppna filen i operativsystemets textredigerare."""
        from core.roster import open_in_editor

        if self._dirty:
            for index, entries in enumerate(self._collect()):
                self.roster.set_entries(entries, index)
            try:
                self.roster.save()
            except RosterError as exc:
                QMessageBox.critical(self, i18n.t("roster.error.title"), str(exc))
                return
            self._dirty = False

        if not open_in_editor(self.roster.path):
            QMessageBox.warning(
                self,
                i18n.t("roster.error.title"),
                i18n.t("roster.open_failed", path=str(self.roster.path)),
            )
            return
        self.accept()

    def _confirm_discard(self) -> bool:
        """Fråga om osparade ändringar ska slängas."""
        answer = QMessageBox.question(
            self,
            i18n.t("roster.confirm.title"),
            i18n.t("roster.confirm.discard"),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            self._on_save()          # accept() anropas av _on_save
            return False
        if answer == QMessageBox.StandardButton.Discard:
            self._dirty = False
            return True
        return False

    def reject(self) -> None:
        """Stäng dialogen (med fråga vid osparade ändringar)."""
        if self._dirty and not self._confirm_discard():
            return
        super().reject()

    # ──────────────────────────────────────────────────────
    # Genväg
    # ──────────────────────────────────────────────────────

    @classmethod
    def edit(
        cls,
        path: Union[str, Path],
        name: str = "",
        parent: Optional[QWidget] = None,
        section_titles: Optional[Sequence[str]] = None,
        base: Optional[Path] = None,
    ) -> bool:
        """
        Öppna redigeraren modalt.

        Returns:
            True om listan sparades, annars False.
        """
        dialog = cls(
            path=path,
            name=name,
            parent=parent,
            section_titles=section_titles,
            base=base,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted
