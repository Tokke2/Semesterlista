"""Weekly package maintenance in the existing Python installation."""
from __future__ import annotations

from importlib import metadata
import logging
import os
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
    """Windows dialog independent of Qt, safe when PySide6 cannot import."""
    if os.name != "nt":
        logger.warning("%s", text)
        return False
    import ctypes
    dialog = ctypes.windll.user32.MessageBoxW
    dialog.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    dialog.restype = ctypes.c_int
    # Yes/No, default No. Never silently consent to changing shared packages.
    flags = (0x04 | 0x20 | 0x100) if question else 0x10
    return dialog(None, text, "Semesterlista – tillägg", flags | 0x10000) == 6


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


def main():
    sys.path.insert(0, str(ROOT))
    from core.logging_setup import setup_logging
    setup_logging(ROOT)
    try:
        executable = Path(sys.executable)
        maintenance_only = "--maintenance-only" in sys.argv
        repair_allowed = "--no-repair" not in sys.argv and not maintenance_only
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
        logging.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
