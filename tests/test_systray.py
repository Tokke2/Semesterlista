#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för systemfältets högerklicksmeny (v2.10.0).

Menyn ska innehålla genvägarna *Inställningar…*, *Sök efter uppdatering…*
och *Om <app> v<version>…*, spegla fönstrets läge i *Visa*/*Dölj* och byta
språk tillsammans med resten av appen.

Kräver PySide6 och körs offscreen. Saknas Qt hoppas filen över.

    python -m unittest discover -s tests -v
    python tests/test_systray.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAVE_QT = True
except Exception:  # pragma: no cover – miljö utan PySide6
    HAVE_QT = False

MAIN_PATH = PROJECT_ROOT / "main.pyw"


class FakeMainWindow:
    """Minimal MainWindow-stub som systemfältshanteraren behöver."""

    def __init__(self) -> None:
        self.visible = False
        self.calls: list = []

    def _app_name(self) -> str:
        return "Semesterlista"

    def show_application(self) -> None:
        self.visible = True
        self.calls.append("show")

    def hide_application(self) -> None:
        self.visible = False
        self.calls.append("hide")

    def isVisible(self) -> bool:  # noqa: N802 – Qt-API
        return self.visible

    def _open_settings(self, check_updates: bool = False) -> None:
        self.calls.append(("settings", check_updates))

    def _show_about(self) -> None:
        self.calls.append("about")

    def _quit_application(self) -> None:
        self.calls.append("quit")


@unittest.skipUnless(HAVE_QT, "PySide6 saknas")
class SystrayMenuTests(unittest.TestCase):
    """Högerklicksmenyn i systemfältet."""

    @classmethod
    def setUpClass(cls) -> None:
        if not MAIN_PATH.exists():  # pragma: no cover – defensivt
            raise unittest.SkipTest("main.pyw saknas")

        cls.app = QApplication.instance() or QApplication([])

        from core import i18n
        from core.settings_manager import SettingsManager

        cls._i18n_tmp = tempfile.TemporaryDirectory()
        cls.i18n = i18n
        i18n.init(SettingsManager(cls._i18n_tmp.name))

        # main.pyw är en .pyw-fil – laddas med SourceFileLoader
        loader = SourceFileLoader("semesterlista_main", str(MAIN_PATH))
        spec = importlib.util.spec_from_loader("semesterlista_main", loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules["semesterlista_main"] = module
        loader.exec_module(module)
        cls.main = module

    @classmethod
    def tearDownClass(cls) -> None:
        cls.i18n.set_language("sv")
        cls._i18n_tmp.cleanup()

    def setUp(self) -> None:
        self.window = FakeMainWindow()
        self.tray = self.main.SystrayManager(self.app, self.window)
        self.addCleanup(self.tray._tray_icon.hide)
        self.menu = self.tray._tray_menu

    def _texts(self) -> list:
        return [a.text() for a in self.menu.actions() if not a.isSeparator()]

    # ── Innehåll ─────────────────────────────────────────

    def test_menu_has_the_new_shortcuts(self) -> None:
        texts = self._texts()
        self.assertIn(self.i18n.t("tray.settings"), texts)
        self.assertIn(self.i18n.t("tray.check_updates"), texts)
        self.assertIn(
            self.i18n.t("tray.about", app="Semesterlista", version=self.main.APP_VERSION),
            texts,
        )

    def test_menu_order(self) -> None:
        texts = self._texts()
        self.assertEqual(
            texts[:2], [self.i18n.t("tray.show", app="Semesterlista"), self.i18n.t("tray.hide")]
        )
        self.assertEqual(texts[-1], self.i18n.t("tray.quit"))

    def test_about_shows_app_version(self) -> None:
        label = self.tray._about_action.text()
        self.assertIn(self.main.APP_VERSION, label)
        self.assertIn("Semesterlista", label)

    # ── Åtgärder ─────────────────────────────────────────

    def test_settings_action_opens_settings(self) -> None:
        self.tray._settings_action.trigger()
        self.assertEqual(self.window.calls, [("settings", False)])

    def test_update_action_opens_settings_and_checks(self) -> None:
        self.tray._update_action.trigger()
        self.assertEqual(self.window.calls, [("settings", True)])

    def test_about_action_shows_about(self) -> None:
        self.tray._about_action.trigger()
        self.assertEqual(self.window.calls, ["about"])

    def test_show_action_shows_window(self) -> None:
        self.tray._show_action.trigger()
        self.assertTrue(self.window.visible)
        self.assertEqual(self.window.calls, ["show"])

    # ── Läget speglas ────────────────────────────────────

    def test_actions_follow_window_state(self) -> None:
        self.tray._sync_actions()
        self.assertFalse(self.window.visible)
        self.assertTrue(self.tray._show_action.isEnabled())
        self.assertFalse(self.tray._hide_action.isEnabled())

        self.window.visible = True
        self.tray._sync_actions()
        self.assertFalse(self.tray._show_action.isEnabled())
        self.assertTrue(self.tray._hide_action.isEnabled())

    def test_default_action_follows_window_state(self) -> None:
        self.tray._sync_actions()
        self.assertIs(self.menu.defaultAction(), self.tray._show_action)

        self.window.visible = True
        self.tray._sync_actions()
        self.assertIs(self.menu.defaultAction(), self.tray._hide_action)

    # ── Språk ────────────────────────────────────────────

    def test_retranslate_follows_language(self) -> None:
        self.i18n.set_language("en")
        self.tray.retranslate()

        texts = self._texts()
        self.assertIn("Settings…", texts)
        self.assertIn("Check for updates…", texts)
        self.assertIn("Quit", texts)
        self.assertTrue(
            any(t.startswith("About Semesterlista v") for t in texts), texts
        )

        self.i18n.set_language("sv")
        self.tray.retranslate()
        self.assertIn("Inställningar…", self._texts())


if __name__ == "__main__":
    unittest.main(verbosity=2)
