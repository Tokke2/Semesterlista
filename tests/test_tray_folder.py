"""Exercise the actual tray class without launching a real tray or file manager."""
import ast
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_settings_dialog import HAVE_QT


@unittest.skipUnless(HAVE_QT, 'Qt unavailable')
class TrayFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtWidgets import QApplication, QMenu, QWidget, QMessageBox
        from PySide6.QtGui import QIcon
        from core import i18n
        source = (Path(__file__).resolve().parent.parent / 'main.pyw').read_text(encoding='utf-8')
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'SystrayManager')
        self.root = Path(tempfile.gettempdir()) / 'Semesterlista å & # % app'
        self.scope = dict(QApplication=QApplication, MainWindow=QWidget, QMenu=QMenu,
                          QSystemTrayIcon=Mock(), app_icon=QIcon, i18n=i18n,
                          APP_VERSION='test', PROJECT_ROOT=self.root, QMessageBox=QMessageBox,
                          logger=logging.getLogger(__name__))
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.pyw', 'exec'), self.scope)
        self.window = QWidget()
        self.window._app_name = lambda: 'Semesterlista'
        for name in ('show_application', 'hide_application', '_open_settings', '_show_about', '_quit_application'):
            setattr(self.window, name, Mock())
        self.tray = self.scope['SystrayManager'](self.app, self.window)
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.tray._tray_menu.deleteLater)

    def test_menu_action_opens_local_app_root_and_keeps_window_hidden(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QMessageBox
        self.assertIn(self.tray._folder_action, self.tray._tray_menu.actions())
        self.assertEqual(self.tray._folder_action.property('semesterlistaIcon'), 'folder')
        with patch.object(QDesktopServices, 'openUrl', return_value=True) as opened, \
             patch.object(QMessageBox, 'warning') as warning:
            self.tray._folder_action.trigger()
            url = opened.call_args.args[0]
            self.assertTrue(url.isLocalFile())
            self.assertEqual(Path(url.toLocalFile()), self.root.resolve())
            warning.assert_not_called()
        self.window.show_application.assert_not_called()
        self.assertFalse(self.window.isVisible())

    def test_failed_open_and_exception_show_saved_path(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QMessageBox
        for failure in (False, OSError('no file manager')):
            with patch.object(QDesktopServices, 'openUrl') as opened, \
                 patch.object(QMessageBox, 'warning') as warning:
                if isinstance(failure, Exception):
                    opened.side_effect = failure
                else:
                    opened.return_value = failure
                self.tray._folder_action.trigger()
                warning.assert_called_once()
                self.assertIn(str(self.root.resolve()), warning.call_args.args[2])

    def test_retranslation_updates_folder_label(self):
        with patch.object(self.scope['i18n'], 't', side_effect=lambda key, **kw: key):
            self.tray.retranslate()
        self.assertEqual(self.tray._folder_action.text(), 'tray.open_app_folder')
