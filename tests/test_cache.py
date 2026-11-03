#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för core/cache.py – den smarta cachen (v2.11.0).

Kontrollerar att cachen städas vid avslut, att nyligen använda filer behålls
vid start, att låsta filer hoppas över och att inget utanför appens egna
mappar rörs.

    python -m unittest discover -s tests -v
    python tests/test_cache.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.cache import (  # noqa: E402
    APP_DIR_NAME,
    PurgeResult,
    SmartCache,
    app_cache_root,
    logo_cache_dir,
)


class CacheFixture(unittest.TestCase):
    """Gemensam testmapp som ser ut som %TEMP%."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self._tmp.name)
        self.cache = SmartCache(root=self.temp_dir)
        self.logo_dir = self.cache.root / "logotyper"
        self.logo_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_file(self, name: str, size: int = 1024, age_seconds: float = 0) -> Path:
        """Skapa en cachefil med given storlek och ålder."""
        path = self.logo_dir / name
        path.write_bytes(b"x" * size)
        if age_seconds:
            old = time.time() - age_seconds
            os.utime(path, (old, old))
        return path


class PathTests(CacheFixture):
    """Sökvägarna."""

    def test_app_cache_root_is_in_temp(self) -> None:
        self.assertEqual(
            app_cache_root(self.temp_dir), self.temp_dir / APP_DIR_NAME
        )

    def test_logo_cache_dir_is_created(self) -> None:
        folder = logo_cache_dir(self.temp_dir)
        self.assertTrue(folder.is_dir())
        self.assertEqual(folder.name, "logotyper")


class PurgeTests(CacheFixture):
    """purge() – städning vid avslut."""

    def test_purge_removes_cached_logos(self) -> None:
        self._make_file("a.png")
        self._make_file("b.png")

        result = self.cache.purge()

        self.assertEqual(result.removed_files, 2)
        self.assertFalse(self.logo_dir.exists())
        self.assertGreater(result.freed_bytes, 0)

    def test_purge_keeps_files_in_use(self) -> None:
        keep = self._make_file("bruk.png")
        self._make_file("gammal.png")

        result = self.cache.purge(keep=[keep])

        self.assertTrue(keep.exists())
        self.assertFalse((self.logo_dir / "gammal.png").exists())
        self.assertEqual(result.removed_files, 1)

    def test_purge_dry_run_removes_nothing(self) -> None:
        path = self._make_file("a.png")

        result = self.cache.purge(dry_run=True)

        self.assertTrue(path.exists())
        self.assertEqual(result.removed_files, 1)

    def test_purge_skips_locked_files(self) -> None:
        path = self._make_file("last.png")

        with mock.patch.object(Path, "unlink", side_effect=PermissionError("låst")):
            result = self.cache.purge()

        self.assertTrue(path.exists())
        self.assertEqual(len(result.skipped), 1)

    def test_purge_ignores_other_temp_files(self) -> None:
        other = self.temp_dir / "annat-program.tmp"
        other.write_bytes(b"data")
        self._make_file("a.png")

        self.cache.purge()

        self.assertTrue(other.exists(), "andra programs filer får inte röras")

    def test_purge_removes_leftover_update_temp(self) -> None:
        leftover = self.temp_dir / "semesterlista_uppdatering_abc"
        leftover.mkdir()
        (leftover / "release.zip").write_bytes(b"z" * 10)

        result = self.cache.purge()

        self.assertFalse(leftover.exists())
        self.assertGreaterEqual(result.removed_dirs, 1)

    def test_purge_without_cache_is_safe(self) -> None:
        self.cache.purge()  # tomt
        self.cache.purge()  # igen
        self.assertEqual(self.cache.entries(), [])


class StaleTests(CacheFixture):
    """clean_stale() – städning vid start."""

    def test_recent_files_are_kept(self) -> None:
        fresh = self._make_file("ny.png")

        result = self.cache.clean_stale()

        self.assertTrue(fresh.exists())
        self.assertEqual(result.removed_files, 0)

    def test_old_files_are_removed(self) -> None:
        old = self._make_file("gammal.png", age_seconds=3 * 3600)

        result = self.cache.clean_stale()

        self.assertFalse(old.exists())
        self.assertEqual(result.removed_files, 1)

    def test_custom_stale_hours(self) -> None:
        file = self._make_file("tvåtimmar.png", age_seconds=2 * 3600)
        cache = SmartCache(root=self.temp_dir, stale_hours=0.5)

        cache.clean_stale()

        self.assertFalse(file.exists())


class SizeAndExitTests(CacheFixture):
    """Storlek och automatisk städning."""

    def test_size_sums_the_files(self) -> None:
        self._make_file("a.png", size=500)
        self._make_file("b.png", size=1500)
        self.assertEqual(self.cache.size(), 2000)

    def test_register_exit_cleanup_is_idempotent(self) -> None:
        self.cache.register_exit_cleanup()
        self.cache.register_exit_cleanup()
        self.assertTrue(self.cache._exit_registered)

    def test_exit_cleanup_does_not_raise(self) -> None:
        self._make_file("a.png")
        self.cache._cleanup_at_exit()
        self.assertFalse(self.logo_dir.exists())

    def test_summary_text(self) -> None:
        self.assertIn("Inget att rensa", PurgeResult().summary())
        self.assertIn("filer", PurgeResult(removed_files=2, freed_bytes=2048).summary())


if __name__ == "__main__":
    unittest.main(verbosity=2)
