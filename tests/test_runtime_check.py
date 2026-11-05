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

    def test_normal_start_does_not_check_or_update_packages(self):
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
