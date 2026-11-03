#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för core/version.py och tools/bump_version.py (v2.11.0).

Kontrollerar att appens version bara finns på ett ställe (config.json) och att
den kan kontrolleras och höjas utan att något glöms.

    python -m unittest discover -s tests -v
    python tests/test_version.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import version  # noqa: E402

BUMP_SCRIPT = PROJECT_ROOT / "tools" / "bump_version.py"


def _make_repo(root: Path, version_str: str = "1.2.3") -> Path:
    """Bygg en minimal kopia av de filer versionskontrollen tittar på."""
    (root / "core").mkdir(parents=True, exist_ok=True)
    (root / "plugins" / "demo").mkdir(parents=True, exist_ok=True)

    (root / "config.json").write_text(
        json.dumps({"app": "demo", "version": version_str}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "main.pyw").write_text(
        f'APP_VERSION: str = "{version_str}"\n', encoding="utf-8"
    )
    (root / "core" / "settings_manager.py").write_text(
        'MODULE_VERSION: str = "1.0.0"\n'
        f'    "version": "{version_str}",\n',
        encoding="utf-8",
    )
    (root / "core" / "old_module.py").write_text(
        'MODULE_VERSION: str = "0.9.0"\n', encoding="utf-8"
    )
    (root / "core" / "synced_module.py").write_text(
        f'MODULE_VERSION: str = "{version_str}"\n', encoding="utf-8"
    )
    (root / "plugins" / "demo" / "plugin.py").write_text(
        f'VERSION:     str = "{version_str}"\n'
        f'    "version": "{version_str}",\n',
        encoding="utf-8",
    )
    return root


class VersionTests(unittest.TestCase):
    """core/version.py – läs, kontrollera och höj versionen."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _make_repo(Path(self._tmp.name) / "repo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_current_version_from_config(self) -> None:
        self.assertEqual(version.current_version(self.root), "1.2.3")

    def test_missing_config_raises(self) -> None:
        (self.root / "config.json").unlink()
        with self.assertRaises(FileNotFoundError):
            version.current_version(self.root)

    def test_synced_repo_has_no_problems(self) -> None:
        self.assertEqual(version.check_versions(self.root), [])

    def test_drift_is_reported(self) -> None:
        plugin = self.root / "plugins" / "demo" / "plugin.py"
        plugin.write_text(
            'VERSION:     str = "1.2.2"\n    "version": "1.2.2",\n',
            encoding="utf-8",
        )
        problems = version.check_versions(self.root)
        self.assertTrue(problems)
        self.assertTrue(any("plugin.py" in p for p in problems))

    def test_apply_version_updates_all_app_level_places(self) -> None:
        changes = version.apply_version(self.root, "2.0.0")

        self.assertEqual(version.current_version(self.root), "2.0.0")
        self.assertIn('"2.0.0"', (self.root / "main.pyw").read_text(encoding="utf-8"))
        self.assertIn(
            '"version": "2.0.0"',
            (self.root / "core" / "settings_manager.py").read_text(encoding="utf-8"),
        )
        plugin_text = (self.root / "plugins" / "demo" / "plugin.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('VERSION:     str = "2.0.0"', plugin_text)  # formatering kvar
        self.assertGreaterEqual(len(changes), 4)
        self.assertEqual(version.check_versions(self.root), [])

    def test_modules_with_own_version_are_untouched(self) -> None:
        version.apply_version(self.root, "2.0.0")
        self.assertIn(
            'MODULE_VERSION: str = "0.9.0"',
            (self.root / "core" / "old_module.py").read_text(encoding="utf-8"),
        )
        # Moduler som följde appen bumpas
        self.assertIn(
            'MODULE_VERSION: str = "2.0.0"',
            (self.root / "core" / "synced_module.py").read_text(encoding="utf-8"),
        )

    def test_invalid_version_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            version.apply_version(self.root, "senaste")

    def test_same_version_gives_no_changes(self) -> None:
        self.assertEqual(version.apply_version(self.root, "1.2.3"), [])

    def test_crlf_is_preserved(self) -> None:
        main_pyw = self.root / "main.pyw"
        main_pyw.write_bytes(b'APP_VERSION: str = "1.2.3"\r\n')
        version.apply_version(self.root, "2.0.0")
        self.assertIn(b"\r\n", main_pyw.read_bytes())


class RealRepoVersionTests(unittest.TestCase):
    """Det riktiga repot ska alltid vara synkat."""

    def test_repo_versions_are_in_sync(self) -> None:
        problems = version.check_versions(PROJECT_ROOT)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_bump_script_check_mode(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUMP_SCRIPT), "--check"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("synkade", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
