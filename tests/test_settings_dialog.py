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

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from core.settings_dialog import (
        HOLIDAY_REGIONS,
        MODULE_VERSION,
        THEME_ORDER,
        SettingsDialog,
    )

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

    def test_module_version(self) -> None:
        self.assertEqual(MODULE_VERSION, "2.8.0")

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
        self.assertFalse(dialog.start_minimized_check.isChecked())
        self.assertFalse(dialog.close_to_tray_check.isChecked())
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
        self.assertFalse(self.manager.get("systray.minimize_to_tray"))
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

    def test_data_path_label_points_to_data_dir(self) -> None:
        dialog = self.make_dialog()
        self.assertEqual(
            dialog._data_path(), str(Path(self._tmp.name) / "data")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
