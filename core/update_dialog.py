#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uppdateringsdialog (PySide6) – v2.4.0
=====================================

GUI-delen av uppdateringen mot GitHub Releases:

    UpdateCheckWorker     – söker efter ny release i en arbetstråd
    UpdateDownloadWorker  – laddar ner i en arbetstråd med progress
    UpdateDialog          – visar version, release-notes och knappar

Modulen innehåller ingen nätverkslogik själv – allt sådant ligger i
core/updater.py (som är Qt-fritt och testbart).

Användning (manuell kontroll):
    from core.update_dialog import UpdateDialog
    dialog = UpdateDialog(updater, parent=self)
    dialog.exec()

Användning (automatisk kontroll vid start):
    from core.update_dialog import UpdateCheckWorker
    worker = UpdateCheckWorker(updater, parent=self)
    worker.checked.connect(self._on_update_checked)
    worker.failed.connect(self._on_update_check_failed)
    worker.start()

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core import i18n
from core.updater import (
    ApplyResult,
    GitHubUpdater,
    UpdateError,
    UpdateInfo,
    is_skipped,
    record_check,
    skip_version,
    snooze,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.4.0"


def _format_mb(num_bytes: int) -> str:
    """Formatera byte som MB med en decimal (sv/en-kompatibelt)."""
    try:
        return f"{int(num_bytes) / (1024 * 1024):.1f}"
    except (TypeError, ValueError):  # pragma: no cover – defensivt
        return "0.0"


# ══════════════════════════════════════════════════════════
# ARBETSTRÅDAR
# ══════════════════════════════════════════════════════════

class UpdateCheckWorker(QThread):
    """
    Söker efter en nyare release utan att blockera gränssnittet.

    Signaler:
        checked(object): UpdateInfo om en nyare version finns, annars None.
        failed(str):     Felmeddelande (nätverk, API, ratelimit …).
    """

    checked = Signal(object)
    failed = Signal(str)

    def __init__(self, updater: GitHubUpdater, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._updater = updater

    def run(self) -> None:  # noqa: D401 – QThread-konvention
        try:
            info = self._updater.check()
        except UpdateError as exc:
            logger.warning(f"Uppdateringskontroll misslyckades: {exc}")
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # pragma: no cover – oväntat fel
            logger.exception("Oväntat fel vid uppdateringskontroll")
            self.failed.emit(str(exc))
            return

        self.checked.emit(info)


class UpdateDownloadWorker(QThread):
    """
    Laddar ner release-filen i bakgrunden.

    Signaler:
        progress(int, int): nedladdade byte, totala byte (0 = okänt).
        downloaded(object): sökvägen till den nedladdade filen (Path).
        failed(str):        Felmeddelande.
    """

    progress = Signal(int, int)
    downloaded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        updater: GitHubUpdater,
        update: UpdateInfo,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._updater = updater
        self._update = update

    def run(self) -> None:  # noqa: D401 – QThread-konvention
        try:
            archive = self._updater.download(
                self._update,
                progress=lambda done, total: self.progress.emit(int(done), int(total)),
            )
        except UpdateError as exc:
            logger.warning(f"Nedladdning misslyckades: {exc}")
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # pragma: no cover – oväntat fel
            logger.exception("Oväntat fel vid nedladdning")
            self.failed.emit(str(exc))
            return

        self.downloaded.emit(archive)


# ══════════════════════════════════════════════════════════
# DIALOGEN
# ══════════════════════════════════════════════════════════

class UpdateDialog(QDialog):
    """
    Visar tillgänglig uppdatering och sköter nedladdning + installation.

    Dialogen kan användas på två sätt:
        - update=None  → söker själv efter uppdatering när den öppnas.
        - update=info  → visar en redan hittad uppdatering direkt
                         (används när den automatiska kontrollen hittat något).
    """

    def __init__(
        self,
        updater: GitHubUpdater,
        parent: Optional[QWidget] = None,
        update: Optional[UpdateInfo] = None,
        settings_manager: Any = None,
        auto: bool = False,
    ):
        """
        Args:
            updater:          GitHubUpdater-instansen.
            parent:           Förälderfönster.
            update:           Redan hittad uppdatering (valfritt).
            settings_manager: Används för att komma ihåg "hoppa över" m.m.
            auto:             True när dialogen öppnats av den automatiska
                              kontrollen (påverkar bara loggning/status).
        """
        super().__init__(parent)

        self._updater = updater
        self._settings_manager = settings_manager
        self._update = update
        self._auto = auto

        self._check_worker: Optional[UpdateCheckWorker] = None
        self._download_worker: Optional[UpdateDownloadWorker] = None
        self._archive: Optional[Path] = None
        self._busy = False

        self.setWindowTitle(i18n.t("update.title_app", app=self._app_name()))
        self.setMinimumWidth(560)
        self.setSizeGripEnabled(True)

        self._build_ui()

        if update is not None:
            self._show_update(update)
        else:
            self._start_check()

    # ──────────────────────────────────────────────────────
    # Publikt gränssnitt
    # ──────────────────────────────────────────────────────

    @property
    def update(self) -> Optional[UpdateInfo]:
        """Uppdateringen dialogen visar (None om ingen hittades)."""
        return self._update

    # ──────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────

    def _app_name(self) -> str:
        """Appens namn (från inställningarna om de finns)."""
        if self._settings_manager is not None:
            try:
                return str(self._settings_manager.get("app_name", "Semesterlista"))
            except Exception:  # pragma: no cover – defensivt
                pass
        return "Semesterlista"

    def _build_ui(self) -> None:
        """Bygg dialogens innehåll."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        self._title_label = QLabel(i18n.t("update.checking_title"))
        title_font = self._title_label.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        layout.addWidget(self._title_label)

        self._summary_label = QLabel(i18n.t("update.checking"))
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        self._version_label = QLabel("")
        self._version_label.setWordWrap(True)
        layout.addWidget(self._version_label)

        self._notes_label = QLabel("")
        self._notes_label.setVisible(False)
        layout.addWidget(self._notes_label)

        self._notes_view = QTextBrowser()
        self._notes_view.setOpenExternalLinks(True)
        self._notes_view.setMinimumHeight(180)
        self._notes_view.setVisible(False)
        layout.addWidget(self._notes_view, stretch=1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # ── Knappar ──────────────────────────────────────
        button_row = QHBoxLayout()

        self._page_button = QPushButton(i18n.t("update.button.release_page"))
        self._page_button.setAutoDefault(False)
        self._page_button.clicked.connect(self._on_open_release_page)
        button_row.addWidget(self._page_button)

        button_row.addStretch(1)

        self._skip_button = QPushButton(i18n.t("update.button.skip"))
        self._skip_button.setAutoDefault(False)
        self._skip_button.clicked.connect(self._on_skip)
        button_row.addWidget(self._skip_button)

        self._later_button = QPushButton(i18n.t("update.button.later"))
        self._later_button.setAutoDefault(False)
        self._later_button.clicked.connect(self._on_later)
        button_row.addWidget(self._later_button)

        self._install_button = QPushButton(i18n.t("update.button.install"))
        self._install_button.setDefault(True)
        self._install_button.clicked.connect(self._on_install)
        button_row.addWidget(self._install_button)

        layout.addLayout(button_row)

        self._install_button.setEnabled(False)

    # ──────────────────────────────────────────────────────
    # Kontroll
    # ──────────────────────────────────────────────────────

    def _start_check(self) -> None:
        """Starta en kontroll i bakgrunden."""
        self._title_label.setText(i18n.t("update.checking_title"))
        self._summary_label.setText(i18n.t("update.checking"))
        self._status_label.setText("")
        self._set_busy(True)

        worker = UpdateCheckWorker(self._updater, parent=self)
        worker.checked.connect(self._on_checked)
        worker.failed.connect(self._on_check_failed)
        worker.finished.connect(worker.deleteLater)
        self._check_worker = worker
        worker.start()

    def _on_checked(self, info: Optional[UpdateInfo]) -> None:
        """Kontrollen är klar."""
        self._check_worker = None
        self._set_busy(False)

        if info is None:
            record_check(self._settings_manager, "", None)
            self._title_label.setText(i18n.t("update.none_title"))
            self._summary_label.setText(
                i18n.t("update.none_body", version=str(self._updater.current))
            )
            self._version_label.setText("")
            self._notes_view.setVisible(False)
            self._notes_label.setVisible(False)
            self._install_button.setEnabled(False)
            self._skip_button.setEnabled(False)
            self._later_button.setText(i18n.t("common.close"))
            return

        record_check(self._settings_manager, info.version, None)
        self._show_update(info)

    def _on_check_failed(self, message: str) -> None:
        """Kontrollen misslyckades."""
        self._check_worker = None
        self._set_busy(False)

        self._title_label.setText(i18n.t("update.error_title"))
        self._summary_label.setText(i18n.t("update.error.check", error=message))
        self._status_label.setText("")
        self._install_button.setEnabled(False)
        self._later_button.setText(i18n.t("common.close"))

        logger.warning(f"Uppdateringskontroll misslyckades: {message}")

    # ──────────────────────────────────────────────────────
    # Visa uppdatering
    # ──────────────────────────────────────────────────────

    def _show_update(self, info: UpdateInfo) -> None:
        """Fyll dialogen med information om en hittad release."""
        self._update = info

        self._title_label.setText(i18n.t("update.found_title"))
        self._summary_label.setText(
            i18n.t(
                "update.found_body",
                new=info.version,
                current=str(self._updater.current),
            )
        )

        details = []
        if info.name and info.name not in (info.tag, f"v{info.version}"):
            details.append(info.name)
        if info.published_date():
            details.append(i18n.t("update.published", date=info.published_date()))
        if info.asset_size:
            details.append(
                i18n.t(
                    "update.asset_size",
                    size=_format_mb(info.asset_size),
                )
            )
        self._version_label.setText(" · ".join(details))

        notes = (info.notes or "").strip()
        self._notes_label.setText(i18n.t("update.notes_label", version=info.version))
        self._notes_label.setVisible(True)
        if notes:
            try:
                self._notes_view.setMarkdown(notes)
            except AttributeError:  # pragma: no cover – äldre Qt
                self._notes_view.setPlainText(notes)
            self._notes_view.setVisible(True)
        else:
            self._notes_view.setPlainText(i18n.t("update.notes_empty"))
            self._notes_view.setVisible(True)

        self._install_button.setEnabled(True)
        if not info.has_asset:
            self._install_button.setText(i18n.t("update.button.release_page"))
            self._install_button.clicked.disconnect()
            self._install_button.clicked.connect(self._on_open_release_page)

        self._later_button.setText(i18n.t("update.button.later"))
        self._skip_button.setEnabled(True)

    # ──────────────────────────────────────────────────────
    # Nedladdning och installation
    # ──────────────────────────────────────────────────────

    def _on_install(self) -> None:
        """Ladda ner och installera uppdateringen."""
        if self._update is None or self._busy:
            return

        if not self._update.has_asset:
            self._on_open_release_page()
            return

        self._set_busy(True)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)          # indeterminate tills vi vet storlek
        self._status_label.setText(i18n.t("update.downloading"))

        worker = UpdateDownloadWorker(self._updater, self._update, parent=self)
        worker.progress.connect(self._on_progress)
        worker.downloaded.connect(self._on_downloaded)
        worker.failed.connect(self._on_download_failed)
        worker.finished.connect(worker.deleteLater)
        self._download_worker = worker
        worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        """Uppdatera progressraden."""
        if total > 0:
            if self._progress.maximum() == 0:
                self._progress.setRange(0, 100)
            percent = max(0, min(100, int(done * 100 / total)))
            self._progress.setValue(percent)
            self._status_label.setText(
                i18n.t(
                    "update.progress",
                    percent=percent,
                    done=_format_mb(done),
                    total=_format_mb(total),
                )
            )
        else:
            self._progress.setRange(0, 0)
            self._status_label.setText(
                i18n.t("update.downloading_bytes", size=_format_mb(done))
            )

    def _on_downloaded(self, archive: Any) -> None:
        """Nedladdningen är klar – installera."""
        self._download_worker = None
        self._archive = Path(archive) if archive else None

        if self._archive is None or self._update is None:
            self._on_download_failed(i18n.t("update.error.download", error="?"))
            return

        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._status_label.setText(i18n.t("update.installing"))
        QApplication.processEvents()

        try:
            result: ApplyResult = self._updater.apply(self._update, self._archive)
        except UpdateError as exc:
            self._on_download_failed(str(exc))
            return
        except Exception as exc:  # pragma: no cover – oväntat fel
            logger.exception("Oväntat fel vid installation")
            self._on_download_failed(str(exc))
            return

        self._finish_apply(result)

    def _finish_apply(self, result: ApplyResult) -> None:
        """Berätta för användaren vad som händer och avsluta vid behov."""
        app_name = self._app_name()
        self._set_busy(False)

        if result.mode == "installer":
            QMessageBox.information(
                self,
                i18n.t("update.title"),
                i18n.t("update.install.installer", app=app_name),
            )
            self._quit_for_update()
            return

        if result.mode == "browser":
            self._status_label.setText(i18n.t("update.install.browser"))
            self.accept()
            return

        answer = QMessageBox.question(
            self,
            i18n.t("update.title"),
            i18n.t("update.install.restart_question", app=app_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if answer == QMessageBox.StandardButton.Yes:
            self._quit_for_update()
            return

        self._status_label.setText(
            i18n.t("update.install.on_exit", app=app_name)
        )
        self._install_button.setEnabled(False)
        self._skip_button.setEnabled(False)
        self._later_button.setText(i18n.t("common.close"))

    def _quit_for_update(self) -> None:
        """Stäng appen så att hjälpskriptet kan slutföra uppdateringen."""
        logger.info("Avslutar appen för att slutföra uppdateringen")
        self.accept()
        QApplication.quit()

    def _on_download_failed(self, message: str) -> None:
        """Nedladdning eller installation misslyckades."""
        self._download_worker = None
        self._set_busy(False)
        self._progress.setVisible(False)
        self._status_label.setText("")

        logger.warning(f"Uppdateringen misslyckades: {message}")
        QMessageBox.warning(
            self,
            i18n.t("update.error_title"),
            i18n.t("update.error.download", error=message),
        )

    # ──────────────────────────────────────────────────────
    # Övriga knappar
    # ──────────────────────────────────────────────────────

    def _on_open_release_page(self) -> None:
        """Öppna releasen i webbläsaren."""
        self._updater.open_release_page(self._update)
        if self._update is None:
            self.accept()

    def _on_later(self) -> None:
        """Påminn igen senare."""
        if self._update is not None:
            snooze(self._settings_manager, 24)
            self._status_label.setText(i18n.t("update.later"))
        self.accept()

    def _on_skip(self) -> None:
        """Hoppa över den här versionen."""
        if self._update is not None:
            skip_version(self._settings_manager, self._update.version)
            logger.info(f"Version v{self._update.version} hoppas över")
        self.accept()

    # ──────────────────────────────────────────────────────
    # Status och stängning
    # ──────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        """Lås knapparna medan något pågår i bakgrunden."""
        self._busy = busy

        for button in (
            self._install_button,
            self._later_button,
            self._skip_button,
            self._page_button,
        ):
            button.setEnabled(not busy)

    def reject(self) -> None:
        """Tillåt inte att dialogen stängs mitt under en nedladdning."""
        if self._busy:
            self._status_label.setText(i18n.t("update.busy"))
            return
        super().reject()

    def closeEvent(self, event) -> None:
        """Stäng bara när inget pågår i bakgrunden."""
        if self._busy:
            self._status_label.setText(i18n.t("update.busy"))
            event.ignore()
            return
        super().closeEvent(event)


# ══════════════════════════════════════════════════════════
# HJÄLPARE FÖR HUVUDFÖNSTRET
# ══════════════════════════════════════════════════════════

def should_prompt(settings_manager: Any, info: Optional[UpdateInfo]) -> bool:
    """
    True om en hittad uppdatering ska visas för användaren.

    Hoppar över versioner som användaren valt att hoppa över.
    """
    if info is None:
        return False
    return not is_skipped(settings_manager, info.version)
