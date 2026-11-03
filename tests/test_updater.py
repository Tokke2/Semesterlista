#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för uppdateringen från GitHub Releases (v2.9.0).

Allt körs offline – nätverksanropen byts ut mot mockar och installationen
testas mot en syntetisk release-zip i en temporär mapp. Ingen Qt behövs.

    python -m unittest discover -s tests -v
    python tests/test_updater.py
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.version import current_version  # noqa: E402

#: Appens version enligt config.json – modulerna som följer appen ska matcha
APP_VERSION = current_version(PROJECT_ROOT)

from core import updater  # noqa: E402
from core.updater import (  # noqa: E402
    MODULE_VERSION,
    InstallResult,
    UpdateError,
    UpdateInfo,
    app_version,
    check_for_update,
    install_from_zip,
    is_newer,
    parse_version,
    restart_command,
    safe_extract,
    verify_payload,
    version_from_config,
)


def make_release_zip(
    target: Path,
    version: str = "2.9.0",
    top_folder: str = "Tokke2-Semesterlista-abc123",
    extra_files: dict[str, str] | None = None,
) -> Path:
    """Bygg en zip som ser ut som en GitHub-zipball."""
    payload = {
        "main.pyw": "# entry point\nAPP_VERSION = '%s'\n" % version,
        "config.json": json.dumps({"version": version, "app_name": "Semesterlista"}),
        "core/__init__.py": "",
        "core/updater.py": "# updater\n",
        "plugins/lista/plugin.py": "# lista\n",
        "spec.md": "# spec\n",
        # Ska aldrig skrivas över:
        "data/settings.json": json.dumps({"theme": "dark"}),
        "Anställda.txt": "Ska inte röras\n",
        "core/__pycache__/x.cpython-311.pyc": "skräp",
        "hyra.bak": "gammal",
    }
    if extra_files:
        payload.update(extra_files)

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in payload.items():
            archive.writestr(f"{top_folder}/{name}", content)
    return target


class VersionTests(unittest.TestCase):
    """Versionstolkning och jämförelse."""

    def test_module_version(self) -> None:
        self.assertEqual(MODULE_VERSION, APP_VERSION)

    def test_parse_version(self) -> None:
        cases = {
            "2.8.1": (2, 8, 1),
            "v2.8.1": (2, 8, 1),
            "V0.0.1": (0, 0, 1),
            "Release 2.9": (2, 9),
            "Semesterlista v2.10.3": (2, 10, 3),
            "": (),
            "ingen version": (),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_version(text), expected)

    def test_is_newer(self) -> None:
        self.assertTrue(is_newer("2.9.0", "2.8.1"))
        self.assertTrue(is_newer("2.9", "2.8.9"))
        self.assertTrue(is_newer("3.0.0", "2.99.99"))
        self.assertTrue(is_newer("v2.8.2", "2.8.1"))
        self.assertFalse(is_newer("2.8.1", "2.8.1"))
        self.assertFalse(is_newer("2.8.0", "2.8.1"))
        self.assertFalse(is_newer("", "2.8.1"))
        self.assertFalse(is_newer("2.8.1", ""))

    def test_version_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"

            # Saknad fil
            self.assertEqual(version_from_config(path), "")

            # Giltig fil
            path.write_text(json.dumps({"version": "2.9.0"}), encoding="utf-8")
            self.assertEqual(version_from_config(path), "2.9.0")

            # Trasig JSON och fil utan version
            path.write_text("{inte json", encoding="utf-8")
            self.assertEqual(version_from_config(path), "")
            path.write_text(json.dumps({"app_name": "Semesterlista"}), encoding="utf-8")
            self.assertEqual(version_from_config(path), "")

    def test_app_version_reads_repo_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "config.json").write_text('{"version": "9.9.9"}', encoding="utf-8")
            self.assertEqual(app_version(Path(tmp)), "9.9.9")


class CheckTests(unittest.TestCase):
    """check_for_update med mockat GitHub-API."""

    def _release(self, tag: str = "v0.0.1") -> dict:
        return {
            "tag_name": tag,
            "name": "Semesterlista " + tag,
            "published_at": "2026-11-02T13:57:26Z",
            "body": "Nytt i releasen",
            "html_url": "https://github.com/Tokke2/Semesterlista/releases/tag/v0.0.1",
            "zipball_url": "https://codeload.github.com/Tokke2/Semesterlista/zip/refs/tags/v0.0.1",
        }

    def _contents(self, version: str) -> dict:
        encoded = base64.b64encode(
            json.dumps({"version": version}).encode("utf-8")
        ).decode("ascii")
        return {"content": encoded, "encoding": "base64"}

    def test_new_version_available(self) -> None:
        def fake_json(url: str, timeout: int = 0):
            if "contents/config.json" in url:
                return self._contents("2.9.0")
            return self._release()

        with mock.patch.object(updater, "_request_json", side_effect=fake_json):
            info = check_for_update("2.8.1")

        self.assertIsInstance(info, UpdateInfo)
        self.assertEqual(info.version, "2.9.0")
        self.assertEqual(info.tag, "v0.0.1")
        self.assertEqual(info.local_version, "2.8.1")
        self.assertTrue(info.available)
        self.assertEqual(info.published_date, "2026-11-02")
        self.assertIn("Nytt", info.notes)
        self.assertTrue(info.zip_url.startswith("https://codeload.github.com"))
        self.assertIn("available", info.as_dict())

    def test_same_version_not_available(self) -> None:
        def fake_json(url: str, timeout: int = 0):
            if "contents/config.json" in url:
                return self._contents("2.8.1")
            return self._release()

        with mock.patch.object(updater, "_request_json", side_effect=fake_json):
            info = check_for_update("2.8.1")

        self.assertFalse(info.available)

    def test_falls_back_to_tag(self) -> None:
        def fake_json(url: str, timeout: int = 0):
            if "contents/config.json" in url:
                raise UpdateError("404")
            return self._release(tag="v2.10.0")

        with mock.patch.object(updater, "_request_json", side_effect=fake_json):
            info = check_for_update("2.9.0")

        self.assertEqual(info.version, "2.10.0")
        self.assertTrue(info.available)

    def test_network_error_propagates(self) -> None:
        with mock.patch.object(
            updater, "_request_json", side_effect=UpdateError("Ingen kontakt")
        ):
            with self.assertRaises(UpdateError):
                check_for_update("2.9.0")

    def test_release_without_tag_is_error(self) -> None:
        with mock.patch.object(updater, "_request_json", return_value={"name": "x"}):
            with self.assertRaises(UpdateError):
                updater.fetch_latest_release()


class ExtractTests(unittest.TestCase):
    """Uppackning – säkerhet och rotmapp."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_safe_extract_returns_payload_root(self) -> None:
        zip_path = make_release_zip(self.tmp / "release.zip")
        root = safe_extract(zip_path, self.tmp / "out")
        self.assertEqual(root.name, "Tokke2-Semesterlista-abc123")
        self.assertTrue((root / "main.pyw").is_file())

    def test_rejects_path_traversal(self) -> None:
        zip_path = self.tmp / "elak.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("../utanfor.txt", "hej")
        with self.assertRaises(UpdateError):
            safe_extract(zip_path, self.tmp / "out")

    def test_rejects_broken_zip(self) -> None:
        zip_path = self.tmp / "trasig.zip"
        zip_path.write_bytes(b"detta ar ingen zip")
        with self.assertRaises(UpdateError):
            safe_extract(zip_path, self.tmp / "out")

    def test_verify_payload_requires_files(self) -> None:
        root = self.tmp / "payload"
        (root / "core").mkdir(parents=True)
        (root / "plugins").mkdir(parents=True)
        (root / "main.pyw").write_text("x", encoding="utf-8")
        (root / "config.json").write_text('{"version": "2.9.0"}', encoding="utf-8")

        self.assertEqual(verify_payload(root), "2.9.0")

        (root / "main.pyw").unlink()
        with self.assertRaises(UpdateError):
            verify_payload(root)

    def test_verify_payload_requires_version(self) -> None:
        root = self.tmp / "payload"
        for name in ("core", "plugins"):
            (root / name).mkdir(parents=True)
        (root / "main.pyw").write_text("x", encoding="utf-8")
        (root / "config.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(UpdateError):
            verify_payload(root)


class InstallTests(unittest.TestCase):
    """install_from_zip mot en temporär appmapp."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

        # "Appens" mapp med gammalt innehåll + användardata
        self.app = self.tmp / "app"
        (self.app / "core").mkdir(parents=True)
        (self.app / "plugins").mkdir(parents=True)
        (self.app / "data").mkdir(parents=True)
        (self.app / "main.pyw").write_text("GAMMAL\n", encoding="utf-8")
        (self.app / "config.json").write_text('{"version": "2.8.1"}', encoding="utf-8")
        (self.app / "core" / "__init__.py").write_text("gammal\n", encoding="utf-8")
        (self.app / "data" / "settings.json").write_text('{"theme": "light"}', encoding="utf-8")
        (self.app / "Anställda.txt").write_text("Anna\n", encoding="utf-8")

        self.zip_path = make_release_zip(self.tmp / "release.zip")

    def test_install_updates_program_files(self) -> None:
        result = install_from_zip(self.zip_path, self.app, local_version="2.8.1")

        self.assertIsInstance(result, InstallResult)
        self.assertEqual(result.version, "2.9.0")
        self.assertGreater(result.file_count, 0)
        self.assertIn("main.pyw", result.files)

        self.assertIn("2.9.0", (self.app / "main.pyw").read_text(encoding="utf-8"))
        self.assertTrue((self.app / "core" / "updater.py").is_file())
        self.assertTrue((self.app / "plugins" / "lista" / "plugin.py").is_file())

    def test_install_keeps_user_data(self) -> None:
        install_from_zip(self.zip_path, self.app, local_version="2.8.1")

        settings = json.loads((self.app / "data" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["theme"], "light")           # data/ orörd
        self.assertEqual(
            (self.app / "Anställda.txt").read_text(encoding="utf-8"), "Anna\n"
        )
        self.assertFalse((self.app / "hyra.bak").exists())
        self.assertFalse((self.app / "core" / "__pycache__").exists())

    def test_install_creates_backup(self) -> None:
        result = install_from_zip(self.zip_path, self.app, local_version="2.8.1")

        self.assertIsNotNone(result.backup)
        self.assertTrue(result.backup.is_file())
        self.assertEqual(result.backup.parent.name, "backup")
        self.assertIn("2.8.1-till-2.9.0", result.backup.name)

        with zipfile.ZipFile(result.backup) as archive:
            names = archive.namelist()
        self.assertIn("main.pyw", names)
        self.assertIn("GAMMAL", zipfile.ZipFile(result.backup).read("main.pyw").decode("utf-8"))

    def test_install_dry_run_writes_nothing(self) -> None:
        result = install_from_zip(
            self.zip_path, self.app, local_version="2.8.1", dry_run=True
        )
        self.assertGreater(result.file_count, 0)
        self.assertIn("GAMMAL", (self.app / "main.pyw").read_text(encoding="utf-8"))
        self.assertIsNone(result.backup)

    def test_install_refuses_older_release(self) -> None:
        older = make_release_zip(self.tmp / "gammal.zip", version="2.7.0")
        with self.assertRaises(UpdateError):
            install_from_zip(older, self.app, local_version="2.8.1")
        self.assertIn("GAMMAL", (self.app / "main.pyw").read_text(encoding="utf-8"))

    def test_install_refuses_bad_payload(self) -> None:
        bad = self.tmp / "dålig.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("mapp/README.md", "hej")
        with self.assertRaises(UpdateError):
            install_from_zip(bad, self.app, local_version="2.8.1")

    def test_missing_zip_is_error(self) -> None:
        with self.assertRaises(UpdateError):
            install_from_zip(self.tmp / "finns-inte.zip", self.app)


class RestartTests(unittest.TestCase):
    """Omstarts-kommandot."""

    def test_restart_command_points_to_main(self) -> None:
        command = restart_command(PROJECT_ROOT)
        self.assertEqual(len(command), 2)
        self.assertTrue(command[1].endswith("main.pyw"))
        self.assertTrue(Path(command[1]).is_file())

    def test_github_release_url(self) -> None:
        self.assertEqual(
            updater.github_release_url(),
            "https://github.com/Tokke2/Semesterlista/releases/latest",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
