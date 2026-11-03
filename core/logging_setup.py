#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detaljerad loggning för Semesterlista (v2.8.0)
==============================================

Ett ställe som styr all loggning: fil (roterande), konsol, felhakar för
ohanterade undantag, Qt-meddelanden och hårda krascher (faulthandler).

    from core.logging_setup import setup_logging, log_startup_context

    log_file = setup_logging()          # data/app.log (fallback: temp)
    log_startup_context()               # python, platform, sökvägar, …
    logging.getLogger(__name__).info("…")

Loggfilen roterar automatiskt (2 MB × 5 filer) och innehåller modul,
radnummer och exakt tid – tillräckligt för att felsöka en användares
installation utan att be om skärmdumpar.

Varför så tidigt? All loggning sätts upp *innan* PySide6 och plugins
importeras, så även saknade moduler (t.ex. en bortglömd fil) hamnar i
loggen i stället för att bara ge en traceback i konsolen.

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import sys
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

MODULE_VERSION: str = "2.11.0"

#: Standardfil (relativt appens rotmapp)
DEFAULT_LOG_DIR: str = "data"
DEFAULT_LOG_FILE: str = "app.log"

#: Rotering: 2 MB per fil, 5 gamla filer
MAX_BYTES: int = 2 * 1024 * 1024
BACKUP_COUNT: int = 5

LOG_FORMAT: str = (
    "[%(asctime)s] %(levelname)-8s %(name)s:%(lineno)d – %(message)s"
)
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

#: Moduler som får logga på INFO även när appen kör på WARNING
_VERBOSE_LOGGERS = ("main", "core", "plugins")

_log_file: Optional[Path] = None
_configured: bool = False
_crash_hook: Optional[Callable[[str], None]] = None
_last_crash: Optional[str] = None
_fault_file: Optional[Any] = None
_previous_excepthook: Optional[Callable[..., Any]] = None


# ══════════════════════════════════════════════════════════
# Sökväg
# ══════════════════════════════════════════════════════════

def log_file_path(
    base_dir: Optional[Path] = None,
    file_name: Optional[str] = None,
) -> Path:
    """
    Sökväg till loggfilen (skapar inte filen).

    Args:
        base_dir:  Appens rotmapp (standard: denna fils förälder/..).
        file_name: Filnamn (standard: "app.log").

    Returns:
        Absolut sökväg till <rot>/data/app.log.
    """
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent.parent
    return root / DEFAULT_LOG_DIR / (file_name or DEFAULT_LOG_FILE)


def get_log_file() -> Optional[Path]:
    """Loggfilen som används (None innan setup_logging körts)."""
    return _log_file


# ══════════════════════════════════════════════════════════
# Uppsättning
# ══════════════════════════════════════════════════════════

def _can_write(path: Path) -> bool:
    """True om filen kan skrivas (skapar mappen vid behov)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8"):
            pass
        return True
    except Exception:
        return False


def _fallback_path() -> Path:
    """Reservplats om appens data/-mapp inte går att skriva i."""
    candidates = [
        Path(tempfile.gettempdir()) / "Semesterlista" / "app.log",
        Path.home() / ".semesterlista" / "app.log",
    ]
    for candidate in candidates:
        if _can_write(candidate):
            return candidate
    return Path(tempfile.gettempdir()) / "semesterlista-app.log"


def setup_logging(
    base_dir: Optional[Path] = None,
    level: Optional[int] = None,
    to_file: bool = True,
    to_console: bool = True,
    file_name: Optional[str] = None,
) -> Optional[Path]:
    """
    Sätt upp loggning för hela appen (anropas en gång, tidigt i main).

    Args:
        base_dir:   Appens rotmapp (standard: projektmappen).
        level:      Nivå för rot-loggern (standard: INFO, eller DEBUG om
                    miljövariabeln SEMESTERLISTA_DEBUG är satt).
        to_file:    Skriv till roterande fil (standard: True).
        to_console: Skriv till konsolen om det finns någon (pythonw har
                    ingen konsol – då hoppas det över).
        file_name:  Eget filnamn (standard: app.log).

    Returns:
        Sökvägen till loggfilen, eller None om fil-loggning inte kunde
        sättas upp.
    """
    global _log_file, _configured

    if _configured:
        return _log_file

    if level is None:
        level = logging.DEBUG if os.getenv("SEMESTERLISTA_DEBUG") else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if to_file:
        target = log_file_path(base_dir, file_name)
        if not _can_write(target):
            target = _fallback_path()

        try:
            handler = logging.handlers.RotatingFileHandler(
                target,
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(formatter)
            handler.setLevel(level)
            root.addHandler(handler)
            _log_file = target
        except Exception as exc:  # pragma: no cover – t.ex. låst fil
            print(f"Kunde inte öppna loggfilen {target}: {exc}", file=sys.stderr)

    # pythonw.exe saknar konsol – sys.stderr är None
    if to_console and sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(level)
        root.addHandler(console)

    # Fånga varningar från warnings-modulen också
    logging.captureWarnings(True)

    _configured = True

    logging.getLogger("main").info("=" * 74)
    logging.getLogger("main").info(
        f"Loggning startad {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
        f"(nivå={logging.getLevelName(level)}, fil={_log_file or 'ingen'})"
    )

    return _log_file


def is_configured() -> bool:
    """True om setup_logging redan körts."""
    return _configured


# ══════════════════════════════════════════════════════════
# Startinformation
# ══════════════════════════════════════════════════════════

def startup_context(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Samla fakta om miljön (används i loggen och i Om-dialogen).

    Returns:
        Dict med python, plattform, sökvägar, argument m.m.
    """
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent.parent
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version.replace("\n", " "),
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cwd": os.getcwd(),
        "app_dir": str(root),
        "frozen": bool(getattr(sys, "frozen", False)),
        "argv": list(sys.argv),
        "pid": os.getpid(),
        "filesystem_encoding": sys.getfilesystemencoding(),
    }


def log_startup_context(
    base_dir: Optional[Path] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Skriv startinformation till loggen och returnera den."""
    logger = logging.getLogger("main.startup")
    context = startup_context(base_dir)
    if extra:
        context.update(extra)

    logger.info("Miljö:")
    for key, value in context.items():
        logger.info(f"  {key:20} = {value}")
    return context


# ══════════════════════════════════════════════════════════
# Felhakar
# ══════════════════════════════════════════════════════════

def install_excepthook(
    on_crash: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Logga alla ohanterade undantag (huvudtråd + arbetstrådar + Qt-slots).

    Args:
        on_crash: Valfri callback som får den formaterade tracebacken
                  (t.ex. för att visa en dialog med loggfilens sökväg).
    """
    global _crash_hook, _previous_excepthook
    _crash_hook = on_crash

    previous = sys.excepthook
    _previous_excepthook = previous

    def _handle(
        exc_type: type,
        exc_value: BaseException,
        exc_tb: Any,
    ) -> None:
        global _last_crash
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc_value, exc_tb)
            return

        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _last_crash = text

        logging.getLogger("crash").critical(
            "Ohanterat fel: %s: %s\n%s",
            exc_type.__name__,
            exc_value,
            text,
        )
        if _log_file:
            logging.getLogger("crash").critical(f"Loggfil: {_log_file}")
        if _crash_hook is not None:
            try:
                _crash_hook(text)
            except Exception:  # pragma: no cover – defensivt
                logging.getLogger("crash").exception("Fel i crash-hook")

        # Behåll standardbeteendet (traceback i konsolen om den finns)
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle

    if hasattr(threading, "excepthook"):
        previous_thread_hook = threading.excepthook

        def _handle_thread(args: Any) -> None:
            text = "".join(
                traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback
                )
            )
            logging.getLogger("crash").critical(
                "Ohanterat fel i tråd %s: %s\n%s",
                getattr(args.thread, "name", "?"),
                args.exc_type.__name__,
                text,
            )
            previous_thread_hook(args)

        threading.excepthook = _handle_thread


def last_crash() -> Optional[str]:
    """Senaste ohanterade felet som text (None om inget inträffat)."""
    return _last_crash


def install_faulthandler() -> Optional[Path]:
    """
    Aktivera faulthandler så att hårda krascher (t.ex. i Qt/C++) skrivs
    till en egen fil: <loggmapp>/crash.log.

    Returns:
        Sökvägen till crash.log, eller None om det inte gick.
    """
    global _fault_file

    if _fault_file is not None:  # redan aktiv
        return Path(_fault_file.name) if hasattr(_fault_file, "name") else None

    try:
        import faulthandler

        base = _log_file.parent if _log_file else Path(tempfile.gettempdir())
        target = base / "crash.log"
        _fault_file = open(target, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_file, all_threads=True)
        logging.getLogger("main").debug(f"faulthandler aktiv ({target})")
        return target
    except Exception as exc:  # pragma: no cover – defensivt
        logging.getLogger("main").warning(f"Kunde inte aktivera faulthandler: {exc}")
        return None


def install_qt_message_handler() -> bool:
    """
    Skicka Qt:s egna meddelanden (varningar från widgets, plugin-fel m.m.)
    till loggen i stället för till konsolen.

    Returns:
        True om Qt-haken installerades (annars False, t.ex. utan PySide6).
    """
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:  # pragma: no cover – Qt saknas
        return False

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    qt_logger = logging.getLogger("qt")

    def _handler(mode: Any, context: Any, message: str) -> None:
        level = levels.get(mode, logging.INFO)
        where = ""
        try:
            file_name = context.file or ""
            if file_name:
                where = f" ({file_name}:{context.line})"
        except Exception:
            pass
        qt_logger.log(level, f"{message}{where}")

    qInstallMessageHandler(_handler)
    logging.getLogger("main").debug("Qt-meddelanden kopplade till loggen")
    return True


# ══════════════════════════════════════════════════════════
# Läs loggen
# ══════════════════════════════════════════════════════════

def tail_log(lines: int = 40) -> List[str]:
    """
    Läs de sista raderna ur loggfilen.

    Args:
        lines: Antal rader (standard 40).

    Returns:
        Lista med rader (tom om loggen inte finns).
    """
    if _log_file is None or not Path(_log_file).exists():
        return []

    try:
        with open(_log_file, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.readlines()
    except Exception:  # pragma: no cover – defensivt
        return []

    return [line.rstrip("\n") for line in content[-max(1, lines):]]


def log_summary() -> Dict[str, Any]:
    """
    Sammanfattning för felsökning (t.ex. i Om-dialogen).

    Returns:
        Dict med loggfil, nivå, antal handlers och senaste krasch.
    """
    root = logging.getLogger()
    return {
        "log_file": str(_log_file) if _log_file else None,
        "level": logging.getLevelName(root.level),
        "handlers": len(root.handlers),
        "configured": _configured,
        "last_crash": _last_crash,
        "fault_log": str(Path(_fault_file.name)) if _fault_file else None,
    }


def reset_logging() -> None:
    """
    Återställ loggningen (används av tester).

    Tar bort våra handlers, stänger faulthandler och sätter tillbaka den
    excepthook som gällde innan ``install_excepthook()`` anropades.
    """
    global _configured, _log_file, _last_crash
    global _fault_file, _crash_hook, _previous_excepthook

    if _fault_file is not None:
        try:
            import faulthandler

            faulthandler.disable()
        except Exception:  # pragma: no cover – defensivt
            pass
        try:
            _fault_file.close()
        except Exception:  # pragma: no cover – defensivt
            pass
        _fault_file = None

    if _previous_excepthook is not None:
        sys.excepthook = _previous_excepthook
        _previous_excepthook = None
    _crash_hook = None

    root = logging.getLogger()
    for handler in list(root.handlers):
        try:
            handler.close()
        except Exception:  # pragma: no cover
            pass
        root.removeHandler(handler)

    _configured = False
    _log_file = None
    _last_crash = None
    logging.captureWarnings(False)


__all__ = [
    "DEFAULT_LOG_FILE",
    "DEFAULT_LOG_DIR",
    "MAX_BYTES",
    "BACKUP_COUNT",
    "get_log_file",
    "install_excepthook",
    "install_faulthandler",
    "install_qt_message_handler",
    "is_configured",
    "last_crash",
    "log_file_path",
    "log_startup_context",
    "log_summary",
    "reset_logging",
    "setup_logging",
    "startup_context",
    "tail_log",
    "MODULE_VERSION",
]
