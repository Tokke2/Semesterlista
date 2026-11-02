#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inställningsdialog för huvudfönstret (v2.8.0)
=============================================

Dialogen som öppnas från **Arkiv → Inställningar** (Ctrl+,):

    Allmänt     språk (svenska/engelska), tema, helgdagsregion
    Fönster     autostart, starta minimerad, minimera/stäng till systemfältet,
                aviseringar och deras varaktighet
    Plugins     aktivera/inaktivera flikar (kräver omstart)
    Avancerat   felsökningsläge, loggning, uppdateringskontroll och
                genvägar till loggfilen

Allt sparas i ``data/settings.json`` / ``data/plugins.json`` via
``SettingsManager``. Språk- och temabyte slår igenom direkt.

Exempel:
    from core.settings_dialog import SettingsDialog

    dialog = SettingsDialog(
        settings_manager=settings_manager,
        theme_manager=theme_manager,
        lock=lock,
        plugin_manager=plugin_manager,
        event_bus=event_bus,
        parent=self,
    )
    dialog.exec()

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import i18n
from core.logging_setup import get_log_file, log_summary, tail_log

logger = logging.getLogger(__name__)

MODULE_VERSION: str = "2.8.0"

#: Temanycklar i den ordning de visas
THEME_ORDER: tuple = ("system", "light", "dark")

#: Helgdagsregioner
HOLIDAY_REGIONS: tuple = ("sv", "us")


class SettingsDialog(QDialog):
    """
    Inställningsdialog med flikarna Allmänt, Fönster, Plugins och Avancerat.

    Alla argument utom ``settings_manager`` är valfria, så dialogen kan
    användas även om en del av appen inte är laddad (t.ex. i tester).
    """

    def __init__(
        self,
        settings_manager: Any,
        theme_manager: Any = None,
        lock: Any = None,
        plugin_manager: Any = None,
        event_bus: Any = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.settings_manager = settings_manager
        self.theme_manager = theme_manager
        self.lock = lock
        self.plugin_manager = plugin_manager
        self.event_bus = event_bus

        self.setWindowTitle(i18n.t("settings.title"))
        self.setMinimumSize(560, 520)
        self.setModal(True)

        try:
            from core.app_icon import app_icon

            self.setWindowIcon(app_icon())
        except Exception:  # pragma: no cover – defensivt
            pass

        self._plugin_checks: Dict[str, QCheckBox] = {}
        self._build_ui()
        self._load_settings()

        logger.debug("Inställningsdialogen skapad")

    # ──────────────────────────────────────────────────────
    # Bygge
    # ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("⚙️ " + i18n.t("settings.title"))
        title.setFont(self.font())
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_general_tab(), i18n.t("settings.tab.general"))
        self._tabs.addTab(self._create_window_tab(), i18n.t("settings.tab.window"))
        self._tabs.addTab(self._create_plugins_tab(), i18n.t("settings.tab.plugins"))
        self._tabs.addTab(self._create_advanced_tab(), i18n.t("settings.tab.advanced"))
        layout.addWidget(self._tabs, 1)

        # Data-mapp
        data_label = QLabel(
            f"{i18n.t('settings.data_path')} {self._data_path()}"
        )
        data_label.setStyleSheet("color: #777; font-size: 11px;")
        data_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(data_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            i18n.t("settings.save")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            i18n.t("settings.cancel")
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_general_tab(self) -> QWidget:
        """Språk, tema och helgdagar."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        appearance = QGroupBox(i18n.t("settings.group.appearance"))
        form = QFormLayout(appearance)

        self.language_combo = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setToolTip(i18n.t("settings.language.tooltip"))
        form.addRow(i18n.t("settings.language"), self.language_combo)

        self.theme_combo = QComboBox()
        for theme in THEME_ORDER:
            self.theme_combo.addItem(i18n.t(f"theme.{theme}.name"), theme)
        form.addRow(i18n.t("settings.theme"), self.theme_combo)

        layout.addWidget(appearance)

        holidays = QGroupBox(i18n.t("settings.group.holidays"))
        holiday_form = QFormLayout(holidays)

        self.holiday_combo = QComboBox()
        for region in HOLIDAY_REGIONS:
            self.holiday_combo.addItem(
                i18n.t(f"settings.holiday_region.{region}"), region
            )
        self.holiday_combo.setToolTip(i18n.t("settings.holiday_region.tooltip"))
        holiday_form.addRow(i18n.t("settings.holiday_region"), self.holiday_combo)

        help_label = QLabel(i18n.t("settings.holiday_region.help"))
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #777;")
        holiday_form.addRow("", help_label)

        layout.addWidget(holidays)
        layout.addStretch()
        return page

    def _create_window_tab(self) -> QWidget:
        """Fönster och systemfält."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        group = QGroupBox(i18n.t("settings.group.window"))
        inner = QVBoxLayout(group)

        self.autostart_check = QCheckBox(i18n.t("settings.autostart"))
        self.start_minimized_check = QCheckBox(i18n.t("settings.start_minimized"))
        self.minimize_to_tray_check = QCheckBox(i18n.t("settings.minimize_to_tray"))
        self.close_to_tray_check = QCheckBox(i18n.t("settings.close_to_tray"))
        self.notifications_check = QCheckBox(i18n.t("settings.notifications"))

        for check in (
            self.autostart_check,
            self.start_minimized_check,
            self.minimize_to_tray_check,
            self.close_to_tray_check,
            self.notifications_check,
        ):
            inner.addWidget(check)

        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel(i18n.t("settings.notification_duration")))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(500, 15000)
        self.duration_spin.setSingleStep(500)
        self.duration_spin.setSuffix(" ms")
        duration_row.addWidget(self.duration_spin)
        duration_row.addStretch()
        inner.addLayout(duration_row)

        if self.lock is None:
            self.autostart_check.setEnabled(False)
            self.autostart_check.setToolTip(i18n.t("settings.autostart.unavailable"))

        layout.addWidget(group)
        layout.addStretch()
        return page

    def _create_plugins_tab(self) -> QWidget:
        """Aktivera/inaktivera plugins."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setSpacing(8)

        group = QGroupBox(i18n.t("settings.group.plugins"))
        group_layout = QVBoxLayout(group)

        hint = QLabel(i18n.t("settings.plugin_restart_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #777;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self._plugin_layout = QVBoxLayout(holder)
        self._plugin_layout.setContentsMargins(0, 0, 0, 0)
        self._plugin_layout.setSpacing(4)

        names = self._plugin_names()
        if not names:
            empty = QLabel(i18n.t("settings.no_plugins"))
            empty.setStyleSheet("color: #777;")
            self._plugin_layout.addWidget(empty)
        else:
            for name in names:
                check = QCheckBox(i18n.plugin_display_name_qt(name))
                check.setToolTip(name)
                self._plugin_checks[name] = check
                self._plugin_layout.addWidget(check)

        self._plugin_layout.addStretch()
        scroll.setWidget(holder)

        group_layout.addWidget(scroll, 1)
        group_layout.addWidget(hint)

        outer.addWidget(group, 1)
        return page

    def _create_advanced_tab(self) -> QWidget:
        """Felsökning och loggning."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        group = QGroupBox(i18n.t("settings.group.advanced"))
        inner = QVBoxLayout(group)

        self.debug_check = QCheckBox(i18n.t("settings.debug_mode"))
        self.debug_check.setToolTip(i18n.t("settings.debug_mode.tooltip"))
        self.log_to_file_check = QCheckBox(i18n.t("settings.log_to_file"))
        self.check_updates_check = QCheckBox(i18n.t("settings.check_updates"))

        for check in (
            self.debug_check,
            self.log_to_file_check,
            self.check_updates_check,
        ):
            inner.addWidget(check)

        log_info = log_summary()
        log_path = log_info.get("log_file") or str(get_log_file() or "—")
        self.log_path_label = QLabel(f"{i18n.t('settings.log_file')} {log_path}")
        self.log_path_label.setStyleSheet("color: #777; font-size: 11px;")
        self.log_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.log_path_label.setWordWrap(True)
        inner.addWidget(self.log_path_label)

        button_row = QHBoxLayout()
        self.open_log_button = QPushButton(i18n.t("settings.open_log_folder"))
        self.open_log_button.clicked.connect(self._open_log_folder)
        self.open_log_button.setEnabled(bool(log_info.get("log_file")))
        button_row.addWidget(self.open_log_button)

        self.copy_log_button = QPushButton(i18n.t("settings.copy_log"))
        self.copy_log_button.clicked.connect(self._copy_log_tail)
        self.copy_log_button.setEnabled(bool(log_info.get("log_file")))
        button_row.addWidget(self.copy_log_button)
        button_row.addStretch()
        inner.addLayout(button_row)

        layout.addWidget(group)
        layout.addStretch()
        return page

    # ──────────────────────────────────────────────────────
    # Ladda / spara
    # ──────────────────────────────────────────────────────

    def _load_settings(self) -> None:
        """Fyll dialogens fält från settings.json."""
        manager = self.settings_manager
        get = manager.get

        language = str(get("language", i18n.DEFAULT_LANGUAGE))
        index = self.language_combo.findData(language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)

        theme = str(get("theme", "system"))
        index = self.theme_combo.findData(theme)
        self.theme_combo.setCurrentIndex(index if index >= 0 else 0)

        region = str(get("holiday_region", "sv"))
        index = self.holiday_combo.findData(region)
        self.holiday_combo.setCurrentIndex(index if index >= 0 else 0)

        self.start_minimized_check.setChecked(bool(get("systray.start_minimized", True)))
        self.minimize_to_tray_check.setChecked(bool(get("systray.minimize_to_tray", True)))
        self.close_to_tray_check.setChecked(bool(get("systray.close_to_tray", True)))
        self.notifications_check.setChecked(bool(get("systray.show_notifications", True)))

        duration = get("systray.notification_duration_ms", 3000)
        try:
            self.duration_spin.setValue(int(duration))
        except (TypeError, ValueError):
            self.duration_spin.setValue(3000)

        if self.lock is not None:
            try:
                self.autostart_check.setChecked(bool(self.lock.get_autostart()))
            except Exception as exc:  # pragma: no cover – defensivt
                logger.warning(f"Kunde inte läsa autostart: {exc}")
                self.autostart_check.setEnabled(False)

        for name, check in self._plugin_checks.items():
            info = manager.get_plugin_info(name)
            check.setChecked(info.get("enabled", True) is not False)

        self.debug_check.setChecked(bool(get("advanced.debug_mode", False)))
        self.log_to_file_check.setChecked(bool(get("advanced.log_to_file", True)))
        self.check_updates_check.setChecked(bool(get("advanced.check_updates", True)))

    def apply_settings(self) -> None:
        """
        Skriv dialogens värden till inställningarna (utan dialogruta).

        Används av ``_save()`` och av testerna.
        """
        manager = self.settings_manager

        language = self.language_combo.currentData()
        theme = self.theme_combo.currentData()
        region = self.holiday_combo.currentData()

        # Språk – slår igenom direkt via i18n-signalen
        if language and language != manager.get("language", i18n.DEFAULT_LANGUAGE):
            i18n.set_language(str(language))
            manager.set("language", language)
            logger.info(f"Språk ändrat till {language}")

        # Tema – ThemeManager applicerar och sparar själv
        if theme:
            if self.theme_manager is not None:
                try:
                    self.theme_manager.set_theme(str(theme))
                except Exception as exc:  # pragma: no cover – defensivt
                    logger.warning(f"Kunde inte byta tema: {exc}")
            manager.set("theme", theme)

        if region:
            manager.set("holiday_region", region)

        manager.set("systray.start_minimized", self.start_minimized_check.isChecked())
        manager.set("systray.minimize_to_tray", self.minimize_to_tray_check.isChecked())
        manager.set("systray.close_to_tray", self.close_to_tray_check.isChecked())
        manager.set("systray.show_notifications", self.notifications_check.isChecked())
        manager.set("systray.notification_duration_ms", self.duration_spin.value())

        if self.lock is not None and self.autostart_check.isEnabled():
            want = self.autostart_check.isChecked()
            try:
                if want != self.lock.get_autostart():
                    self.lock.set_autostart(want)
                    logger.info(f"Autostart {'aktiverad' if want else 'avaktiverad'}")
                # Håll advanced.autostart i takt med systemets verkliga läge
                manager.set("advanced.autostart", want)
            except Exception as exc:  # pragma: no cover – defensivt
                logger.warning(f"Kunde inte ändra autostart: {exc}")

        for name, check in self._plugin_checks.items():
            manager.set_plugin_enabled(name, check.isChecked())

        manager.set("advanced.debug_mode", self.debug_check.isChecked())
        manager.set("advanced.log_to_file", self.log_to_file_check.isChecked())
        manager.set("advanced.check_updates", self.check_updates_check.isChecked())

        logger.info(
            "Inställningar sparade: språk=%s, tema=%s, region=%s, "
            "plugins=%s, debug=%s",
            language,
            theme,
            region,
            {name: check.isChecked() for name, check in self._plugin_checks.items()},
            self.debug_check.isChecked(),
        )

        if self.event_bus is not None:
            try:
                self.event_bus.emit("settings:changed", {"source": "settings_dialog"})
            except Exception:  # pragma: no cover – defensivt
                pass

    def _save(self) -> None:
        """Spara och stäng."""
        try:
            self.apply_settings()
        except Exception as exc:
            logger.exception("Kunde inte spara inställningarna")
            QMessageBox.critical(
                self,
                i18n.t("settings.title"),
                i18n.t("settings.save_error", error=exc),
            )
            return

        QMessageBox.information(
            self,
            i18n.t("settings.title"),
            i18n.t("settings.saved"),
        )
        self.accept()

    # ──────────────────────────────────────────────────────
    # Hjälp
    # ──────────────────────────────────────────────────────

    def _data_path(self) -> str:
        """Sökvägen till data-mappen (där JSON-filerna ligger)."""
        getter = getattr(self.settings_manager, "get_data_path", None)
        if callable(getter):
            try:
                return str(getter())
            except Exception:  # pragma: no cover – defensivt
                pass
        return "data/"

    def _plugin_names(self) -> List[str]:
        """Alla kända plugins (från plugins.json eller PluginManager)."""
        names: List[str] = []

        try:
            names.extend(self.settings_manager.list_plugins())
        except Exception:  # pragma: no cover – defensivt
            pass

        if self.plugin_manager is not None:
            try:
                for name in self.plugin_manager.get_plugin_order():
                    plugin = self.plugin_manager.get_plugin(name)
                    display = plugin.get_name() if plugin is not None else name
                    if display not in names:
                        names.append(display)
            except Exception as exc:  # pragma: no cover – defensivt
                logger.warning(f"Kunde inte läsa plugin-listan: {exc}")

        return names

    def _open_log_folder(self) -> None:
        """Öppna mappen med loggfilen i filhanteraren."""
        log_file = get_log_file()
        if log_file is None:
            return

        folder = Path(log_file).parent
        try:
            if platform.system() == "Windows":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)
        except Exception as exc:
            logger.warning(f"Kunde inte öppna loggmappen: {exc}")
            QMessageBox.warning(
                self,
                i18n.t("settings.title"),
                i18n.t("settings.open_log_error", error=exc),
            )

    def _copy_log_tail(self) -> None:
        """Kopiera de sista loggraderna till urklipp."""
        from PySide6.QtWidgets import QApplication

        text = "\n".join(tail_log(60))
        if not text:
            QMessageBox.information(
                self,
                i18n.t("settings.title"),
                i18n.t("settings.log_empty"),
            )
            return

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            logger.info("Senaste loggraderna kopierade till urklipp")


__all__ = ["SettingsDialog", "THEME_ORDER", "HOLIDAY_REGIONS", "MODULE_VERSION"]
