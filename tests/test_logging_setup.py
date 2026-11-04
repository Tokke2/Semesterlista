#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för den detaljerade loggningen (v2.8.0).

Kräver ingen Qt – bara standardbiblioteket. Testar:

    * sökvägsval (data/app.log, eget filnamn, reservplats)
    * att filen skrivs med rätt format och nivå
    * SEMESTERLISTA_DEBUG → DEBUG
    * rotering (app.log.1 när filen blir för stor)
    * tail_log/log_summary
    * excepthook, faulthandler och reset_logging

    python -m unittest discover -s tests -v
    python tests/test_logging_setup.py
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.version import current_version  # noqa: E402

#: Appens version enligt config.json – modulerna som följer appen ska matcha
APP_VERSION = current_version(PROJECT_ROOT)

from core import logging_setup  # noqa: E402
from core.logging_setup import (  # noqa: E402
    ARCHIVE_SUBDIR,
    BACKUP_COUNT,
    LOG_SUBDIR,
    MAX_BYTES,
    MODULE_VERSION,
    archive_dir_path,
    archive_previous_days,
    archive_target,
    clear_error_log,
    error_log_lines,
    error_log_path,
    get_error_log_file,
    get_log_file,
    log_dir_path,
    tail_error_log,
    install_excepthook,
    install_faulthandler,
    is_configured,
    last_crash,
    log_file_path,
    log_startup_context,
    log_summary,
    reset_logging,
    setup_logging,
    startup_context,
    tail_log,
)


class LoggingTestCase(unittest.TestCase):
    """Bas som ser till att varje test börjar och slutar utan loggning."""

    def setUp(self) -> None:
        reset_logging()
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(reset_logging)

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")


class PathTests(LoggingTestCase):
    """Sökvägar – ingen loggning behöver startas."""

    def test_module_version(self) -> None:
        self.assertEqual(MODULE_VERSION, APP_VERSION)

    def test_default_path(self) -> None:
        path = log_file_path(self.base)
        self.assertEqual(path, self.base / "data" / "loggar" / "app.log")

    def test_logs_live_in_their_own_subfolder(self) -> None:
        """Loggarna har en egen undermapp: data/loggar (v2.12.0)."""
        self.assertEqual(log_dir_path(self.base), self.base / "data" / "loggar")
        self.assertEqual(
            error_log_path(self.base), self.base / "data" / "loggar" / "fel.log"
        )
        self.assertEqual(
            archive_dir_path(self.base), self.base / "data" / "loggar" / "arkiv"
        )

    def test_archive_name_has_the_date(self) -> None:
        target = archive_target(self.base / "data" / "loggar" / "app.log",
                                date(2026, 11, 2))
        self.assertEqual(
            target, self.base / "data" / "loggar" / "arkiv" / "app-2026-11-02.log"
        )

    def test_custom_file_name(self) -> None:
        path = log_file_path(self.base, "test.log")
        self.assertEqual(path, self.base / "data" / "loggar" / "test.log")

    def test_rotation_settings(self) -> None:
        self.assertEqual(MAX_BYTES, 2 * 1024 * 1024)
        self.assertEqual(BACKUP_COUNT, 5)

    def test_fallback_path_outside_base(self) -> None:
        fallback = logging_setup._fallback_path()
        self.assertIsInstance(fallback, Path)
        self.assertEqual(fallback.name, "app.log")
        self.assertTrue(fallback.is_absolute())


class SetupTests(LoggingTestCase):
    """setup_logging skriver fil och sätter rätt nivå."""

    def test_creates_file_and_writes(self) -> None:
        path = setup_logging(self.base, to_console=False)
        self.assertIsNotNone(path)
        self.assertTrue(Path(path).exists())
        self.assertTrue(is_configured())

        logging.getLogger("core.test").info("Hej från testet")
        content = self._read(Path(path))

        self.assertIn("Hej från testet", content)
        self.assertIn("INFO", content)
        self.assertIn("core.test:", content)
        self.assertIn("–", content)          # formatet använder tankstreck
        self.assertIn("Loggning startad", content)

    def test_format_has_timestamp(self) -> None:
        path = setup_logging(self.base, to_console=False)
        logging.getLogger("main").info("Tidsstämpel")
        line = [l for l in self._read(Path(path)).splitlines() if "Tidsstämpel" in l][0]
        # [2026-11-02 12:34:56] INFO     main:123 – Tidsstämpel
        self.assertTrue(line.startswith("["))
        self.assertRegex(line, r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")

    def test_default_level_is_info(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEMESTERLISTA_DEBUG", None)
            setup_logging(self.base, to_console=False)
        self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_debug_via_environment(self) -> None:
        with mock.patch.dict(os.environ, {"SEMESTERLISTA_DEBUG": "1"}):
            path = setup_logging(self.base, to_console=False)
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

        logging.getLogger("main").debug("Detalj")
        self.assertIn("Detalj", self._read(Path(path)))

    def test_second_call_is_noop(self) -> None:
        first = setup_logging(self.base, to_console=False)
        second = setup_logging(self.base / "annan", to_console=False)
        self.assertEqual(first, second)

    def test_get_log_file(self) -> None:
        self.assertIsNone(get_log_file())
        path = setup_logging(self.base, to_console=False)
        self.assertEqual(Path(get_log_file()), Path(path))

    def test_custom_file_name(self) -> None:
        path = setup_logging(self.base, to_console=False, file_name="körning.log")
        self.assertEqual(Path(path).name, "körning.log")
        self.assertTrue(Path(path).exists())

    def test_fallback_when_data_dir_not_writable(self) -> None:
        fallback = self.base / "reserv" / "app.log"
        fallback.parent.mkdir(parents=True, exist_ok=True)

        with mock.patch.object(logging_setup, "_can_write", return_value=False), \
                mock.patch.object(logging_setup, "_fallback_path", return_value=fallback):
            path = setup_logging(self.base, to_console=False)

        self.assertEqual(Path(path), fallback)
        self.assertTrue(fallback.exists())


class RotationTests(LoggingTestCase):
    """Filen roterar när den blir större än MAX_BYTES."""

    def test_rotates_to_backup(self) -> None:
        with mock.patch.object(logging_setup, "MAX_BYTES", 400):
            path = setup_logging(self.base, to_console=False)
            for index in range(60):
                logging.getLogger("main").info("Rad %02d %s", index, "x" * 30)
            for handler in logging.getLogger().handlers:
                handler.flush()

        log_file = Path(path)
        backup = log_file.with_suffix(".log.1")
        self.assertTrue(log_file.exists())
        self.assertTrue(backup.exists(), "ingen roterad fil skapades")
        self.assertLessEqual(backup.stat().st_size, 400 * 2)  # rimlig storlek


class TailTests(LoggingTestCase):
    """tail_log och log_summary."""

    def test_tail_before_setup(self) -> None:
        self.assertEqual(tail_log(10), [])

    def test_tail_returns_last_lines(self) -> None:
        setup_logging(self.base, to_console=False)
        for index in range(30):
            logging.getLogger("main").info("Rad %d", index)
        for handler in logging.getLogger().handlers:
            handler.flush()

        lines = tail_log(5)
        self.assertEqual(len(lines), 5)
        self.assertIn("Rad 29", lines[-1])

    def test_tail_zero_means_one(self) -> None:
        setup_logging(self.base, to_console=False)
        logging.getLogger("main").info("Enda raden")
        for handler in logging.getLogger().handlers:
            handler.flush()
        self.assertEqual(len(tail_log(0)), 1)

    def test_summary(self) -> None:
        path = setup_logging(self.base, to_console=False)
        summary = log_summary()
        self.assertEqual(summary["log_file"], str(path))
        self.assertTrue(summary["configured"])
        self.assertIn(summary["level"], ("INFO", "DEBUG"))
        self.assertGreaterEqual(summary["handlers"], 1)


class ContextTests(LoggingTestCase):
    """Miljöinformation för uppstarten."""

    def test_startup_context_keys(self) -> None:
        context = startup_context()
        for key in ("timestamp", "python", "platform", "cwd"):
            with self.subTest(key=key):
                self.assertIn(key, context)
        self.assertIn(sys.version.split()[0], context["python"])

    def test_log_startup_context(self) -> None:
        path = setup_logging(self.base, to_console=False)
        log_startup_context(self.base, extra={"test": "värde"})
        for handler in logging.getLogger().handlers:
            handler.flush()
        content = self._read(Path(path))
        self.assertIn("värde", content)


class CrashHookTests(LoggingTestCase):
    """excepthook, faulthandler och reset_logging."""

    def test_excepthook_logs_and_calls_callback(self) -> None:
        path = setup_logging(self.base, to_console=False)
        received: list[str] = []
        install_excepthook(received.append)

        with mock.patch.object(sys, "stderr", new=open(os.devnull, "w", encoding="utf-8")):
            try:
                raise ValueError("Avsiktligt testfel")
            except ValueError:
                exc_type, exc_value, exc_tb = sys.exc_info()
                sys.excepthook(exc_type, exc_value, exc_tb)

        self.assertEqual(len(received), 1)
        self.assertIn("Avsiktligt testfel", received[0])
        self.assertIsNotNone(last_crash())
        self.assertIn("Ohanterat fel", self._read(Path(path)))

    def test_keyboard_interrupt_passes_through(self) -> None:
        setup_logging(self.base, to_console=False)
        received: list[str] = []
        install_excepthook(received.append)

        with mock.patch.object(sys, "stderr", new=open(os.devnull, "w", encoding="utf-8")):
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)

        self.assertEqual(received, [])

    def test_faulthandler_creates_crash_log(self) -> None:
        setup_logging(self.base, to_console=False)
        path = install_faulthandler()
        self.assertIsNotNone(path)
        self.assertEqual(Path(path).name, "crash.log")

    def test_reset_restores_state(self) -> None:
        original = sys.excepthook
        setup_logging(self.base, to_console=False)
        install_excepthook(lambda text: None)
        self.assertNotEqual(sys.excepthook, original)

        reset_logging()

        self.assertEqual(sys.excepthook, original)
        self.assertFalse(is_configured())
        self.assertIsNone(get_log_file())
        self.assertIsNone(last_crash())
        self.assertEqual(logging.getLogger().handlers, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class LogFolderTests(LoggingTestCase):
    """Loggarna ligger i en egen undermapp (v2.12.0)."""

    def test_folder_constants(self) -> None:
        self.assertEqual(LOG_SUBDIR, "loggar")
        self.assertEqual(ARCHIVE_SUBDIR, "arkiv")

    def test_setup_creates_the_folder(self) -> None:
        path = setup_logging(self.base, to_console=False)
        self.assertTrue(Path(path).parent.is_dir())
        self.assertEqual(Path(path).parent.name, "loggar")
        self.assertFalse((self.base / "data" / "app.log").exists(),
                         "loggen ska inte ligga direkt i data/")


class ArchiveTests(LoggingTestCase):
    """Gårdagens logg arkiveras, dagens lämnas ifred (v2.12.0)."""

    def _write_log(self, path: Path, text: str, days_ago: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        stamp = time.time() - days_ago * 86400
        os.utime(path, (stamp, stamp))

    def test_previous_day_is_archived_at_startup(self) -> None:
        log_file = log_file_path(self.base)
        self._write_log(log_file, "[gammal rad]\n", days_ago=1)

        path = setup_logging(self.base, to_console=False)

        archived = list(archive_dir_path(self.base).glob("app-*.log"))
        self.assertEqual(len(archived), 1, "gårdagens logg arkiverades inte")
        self.assertIn("[gammal rad]", archived[0].read_text(encoding="utf-8"))
        self.assertNotIn("[gammal rad]", Path(path).read_text(encoding="utf-8"))
        # Arkivnamnet bär dagen loggen skrevs
        expected = date.fromtimestamp(time.time() - 86400).isoformat()
        self.assertEqual(archived[0].name, f"app-{expected}.log")

    def test_today_is_not_archived(self) -> None:
        log_file = log_file_path(self.base)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("[dagens rad]\n", encoding="utf-8")

        path = setup_logging(self.base, to_console=False)

        self.assertFalse(archive_dir_path(self.base).exists())
        self.assertIn("[dagens rad]", Path(path).read_text(encoding="utf-8"))

    def test_midnight_rotation_archives_the_old_content(self) -> None:
        """Är appen igång över midnatt arkiveras raderna vid nästa loggning."""
        path = Path(setup_logging(self.base, to_console=False))
        logging.getLogger("main").info("rad före midnatt")
        for handler in logging.getLogger().handlers:
            handler.flush()

        handler = next(
            h for h in logging.getLogger().handlers
            if isinstance(h, logging_setup._RotatingDailyFileHandler)
        )
        # Låtsas att det redan har blivit nästa dag
        handler._day = date(2020, 1, 1)
        old = time.time() - 86400
        os.utime(path, (old, old))

        logging.getLogger("main").info("rad efter midnatt")
        handler.flush()

        archived = list(archive_dir_path(self.base).glob("app-*.log"))
        self.assertEqual(len(archived), 1)
        archived_text = archived[0].read_text(encoding="utf-8")
        self.assertIn("rad före midnatt", archived_text)
        self.assertNotIn("rad efter midnatt", archived_text)
        self.assertIn("rad efter midnatt", path.read_text(encoding="utf-8"))
        self.assertNotIn("rad före midnatt", path.read_text(encoding="utf-8"))

    def test_missing_file_is_ignored(self) -> None:
        self.assertIsNone(archive_previous_days(self.base / "finns-inte.log"))

    def test_archive_appends_same_day(self) -> None:
        target = self.base / "data" / "loggar" / "app.log"
        target.parent.mkdir(parents=True, exist_ok=True)

        for text in ("första\n", "andra\n"):
            target.write_text(text, encoding="utf-8")
            stamp = time.time() - 86400
            os.utime(target, (stamp, stamp))
            archive_previous_days(target)

        archived = list((self.base / "data" / "loggar" / "arkiv").glob("app-*.log"))
        self.assertEqual(len(archived), 1)
        content = archived[0].read_text(encoding="utf-8")
        self.assertIn("första", content)
        self.assertIn("andra", content)


class ErrorLogTests(LoggingTestCase):
    """Fel hamnar i en egen fil som aldrig arkiveras (v2.12.0)."""

    def test_error_log_is_created_next_to_app_log(self) -> None:
        setup_logging(self.base, to_console=False)
        self.assertEqual(
            Path(get_error_log_file()),
            self.base / "data" / "loggar" / "fel.log",
        )
        self.assertTrue(Path(get_error_log_file()).exists())

    def test_only_errors_are_written_there(self) -> None:
        setup_logging(self.base, to_console=False)
        logging.getLogger("test.fel").info("bara info")
        logging.getLogger("test.fel").warning("bara varning")
        logging.getLogger("test.fel").error("riktigt fel")
        for handler in logging.getLogger().handlers:
            handler.flush()

        content = Path(get_error_log_file()).read_text(encoding="utf-8")
        self.assertIn("riktigt fel", content)
        self.assertNotIn("bara info", content)
        self.assertNotIn("bara varning", content)

    def test_errors_are_not_archived(self) -> None:
        setup_logging(self.base, to_console=False)
        logging.getLogger("test.fel").error("gammalt fel")
        for handler in logging.getLogger().handlers:
            handler.flush()

        error_log = Path(get_error_log_file())
        old = time.time() - 3 * 86400
        os.utime(error_log, (old, old))
        reset_logging()
        setup_logging(self.base, to_console=False)

        self.assertTrue(error_log.exists(), "felloggen ska inte flyttas")
        self.assertIn("gammalt fel", error_log.read_text(encoding="utf-8"))

    def test_clear_error_log(self) -> None:
        setup_logging(self.base, to_console=False)
        logging.getLogger("test.fel").error("åtgärdat fel")
        for handler in logging.getLogger().handlers:
            handler.flush()
        self.assertGreater(error_log_lines(), 1)

        self.assertTrue(clear_error_log())
        self.assertEqual(error_log_lines(), 1)
        content = Path(get_error_log_file()).read_text(encoding="utf-8")
        self.assertNotIn("åtgärdat fel", content)
        self.assertIn("rensad", content)

    def test_clear_before_setup_returns_false(self) -> None:
        self.assertFalse(clear_error_log())

    def test_tail_error_log(self) -> None:
        setup_logging(self.base, to_console=False)
        logging.getLogger("test.fel").error("sista felet")
        for handler in logging.getLogger().handlers:
            handler.flush()

        lines = tail_error_log(5)
        self.assertTrue(any("sista felet" in line for line in lines))

    def test_summary_has_error_log(self) -> None:
        setup_logging(self.base, to_console=False)
        info = log_summary()
        self.assertEqual(info["error_log"], str(self.base / "data" / "loggar" / "fel.log"))
        self.assertEqual(info["archive_dir"], str(self.base / "data" / "loggar" / "arkiv"))
        self.assertEqual(info["log_dir"], str(self.base / "data" / "loggar"))
        self.assertIn("error_lines", info)
