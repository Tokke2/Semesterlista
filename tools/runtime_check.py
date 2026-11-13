"""Weekly package maintenance in the existing Python installation."""
from __future__ import annotations

from importlib import metadata
import logging
import os
import shutil
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DEPENDENCY_EXIT_CODE = 42
HANDLED_ERROR_EXIT_CODE = 43
def available_optional_packages():
    found = []
    for name in OPTIONAL_PACKAGES:
        try:
            metadata.version(name)
            found.append(name)
        except metadata.PackageNotFoundError:
            pass
    return found


OPTIONAL_PACKAGES = ("pymupdf", "svglib")
logger = logging.getLogger("semesterlista.runtime")


def run(command, timeout=240):
    result = subprocess.run(command, capture_output=True, text=True,
                            errors="replace", timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    logger.info("%s\n%s\n%s", command, result.stdout, result.stderr)
    if result.returncode:
        raise RuntimeError(f"Kommandot misslyckades ({result.returncode}): {command}")
    return result.stdout


def prepare_environment(root=ROOT):
    executable = Path(sys.executable)
    # The launcher selects the base interpreter, never an application venv.
    try:
        optional = available_optional_packages()
        run([str(executable), "-m", "pip", "install", "--upgrade",
             "--disable-pip-version-check", "--no-input", "--timeout", "15", "--retries", "1",
             "-r", str(root / "requirements.txt"), *optional])
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
        logger.warning("Tillägg kunde inte uppdateras: %s", exc)
        print("Tillägg kunde inte uppdateras; kontrollerar befintlig miljö.", flush=True)
    # Offline may be fine, but do not launch a broken/partially updated environment.
    run([str(executable), "-m", "pip", "check"])
    run([str(executable), "-c", "from PySide6 import QtWidgets; import reportlab.pdfgen.canvas"])
    return executable


def native_message(text, question=False):
    """Platform dialog independent of Qt, safe when PySide6 cannot import."""
    if os.name != "nt":
        return posix_message(text, question)
    import ctypes
    dialog = ctypes.windll.user32.MessageBoxW
    dialog.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    dialog.restype = ctypes.c_int
    # Yes/No, default No. Never silently consent to changing shared packages.
    flags = (0x04 | 0x20 | 0x100) if question else 0x10
    return dialog(None, text, "Semesterlista – tillägg", flags | 0x10000) == 6


def posix_message(text, question=False):
    """Ask before repairs even when Qt is missing. Closing means no consent."""
    try:
        if platform.system() == "Darwin":
            buttons = '{"Nej", "Ja"}' if question else '{"OK"}'
            default = '"Nej"' if question else '"OK"'
            script = ('on run argv\n'
                      'set answer to display dialog (item 1 of argv) with title "Semesterlista" '
                      f'buttons {buttons} default button {default}\n'
                      'return button returned of answer\nend run')
            result = subprocess.run(['/usr/bin/osascript', '-e', script, text],
                                    capture_output=True, text=True, check=False)
            return question and result.returncode == 0 and result.stdout.strip() == 'Ja'
        if shutil.which('zenity'):
            command = ['zenity', '--question' if question else '--error',
                       '--title=Semesterlista', '--no-markup', '--text=' + text]
            if question:
                command += ['--default-cancel', '--ok-label=Ja', '--cancel-label=Nej']
            return subprocess.run(command, check=False).returncode == 0 and question
        if shutil.which('kdialog'):
            option = '--warningyesno' if question else '--error'
            command = ['kdialog', '--title', 'Semesterlista', option, text]
            if question:
                command += ['--defaultno']
            return subprocess.run(command, check=False).returncode == 0 and question
        import tkinter
        from tkinter import messagebox
        window = tkinter.Tk()
        window.withdraw()
        try:
            if question:
                return bool(messagebox.askyesno('Semesterlista', text, default='no', parent=window))
            messagebox.showerror('Semesterlista', text, parent=window)
            return False
        finally:
            window.destroy()
    except Exception:
        logger.exception('Kunde inte visa startdialog')
        return False


def offer_repair():
    return native_message(
        "Nödvändiga tillägg saknas eller kunde inte laddas.\n\n"
        "Vill du installera/reparera och uppdatera PySide6, reportlab och deras beroenden?\n"
        "Efteråt försöker appen starta igen. Hämtningen kan ta några minuter.\n\n"
        f"Befintlig Python: {sys.executable}\n"
        "Ingen ny Python eller separat miljö skapas. Andra program som använder samma "
        "Python kan påverkas. Stäng dem först.\n\n"
        "Ja = reparera och försök igen. Nej = avsluta utan installation.", question=True)


def repair_environment(root=ROOT):
    """Explicit user-approved repair, separate from weekly automatic maintenance."""
    executable = str(sys.executable)
    try:
        run([executable, "-m", "pip", "--version"], timeout=30)
    except RuntimeError:
        run([executable, "-m", "ensurepip", "--upgrade"])
    run([executable, "-m", "pip", "install", "--upgrade", "--force-reinstall",
         "--disable-pip-version-check", "--no-input", "--timeout", "15", "--retries", "1",
         "-r", str(root / "requirements.txt")])
    run([executable, "-m", "pip", "check"])
    run([executable, "-c", "from PySide6 import QtWidgets; import reportlab.pdfgen.canvas"], timeout=60)
    logger.info("Tillägg reparerade i befintlig Python: %s", executable)
    return Path(executable)


def acquire_repair_lock(root=ROOT):
    """POSIX equivalent of the Windows launcher's lifetime maintenance mutex."""
    import fcntl
    path = Path(root) / 'data' / 'runtime.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except BlockingIOError:
        handle.close()
        return None
    except BaseException:
        handle.close()
        raise


def preferred_python():
    from tools.python_selection import select_python
    return select_python()


def main():
    sys.path.insert(0, str(ROOT))
    from core.logging_setup import setup_logging
    setup_logging(ROOT)
    repair_lock = None
    try:
        executable = Path(sys.executable)
        already_selected = os.environ.pop('SEMESTERLISTA_PYTHON_SELECTED', '') == '1'
        if os.name != 'nt' and not already_selected and not any(
                arg in sys.argv for arg in ('--maintain', '--maintenance-only')):
            selected = preferred_python()
            if os.path.realpath(selected) != os.path.realpath(sys.executable):
                logger.info('Vald kompatibel system-Python: %s (startad från %s)', selected, sys.executable)
                return subprocess.run(
                    [selected, str(ROOT / 'tools' / 'runtime_check.py'), *sys.argv[1:]],
                    cwd=ROOT, env=dict(os.environ, SEMESTERLISTA_PYTHON_SELECTED='1')).returncode
        maintenance_only = "--maintenance-only" in sys.argv
        repair_allowed = "--no-repair" not in sys.argv and not maintenance_only
        if os.name != "nt":
            repair_lock = acquire_repair_lock()
            if repair_lock is None:
                repair_allowed = False
        repaired = False
        if "--maintain" in sys.argv or maintenance_only:
            try:
                executable = prepare_environment()
            except Exception:
                logger.exception("Veckounderhållet kunde inte verifiera tilläggen")
                if not repair_allowed:
                    raise
                if not offer_repair():
                    return 0
                executable = repair_environment()
                repaired = True
        if maintenance_only:
            return 0
        env = dict(os.environ, SEMESTERLISTA_RUNTIME_READY="1")
        if "--autostart" in sys.argv:
            env["SEMESTERLISTA_AUTOSTART"] = "1"
        if os.name == "nt":
            executable = executable.with_name("pythonw.exe")

        def launch():
            # The launcher owns the maintenance mutex throughout the app lifetime.
            return subprocess.run([str(executable), str(ROOT / "main.pyw")], env=env,
                                  cwd=ROOT).returncode

        code = launch()
        if code != DEPENDENCY_EXIT_CODE:
            return code
        if not repair_allowed:
            native_message("Tillägg kunde inte laddas. En annan app/startkontroll körs. "
                           "Stäng Semesterlista och starta igen för att kunna reparera tilläggen.")
            return 0  # Error already shown; avoid a second PowerShell popup.
        if repaired:
            raise RuntimeError("Tilläggen kunde fortfarande inte laddas efter reparation.")
        if not offer_repair():
            logger.info("Användaren avböjde reparation; ingen installation gjordes")
            return 0
        repair_environment()
        code = launch()  # One retry only, never a restart/install loop.
        if code == DEPENDENCY_EXIT_CODE:
            raise RuntimeError("Tilläggen kunde fortfarande inte laddas efter reparation.")
        return code
    except Exception:
        logger.exception("Startkontrollen misslyckades")
        if "--maintenance-only" not in sys.argv:
            native_message("Start eller reparation misslyckades. Ingen ny Python har installerats.\n"
                           f"Se felloggen: {ROOT / 'data' / 'loggar' / 'fel.log'}")
            return HANDLED_ERROR_EXIT_CODE
        return 1
    finally:
        if repair_lock is not None:
            repair_lock.close()
        logging.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
