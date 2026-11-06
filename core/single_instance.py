r"""
Single-instance-lock – Säkerställer att endast en instans körs.

Detta modul förhindrar att flera instanser av applikationen
startas samtidigt. Vid försök att starta en andra instans skickas
en "bring-to-front"-signal till den befintliga instansen, som då
visar sitt fönster.

UPPDATERAD v2.2.0: Synkad med plugin.py v2.2.0 och settings_manager.py v2.2.0.
                   Tillagt: Autostart med OS (Windows, macOS, Linux).
                   Autostart kan aktiveras/avaktiveras via settings:
                     settings_manager.set("advanced.autostart", True/False)
                   Plattformsspecifik implementation:
                     Windows → HKCU\Software\Microsoft\Windows\CurrentVersion\Run
                     macOS   → ~/Library/LaunchAgents/com.semesterlista.plist
                     Linux   → ~/.config/autostart/semesterlista.desktop

Implementation:
    Primär:   QSharedMemory + QLocalServer/QLocalSocket (PySide6)
    Fallback: TCP-socket på localhost med unik port

Användning:
    from core.single_instance import SingleInstanceLock

    lock = SingleInstanceLock("Semesterlista")
    if lock.is_running():
        lock.send_to_existing()  # Visa befintlig instans
        sys.exit(0)

    # ... starta applikationen ...

    # Aktivera autostart:
    lock.set_autostart(True)

    # Kolla om autostart är aktiverat:
    enabled = lock.get_autostart()

    # Vid avslut:
    lock.release()

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import sys
import os
import socket
import hashlib
import platform
import subprocess
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# QSharedMemory – cross-platform
try:
    from PySide6.QtCore import QSharedMemory
    _HAS_SHARED_MEMORY = True
except ImportError:
    _HAS_SHARED_MEMORY = False

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.18.1"

# ──────────────────────────────────────────────────────────
# Autostart-konstanter
# ──────────────────────────────────────────────────────────
AUTOSTART_APP_NAME:    str = "Semesterlista"
AUTOSTART_MACOS_PLIST: str = "com.semesterlista.plist"
AUTOSTART_LINUX_FILE:  str = "semesterlista.desktop"
AUTOSTART_WIN_REG_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Run"


# ══════════════════════════════════════════════════════════
# HJÄLPFUNKTIONER
# ══════════════════════════════════════════════════════════

def _get_app_key(app_name: str) -> str:
    """
    Skapa en unik nyckel baserat på applikationsnamnet.

    Använder MD5-hash för att skapa en plattformssäker sträng
    utan specialtecken som kan störa QSharedMemory eller sockets.

    Args:
        app_name: Applikationens namn.

    Returns:
        str: Unik nyckel (hex-sträng, 32 tecken).
    """
    return hashlib.md5(app_name.encode("utf-8")).hexdigest()


def _get_lock_file_path(app_name: str) -> Path:
    """
    Returnera sökväg till lock-fil.

    Args:
        app_name: Applikationens namn.

    Returns:
        Path: Sökväg till lock-fil i temp-katalogen.
    """
    key = _get_app_key(app_name)
    if platform.system() == "Windows":
        temp_dir = Path(
            os.environ.get(
                "TEMP",
                str(Path.home() / "AppData" / "Local" / "Temp"),
            )
        )
    else:
        temp_dir = Path("/tmp")
    return temp_dir / f".{key}_single_instance.lock"


def _find_available_port(start_port: int = 49200, max_attempts: int = 100) -> int:
    """
    Hitta en ledig TCP-port för socket-baserad fallback.

    Args:
        start_port:   Port att börja söka från.
        max_attempts: Max antal portar att testa.

    Returns:
        int: Ledig port, eller start_port om ingen hittas.
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.close()
            return port
        except OSError:
            continue
    return start_port


def _get_socket_port(app_name: str) -> int:
    """
    Beräkna en deterministisk port baserat på applikationsnamnet.

    Args:
        app_name: Applikationens namn.

    Returns:
        int: Portnummer (mellan 49152 och 65535).
    """
    key = _get_app_key(app_name)
    port_hash = int(key[:4], 16)
    return 49152 + (port_hash % 16384)


def _get_executable_path() -> str:
    """
    Returnera sökvägen till det körbara programmet.

    Hanterar:
      - Fryst applikation (PyInstaller exe)
      - Python-skript (.py / .pyw)
      - pythonw.exe på Windows (utan terminalfönster)

    Returns:
        str: Absolut sökväg till körbara filen, med lämpliga argument.
    """
    # Fryst applikation (PyInstaller)
    if getattr(sys, "frozen", False):
        return sys.executable

    # Python-skript
    script = Path(sys.argv[0]).resolve()

    if platform.system() == "Windows":
        # Föredra pythonw.exe för att undvika terminalfönster
        python_w = Path(sys.executable).parent / "pythonw.exe"
        if python_w.exists():
            return f'"{python_w}" "{script}"'
        return f'"{sys.executable}" "{script}"'

    return f'"{sys.executable}" "{script}"'


# ══════════════════════════════════════════════════════════
# AUTOSTART-HANTERARE
# ══════════════════════════════════════════════════════════

class AutostartManager:
    """
    Hanterar autostart med operativsystemet.

    Plattformsspecifik implementation:
        Windows → Registernyckel HKCU Run
        macOS   → LaunchAgent plist
        Linux   → XDG autostart .desktop-fil

    Alla operationer är tyst-felande (try/except) – autostart
    är en valfri funktion och ska aldrig krascha appen.
    """

    def __init__(self, app_name: str = AUTOSTART_APP_NAME):
        self._app_name: str   = app_name
        self._system:   str   = platform.system()
        self._exe_path: str   = _get_executable_path()

    # ──────────────────────────────────────────────────────────
    # Publikt API
    # ──────────────────────────────────────────────────────────

    def is_enabled(self) -> bool:
        """
        Kolla om autostart är aktiverat för detta OS.

        Returns:
            bool: True om autostart är aktiverat.
        """
        try:
            if self._system == "Windows":
                return self._is_enabled_windows()
            elif self._system == "Darwin":
                return self._is_enabled_macos()
            else:
                return self._is_enabled_linux()
        except Exception:
            return False

    def enable(self) -> bool:
        """
        Aktivera autostart med OS.

        Returns:
            bool: True om autostart aktiverades.
        """
        try:
            if self._system == "Windows":
                return self._enable_windows()
            elif self._system == "Darwin":
                return self._enable_macos()
            else:
                return self._enable_linux()
        except Exception:
            return False

    def disable(self) -> bool:
        """
        Avaktivera autostart med OS.

        Returns:
            bool: True om autostart avaktiverades.
        """
        try:
            if self._system == "Windows":
                return self._disable_windows()
            elif self._system == "Darwin":
                return self._disable_macos()
            else:
                return self._disable_linux()
        except Exception:
            return False

    def set(self, enabled: bool) -> bool:
        """
        Sätt autostart till aktiverat eller avaktiverat.

        Args:
            enabled: True = aktivera, False = avaktivera.

        Returns:
            bool: True om operationen lyckades.
        """
        if enabled:
            return self.enable()
        return self.disable()

    def get_status_text(self) -> str:
        """
        Returnera läsbar status för autostart.

        Returns:
            str: "Aktiverad", "Avaktiverad" eller "Ej tillgänglig".
        """
        try:
            if self.is_enabled():
                return "Aktiverad"
            return "Avaktiverad"
        except Exception:
            return "Ej tillgänglig"

    def get_platform_info(self) -> str:
        """
        Returnera info om hur autostart implementeras på detta OS.

        Returns:
            str: Beskrivning av implementationen.
        """
        if self._system == "Windows":
            return f"Windows-register: HKCU\\{AUTOSTART_WIN_REG_KEY}"
        elif self._system == "Darwin":
            plist_path = self._get_macos_plist_path()
            return f"macOS LaunchAgent: {plist_path}"
        else:
            desktop_path = self._get_linux_desktop_path()
            return f"XDG Autostart: {desktop_path}"

    # ──────────────────────────────────────────────────────────
    # Windows-implementation
    # ──────────────────────────────────────────────────────────

    def _is_enabled_windows(self) -> bool:
        """Kolla om autostart är aktiverat i Windows-registret."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                AUTOSTART_WIN_REG_KEY,
                0,
                winreg.KEY_READ,
            )
            try:
                value, _ = winreg.QueryValueEx(key, self._app_name)
                winreg.CloseKey(key)
                return bool(value)
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False

    def _enable_windows(self) -> bool:
        """Lägg till autostart i Windows-registret."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                AUTOSTART_WIN_REG_KEY,
                0,
                winreg.KEY_WRITE,
            )
            winreg.SetValueEx(
                key,
                self._app_name,
                0,
                winreg.REG_SZ,
                self._exe_path,
            )
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _disable_windows(self) -> bool:
        """Ta bort autostart från Windows-registret."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                AUTOSTART_WIN_REG_KEY,
                0,
                winreg.KEY_WRITE,
            )
            try:
                winreg.DeleteValue(key, self._app_name)
            except FileNotFoundError:
                pass  # Nyckeln fanns inte – OK
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    # ──────────────────────────────────────────────────────────
    # macOS-implementation
    # ──────────────────────────────────────────────────────────

    def _get_macos_plist_path(self) -> Path:
        """Returnera sökväg till LaunchAgent plist-fil."""
        return (
            Path.home()
            / "Library"
            / "LaunchAgents"
            / AUTOSTART_MACOS_PLIST
        )

    def _is_enabled_macos(self) -> bool:
        """Kolla om LaunchAgent plist finns."""
        return self._get_macos_plist_path().exists()

    def _enable_macos(self) -> bool:
        """Skapa LaunchAgent plist för autostart vid inloggning."""
        plist_path = self._get_macos_plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)

        # Bygg plist-innehåll
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{AUTOSTART_MACOS_PLIST.replace(".plist", "")}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{self._exe_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/dev/null</string>
    <key>StandardErrorPath</key>
    <string>/dev/null</string>
</dict>
</plist>
"""
        try:
            plist_path.write_text(plist_content, encoding="utf-8")
            # Ladda LaunchAgent
            subprocess.run(
                ["launchctl", "load", str(plist_path)],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            return False

    def _disable_macos(self) -> bool:
        """Ta bort LaunchAgent plist."""
        plist_path = self._get_macos_plist_path()
        try:
            if plist_path.exists():
                # Avlasta LaunchAgent
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True,
                    timeout=5,
                )
                plist_path.unlink()
            return True
        except Exception:
            return False

    # ──────────────────────────────────────────────────────────
    # Linux-implementation (XDG Autostart)
    # ──────────────────────────────────────────────────────────

    def _get_linux_desktop_path(self) -> Path:
        """Returnera sökväg till XDG .desktop-fil."""
        xdg_config = Path(
            os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        )
        return xdg_config / "autostart" / AUTOSTART_LINUX_FILE

    def _is_enabled_linux(self) -> bool:
        """Kolla om XDG autostart .desktop-fil finns och är aktiverad."""
        desktop_path = self._get_linux_desktop_path()
        if not desktop_path.exists():
            return False
        try:
            content = desktop_path.read_text(encoding="utf-8")
            # Kolla att Hidden=true inte är satt
            if "Hidden=true" in content:
                return False
            if "X-GNOME-Autostart-enabled=false" in content:
                return False
            return True
        except Exception:
            return False

    def _enable_linux(self) -> bool:
        """Skapa XDG autostart .desktop-fil."""
        desktop_path = self._get_linux_desktop_path()
        desktop_path.parent.mkdir(parents=True, exist_ok=True)

        desktop_content = f"""[Desktop Entry]
Type=Application
Name={self._app_name}
Comment=Startar {self._app_name} automatiskt vid inloggning
Exec={self._exe_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
StartupNotify=false
Terminal=false
"""
        try:
            desktop_path.write_text(desktop_content, encoding="utf-8")
            return True
        except Exception:
            return False

    def _disable_linux(self) -> bool:
        """Ta bort XDG autostart .desktop-fil."""
        desktop_path = self._get_linux_desktop_path()
        try:
            if desktop_path.exists():
                desktop_path.unlink()
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return (
            f"<AutostartManager '{self._app_name}' "
            f"platform={self._system} "
            f"enabled={self.is_enabled()}>"
        )


# ══════════════════════════════════════════════════════════
# SINGLEINSTANCELOCK – Huvudklass
# ══════════════════════════════════════════════════════════

class SingleInstanceLock(QObject):
    """
    Single-instance-lock via QSharedMemory + QLocalServer.

    Säkerställer att endast en instans av applikationen körs.
    Vid försök att starta en andra instans:
    1. Den nya instansen upptäcker att en redan körs
    2. Skickar "bring-to-front"-signal till den befintliga
    3. Den befintliga instansen visar sitt fönster
    4. Den nya instansen avslutas

    v2.2.0: Inkluderar AutostartManager för OS-autostart.
            Aktivera/avaktivera via:
                lock.set_autostart(True)
                lock.set_autostart(False)
                lock.get_autostart()

    Signaler:
        instance_started(): Emitteras när en andra instans försöker starta.
                            Koppla till att visa fönstret.
    """

    # ──────────────────────────────────────────────────────────
    # Signaler
    # ──────────────────────────────────────────────────────────

    instance_started = Signal()
    """
    Emitteras när en andra instans försöker starta.

    Koppla denna till att visa huvudfönstret:
        lock.instance_started.connect(main_window.show_application)
    """

    # ──────────────────────────────────────────────────────────
    # Konstruktor
    # ──────────────────────────────────────────────────────────

    def __init__(self, app_name: str):
        """
        Initiera single-instance-låset.

        Args:
            app_name: Unikt applikationsnamn (t.ex. "Semesterlista").
        """
        super().__init__()

        self._app_name:  str = app_name
        self._app_key:   str = _get_app_key(app_name)

        # Primärt lås: QSharedMemory
        self._shared_memory: Optional[QSharedMemory] = None
        self._is_primary:    bool                    = False
        self._pending_show = False
        self._activation_ready = False
        self._socket_timer = None

        # IPC: QLocalServer
        self._local_server: Optional[QLocalServer] = None
        self._server_name:  str = f"{self._app_key}_server"

        # Fallback: TCP-socket
        self._socket:      Optional[socket.socket] = None
        self._socket_port: int = _get_socket_port(app_name)

        # Lock-fil
        self._lock_file: Path = _get_lock_file_path(app_name)

        # Autostart-hanterare (v2.2.0)
        self._autostart: AutostartManager = AutostartManager(app_name)

        # Initiera lås
        self._setup_lock()

    # ──────────────────────────────────────────────────────────
    # Lås-initiering
    # ──────────────────────────────────────────────────────────

    def _setup_lock(self) -> None:
        """Sätt upp single-instance-låset (QSharedMemory eller fallback)."""
        if _HAS_SHARED_MEMORY:
            self._setup_shared_memory()
        else:
            self._setup_socket_lock()

    def _setup_shared_memory(self) -> None:
        """Sätt upp QSharedMemory-lås."""
        self._shared_memory = QSharedMemory(self._app_key)

        if self._shared_memory.create(1):
            self._is_primary = True
            self._start_local_server()
            self._write_lock_file()
        else:
            error = self._shared_memory.error()
            if error == QSharedMemory.SharedMemoryError.AlreadyExists:
                probe = QSharedMemory(self._app_key)
                if probe.attach():
                    probe.detach()  # Reap a stale Unix segment; live owners keep it attached.
                if self._shared_memory.create(1):
                    self._is_primary = True
                    self._start_local_server()
                    self._write_lock_file()
                else:
                    self._is_primary = False
            else:
                try:
                    self._shared_memory.attach()
                    self._shared_memory.detach()
                except Exception:
                    pass
                if self._shared_memory.create(1):
                    self._is_primary = True
                    self._start_local_server()
                    self._write_lock_file()
                else:
                    self._is_primary = False

    def _setup_socket_lock(self) -> None:
        """Sätt upp socket-baserat lås (fallback)."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self._socket.bind(("127.0.0.1", self._socket_port))
            self._socket.listen(1)
            self._socket.setblocking(False)
            self._is_primary = True
            self._write_lock_file()
            self._start_local_server()
            self._socket_timer = QTimer(self)
            self._socket_timer.timeout.connect(self._poll_socket)
            self._socket_timer.start(100)
        except OSError:
            self._is_primary = False
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

    # ──────────────────────────────────────────────────────────
    # QLocalServer – IPC
    # ──────────────────────────────────────────────────────────

    def _start_local_server(self) -> None:
        """Starta QLocalServer för bring-to-front IPC."""
        QLocalServer.removeServer(self._server_name)
        self._local_server = QLocalServer(self)
        self._local_server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._local_server.newConnection.connect(self._on_new_connection)

        if not self._local_server.listen(self._server_name):
            alt_name = f"{self._server_name}_alt"
            QLocalServer.removeServer(alt_name)
            if self._local_server.listen(alt_name):
                self._server_name = alt_name

    def set_activation_handler(self, callback):
        """Do not lose a second launch while the first UI is still loading."""
        self.instance_started.connect(callback)
        self._activation_ready = True
        if self._pending_show:
            self._pending_show = False
            QTimer.singleShot(0, callback)

    def _request_show(self):
        if self._activation_ready:
            self.instance_started.emit()
        else:
            self._pending_show = True

    @Slot()
    def _on_new_connection(self):
        if self._local_server is None:
            return
        while self._local_server.hasPendingConnections():
            client = self._local_server.nextPendingConnection()
            buffer = bytearray()

            def receive(client=client, buffer=buffer):
                buffer.extend(bytes(client.readAll()))
                if bytes(buffer) == b"show":
                    self._request_show()
                    client.disconnectFromServer()
                elif len(buffer) >= 4:
                    client.disconnectFromServer()

            client.readyRead.connect(receive)
            client.disconnected.connect(client.deleteLater)
            if client.bytesAvailable():
                receive()

    def _poll_socket(self):
        if self._socket is None:
            return
        try:
            client, _ = self._socket.accept()
        except OSError:
            return
        with client:
            client.settimeout(.1)
            try:
                if client.recv(16) == b"show":
                    self._request_show()
            except OSError:
                pass

    # ──────────────────────────────────────────────────────────
    # Lock-fil
    # ──────────────────────────────────────────────────────────

    def _write_lock_file(self) -> None:
        """Skriv lock-fil med aktuell PID."""
        try:
            self._lock_file.write_text(str(os.getpid()))
        except OSError:
            pass

    def _remove_lock_file(self) -> None:
        """Ta bort lock-filen vid avslut."""
        try:
            if self._lock_file.exists():
                self._lock_file.unlink()
        except OSError:
            pass

    # ──────────────────────────────────────────────────────────
    # Publika metoder – Single Instance
    # ──────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """
        Kolla om en annan instans redan körs.

        Returns:
            bool: True om en annan instans redan körs.
        """
        return not self._is_primary

    def get_version(self) -> str:
        """Returnera modulens versionsnummer."""
        return MODULE_VERSION

    def send_to_existing(self) -> bool:
        """
        Skicka bring-to-front-signal till befintlig instans.

        Returns:
            bool: True om meddelandet skickades.
        """
        self._allow_existing_foreground()
        for attempt in range(10):
            if self._try_qlocal_socket() or self._try_tcp_socket():
                return True
            if attempt < 9:
                time.sleep(.1)
        self._cleanup_stale_lock()
        return False

    def _try_qlocal_socket(self) -> bool:
        """Försök skicka via QLocalSocket."""
        for name in (self._server_name, self._server_name + "_alt"):
            socket_conn = QLocalSocket()
            socket_conn.connectToServer(name)
            if socket_conn.waitForConnected(200):
                socket_conn.write(b"show")
                socket_conn.flush()
                sent = socket_conn.bytesToWrite() == 0 or socket_conn.waitForBytesWritten(1000)
                socket_conn.disconnectFromServer()
                socket_conn.deleteLater()
                if sent:
                    return True
            else:
                socket_conn.deleteLater()
        return False

    def _allow_existing_foreground(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            pid = int(self._lock_file.read_text().strip())
            ctypes.windll.user32.AllowSetForegroundWindow(pid)
        except (OSError, ValueError, AttributeError):
            pass

    def _try_tcp_socket(self) -> bool:
        """Försök skicka via TCP-socket (fallback)."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(("127.0.0.1", self._socket_port))
            sock.sendall(b"show")
            sock.close()
            return True
        except (OSError, ConnectionRefusedError, TimeoutError):
            return False

    def _cleanup_stale_lock(self) -> None:
        """Rensa gammalt lås från kraschad instans."""
        try:
            if self._lock_file.exists():
                pid_str = self._lock_file.read_text().strip()
                pid = int(pid_str)
                if not self._is_pid_alive(pid):
                    self._lock_file.unlink()
                    if self._shared_memory is not None:
                        try:
                            self._shared_memory.attach()
                            self._shared_memory.detach()
                        except Exception:
                            pass
                    QLocalServer.removeServer(self._server_name)
        except (OSError, ValueError):
            try:
                self._lock_file.unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Kolla om en process lever."""
        if pid <= 0:
            return False
        if sys.platform == "win32":
            # os.kill(pid, 0) is NOT a safe existence probe on Windows.
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
            handle = kernel.OpenProcess(0x1000, False, pid)
            if not handle:
                return kernel.GetLastError() == 5  # Access denied is not proof of death.
            try:
                code = ctypes.c_ulong()
                return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
            finally:
                kernel.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except (OSError, ProcessLookupError):
            return False

    # ──────────────────────────────────────────────────────────
    # Publika metoder – Autostart (v2.2.0)
    # ──────────────────────────────────────────────────────────

    def get_autostart(self) -> bool:
        """
        Kolla om autostart med OS är aktiverat.

        Kontrollerar OS-specifik autostart-registrering:
            Windows → Registernyckel
            macOS   → LaunchAgent plist
            Linux   → XDG .desktop-fil

        Returns:
            bool: True om autostart är aktiverat.

        Exempel:
            if lock.get_autostart():
                print("Autostart är aktiverat")
        """
        return self._autostart.is_enabled()

    def set_autostart(self, enabled: bool) -> bool:
        """
        Aktivera eller avaktivera autostart med OS.

        Plattformsspecifik implementation:
            Windows → Lägger till/tar bort HKCU Run-registernyckel
                      Använder pythonw.exe för att undvika terminal
            macOS   → Skapar/tar bort LaunchAgent plist
                      ~/Library/LaunchAgents/com.semesterlista.plist
            Linux   → Skapar/tar bort XDG .desktop-fil
                      ~/.config/autostart/semesterlista.desktop

        Args:
            enabled: True = aktivera autostart,
                     False = avaktivera autostart.

        Returns:
            bool: True om operationen lyckades.

        Exempel:
            # Aktivera autostart
            success = lock.set_autostart(True)
            if success:
                print("Autostart aktiverat!")

            # Avaktivera autostart
            lock.set_autostart(False)
        """
        return self._autostart.set(enabled)

    def get_autostart_info(self) -> str:
        r"""
        Returnera information om autostart-implementationen.

        Visar var på disken/registret autostart lagras.

        Returns:
            str: Beskrivning av autostart-platsen för detta OS.

        Exempel:
            info = lock.get_autostart_info()
            print(info)
            # → "Windows-register: HKCU\Software\Microsoft\..."
        """
        return self._autostart.get_platform_info()

    def get_autostart_status_text(self) -> str:
        """
        Returnera läsbar status för autostart.

        Returns:
            str: "Aktiverad", "Avaktiverad" eller "Ej tillgänglig".
        """
        return self._autostart.get_status_text()

    @property
    def autostart_manager(self) -> AutostartManager:
        """
        Read-only access till AutostartManager.

        Kan användas för direkt åtkomst till avancerade
        autostart-funktioner.
        """
        return self._autostart

    # ──────────────────────────────────────────────────────────
    # Livscykel
    # ──────────────────────────────────────────────────────────

    def release(self) -> None:
        """
        Frigör single-instance-låset.

        Ska anropas vid normal avslutning av applikationen.
        OBS: Påverkar INTE autostart-inställningen.
        """
        was_primary = self._is_primary
        if self._socket_timer is not None:
            self._socket_timer.stop()
        if self._local_server is not None:
            self._local_server.close()
            QLocalServer.removeServer(self._server_name)
            self._local_server = None

        if self._shared_memory is not None and self._is_primary:
            try:
                self._shared_memory.detach()
            except Exception:
                pass
            self._shared_memory = None

        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        if was_primary:
            self._remove_lock_file()
        self._is_primary = False

    def __del__(self) -> None:
        """Destruktor – frigör resurser."""
        try:
            self.release()
        except Exception:
            pass

    def __repr__(self) -> str:
        """Debug-representation."""
        status = "primary" if self._is_primary else "secondary (blocked)"
        autostart = "autostart=on" if self.get_autostart() else "autostart=off"
        return (
            f"<SingleInstanceLock '{self._app_name}' "
            f"v{MODULE_VERSION} ({status}, {autostart}, "
            f"port={self._socket_port})>"
        )


# ══════════════════════════════════════════════════════════
# FRISTÅENDE HJÄLPFUNKTIONER
# ══════════════════════════════════════════════════════════

def check_single_instance(app_name: str) -> bool:
    """
    Snabbkontroll: körs redan en instans?

    Kan anropas innan QApplication skapas.

    Args:
        app_name: Applikationens namn.

    Returns:
        bool: True om en instans redan körs.
    """
    lock_file = _get_lock_file_path(app_name)
    if lock_file.exists():
        try:
            pid_str = lock_file.read_text().strip()
            pid = int(pid_str)
            if SingleInstanceLock._is_pid_alive(pid):
                return True
            lock_file.unlink(missing_ok=True)
        except (OSError, ValueError):
            lock_file.unlink(missing_ok=True)

    port = _get_socket_port(app_name)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        sock.bind(("127.0.0.1", port))
        sock.close()
        return False
    except OSError:
        return True


def send_to_existing(app_name: str) -> bool:
    """
    Skicka bring-to-front-signal till befintlig instans.

    Args:
        app_name: Applikationens namn.

    Returns:
        bool: True om meddelandet skickades.
    """
    port = _get_socket_port(app_name)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect(("127.0.0.1", port))
        sock.sendall(b"show")
        sock.close()
        return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        return False