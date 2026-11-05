"""Weekly package maintenance in the existing Python installation."""
from __future__ import annotations

from importlib import metadata
import logging
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
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
    run([str(executable), "-c", "from PySide6 import QtWidgets; import reportlab"])
    return executable


def main():
    sys.path.insert(0, str(ROOT))
    from core.logging_setup import setup_logging
    setup_logging(ROOT)
    try:
        executable = Path(sys.executable)
        if "--maintain" in sys.argv or "--maintenance-only" in sys.argv:
            executable = prepare_environment()
        if "--maintenance-only" in sys.argv:
            return 0
        env = dict(os.environ, SEMESTERLISTA_RUNTIME_READY="1")
        if os.name == "nt":
            executable = executable.with_name("pythonw.exe")
        logging.shutdown()
        # Hold the launcher's mutex until the app exits, protecting loaded packages.
        return subprocess.run([str(executable), str(ROOT / "main.pyw")], env=env,
                              cwd=ROOT).returncode
    except Exception:
        logger.exception("Startkontrollen misslyckades")
        print("Startkontrollen misslyckades. Se data/loggar/app.log.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
