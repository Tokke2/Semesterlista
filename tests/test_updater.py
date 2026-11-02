#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för core/updater.py – automatisk uppdatering mot GitHub Releases.

Körs utan PySide6 och utan nätverk (lokal HTTP-server som låtsas vara
GitHub API):

    python -m unittest discover -s tests -v
    python tests/test_updater.py
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import updater as updater_module  # noqa: E402
from core.updater import (  # noqa: E402
    DEFAULT_UPDATE_CONFIG,
    GitHubUpdater,
    UpdateApplyError,
    UpdateCheckError,
    UpdateDownloadError,
    UpdateInfo,
    Version,
    auto_check_enabled,
    clear_snooze,
    compare_versions,
    is_newer,
    is_skipped,
    load_update_config,
    normalize_version,
    record_check,
    should_auto_check,
    skip_version,
    skipped_version,
    snooze,
)


# ══════════════════════════════════════════════════════════
# HJÄLPKLASSER
# ══════════════════════════════════════════════════════════

class FakeSettings:
    """Minimal SettingsManager-ersättare (punktnotation + get/set)."""

    def __init__(self, data=None):
        self.data = data or {}

    def get(self, key, default=None):
        value = self.data
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def set(self, key, value):
        parts = key.split(".")
        target = self.data
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value


class _FakeGitHub(BaseHTTPRequestHandler):
    """Liten HTTP-server som svarar som GitHub API."""

    routes = {}

    def do_GET(self):  # noqa: N802 – HTTP-metod
        route = self.routes.get(self.path)
        if route is None:
            self.send_error(404, "Not found")
            return

        status, headers, body = route
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D401 – tyst server
        pass


def make_release(
    tag,
    version_assets=(),
    body="Release notes",
    prerelease=False,
    draft=False,
    html_url=None,
):
    """Bygg ett release-objekt likt GitHubs API."""
    assets = []
    for name, url, size, digest in version_assets:
        assets.append({
            "name": name,
            "browser_download_url": url,
            "url": url,
            "size": size,
            "digest": digest,
        })
    return {
        "tag_name": tag,
        "name": f"Semesterlista {tag}",
        "body": body,
        "published_at": "2026-10-01T12:00:00Z",
        "html_url": html_url or f"https://github.com/Tokke2/Semesterlista/releases/tag/{tag}",
        "prerelease": prerelease,
        "draft": draft,
        "assets": assets,
    }


def make_zip(entries):
    """Skapa ett zip-arkiv i minnet: {namn: innehåll}."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


class UpdaterTestCase(unittest.TestCase):
    """Bas med en lokal HTTP-server per testklass."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeGitHub)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.api_base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        _FakeGitHub.routes = {}
        self.tmp = Path(tempfile.mkdtemp(prefix="semesterlista-test-"))
        self.app_root = self.tmp / "Semesterlista"
        self.app_root.mkdir()
        (self.app_root / "main.pyw").write_text("print('hej')\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── Hjälpare ─────────────────────────────────────────

    def releases_route(self, releases, status=200, headers=None):
        body = json.dumps(releases).encode("utf-8")
        _FakeGitHub.routes[
            "/repos/Tokke2/Semesterlista/releases?per_page=50"
        ] = (
            status,
            headers or {"Content-Type": "application/json"},
            body,
        )

    def file_route(self, path, payload, headers=None):
        _FakeGitHub.routes[path] = (
            200,
            headers or {"Content-Type": "application/octet-stream"},
            payload,
        )

    def make_updater(self, current="2.3.0", **kwargs):
        options = dict(
            current_version=current,
            app_root=self.app_root,
            api_base=self.api_base,
            token="",
            timeout=5,
            work_dir=self.tmp / "work",
        )
        options.update(kwargs)
        return GitHubUpdater(**options)


# ══════════════════════════════════════════════════════════
# VERSIONER
# ══════════════════════════════════════════════════════════

class TestVersions(unittest.TestCase):

    def test_parse_olika_format(self):
        self.assertEqual(str(Version.parse("2.4.0")), "2.4.0")
        self.assertEqual(str(Version.parse("v2.4.0")), "2.4.0")
        self.assertEqual(str(Version.parse("2.4")), "2.4.0")
        self.assertEqual(str(Version.parse("release-2.4.1")), "2.4.1")
        self.assertEqual(str(Version.parse("2.4.0-beta.2")), "2.4.0-beta.2")

    def test_ogiltig_version(self):
        with self.assertRaises(ValueError):
            Version.parse("senaste")
        with self.assertRaises(ValueError):
            Version.parse("")

    def test_jamforelse(self):
        self.assertEqual(compare_versions("2.4.0", "2.3.9"), 1)
        self.assertEqual(compare_versions("2.4.0", "2.4.0"), 0)
        self.assertEqual(compare_versions("2.3.0", "2.4.0"), -1)
        self.assertTrue(is_newer("v2.10.0", "2.9.9"))
        self.assertFalse(is_newer("2.4.0", "2.4.0"))

    def test_forhandsversion_ar_aldre_an_final(self):
        self.assertTrue(Version.parse("2.4.0") > Version.parse("2.4.0-rc.1"))
        self.assertTrue(Version.parse("2.4.0-rc.2") > Version.parse("2.4.0-beta.9"))
        self.assertTrue(Version.parse("2.4.0-beta.1") > Version.parse("2.3.9"))

    def test_normalize(self):
        self.assertEqual(normalize_version("v2.4.0"), "2.4.0")


# ══════════════════════════════════════════════════════════
# KONTROLL MOT GITHUB API
# ══════════════════════════════════════════════════════════

class TestCheck(UpdaterTestCase):

    def test_hittar_nyare_version(self):
        self.releases_route([
            make_release("v2.4.0", [("Semesterlista-v2.4.0.zip", "http://x/zip", 100, "")]),
        ])
        info = self.make_updater().check()
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "2.4.0")
        self.assertEqual(info.asset_name, "Semesterlista-v2.4.0.zip")
        self.assertTrue(info.has_asset)

    def test_ingen_uppdatering_ger_none(self):
        self.releases_route([make_release("v2.3.0")])
        self.assertIsNone(self.make_updater().check())

    def test_draft_och_forhandsversion_hoppas_over(self):
        self.releases_route([
            make_release("v2.9.0", draft=True),
            make_release("v2.8.0", prerelease=True),
        ])
        self.assertIsNone(self.make_updater().check())

    def test_prerelease_kan_tillatas(self):
        self.releases_route([make_release("v2.8.0", prerelease=True)])
        updater = self.make_updater(channel="prerelease")
        info = updater.check()
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "2.8.0")

    def test_valjer_hoegsta_versionen(self):
        self.releases_route([
            make_release("v2.4.0"),
            make_release("v2.5.1"),
            make_release("v2.5.0"),
        ])
        info = self.make_updater().check()
        self.assertEqual(info.version, "2.5.1")

    def test_ogiltig_tagg_ignoreras(self):
        self.releases_route([
            make_release("nattlig-build"),
            make_release("v2.4.0"),
        ])
        info = self.make_updater().check()
        self.assertEqual(info.version, "2.4.0")

    def test_ratelimit_ger_tydligt_fel(self):
        self.releases_route(
            {"message": "API rate limit exceeded"},
            status=403,
            headers={
                "Content-Type": "application/json",
                "X-RateLimit-Remaining": "0",
            },
        )
        with self.assertRaises(UpdateCheckError) as ctx:
            self.make_updater().check()
        self.assertIn("gräns", str(ctx.exception).lower())

    def test_natverksfel(self):
        updater = self.make_updater(api_base="http://127.0.0.1:1")
        with self.assertRaises(UpdateCheckError):
            updater.check()

    def test_valjer_installationsprogram_fore_arkiv(self):
        assets = [
            ("Semesterlista-v2.4.0.zip", "http://x/zip", 5_000_000, ""),
            ("Semesterlista-v2.4.0-setup.exe", "http://x/exe", 8_000_000, ""),
            ("Semesterlista-v2.4.0-setup.exe.sha256", "http://x/sha", 64, ""),
        ]
        self.releases_route([make_release("v2.4.0", assets)])
        info = self.make_updater().check()
        self.assertEqual(info.asset_name, "Semesterlista-v2.4.0-setup.exe")
        self.assertTrue(info.is_installer)
        self.assertEqual(info.checksum_url, "http://x/sha")


# ══════════════════════════════════════════════════════════
# NEDLADDNING
# ══════════════════════════════════════════════════════════

class TestDownload(UpdaterTestCase):

    def test_laddar_ner_och_verifierar_digest(self):
        payload = make_zip({"Semesterlista/main.pyw": "print('ny')\n"})
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        self.file_route("/download/app.zip", payload)
        self.releases_route([
            make_release("v2.4.0", [("Semesterlista-v2.4.0.zip", f"{self.api_base}/download/app.zip", len(payload), digest)]),
        ])

        updater = self.make_updater()
        info = updater.check()

        progress = []
        archive = updater.download(info, progress=lambda done, total: progress.append((done, total)))

        self.assertTrue(archive.exists())
        self.assertEqual(archive.read_bytes(), payload)
        self.assertTrue(progress)
        self.assertEqual(progress[-1][0], len(payload))

    def test_fel_checksumma_ger_fel(self):
        payload = b"fel innehall"
        self.file_route("/download/app.zip", payload)
        self.releases_route([
            make_release("v2.4.0", [("Semesterlista-v2.4.0.zip", f"{self.api_base}/download/app.zip", len(payload), "sha256:" + "0" * 64)]),
        ])
        updater = self.make_updater()
        info = updater.check()

        with self.assertRaises(UpdateDownloadError):
            updater.download(info)

    def test_checksumma_fran_systerfil(self):
        payload = b"byggd app"
        checksum = hashlib.sha256(payload).hexdigest()
        self.file_route("/download/app.zip", payload)
        self.file_route("/download/app.zip.sha256", f"{checksum}  Semesterlista-v2.4.0.zip\n".encode())
        self.releases_route([
            make_release("v2.4.0", [
                ("Semesterlista-v2.4.0.zip", f"{self.api_base}/download/app.zip", len(payload), ""),
                ("Semesterlista-v2.4.0.zip.sha256", f"{self.api_base}/download/app.zip.sha256", 100, ""),
            ]),
        ])
        updater = self.make_updater()
        info = updater.check()
        archive = updater.download(info)
        self.assertEqual(archive.read_bytes(), payload)

    def test_release_utan_fil(self):
        self.releases_route([make_release("v2.4.0")])
        updater = self.make_updater()
        info = updater.check()
        with self.assertRaises(UpdateDownloadError):
            updater.download(info)


# ══════════════════════════════════════════════════════════
# UPPACKNING OCH INSTALLATION
# ══════════════════════════════════════════════════════════

class TestApply(UpdaterTestCase):

    def _write_zip(self, entries):
        archive = self.tmp / "Semesterlista-v2.4.0.zip"
        archive.write_bytes(make_zip(entries))
        return archive

    def test_packar_upp_och_undviker_anvandardata(self):
        archive = self._write_zip({
            "Semesterlista/main.pyw": "print('ny')\n",
            "Semesterlista/core/updater.py": "# ny\n",
            "Semesterlista/data/settings.json": "{}",
            "Semesterlista/Anställda.txt": "ska inte skrivas över",
        })
        updater = self.make_updater()
        source = updater.stage_archive(archive)

        self.assertTrue((source / "main.pyw").exists())
        self.assertTrue((source / "core" / "updater.py").exists())
        self.assertFalse((source / "data").exists())
        self.assertFalse((source / "Anställda.txt").exists())

    def test_path_traversal_avvisas(self):
        archive = self._write_zip({"../outside.txt": "farligt"})
        updater = self.make_updater()
        with self.assertRaises(UpdateApplyError):
            updater.stage_archive(archive)

    def test_arkivering_skriver_hjalpscript(self):
        archive = self._write_zip({"Semesterlista/main.pyw": "print('ny')\n"})
        updater = self.make_updater(install_mode="archive")
        info = UpdateInfo(version="2.4.0", asset_name=archive.name, asset_url="http://x")

        with mock.patch.object(GitHubUpdater, "_launch_script") as launch:
            result = updater.apply(info, archive, pid=999999)

        self.assertTrue(launch.called)
        self.assertEqual(result.mode, "archive")
        self.assertIsNotNone(result.script)
        self.assertTrue(result.script.exists())

        text = result.script.read_text(encoding="utf-8")
        self.assertIn(str(self.app_root), text)
        self.assertIn("999999", text)

        if updater_module.os.name == "nt":
            self.assertIn("tasklist", text)
            self.assertIn("xcopy", text)
        else:
            self.assertIn("kill -0", text)
            self.assertIn("cp -a", text)
            self.assertIn(str(self.app_root / "main.pyw"), text)

    def test_dry_run_startar_inget(self):
        archive = self._write_zip({"main.pyw": "print('ny')\n"})
        updater = self.make_updater(install_mode="archive")

        with mock.patch.object(GitHubUpdater, "_launch_script") as launch:
            result = updater.apply(
                UpdateInfo(version="2.4.0"),
                archive,
                pid=1234,
                dry_run=True,
            )

        self.assertFalse(launch.called)
        self.assertTrue(result.dry_run)
        self.assertTrue(result.requires_restart)

    def test_installationsprogram_startas(self):
        installer = self.tmp / "Semesterlista-v2.4.0-setup.exe"
        installer.write_bytes(b"MZ")
        updater = self.make_updater(install_mode="installer")

        with mock.patch.object(updater_module.subprocess, "Popen") as popen:
            result = updater.apply(
                UpdateInfo(version="2.4.0"),
                installer,
                dry_run=True,
            )

        self.assertEqual(result.mode, "installer")
        self.assertFalse(popen.called)   # dry_run
        self.assertIsNotNone(result.command)

    def test_saknad_fil_ger_fel(self):
        updater = self.make_updater(install_mode="archive")
        with self.assertRaises(UpdateApplyError):
            updater.apply(
                UpdateInfo(version="2.4.0"),
                self.tmp / "finns-inte.zip",
            )


# ══════════════════════════════════════════════════════════
# INSTÄLLNINGAR OCH KONFIGURATION
# ══════════════════════════════════════════════════════════

class TestSettingsHelpers(unittest.TestCase):

    def test_auto_check_enabled(self):
        self.assertFalse(auto_check_enabled(None))
        self.assertTrue(auto_check_enabled(FakeSettings()))
        self.assertFalse(auto_check_enabled(FakeSettings({"updates": {"auto_check": False}})))

    def test_should_auto_check_respekterar_intervall(self):
        settings = FakeSettings()
        now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)

        self.assertTrue(should_auto_check(settings, now))

        record_check(settings, "2.4.0", now)
        self.assertFalse(should_auto_check(settings, now + timedelta(hours=1)))
        self.assertTrue(should_auto_check(settings, now + timedelta(hours=25)))

    def test_snooze_skjuter_upp(self):
        settings = FakeSettings()
        now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        snooze(settings, hours=6, now=now)

        self.assertFalse(should_auto_check(settings, now + timedelta(hours=1)))
        self.assertTrue(should_auto_check(settings, now + timedelta(hours=7)))

        clear_snooze(settings)
        self.assertTrue(should_auto_check(settings, now + timedelta(hours=1)))

    def test_skip_version(self):
        settings = FakeSettings()
        self.assertFalse(is_skipped(settings, "2.4.0"))

        skip_version(settings, "2.4.0")
        self.assertEqual(skipped_version(settings), "2.4.0")
        self.assertTrue(is_skipped(settings, "v2.4.0"))
        self.assertFalse(is_skipped(settings, "2.5.0"))

    def test_avstangd_kontroll(self):
        settings = FakeSettings({"updates": {"auto_check": False}})
        self.assertFalse(should_auto_check(settings))


class TestConfig(unittest.TestCase):

    def test_laser_update_sektion(self):
        tmp = Path(tempfile.mkdtemp(prefix="semesterlista-config-"))
        try:
            (tmp / "config.json").write_text(json.dumps({
                "version": "2.4.0",
                "update": {"owner": "nagon", "repo": "annat", "channel": "prerelease"},
            }), encoding="utf-8")

            config = load_update_config(tmp)
            self.assertEqual(config["owner"], "nagon")
            self.assertEqual(config["repo"], "annat")
            self.assertEqual(config["channel"], "prerelease")
            self.assertEqual(
                config["check_interval_hours"],
                DEFAULT_UPDATE_CONFIG["check_interval_hours"],
            )

            updater = GitHubUpdater.from_config(tmp)
            self.assertEqual(updater.current, Version.parse("2.4.0"))
            self.assertEqual(updater.owner, "nagon")
            self.assertEqual(updater.channel, "prerelease")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_trasig_config_ger_standardvarden(self):
        tmp = Path(tempfile.mkdtemp(prefix="semesterlista-config-"))
        try:
            (tmp / "config.json").write_text("{ inte json", encoding="utf-8")
            config = load_update_config(tmp)
            self.assertEqual(config["owner"], DEFAULT_UPDATE_CONFIG["owner"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_repo_config_ar_satt(self):
        config = load_update_config(PROJECT_ROOT)
        self.assertEqual(config["owner"], "Tokke2")
        self.assertEqual(config["repo"], "Semesterlista")
        self.assertIn("*.zip", config["asset_patterns"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
