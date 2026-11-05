"""Runtime maintenance must never use system pip or recreate an existing venv."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools import runtime_check as runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe = self.root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        self.exe.parent.mkdir(parents=True)
        self.exe.touch()
        optional = patch.object(runtime, "available_optional_packages", return_value=[])
        optional.start()
        self.addCleanup(optional.stop)

    def test_existing_environment_is_reused_and_only_its_packages_updated(self):
        with patch.object(runtime, "run", return_value="[]") as command:
            self.assertEqual(runtime.prepare_environment(self.root), self.exe)
        calls = [c.args[0] for c in command.call_args_list]
        self.assertTrue(all(c[0] == str(self.exe) for c in calls))
        self.assertFalse(any("venv" in c for c in calls))
        self.assertIn("--upgrade", calls[1])
        self.assertIn(str(self.root / "requirements.txt"), calls[1])

    def test_optional_packages_only_when_already_installed(self):
        with patch.object(runtime, "run", side_effect=[json.dumps([{"name": "PyMuPDF"}]), "", "", ""]) as command:
            runtime.prepare_environment(self.root)
        args = command.call_args_list[1].args[0]
        self.assertIn("pymupdf", args)
        self.assertNotIn("svglib", args)

    def test_offline_uses_existing_environment_after_health_checks(self):
        with patch.object(runtime, "run", side_effect=["[]", subprocess.TimeoutExpired("pip", 240), "", ""]) as command:
            self.assertEqual(runtime.prepare_environment(self.root), self.exe)
        self.assertIn("check", command.call_args_list[2].args[0])
        self.assertIn("-c", command.call_args_list[3].args[0])

    def test_broken_dependencies_prevent_launch(self):
        with patch.object(runtime, "run", side_effect=["[]", "", RuntimeError("conflict")]):
            with self.assertRaises(RuntimeError):
                runtime.prepare_environment(self.root)

    def test_existing_broken_environment_is_not_overwritten(self):
        self.exe.unlink()
        with patch.object(runtime, "run") as command:
            with self.assertRaises(RuntimeError):
                runtime.prepare_environment(self.root)
            command.assert_not_called()

    def test_missing_environment_is_created_once(self):
        import shutil
        shutil.rmtree(self.root / ".venv")
        with patch.object(runtime, "run", side_effect=["", "[]", "", "", ""]) as command:
            runtime.prepare_environment(self.root)
        args = command.call_args_list[0].args[0]
        self.assertEqual(args[1:], ["-m", "venv", str(self.root / ".venv")])
