"""Real Qt checks for hidden/maximized startup and explicit reactivation."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_settings_dialog import HAVE_QT


@unittest.skipUnless(HAVE_QT, 'Qt unavailable')
class MinimizedStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def window(self, maximized, tray=True):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMainWindow
        from core.window_state import clamp_geometry
        source = (Path(__file__).resolve().parent.parent / 'main.pyw').read_text(encoding='utf-8')
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
        names = ('_restore_window_state', 'initialize_start_visibility', 'show_application')
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        scope = {'Qt': Qt, 'clamp_geometry': clamp_geometry, 'sys': SimpleNamespace(platform='linux'),
                 'QSystemTrayIcon': SimpleNamespace(isSystemTrayAvailable=lambda: tray)}
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'main.pyw', 'exec'), scope)
        window = QMainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.hide)
        saved = {'window.maximized': maximized, 'systray.start_minimized': False}
        window._settings_manager = SimpleNamespace(get=lambda key, default: saved.get(key, default))
        window._screen_rects = lambda: [(0, 0, 1920, 1040)]
        window._event_bus = SimpleNamespace(emit=Mock())
        window.window_shown = SimpleNamespace(emit=Mock())
        return window, scope

    def test_normal_and_previously_maximized_start_hidden(self):
        for maximized in (False, True):
            window, methods = self.window(maximized)
            methods['_restore_window_state'](window)
            self.assertFalse(window.isVisible())  # No initial flash from restoring geometry.
            methods['initialize_start_visibility'](window)
            self.app.processEvents()
            self.assertFalse(window.isVisible())
            self.assertTrue(window.isMinimized())
            methods['show_application'](window)  # Tray click or second launch.
            self.app.processEvents()
            self.assertTrue(window.isVisible())
            self.assertFalse(window.isMinimized())
            self.assertEqual(window.isMaximized(), maximized)
            window.hide()

    def test_without_tray_starts_minimized_not_unreachable(self):
        window, methods = self.window(False, tray=False)
        methods['_restore_window_state'](window)
        methods['initialize_start_visibility'](window)
        self.app.processEvents()
        self.assertTrue(window.isMinimized())
        self.assertTrue(window.isVisible())
