"""Shared Python maintenance only when requested by the weekly launcher."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import runtime_check as runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        selection = patch.object(runtime, "preferred_python", return_value=sys.executable)
        selection.start()
        self.addCleanup(selection.stop)
        optional = patch.object(runtime, "available_optional_packages", return_value=[])
        optional.start()
        self.addCleanup(optional.stop)

    def test_shared_interpreter_is_used_without_venv(self):
        with patch.object(runtime, "run", return_value="") as command:
            self.assertEqual(runtime.prepare_environment(self.root), Path(sys.executable))
        calls = [c.args[0] for c in command.call_args_list]
        self.assertTrue(all(c[0] == sys.executable for c in calls))
        self.assertFalse(any("venv" in c for c in calls))
        self.assertFalse((self.root / ".venv").exists())
        self.assertIn("--upgrade", calls[0])
        self.assertIn(str(self.root / "requirements.txt"), calls[0])

    def test_optional_packages_only_when_already_installed(self):
        with patch.object(runtime, "available_optional_packages", return_value=["pymupdf"]):
            with patch.object(runtime, "run", return_value="") as command:
                runtime.prepare_environment(self.root)
        args = command.call_args_list[0].args[0]
        self.assertIn("pymupdf", args)
        self.assertNotIn("svglib", args)

    def test_offline_health_checks(self):
        with patch.object(runtime, "run", side_effect=[subprocess.TimeoutExpired("pip", 240), "", ""]) as command:
            runtime.prepare_environment(self.root)
        self.assertIn("check", command.call_args_list[1].args[0])
        self.assertIn("-c", command.call_args_list[2].args[0])

    def test_broken_dependencies_prevent_launch(self):
        with patch.object(runtime, "run", side_effect=["", RuntimeError("conflict")]):
            with self.assertRaises(RuntimeError):
                runtime.prepare_environment(self.root)

    def test_normal_start_does_not_run_pip_or_update_packages(self):
        with patch.object(sys, "argv", ["runtime_check.py"]), \
             patch("core.logging_setup.setup_logging"), \
             patch.object(runtime.logging, "shutdown"), \
             patch.object(runtime, "prepare_environment") as prepare, \
             patch.object(runtime.subprocess, "run") as launch:
            launch.return_value.returncode = 0
            self.assertEqual(runtime.main(), 0)
            prepare.assert_not_called()
            launch.assert_called_once()

    def test_scheduled_maintenance_does_not_launch_app(self):
        with patch.object(sys, "argv", ["runtime_check.py", "--maintenance-only"]), \
             patch("core.logging_setup.setup_logging"), \
             patch.object(runtime, "prepare_environment", return_value=Path(sys.executable)) as prepare, \
             patch.object(runtime.subprocess, "run") as launch:
            self.assertEqual(runtime.main(), 0)
            prepare.assert_called_once()
            launch.assert_not_called()

    def test_package_commands_do_not_open_windows_console(self):
        with patch.object(runtime.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
             patch.object(runtime.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "ok", "")) as command:
            self.assertEqual(runtime.run(["python", "-m", "pip", "check"]), "ok")
            self.assertEqual(command.call_args.kwargs["creationflags"], 0x08000000)

    def _startup(self, codes, answer=True, repair_error=None, arguments=()):
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', ['runtime_check.py', *arguments]))
            stack.enter_context(patch('core.logging_setup.setup_logging'))
            stack.enter_context(patch.object(runtime.logging, 'shutdown'))
            prompt = stack.enter_context(patch.object(runtime, 'offer_repair', return_value=answer))
            repair = stack.enter_context(patch.object(runtime, 'repair_environment', side_effect=repair_error))
            notice = stack.enter_context(patch.object(runtime, 'native_message'))
            launch = stack.enter_context(patch.object(runtime.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], code) for code in codes]))
            result = runtime.main()
            return result, prompt.call_count, repair.call_count, launch.call_count, notice.call_count

    def test_autostart_marker_reaches_main(self):
        with patch.object(sys, 'argv', ['runtime_check.py', '--autostart']), \
             patch('core.logging_setup.setup_logging'), \
             patch.object(runtime.logging, 'shutdown'), \
             patch.object(runtime.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(runtime.main(), 0)
            self.assertEqual(run.call_args.kwargs['env']['SEMESTERLISTA_AUTOSTART'], '1')

    def test_missing_dependencies_offer_repair_and_retry_once(self):
        self.assertEqual(self._startup([42, 0]), (0, 1, 1, 2, 0))

    def test_declining_does_not_install_or_retry(self):
        self.assertEqual(self._startup([42], answer=False), (0, 1, 0, 1, 0))

    def test_failed_repair_reports_error_without_restart_loop(self):
        with self.assertLogs('semesterlista.runtime', level='ERROR'):
            result = self._startup([42], repair_error=RuntimeError('offline'))
        self.assertEqual(result, (runtime.HANDLED_ERROR_EXIT_CODE, 1, 1, 1, 1))

    def test_second_import_failure_does_not_offer_again(self):
        with self.assertLogs('semesterlista.runtime', level='ERROR'):
            result = self._startup([42, 42])
        self.assertEqual(result, (runtime.HANDLED_ERROR_EXIT_CODE, 1, 1, 2, 1))

    def test_other_app_errors_do_not_trigger_package_install(self):
        self.assertEqual(self._startup([1]), (1, 0, 0, 1, 0))

    def test_missing_dependencies_without_mutex_never_install(self):
        self.assertEqual(self._startup([42], arguments=['--no-repair']), (0, 0, 0, 1, 1))

    def test_explicit_repair_uses_same_python_and_requirements(self):
        with patch.object(runtime, 'run', return_value='') as command:
            self.assertEqual(runtime.repair_environment(self.root), Path(sys.executable))
        calls = [c.args[0] for c in command.call_args_list]
        self.assertTrue(all(c[0] == sys.executable for c in calls))
        self.assertIn('--force-reinstall', calls[1])
        self.assertIn(str(self.root / 'requirements.txt'), calls[1])
        self.assertIn('check', calls[-2])
        self.assertIn('reportlab.pdfgen.canvas', calls[-1][-1])
        self.assertFalse(any('venv' in c for c in calls))

    def test_missing_pip_bootstrapped_in_existing_python(self):
        with patch.object(runtime, 'run', side_effect=[RuntimeError('no pip'), '', '', '', '']) as command:
            runtime.repair_environment(self.root)
        self.assertEqual(command.call_args_list[1].args[0], [sys.executable, '-m', 'ensurepip', '--upgrade'])

    def test_failed_weekly_check_can_offer_manual_repair(self):
        with patch.object(runtime, 'prepare_environment', side_effect=RuntimeError('missing Qt')):
            with self.assertLogs('semesterlista.runtime', level='ERROR'):
                self.assertEqual(self._startup([0], arguments=['--maintain']), (0, 1, 1, 1, 0))

    def test_scheduled_failure_never_prompts_or_repairs(self):
        with patch.object(runtime, 'prepare_environment', side_effect=RuntimeError('offline')):
            with self.assertLogs('semesterlista.runtime', level='ERROR'):
                self.assertEqual(self._startup([], arguments=['--maintenance-only']), (1, 0, 0, 0, 0))

    def test_real_main_reports_dependency_exit_without_qt(self):
        import os
        import shutil
        root = Path(__file__).resolve().parent.parent
        entry = self.root / 'main.pyw'
        shutil.copyfile(root / 'main.pyw', entry)
        code = '''import sys, runpy
class MissingPackages:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'reportlab'):
            raise ModuleNotFoundError('Simulated missing dependency', name=fullname)
sys.meta_path.insert(0, MissingPackages())
runpy.run_path(sys.argv[1], run_name='__main__')
'''
        env = dict(os.environ, SEMESTERLISTA_RUNTIME_READY='1', PYTHONPATH=str(root))
        result = subprocess.run([sys.executable, '-c', code, str(entry)], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, runtime.DEPENDENCY_EXIT_CODE, result.stderr)
        self.assertIn('Simulated missing dependency', (self.root / 'data/loggar/fel.log').read_text(encoding='utf-8'))

    def test_native_confirmation_defaults_to_no_without_qt(self):
        import ctypes
        from unittest.mock import MagicMock
        api = MagicMock()
        api.user32.MessageBoxW.return_value = 7
        with patch.object(runtime.os, 'name', 'nt'), patch.object(ctypes, 'windll', api, create=True):
            self.assertFalse(runtime.native_message('Repair?', question=True))
            flags = api.user32.MessageBoxW.call_args.args[-1]
            self.assertTrue(flags & 0x100)  # Second button (No) is default.
            self.assertTrue(flags & 0x04)   # Yes/No, not an automatic action.
            api.user32.MessageBoxW.return_value = 6
            self.assertTrue(runtime.native_message('Repair?', question=True))
