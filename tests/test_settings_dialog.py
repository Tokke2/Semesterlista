#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för inställningsdialogen (v2.8.0).

Dialogen kräver PySide6. Saknas det hoppas hela filen över. Testerna körs
off-screen och använder en temporär data/-mapp, så riktiga inställningar
rörs aldrig.

    python -m unittest discover -s tests -v
    python tests/test_settings_dialog.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.version import current_version  # noqa: E402

#: Appens version enligt config.json – modulerna som följer appen ska matcha
APP_VERSION = current_version(PROJECT_ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from core.settings_dialog import (
        HOLIDAY_REGIONS,
        MODULE_VERSION,
        THEME_ORDER,
        SettingsDialog,
    )
    from core.updater import UpdateInfo

    HAVE_QT = True
except Exception:  # pragma: no cover – miljö utan PySide6
    HAVE_QT = False


class FakeLock:
    """Låtsas om SingleInstanceLock (autostart utan register/autostartfil)."""

    def __init__(self, autostart: bool = False):
        self.autostart = autostart
        self.calls: list[bool] = []

    def get_autostart(self) -> bool:
        return self.autostart

    def set_autostart(self, value: bool) -> bool:
        self.autostart = bool(value)
        self.calls.append(bool(value))
        return True


class FakeThemeManager:
    """Registrerar temabytet i stället för att måla om appen."""

    VALID_THEMES = ("dark", "light", "system")

    def __init__(self) -> None:
        self.themes: list[str] = []

    def set_theme(self, theme: str) -> None:
        self.themes.append(theme)


class FakePlugin:
    def __init__(self, name: str):
        self._name = name

    def get_name(self) -> str:
        return self._name


class FakePluginManager:
    """Minimal PluginManager med två plugins."""

    def __init__(self) -> None:
        self._plugins = {
            "lista": FakePlugin("Semesterlista & Limokörning"),
            "hyra": FakePlugin("Hyresfakturering"),
        }
        self._order = ["lista", "hyra"]

    def get_plugin_order(self) -> list[str]:
        return list(self._order)

    def get_plugin(self, name: str):
        return self._plugins.get(name)


@unittest.skipUnless(HAVE_QT, "PySide6 saknas")
class SettingsDialogTests(unittest.TestCase):
    """Bygge, inläsning och sparande av inställningar."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.app = QApplication.instance() or QApplication([])
        except Exception as exc:  # pragma: no cover – ingen skärm
            raise unittest.SkipTest(f"Qt kunde inte startas: {exc}")

        from core import i18n

        cls.i18n = i18n
        cls.original_language = i18n.current_language()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.i18n.set_language(cls.original_language)

    def setUp(self) -> None:
        from core.settings_manager import SettingsManager

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

        # Never open a blocking native prompt in the test runner.
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        prompt = patch("core.settings_dialog.QMessageBox.question",
                       return_value=QMessageBox.StandardButton.No)
        self.update_question = prompt.start()
        self.addCleanup(prompt.stop)

        self.manager = SettingsManager(self._tmp.name)
        self.i18n.init(self.manager)

        self.theme_manager = FakeThemeManager()
        self.lock = FakeLock()
        self.plugin_manager = FakePluginManager()

        self.addCleanup(self.i18n.set_language, self.original_language)

    def make_dialog(self, **kwargs) -> "SettingsDialog":
        params = dict(
            settings_manager=self.manager,
            theme_manager=self.theme_manager,
            lock=self.lock,
            plugin_manager=self.plugin_manager,
            event_bus=None,
        )
        params.update(kwargs)
        dialog = SettingsDialog(**params)
        self.addCleanup(dialog.deleteLater)
        return dialog

    # ── Bygge ────────────────────────────────────────────

    def test_small_window_scrolls_without_hiding_actions(self) -> None:
        from PySide6.QtWidgets import QDialogButtonBox, QScrollArea
        from PySide6.QtCore import QPoint
        for language in ("sv", "en"):
            self.i18n.set_language(language)
            dialog = self.make_dialog()
            dialog._tabs.setCurrentIndex(3)
            dialog.update_status_label.setText("Release notes\n" * 35)
            dialog.resize(560, 420)
            dialog.show()
            self.app.processEvents()
            scroll = dialog._tabs.currentWidget()
            self.assertIsInstance(scroll, QScrollArea)
            self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
            self.assertLessEqual(dialog.height(), 420)
            buttons = dialog.findChild(QDialogButtonBox)
            self.assertTrue(dialog.rect().contains(buttons.mapTo(dialog, buttons.rect().bottomRight())))
            scroll.ensureWidgetVisible(dialog.update_release_button)
            self.app.processEvents()
            button = dialog.update_release_button
            self.assertTrue(scroll.viewport().rect().contains(button.mapTo(scroll.viewport(), QPoint(1, 1))))
            self.assertGreaterEqual(button.height(), button.minimumSizeHint().height())
            dialog.close()

    def test_all_tabs_have_scroll_access(self) -> None:
        from PySide6.QtWidgets import QScrollArea
        dialog = self.make_dialog()
        for index in range(dialog._tabs.count()):
            self.assertIsInstance(dialog._tabs.widget(index), QScrollArea)
            self.assertTrue(dialog._tabs.widget(index).widgetResizable())

    def test_module_version(self) -> None:
        self.assertEqual(MODULE_VERSION, APP_VERSION)

    def test_has_four_tabs(self) -> None:
        dialog = self.make_dialog()
        self.assertEqual(dialog._tabs.count(), 4)
        titles = [dialog._tabs.tabText(i) for i in range(4)]
        self.assertEqual(
            titles,
            [
                self.i18n.t("settings.tab.general"),
                self.i18n.t("settings.tab.window"),
                self.i18n.t("settings.tab.plugins"),
                self.i18n.t("settings.tab.advanced"),
            ],
        )

    def test_window_title(self) -> None:
        dialog = self.make_dialog()
        self.assertEqual(dialog.windowTitle(), self.i18n.t("settings.title"))

    def test_combos_have_expected_values(self) -> None:
        dialog = self.make_dialog()
        languages = [
            dialog.language_combo.itemData(i)
            for i in range(dialog.language_combo.count())
        ]
        self.assertEqual(languages, list(self.i18n.LANGUAGES))

        themes = [
            dialog.theme_combo.itemData(i) for i in range(dialog.theme_combo.count())
        ]
        self.assertEqual(themes, list(THEME_ORDER))

        regions = [
            dialog.holiday_combo.itemData(i)
            for i in range(dialog.holiday_combo.count())
        ]
        self.assertEqual(regions, list(HOLIDAY_REGIONS))

    def test_plugin_checkboxes(self) -> None:
        dialog = self.make_dialog()
        self.assertIn("Semesterlista & Limokörning", dialog._plugin_checks)
        self.assertIn("Hyresfakturering", dialog._plugin_checks)

    def test_autostart_disabled_without_lock(self) -> None:
        dialog = self.make_dialog(lock=None)
        self.assertFalse(dialog.autostart_check.isEnabled())

    def test_works_without_optional_components(self) -> None:
        dialog = self.make_dialog(
            theme_manager=None, lock=None, plugin_manager=None, event_bus=None
        )
        self.assertEqual(dialog._tabs.count(), 4)

    # ── Inläsning ────────────────────────────────────────

    def test_loads_saved_values(self) -> None:
        self.manager.set("language", "en")
        self.manager.set("theme", "light")
        self.manager.set("holiday_region", "us")
        self.manager.set("systray.start_minimized", False)
        self.manager.set("systray.close_to_tray", False)
        self.manager.set("systray.show_notifications", False)
        self.manager.set("systray.notification_duration_ms", 5500)
        self.manager.set("advanced.debug_mode", True)
        self.manager.set("advanced.log_to_file", False)
        self.manager.set("advanced.check_updates", False)
        self.lock.autostart = True

        dialog = self.make_dialog()

        self.assertEqual(dialog.language_combo.currentData(), "en")
        self.assertEqual(dialog.theme_combo.currentData(), "light")
        self.assertEqual(dialog.holiday_combo.currentData(), "us")
        self.assertTrue(dialog.start_minimized_check.isChecked())
        self.assertFalse(dialog.start_minimized_check.isEnabled())
        self.assertTrue(dialog.close_to_tray_check.isChecked())
        self.assertFalse(dialog.close_to_tray_check.isEnabled())
        self.assertFalse(dialog.minimize_to_tray_check.isEnabled())
        self.assertFalse(dialog.notifications_check.isChecked())
        self.assertEqual(dialog.duration_spin.value(), 5500)
        self.assertTrue(dialog.debug_check.isChecked())
        self.assertFalse(dialog.log_to_file_check.isChecked())
        self.assertFalse(dialog.check_updates_check.isChecked())
        self.assertTrue(dialog.autostart_check.isChecked())

    def test_unknown_values_fall_back(self) -> None:
        self.manager.set("theme", "okänt-tema")
        self.manager.set("holiday_region", "fi")
        dialog = self.make_dialog()
        self.assertEqual(dialog.theme_combo.currentData(), "system")
        self.assertEqual(dialog.holiday_combo.currentData(), "sv")

    # ── Sparande ─────────────────────────────────────────

    def test_apply_settings_persists(self) -> None:
        dialog = self.make_dialog()

        index = dialog.theme_combo.findData("light")
        dialog.theme_combo.setCurrentIndex(index)
        index = dialog.holiday_combo.findData("us")
        dialog.holiday_combo.setCurrentIndex(index)
        dialog.minimize_to_tray_check.setChecked(False)
        dialog.duration_spin.setValue(2500)
        dialog.debug_check.setChecked(True)
        dialog._plugin_checks["Hyresfakturering"].setChecked(False)

        dialog.apply_settings()

        self.assertEqual(self.manager.get("theme"), "light")
        self.assertEqual(self.manager.get("holiday_region"), "us")
        self.assertTrue(self.manager.get("systray.minimize_to_tray"))
        self.assertEqual(self.manager.get("systray.notification_duration_ms"), 2500)
        self.assertTrue(self.manager.get("advanced.debug_mode"))

        # Themesättaren anropas och plugin-statusen sparas i plugins.json
        self.assertEqual(self.theme_manager.themes, ["light"])
        self.assertFalse(
            self.manager.get_plugin_info("Hyresfakturering").get("enabled")
        )

        # Inställningarna ligger kvar efter omläsning från disk
        self.manager.reload()
        self.assertEqual(self.manager.get("theme"), "light")

    def test_apply_settings_changes_language(self) -> None:
        dialog = self.make_dialog()
        index = dialog.language_combo.findData("en")
        dialog.language_combo.setCurrentIndex(index)

        dialog.apply_settings()

        self.assertEqual(self.manager.get("language"), "en")
        self.assertEqual(self.i18n.current_language(), "en")

    def test_apply_settings_sets_autostart(self) -> None:
        dialog = self.make_dialog()
        dialog.autostart_check.setChecked(True)
        dialog.apply_settings()

        self.assertTrue(self.lock.autostart)
        self.assertEqual(self.lock.calls, [True])
        self.assertTrue(self.manager.get("advanced.autostart"))

    def test_apply_settings_keeps_autostart_when_unchanged(self) -> None:
        self.lock.autostart = True
        dialog = self.make_dialog()
        dialog.apply_settings()
        self.assertEqual(self.lock.calls, [])

    def test_apply_without_theme_manager(self) -> None:
        dialog = self.make_dialog(theme_manager=None)
        index = dialog.theme_combo.findData("dark")
        dialog.theme_combo.setCurrentIndex(index)
        dialog.apply_settings()
        self.assertEqual(self.manager.get("theme"), "dark")

    # ── Uppdatering från GitHub (v2.9.0) ────────────────

    def _update_info(self, version: str = "2.9.0", local: str = "2.8.1") -> "UpdateInfo":
        return UpdateInfo(
            tag="v0.0.1",
            version=version,
            name="Semesterlista v0.0.1",
            published_at="2026-11-02T13:57:26Z",
            notes="Nytt: uppdateringsknapp",
            html_url="https://github.com/Tokke2/Semesterlista/releases/tag/v0.0.1",
            zip_url="https://codeload.github.com/Tokke2/Semesterlista/zip/refs/tags/v0.0.1",
            local_version=local,
        )

    def test_cache_checkbox_exists_and_defaults_on(self) -> None:
        """Smart cache: rutan är ikryssad som standard (v2.11.0)."""
        dialog = self.make_dialog()
        self.assertTrue(dialog.clear_cache_check.isChecked())
        self.assertIn("cache", dialog.cache_size_label.text().lower())

    def test_cache_checkbox_is_saved(self) -> None:
        dialog = self.make_dialog()
        dialog.clear_cache_check.setChecked(False)
        dialog.apply_settings()
        self.assertFalse(self.manager.get("advanced.clear_cache_on_exit"))

        dialog2 = self.make_dialog()
        self.assertFalse(dialog2.clear_cache_check.isChecked())

    def test_error_log_widgets_exist(self) -> None:
        """Felloggen har egna rader i Avancerat (v2.12.0)."""
        dialog = self.make_dialog()
        self.assertIn("fellogg", dialog.error_log_label.text().lower())
        self.assertTrue(dialog.open_error_log_button.text())
        self.assertTrue(dialog.clear_error_log_button.text())
        # Utan fellogg (ingen loggning igång) är knapparna avstängda
        self.assertFalse(dialog.open_error_log_button.isEnabled())

    def test_error_log_buttons_are_translated(self) -> None:
        from core import i18n

        old = i18n.current_language()
        try:
            i18n.set_language("en")
            dialog = self.make_dialog()
            self.assertEqual(
                dialog.open_error_log_button.text(), i18n.t("settings.open_error_log")
            )
            self.assertEqual(
                dialog.clear_error_log_button.text(), i18n.t("settings.clear_error_log")
            )
            dialog.deleteLater()
        finally:
            i18n.set_language(old)

    def test_update_group_exists(self) -> None:
        dialog = self.make_dialog(app_version="2.8.1")
        self.assertTrue(dialog.update_check_button.isEnabled())
        self.assertFalse(dialog.update_install_button.isEnabled())
        self.assertIn("2.8.1", dialog.update_version_label.text())
        self.assertTrue(dialog.update_release_button.isEnabled())

    def test_update_available_enables_install(self) -> None:
        dialog = self.make_dialog(app_version="2.8.1")
        dialog._on_update_checked(self._update_info(), None)

        self.assertTrue(dialog.update_install_button.isEnabled())
        self.assertIn("2.9.0", dialog.update_status_label.text())
        self.assertIn("2026-11-02", dialog.update_status_label.text())
        self.assertIn("uppdateringsknapp", dialog.update_status_label.text())

    def test_new_update_prompts_and_no_does_not_install(self) -> None:
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        dialog = self.make_dialog(app_version="2.8.1")
        with patch("core.settings_dialog.threading.Thread") as worker:
            dialog._on_update_checked(self._update_info(), None)
            worker.assert_not_called()
        self.update_question.assert_called_once()
        args = self.update_question.call_args.args
        self.assertIn("2.8.1", args[2])
        self.assertIn("2.9.0", args[2])
        self.assertEqual(args[-1], QMessageBox.StandardButton.No)
        self.assertTrue(dialog.update_install_button.isEnabled())
        self.assertFalse(dialog._update_busy)

    def test_new_update_yes_starts_one_install_without_second_prompt(self) -> None:
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        self.update_question.return_value = QMessageBox.StandardButton.Yes
        dialog = self.make_dialog(app_version="2.8.1")
        info = self._update_info()
        with patch("core.settings_dialog.threading.Thread") as worker:
            dialog._on_update_checked(info, None)
            worker.assert_called_once_with(target=dialog._install_worker,
                                           args=(info,), daemon=True)
            worker.return_value.start.assert_called_once()
        self.update_question.assert_called_once()
        self.assertTrue(dialog._update_busy)
        self.assertFalse(dialog.update_install_button.isEnabled())
        self.assertFalse(dialog.update_check_button.isEnabled())

    def test_no_prompt_for_latest_error_or_missing_download(self) -> None:
        dialog = self.make_dialog(app_version="2.9.0")
        no_zip = self._update_info()
        no_zip.zip_url = ""
        for info, error in [
            (self._update_info(version="2.9.0", local="2.9.0"), None),
            (None, RuntimeError("offline")),
            (no_zip, None),
        ]:
            dialog._on_update_checked(info, error)
            self.update_question.assert_not_called()
        dialog.install_update()
        self.update_question.assert_not_called()

    def test_update_latest_disables_install(self) -> None:
        dialog = self.make_dialog(app_version="2.9.0")
        dialog._on_update_checked(self._update_info(version="2.9.0", local="2.9.0"), None)

        self.assertFalse(dialog.update_install_button.isEnabled())
        self.assertIn("senaste", dialog.update_status_label.text())

    def test_update_error_is_shown(self) -> None:
        dialog = self.make_dialog(app_version="2.9.0")
        dialog._on_update_checked(None, RuntimeError("Ingen kontakt med GitHub"))

        self.assertFalse(dialog.update_install_button.isEnabled())
        self.assertIn("Ingen kontakt", dialog.update_status_label.text())

    def test_update_without_zip_disables_install(self) -> None:
        dialog = self.make_dialog(app_version="2.8.1")
        info = self._update_info()
        info.zip_url = ""
        dialog._on_update_checked(info, None)
        self.assertFalse(dialog.update_install_button.isEnabled())

    def test_install_update_without_info_is_noop(self) -> None:
        dialog = self.make_dialog(app_version="2.8.1")
        dialog.install_update()          # ska bara returnera
        self.assertFalse(dialog.update_install_button.isEnabled())

    def test_check_for_updates_reports_error(self) -> None:
        """Knappen anropar GitHub i bakgrunden – fel ska hamna i statusraden."""
        from unittest import mock

        from core import updater

        dialog = self.make_dialog(app_version="2.9.0")
        with mock.patch.object(
            updater, "check_for_update", side_effect=RuntimeError("nätet är nere")
        ):
            dialog.check_for_updates()
            self.assertFalse(dialog.update_check_button.isEnabled())

            import time

            for _ in range(200):
                self.app.processEvents()
                if dialog.update_check_button.isEnabled():
                    break
                time.sleep(0.01)

        self.assertTrue(dialog.update_check_button.isEnabled())
        self.assertIn("nätet är nere", dialog.update_status_label.text())

    def test_data_path_label_points_to_data_dir(self) -> None:
        dialog = self.make_dialog()
        self.assertEqual(
            dialog._data_path(), str(Path(self._tmp.name) / "data")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
