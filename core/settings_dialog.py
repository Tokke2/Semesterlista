#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inställningsdialog för huvudfönstret (v2.9.0)
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
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QProcess, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import i18n, updater
from core.logging_setup import (
    clear_error_log,
    error_log_lines,
    get_error_log_file,
    get_log_file,
    log_summary,
    tail_log,
)

logger = logging.getLogger(__name__)

MODULE_VERSION: str = "2.17.0"

#: Temanycklar i den ordning de visas
THEME_ORDER: tuple = ("system", "light", "dark", "contrast")

#: Helgdagsregioner
HOLIDAY_REGIONS: tuple = ("sv", "us")


class _UpdateSignals(QObject):
    """
    Brygga mellan uppdateringens arbetstråd och gränssnittet.

    Signalerna skickas från en vanlig ``threading.Thread`` och levereras
    automatiskt i GUI-tråden (Qt köar signaler mellan trådar).
    """

    checked  = Signal(object, object)   # (UpdateInfo | None, fel | None)
    progress = Signal(int, int)         # (nedladdat, totalt)
    installed = Signal(object, object)  # (InstallResult | None, fel | None)


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
        app_version: str = "",
    ):
        super().__init__(parent)

        self.settings_manager = settings_manager
        self.theme_manager = theme_manager
        self.lock = lock
        self.plugin_manager = plugin_manager
        self.event_bus = event_bus
        self.app_version = app_version
        self._app_version = app_version or updater.app_version(self._app_dir())

        # Uppdatering (v2.9.0)
        self._update_info: Optional[updater.UpdateInfo] = None
        self._update_busy = False
        self._update_signals = _UpdateSignals(self)
        self._update_signals.checked.connect(self._on_update_checked)
        self._update_signals.progress.connect(self._on_update_progress)
        self._update_signals.installed.connect(self._on_update_installed)

        self.setWindowTitle(i18n.t("settings.title"))
        self.setMinimumSize(460, 320)
        self.setModal(True)

        try:
            from core.app_icon import app_icon

            self.setWindowIcon(app_icon())
        except Exception:  # pragma: no cover – defensivt
            pass

        self._plugin_checks: Dict[str, QCheckBox] = {}
        self._build_ui()
        self._load_settings()
        # Logical pixels: respect the work area also with Windows DPI scaling.
        screen = self.screen()
        if screen is not None:
            area = screen.availableGeometry()
            self.resize(min(720, area.width() - 48), min(780, area.height() - 80))

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
        self._tabs.addTab(self._scrollable_tab(self._create_general_tab()), i18n.t("settings.tab.general"))
        self._tabs.addTab(self._scrollable_tab(self._create_window_tab()), i18n.t("settings.tab.window"))
        self._tabs.addTab(self._scrollable_tab(self._create_plugins_tab()), i18n.t("settings.tab.plugins"))
        self._tabs.addTab(self._scrollable_tab(self._create_advanced_tab()), i18n.t("settings.tab.advanced"))
        layout.addWidget(self._tabs, 1)

        # Data-mapp
        data_label = QLabel(
            f"{i18n.t('settings.data_path')} {self._data_path()}"
        )
        data_label.setWordWrap(True)
        data_label.setProperty("role", "muted")
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

    @staticmethod
    def _scrollable_tab(page: QWidget) -> QScrollArea:
        """Keep controls at their minimum size; scroll instead of clipping."""
        page.layout().setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

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
        help_label.setProperty("role", "muted")
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
        hint.setProperty("role", "muted")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self._plugin_layout = QVBoxLayout(holder)
        self._plugin_layout.setContentsMargins(0, 0, 0, 0)
        self._plugin_layout.setSpacing(4)

        names = self._plugin_names()
        if not names:
            empty = QLabel(i18n.t("settings.no_plugins"))
            empty.setProperty("role", "muted")
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

        # Smart cache (v2.11.0): städa rastrerade logotyper vid avslut
        self.clear_cache_check = QCheckBox(i18n.t("settings.clear_cache_on_exit"))
        self.clear_cache_check.setToolTip(
            i18n.t("settings.clear_cache_on_exit.tooltip")
        )

        for check in (
            self.debug_check,
            self.log_to_file_check,
            self.check_updates_check,
            self.clear_cache_check,
        ):
            inner.addWidget(check)

        self.cache_size_label = QLabel(
            i18n.t("settings.cache_size", size=self._cache_size_text())
        )
        self.cache_size_label.setProperty("role", "muted")
        inner.addWidget(self.cache_size_label)

        log_info = log_summary()
        log_path = log_info.get("log_file") or str(get_log_file() or "—")
        self.log_path_label = QLabel(f"{i18n.t('settings.log_file')} {log_path}")
        self.log_path_label.setProperty("role", "muted")
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

        # Felloggen (v2.12.0): egna fel, kvar tills de är åtgärdade
        error_path = log_info.get("error_log") or str(get_error_log_file() or "—")
        self.error_log_label = QLabel(
            i18n.t(
                "settings.error_log_file",
                path=error_path,
                count=log_info.get("error_lines", 0),
            )
        )
        self.error_log_label.setProperty("role", "muted")
        self.error_log_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.error_log_label.setWordWrap(True)
        inner.addWidget(self.error_log_label)

        error_row = QHBoxLayout()
        self.open_error_log_button = QPushButton(i18n.t("settings.open_error_log"))
        self.open_error_log_button.clicked.connect(self._open_error_log)
        self.open_error_log_button.setEnabled(bool(log_info.get("error_log")))
        error_row.addWidget(self.open_error_log_button)

        self.clear_error_log_button = QPushButton(i18n.t("settings.clear_error_log"))
        self.clear_error_log_button.setToolTip(i18n.t("settings.clear_error_log.tooltip"))
        self.clear_error_log_button.clicked.connect(self._clear_error_log)
        self.clear_error_log_button.setEnabled(
            bool(log_info.get("error_log")) and log_info.get("error_lines", 0) > 1
        )
        error_row.addWidget(self.clear_error_log_button)
        error_row.addStretch()
        inner.addLayout(error_row)

        layout.addWidget(group)
        layout.addWidget(self._create_update_group())
        layout.addStretch()
        return page

    @staticmethod
    def _cache_size_text() -> str:
        """
        Storlek på appens cache som läsbar text ("18 kB" / "1,4 MB").

        Visas under *Rensa cache vid avslut* så att man ser hur mycket som
        faktiskt städas (v2.11.0).
        """
        try:
            from core.cache import get_cache

            size = get_cache().size()
        except Exception:  # pragma: no cover – defensivt
            size = 0

        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")
        return f"{size / 1024:.0f} kB"

    def _create_update_group(self) -> QGroupBox:
        """Uppdatering från GitHub Releases (v2.9.0)."""
        group = QGroupBox(i18n.t("update.group"))
        inner = QVBoxLayout(group)

        self.update_version_label = QLabel(
            i18n.t("update.current", version=self._app_version or "—")
        )
        self.update_version_label.setProperty("role", "muted")
        inner.addWidget(self.update_version_label)

        self.update_status_label = QLabel("")
        self.update_status_label.setWordWrap(True)
        self.update_status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        inner.addWidget(self.update_status_label)

        button_row = QVBoxLayout()

        self.update_check_button = QPushButton(i18n.t("update.check"))
        self.update_check_button.clicked.connect(self.check_for_updates)
        button_row.addWidget(self.update_check_button)

        self.update_install_button = QPushButton(i18n.t("update.install"))
        self.update_install_button.setEnabled(False)
        self.update_install_button.clicked.connect(self.install_update)
        button_row.addWidget(self.update_install_button)

        self.update_release_button = QPushButton(i18n.t("update.release_page"))
        self.update_release_button.clicked.connect(self._open_release_page)
        button_row.addWidget(self.update_release_button)

        button_row.addStretch()
        inner.addLayout(button_row)
        return group

    # ──────────────────────────────────────────────────────
    # Uppdatering från GitHub (v2.9.0)
    # ──────────────────────────────────────────────────────

    def _app_dir(self) -> Path:
        """Appens rotmapp (data/-mappens förälder)."""
        data_dir = Path(self._data_path())
        return data_dir.parent if data_dir.name == "data" else data_dir

    def check_for_updates(self) -> None:
        """
        Sök efter en nyare release på GitHub (i bakgrunden).

        Knappen är avstängd medan sökningen pågår. Nätverksfel visas i
        statusraden i stället för att kasta undantag.
        """
        if self._update_busy:
            return

        self._update_busy = True
        self.update_check_button.setEnabled(False)
        self.update_install_button.setEnabled(False)
        self.update_status_label.setText(i18n.t("update.checking"))
        logger.info("Söker efter uppdatering (lokal version %s)", self._app_version)

        threading.Thread(target=self._check_worker, daemon=True).start()

    def show_update_check(self) -> None:
        """Visa Avancerat-fliken och sök direkt efter uppdatering."""
        if self._tabs.count():
            self._tabs.setCurrentIndex(self._tabs.count() - 1)
        self.check_for_updates()

    def _check_worker(self) -> None:
        """Arbetstråd: fråga GitHub efter senaste releasen."""
        try:
            info = updater.check_for_update(self._app_version)
            self._update_signals.checked.emit(info, None)
        except Exception as exc:  # noqa: BLE001 – allt ska bli ett meddelande
            logger.warning("Uppdateringskontrollen misslyckades: %s", exc)
            self._update_signals.checked.emit(None, exc)

    def _on_update_checked(self, info: Any, error: Any) -> None:
        """Visa resultatet av sökningen."""
        self._update_busy = False
        self.update_check_button.setEnabled(True)

        if error is not None or info is None:
            self._update_info = None
            self.update_install_button.setEnabled(False)
            self.update_status_label.setText(
                i18n.t("update.error", error=error or "?")
            )
            return

        self._update_info = info
        self.update_version_label.setText(
            i18n.t("update.current", version=info.local_version or self._app_version)
        )

        if info.available:
            text = i18n.t(
                "update.available",
                version=info.version,
                date=info.published_date or "—",
            )
            notes = (info.notes or "").strip()
            if notes:
                text += "\n\n" + i18n.t("update.notes") + "\n" + notes[:600]
            self.update_status_label.setText(text)
            self.update_install_button.setEnabled(bool(info.zip_url))
            if not info.zip_url:
                self.update_status_label.setText(
                    text + "\n" + i18n.t("update.no_zip")
                )
            else:
                # Manual search (settings, Help or tray): offer the existing
                # confirmation immediately. No installation without Yes.
                self.install_update()
        else:
            self.update_status_label.setText(
                i18n.t("update.latest", version=info.version or self._app_version)
            )
            self.update_install_button.setEnabled(False)

    def install_update(self) -> None:
        """Fråga först, ladda sedan ner och installera i bakgrunden."""
        info = self._update_info
        if info is None or not info.available or not info.zip_url or self._update_busy:
            return

        answer = QMessageBox.question(
            self,
            i18n.t("update.confirm_title"),
            i18n.t("update.confirm", old=info.local_version, new=info.version),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._update_busy = True
        self.update_check_button.setEnabled(False)
        self.update_install_button.setEnabled(False)
        self.update_status_label.setText(i18n.t("update.downloading", percent=0))

        threading.Thread(target=self._install_worker, args=(info,), daemon=True).start()

    def _install_worker(self, info: Any) -> None:
        """Arbetstråd: ladda ner releasen och skriv filerna."""
        import tempfile

        try:
            with tempfile.TemporaryDirectory(prefix="semesterlista_update_") as tmp:
                zip_path = updater.download_release(
                    info,
                    Path(tmp) / "release.zip",
                    progress=lambda done, total: self._update_signals.progress.emit(
                        done, total
                    ),
                )
                self._update_signals.progress.emit(0, 0)  # 0 = "installerar"
                result = updater.install_from_zip(
                    zip_path,
                    self._app_dir(),
                    local_version=info.local_version,
                )
            self._update_signals.installed.emit(result, None)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Uppdateringen misslyckades")
            self._update_signals.installed.emit(None, exc)

    def _on_update_progress(self, done: int, total: int) -> None:
        """Visa nedladdningens förlopp."""
        if done == 0 and total == 0:
            self.update_status_label.setText(i18n.t("update.installing"))
            return

        percent = int(done * 100 / total) if total else 0
        self.update_status_label.setText(
            i18n.t("update.downloading", percent=min(percent, 99))
        )

    def _on_update_installed(self, result: Any, error: Any) -> None:
        """Klar (eller fel) – erbjud omstart."""
        self._update_busy = False
        self.update_check_button.setEnabled(True)

        if error is not None or result is None:
            self.update_status_label.setText(
                i18n.t("update.install_error", error=error or "?")
            )
            QMessageBox.warning(
                self,
                i18n.t("update.confirm_title"),
                i18n.t("update.install_error", error=error or "?"),
            )
            return

        self.update_status_label.setText(
            i18n.t(
                "update.done",
                version=result.version,
                files=result.file_count,
                backup=result.backup or "—",
            )
        )
        self.update_install_button.setEnabled(False)

        if self.event_bus is not None:
            try:
                self.event_bus.emit("app:updated", {"version": result.version})
            except Exception:  # pragma: no cover – defensivt
                pass

        answer = QMessageBox.question(
            self,
            i18n.t("update.restart_title"),
            i18n.t("update.restart_question", version=result.version),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.restart_application()
        else:
            QMessageBox.information(
                self,
                i18n.t("update.restart_title"),
                i18n.t("update.restart_manual"),
            )

    def restart_application(self) -> None:
        """Starta om appen med den nya versionen."""
        from PySide6.QtWidgets import QApplication

        command = updater.restart_command(self._app_dir())
        logger.info("Startar om appen: %s", " ".join(command))

        started = QProcess.startDetached(command[0], command[1:])
        if not started:
            QMessageBox.warning(
                self,
                i18n.t("update.restart_title"),
                i18n.t("update.restart_manual"),
            )
            return

        QApplication.quit()

    def _open_release_page(self) -> None:
        """Öppna release-sidan i webbläsaren."""
        url = (
            self._update_info.html_url
            if self._update_info is not None and self._update_info.html_url
            else updater.github_release_url()
        )
        logger.info("Öppnar release-sidan: %s", url)
        QDesktopServices.openUrl(QUrl(url))

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
        self.clear_cache_check.setChecked(
            bool(get("advanced.clear_cache_on_exit", True))
        )

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
        manager.set(
            "advanced.clear_cache_on_exit", self.clear_cache_check.isChecked()
        )

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

    def _open_error_log(self) -> None:
        """Öppna felloggen i systemets standardprogram (v2.12.0)."""
        error_log = get_error_log_file()
        if error_log is None or not Path(error_log).exists():
            QMessageBox.information(
                self,
                i18n.t("settings.title"),
                i18n.t("settings.error_log_empty"),
            )
            return

        try:
            if platform.system() == "Windows":
                os.startfile(str(error_log))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(error_log)], check=False)
            else:
                subprocess.run(["xdg-open", str(error_log)], check=False)
        except Exception as exc:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte öppna felloggen: {exc}")
            QMessageBox.warning(
                self,
                i18n.t("settings.title"),
                i18n.t("settings.open_log_error", error=exc),
            )

    def _clear_error_log(self) -> None:
        """Rensa felloggen när felen är åtgärdade (v2.12.0)."""
        answer = QMessageBox.question(
            self,
            i18n.t("settings.title"),
            i18n.t("settings.clear_error_log_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        if clear_error_log():
            logger.info("Felloggen rensad av användaren")
            self.error_log_label.setText(
                i18n.t(
                    "settings.error_log_file",
                    path=str(get_error_log_file() or "—"),
                    count=error_log_lines(),
                )
            )
            self.clear_error_log_button.setEnabled(False)
        else:
            QMessageBox.warning(
                self,
                i18n.t("settings.title"),
                i18n.t("settings.clear_error_log_failed"),
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
