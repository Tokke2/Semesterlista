"""Autostart registration and quiet duplicate launches; no login needed."""
import ast
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from core.platform_launch import launch_arguments, desktop_entry


class QuietAutostartTests(unittest.TestCase):
    def test_login_arguments_are_explicit_but_normal_launch_is_unchanged(self):
        self.assertNotIn('--autostart', launch_arguments())
        self.assertEqual(launch_arguments(autostart=True)[-1], '--autostart')
        self.assertIn('--autostart', desktop_entry(autostart=True))
        self.assertNotIn('--autostart', desktop_entry())

    def test_duplicate_autostart_does_not_reveal_existing_window(self):
        source = (Path(__file__).resolve().parent.parent / 'main.pyw').read_text(encoding='utf-8')
        main = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        check = next(n for n in main.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'lock.is_running()')
        for autostart in (True, False):
            lock = Mock()
            scope = dict(lock=lock, AUTOSTART_LAUNCH=autostart, logger=logging.getLogger(__name__),
                         sys=sys, app_name='Semesterlista')
            with self.assertRaises(SystemExit):
                exec(compile(ast.Module(body=[check], type_ignores=[]), 'main.pyw', 'exec'), scope)
            self.assertEqual(lock.send_to_existing.call_count, 0 if autostart else 1)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        try:
            from core import single_instance
        except ImportError:
            self.skipTest('QtCore missing')
        self.module = single_instance

    def test_windows_command_uses_launcher_not_pinned_python_or_argv(self):
        with patch.object(self.module.platform, 'system', return_value='Windows'), \
             patch('core.roster.app_root', return_value=Path(tempfile.gettempdir()) / 'App å & spaces'), \
             patch.object(sys, 'argv', ['unrelated-script.py']):
            command = self.module._get_executable_path()
        self.assertIn('wscript.exe', command)
        self.assertIn('Starta Semesterlista.vbs', command)
        self.assertIn('/autostart', command)
        self.assertNotIn('pythonw.exe', command)
        self.assertNotIn('unrelated-script', command)

    def test_linux_stale_entry_is_repaired_with_absolute_paths(self):
        manager = self.module.AutostartManager()
        manager._system = 'Linux'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'autostart.desktop'
            path.write_text('[Desktop Entry]\nExec=old-python old.py\n', encoding='utf-8')
            with patch.object(manager, '_get_linux_desktop_path', return_value=path):
                self.assertTrue(manager.needs_refresh())
                self.assertTrue(manager.enable())
                self.assertFalse(manager.needs_refresh())
                self.assertIn('--autostart', path.read_text(encoding='utf-8'))
                self.assertTrue(manager.disable())
                self.assertFalse(path.exists())

    @unittest.skipUnless(os.name == 'nt', 'native Windows registry test')
    def test_windows_register_migrate_remove_only_our_unique_entry(self):
        import uuid
        import winreg
        manager = self.module.AutostartManager('Semesterlista-test-' + uuid.uuid4().hex)
        try:
            self.assertTrue(manager.enable())
            self.assertTrue(manager.is_enabled())
            self.assertFalse(manager.needs_refresh())
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.module.AUTOSTART_WIN_REG_KEY,
                                0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, manager._app_name, 0, winreg.REG_SZ, '"old-pythonw.exe" "old.pyw"')
            self.assertTrue(manager.needs_refresh())
            self.assertTrue(manager.enable())
            self.assertFalse(manager.needs_refresh())
        finally:
            self.assertTrue(manager.disable())
        self.assertFalse(manager.is_enabled())
