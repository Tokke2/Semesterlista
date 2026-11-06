"""Native launcher and non-Qt recovery tests across supported operating systems."""
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from core.platform_launch import desktop_entry, desktop_exec, launch_arguments
from tools import install_launcher, runtime_check


class PlatformLaunchTests(unittest.TestCase):
    def test_runtime_uses_existing_python_and_absolute_app_path(self):
        root = Path(tempfile.gettempdir()) / 'Semester lista å & %'
        arguments = launch_arguments(root)
        self.assertEqual(len(arguments), 2)
        self.assertTrue(Path(arguments[0]).is_absolute())
        self.assertEqual(arguments[1], str(root / 'tools' / 'runtime_check.py'))

    def test_desktop_escaping_no_shell_expansion_or_field_codes(self):
        text = desktop_exec(['/python', '/app with %f $HOME "quote" `code`/start.py'])
        self.assertIn('%%f', text)
        self.assertIn('\\\\$HOME', text)
        self.assertIn('\\\\"quote\\\\"', text)
        self.assertIn('\\\\`code\\\\`', text)
        with self.assertRaises(ValueError):
            desktop_exec(['/python', '/app\nExec=bad'])

    def test_linux_launcher_uses_xdg_and_has_no_terminal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'App å & %'
            root.mkdir()
            with patch.dict(os.environ, {'XDG_DATA_HOME': temporary}):
                path = install_launcher.install_linux(root)
            self.assertEqual(path, Path(temporary) / 'applications' / 'semesterlista.desktop')
            text = path.read_text(encoding='utf-8')
            self.assertIn('Terminal=false', text)
            self.assertIn('runtime_check.py', text)
            self.assertIn('appikon-256.png', text)
            self.assertEqual(text, desktop_entry(root))

    def test_macos_native_confirmation_default_no_and_literal_arguments(self):
        text = 'Repair? "quotes" & å\nNo shell execution'
        with patch.object(runtime_check.platform, 'system', return_value='Darwin'), \
             patch.object(runtime_check.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'Ja\n')) as run:
            self.assertTrue(runtime_check.posix_message(text, question=True))
            args = run.call_args.args[0]
            self.assertEqual(args[-1], text)
            self.assertIn('default button "Nej"', args[2])
            run.return_value.returncode = 1
            self.assertFalse(runtime_check.posix_message(text, question=True))

    def test_linux_confirmation_default_cancel_no_install_on_close(self):
        with patch.object(runtime_check.platform, 'system', return_value='Linux'), \
             patch.object(runtime_check.shutil, 'which', return_value='/usr/bin/zenity'), \
             patch.object(runtime_check.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertFalse(runtime_check.posix_message('Install?', question=True))
            self.assertIn('--default-cancel', run.call_args.args[0])

    @unittest.skipUnless(platform.system() == 'Darwin', 'native macOS compiler required')
    def test_native_macos_bundle_has_shared_icon_and_real_executable(self):
        import shutil
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'App å & %'
            root.mkdir()
            shutil.copytree(install_launcher.ROOT / 'assets' / 'ikon', root / 'assets' / 'ikon')
            target = install_launcher.install_macos(root)
            info = plistlib.loads((target / 'Contents' / 'Info.plist').read_bytes())
            self.assertEqual(info['CFBundleIdentifier'], 'se.semesterlista.launcher')
            self.assertTrue((target / 'Contents' / 'MacOS' / info['CFBundleExecutable']).is_file())
            self.assertTrue((target / 'Contents' / 'Resources' / 'applet.icns').is_file())
            with self.assertRaises(FileExistsError):
                install_launcher.install_macos(root)


class PosixRepairLockTests(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'Windows launcher uses its named mutex')
    def test_second_launcher_cannot_repair_shared_packages(self):
        with tempfile.TemporaryDirectory() as root:
            first = runtime_check.acquire_repair_lock(root)
            self.assertIsNotNone(first)
            try:
                self.assertIsNone(runtime_check.acquire_repair_lock(root))
            finally:
                first.close()
            second = runtime_check.acquire_repair_lock(root)
            self.assertIsNotNone(second)
            second.close()


class AutostartSerializationTests(unittest.TestCase):
    def test_macos_arguments_are_not_one_shell_string(self):
        try:
            from core.single_instance import AutostartManager
        except ImportError:
            self.skipTest('QtCore missing')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'test.plist'
            manager = AutostartManager()
            arguments = ['/python path/python3', '/App å & space/tools/runtime_check.py']
            with patch.object(manager, '_get_macos_plist_path', return_value=path), \
                 patch('core.single_instance.launch_arguments', return_value=arguments), \
                 patch('core.single_instance.subprocess.run') as run:
                self.assertTrue(manager._enable_macos())
                self.assertEqual(plistlib.loads(path.read_bytes())['ProgramArguments'], arguments)
                run.assert_called_once()
                previous = path.read_bytes()
                run.side_effect = OSError('launchctl failed')
                self.assertFalse(manager._enable_macos())
                self.assertEqual(path.read_bytes(), previous)
