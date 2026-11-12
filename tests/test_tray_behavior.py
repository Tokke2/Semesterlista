"""Actual window methods: close/minimize park the app, explicit Quit exits."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from test_settings_dialog import HAVE_QT


@unittest.skipUnless(HAVE_QT, 'Qt unavailable')
class TrayBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def window(self, tray):
        from PySide6.QtCore import Qt, QEvent, QTimer
        from PySide6.QtWidgets import QApplication, QMainWindow
        source = (Path(__file__).resolve().parent.parent / 'main.pyw').read_text(encoding='utf-8')
        original = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
        names = ('closeEvent', 'changeEvent', '_hide_if_minimized', 'hide_application',
                 'show_application', '_quit_application')
        original.body = [n for n in original.body if isinstance(n, ast.FunctionDef) and n.name in names]
        scope = dict(Qt=Qt, QEvent=QEvent, QTimer=QTimer, QMainWindow=QMainWindow,
                     QApplication=QApplication, sys=SimpleNamespace(platform='linux'),
                     QSystemTrayIcon=SimpleNamespace(isSystemTrayAvailable=lambda: tray))
        exec(compile(ast.Module(body=[original], type_ignores=[]), 'main.pyw', 'exec'), scope)
        window = scope['MainWindow']()
        window._save_window_state = Mock()
        window._settings_manager = SimpleNamespace(get=lambda key, default: False, set=Mock())
        window._plugin_manager = SimpleNamespace(shutdown_all=Mock(), get_plugin_order=lambda: [])
        window._event_bus = SimpleNamespace(emit=Mock())
        window.window_shown = SimpleNamespace(emit=Mock())
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.hide)
        window.show()
        self.app.processEvents()
        return window

    def test_close_ignores_old_false_setting_and_restores(self):
        window = self.window(tray=True)
        window.close()
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        window._plugin_manager.shutdown_all.assert_not_called()
        window._save_window_state.assert_called()
        window.show_application()
        self.assertTrue(window.isVisible())
        self.assertFalse(window.isMinimized())

    def test_minimize_goes_to_tray_and_quick_restore_is_not_hidden(self):
        window = self.window(tray=True)
        window.showMinimized()
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        window.show_application()
        window.showMinimized()
        window.show_application()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        self.assertFalse(window.isMinimized())

    def test_without_tray_close_and_minimize_remain_reachable(self):
        window = self.window(tray=False)
        window.close()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        self.assertTrue(window.isMinimized())
        window.show_application()
        window.showMinimized()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        window._plugin_manager.shutdown_all.assert_not_called()

    def test_explicit_quit_and_quitting_close_are_not_intercepted(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QCloseEvent
        window = self.window(tray=True)
        with patch.object(QApplication, 'quit') as quit_app:
            window._quit_application()
            quit_app.assert_called_once()
        window._plugin_manager.shutdown_all.assert_called_once()
        event = QCloseEvent()
        window.closeEvent(event)
        self.assertTrue(event.isAccepted())
