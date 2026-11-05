#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semesterlista – Plugin-baserad Desktop App (PySide6)

Entry point för applikationen. Startar minimerat i systemfältet,
laddar plugins som tabbar och hanterar all UI via PySide6.

Körs utan terminalfönster (använd pythonw.exe eller .pyw på Windows).

UPPDATERAD v2.10.0: LOGOTYP I DROPDOWN + AUTOMATISK STORLEK I PDF.
                   Nytt: core/logo_picker.py – väljaren är en dropdown med
                   alla bilder i assets/ och dess undermappar,
                   förhandsgranskning som skalar sig själv och knappen
                   "Infoga SVG…" för bilder utanför assets/. Valet sparas
                   direkt i pluginets inställningar.
                   Nytt: PdfLogo.auto_size() – logotypen får 15 % av
                   sidbredden / 8 % av sidhöjden (tak 60 × 25 mm, minsta
                   ruta 36 × 12 pt) och proportionerna behålls på både
                   liggande och stående sidor.
                   Nytt i systemfältets högerklicksmeny: Inställningar…,
                   Sök efter uppdatering… och Om <app> v<version>…. Visa
                   och Dölj speglar fönstrets läge (Visa är standardval).
                   APP_VERSION bumpat till 2.10.0.
UPPDATERAD v2.9.0: UPPDATERING FRÅN GITHUB RELEASES.
                   Nytt: core/updater.py, knappen Hjälp → Sök efter
                   uppdatering… och gruppen Uppdatering under
                   Inställningar → Avancerat. Hämtar zipball från
                   releasen, säkerhetskopierar i data/backup/ och
                   startar om appen. Användarens listor och data/
                   rörs aldrig. Automatisk kontroll vid start kan
                   stängas av i Avancerat.
UPPDATERAD v2.8.0: DETALJERAD LOGGNING OCH INSTÄLLNINGSDIALOG.
                   Nytt: core/logging_setup.py – data/app.log (roterande,
                   2 MB × 5), data/crash.log via faulthandler, Qt:s egna
                   meddelanden i loggen och SEMESTERLISTA_DEBUG=1 för
                   DEBUG-nivå. Uppstarten loggas steg för steg med
                   tidsåtgång, och fel visas i en ruta med loggfilens väg.
                   Nytt: core/settings_dialog.py – flikarna Allmänt,
                   Fönster, Plugins och Avancerat. Saknas modulen startar
                   appen ändå (menyvalet inaktiveras och felet loggas).
                   APP_VERSION bumpat till 2.8.0.
UPPDATERAD v2.7.0: GEMENSAM APP-IKON ÖVERALLT.
                   Nytt: assets/ikon med SVG, PNG (16–256 px) och ICO samt
                   core/app_icon.py. Ikonen används av fönstret,
                   systemfältet och aktivitetsfältet (även
                   aktivitetshanteraren via AppUserModelID på Windows).
                   Reservikon ritas programmatiskt om bilderna saknas.
UPPDATERAD v2.6.0: VALBAR SIDLAYOUT OCH 1–3 MÅNADER PER BLAD.
                   Nytt: PDF:en kan skrivas ut liggande (A4, 270 mm
                   tabell – standard) eller stående (A4, 190 mm).
                   Nytt: 1, 2 eller 3 månader per blad (tidigare 2/3).
                   Startmånad väljs som förut (standard jan–dec eller
                   valfri månad, även över årsskifte).
                   Valen sparas per flik och valideras före export.
                   APP_VERSION bumpat till 2.6.0.
UPPDATERAD v2.5.0: FLIKAR FÖR HYRA, SEMESTERLISTA OCH FORDON + SVG-LOGOTYP.
                   Nytt: fliken "Fordon" (plugins/fordon) – ärver
                   lista-pluginets vy men låser läget till Limokörning.
                   Flikarna sorteras på TAB_ORDER: Hyra → Semesterlista
                   → Fordon, oberoende av mappordning.
                   Nytt: core/pdf_assets.py – logotyper från assets/
                   (även undermappar) bäddas in i PDF:en på varje sida.
                   SVG stöds som vektor via svglib, annars rasteriseras
                   den i 300 dpi med Qt (inget extra beroende).
                   Nytt: core/logo_dialog.py – välj logotyp med
                   förhandsgranskning; sparas per flik.
                   APP_VERSION bumpat till 2.5.0.
UPPDATERAD v2.4.0: BÄTTRE HANTERING AV ANSTÄLLDA, FORDON & HYRESGÄSTER.
                   Nytt: core/roster.py – en gemensam inläsare/skrivare för
                   Anställda.txt, Fordon.txt och Hyresgäster.txt
                   (kommentarer, teckenkodning, dubbletter, validering,
                   atomär skrivning med backup).
                   Nytt: core/list_editor_dialog.py – redigera listorna
                   direkt i appen (lägg till, ändra, ta bort, sortera,
                   klistra in flera) med flikar för hyresgästernas
                   månads- och kvartalslista.
                   Plugins: knapparna "Hantera lista…" (Semesterlista &
                   Limokörning) och "Hantera hyresgäster…"
                   (Hyresfakturering) öppnar redigeraren.
                   APP_VERSION bumpat till 2.4.0.
UPPDATERAD v2.3.0: TVÅSPRÅKIG (svenska/engelska) – väljs i
                   Arkiv → Inställningar → Språk.
                   Alla texter hämtas via core/i18n.py (core.i18n.t()).
                   Menyer, tabbar, statusrad och systemfält byggs om
                   direkt vid språkbyte (_retranslate_ui) – ingen omstart.
                   NYTT: Riktig inställningsdialog (core/settings_dialog.py)
                   med språk, tema, helgdagar (Sverige/USA), fönster,
                   plugins och avancerat.
                   NYTT: Plugins som inaktiverats i Inställningar laddas inte.
                   FIXAT: _show_tab() lägger inte längre till dubbletter
                   av en tabb som redan visas.
                   APP_VERSION bumpat till 2.3.0.
UPPDATERAD v2.2.0: Synkad med alla kärnmoduler och plugins v2.2.0.
                   APP_VERSION bumpat till 2.2.0.
                   Tillagt: Autostart-menyval i Arkiv-menyn.
                   Tillagt: autostart via SingleInstanceLock.set_autostart().
                   Tillagt: AA_EnableHighDpiScaling för hög DPI.
                   Tillagt: _apply_theme() kopplas till theme_changed-signal.
                   Förbättrad: _show_about() med dynamiskt copyright-år.
                   Förbättrad: _init_menu_bar() – Arkiv → Autostart (checkable).

Arkitektur:
    main.py → App → QApplication → MainWindow(QMainWindow)
                                   ├── QTabWidget (plugins som tabbar)
                                   ├── Menyrad (Arkiv, Visa, Utseende, Hjälp)
                                   ├── StatusBar
                                   └── SystrayManager (systemfält)

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import sys
import os
import time
import ctypes
import threading
import importlib
import importlib.util
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING

# ──────────────────────────────────────────────────────────
# Projekt-root – måste ligga först, importerna nedan kräver den
# ──────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).resolve().parent

# A .pyw file cannot bootstrap a missing interpreter; the Windows launcher can.
# Direct Windows starts are also routed through maintenance before Qt imports.
if __name__ == "__main__" and sys.platform == "win32":
    if os.environ.pop("SEMESTERLISTA_RUNTIME_READY", "") != "1":
        import subprocess
        subprocess.Popen([
            "powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass", "-File",
            str(PROJECT_ROOT / "tools" / "start_semesterlista.ps1"),
        ], cwd=PROJECT_ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
        raise SystemExit(0)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ──────────────────────────────────────────────────────────
# Loggning (v2.8.0)
# ──────────────────────────────────────────────────────────
# Sätts upp INNAN PySide6 och plugins importeras, så att även importfel och
# saknade filer hamnar i data/app.log i stället för bara i konsolen
# (pythonw.exe har ingen konsol).
#
#   Fil     data/loggar/app.log   (roterar vid 2 MB, 5 gamla filer sparas)
#   Fel     data/loggar/fel.log   (ERROR/CRITICAL, arkiveras aldrig)
#   Arkiv   data/loggar/arkiv/app-<dag>.log  (tidigare dagar)
#   Reserv  %TEMP%/Semesterlista/app.log om data/ inte går att skriva
#   Nivå    INFO, eller DEBUG om miljövariabeln SEMESTERLISTA_DEBUG är satt
#   Krasch  data/crash.log (faulthandler, t.ex. segmenteringsfel)
#
try:
    from core.logging_setup import (
        get_error_log_file,
        get_log_file,
        install_excepthook,
        install_faulthandler,
        install_qt_message_handler,
        log_startup_context,
        setup_logging,
        tail_log,
    )

    LOG_FILE: Optional[Path] = setup_logging(PROJECT_ROOT)
    install_excepthook()
    install_faulthandler()
    _LOGGING_ERROR: Optional[BaseException] = None
except Exception as _exc:  # pragma: no cover – loggningen får aldrig stoppa appen
    LOG_FILE = None
    _LOGGING_ERROR = _exc
    setup_logging = None  # type: ignore[assignment]
    install_excepthook = None  # type: ignore[assignment]
    install_faulthandler = None  # type: ignore[assignment]
    install_qt_message_handler = None  # type: ignore[assignment]
    log_startup_context = None  # type: ignore[assignment]
    get_log_file = lambda: None  # type: ignore[assignment]
    get_error_log_file = lambda: None  # type: ignore[assignment]
    tail_log = lambda lines=40: []  # type: ignore[assignment]
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

logger = logging.getLogger("main")

if _LOGGING_ERROR is not None:
    logger.error("Kunde inte sätta upp fil-loggning: %s", _LOGGING_ERROR)

# ──────────────────────────────────────────────────────────
# PySide6 – Modern GUI
# ──────────────────────────────────────────────────────────
try:
    importlib.import_module("reportlab.pdfgen.canvas")
    from PySide6.QtWidgets import (
        QApplication,
        QMainWindow,
        QTabWidget,
            QMenu,
            QWidget,
        QVBoxLayout,
            QStatusBar,
        QLabel,
            QMessageBox,
        QSizePolicy,
            QSystemTrayIcon,
    )
    from PySide6.QtCore import (
        Qt,
        QEvent,
        QObject,
                Signal,
        Slot,
    )
    from PySide6.QtGui import (
        QAction,
        QActionGroup,
        QGuiApplication,
                                QKeySequence,
                )
except Exception as _qt_error:  # pragma: no cover – miljö utan PySide6
    logger.critical("Nödvändiga tillägg kunde inte importeras", exc_info=_qt_error)
    print(
        "Nödvändiga tillägg saknas eller kunde inte laddas. Installera beroendena med:\n"
        "    pip install PySide6 reportlab\n"
        f"Loggfil: {LOG_FILE or 'kunde inte skapas'}",
        file=sys.stderr,
    )
    from tools.runtime_check import DEPENDENCY_EXIT_CODE
    raise SystemExit(DEPENDENCY_EXIT_CODE)

# ──────────────────────────────────────────────────────────
# Kärnmoduler
# ──────────────────────────────────────────────────────────
from core.event_bus import EventBus
from core.settings_manager import SettingsManager
from core.theme_manager import ThemeManager
from core.single_instance import SingleInstanceLock
from core import i18n, updater
from core.app_icon import apply_app_icon, app_icon, set_windows_app_user_model_id
from core.window_state import clamp_geometry
from core.cache import get_cache
from plugins.base_plugin import BasePlugin

# Inställningsdialogen är valfri: saknas filen ska appen ändå starta, men
# menyvalet inaktiveras och orsaken skrivs till loggen (v2.8.0).
try:
    from core.settings_dialog import SettingsDialog

    SETTINGS_DIALOG_ERROR: Optional[BaseException] = None
except Exception as _sd_error:
    SettingsDialog = None  # type: ignore[assignment,misc]
    SETTINGS_DIALOG_ERROR = _sd_error
    logger.error(
        "core/settings_dialog.py kunde inte importeras (%s). "
        "Arkiv → Inställningar inaktiveras. Kontrollera att filen finns i "
        "core/ (git pull) och att den går att läsa.",
        _sd_error,
        exc_info=True,
    )

if TYPE_CHECKING:
    pass

# ──────────────────────────────────────────────────────────
# Applikationsversion – EN källa för alla versioner
# ──────────────────────────────────────────────────────────
APP_VERSION: str = "2.17.2"

# ──────────────────────────────────────────────────────────
# Copyright-år – dynamiskt
# ──────────────────────────────────────────────────────────
COPYRIGHT_YEAR: str = str(datetime.now().year)


# ══════════════════════════════════════════════════════════
# HJÄLPFUNKTION – Dölj terminalfönster (Windows)
# ══════════════════════════════════════════════════════════

def hide_console_window() -> None:
    """
    Dölj terminal-/konsolfönstret på Windows.

    Gör att .py-filen kan dubbelklickas utan att ett svart
    terminalfönster visas. På Linux/Mac görs ingenting.
    """
    try:
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            user32   = ctypes.windll.user32
            hwnd     = kernel32.GetConsoleWindow()
            if hwnd:
                user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass  # Inte kritiskt


# ══════════════════════════════════════════════════════════
# PLUGIN MANAGER
# ══════════════════════════════════════════════════════════

class PluginManager:
    """
    Hanterar laddning och livscykel för plugins.

    Upptäcker plugins i plugins/-mappen, laddar dem dynamiskt
    och hanterar initialize/shutdown via EventBus.
    """

    def __init__(
        self,
        event_bus:        EventBus,
        settings_manager: SettingsManager,
    ):
        self._event_bus:        EventBus        = event_bus
        self._settings_manager: SettingsManager = settings_manager
        self.plugins:           Dict[str, BasePlugin] = {}
        self.plugin_order:      List[str]             = []

    def discover_plugins(self, plugins_dir: Path) -> List[Dict[str, Any]]:
        """
        Upptäck alla tillgängliga plugins i plugins/-mappen.

        En plugin är en undermapp med en plugin.py-fil.
        Mappar som börjar med _ ignoreras.

        Args:
            plugins_dir: Sökväg till plugins/-mappen.

        Returns:
            List[Dict]: Lista med {'name': ..., 'path': ...}.
        """
        discovered: List[Dict[str, Any]] = []

        if not plugins_dir.exists():
            plugins_dir.mkdir(parents=True, exist_ok=True)
            return discovered

        for item in sorted(plugins_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("_"):
                plugin_file = item / "plugin.py"
                if plugin_file.exists():
                    discovered.append({
                        "name": item.name,
                        "path": plugin_file,
                    })

        return discovered

    def load_plugin(self, plugin_info: Dict[str, Any]) -> bool:
        """
        Ladda en specifik plugin dynamiskt.

        1. Importerar plugin-modulen
        2. Letar efter Plugin-klass som ärver BasePlugin
        3. Instantierar med (event_bus, settings_manager)
        4. Registrerar i self.plugins

        Args:
            plugin_info: {'name': ..., 'path': ...}.

        Returns:
            bool: True om pluginen laddades.
        """
        try:
            module_name = f"plugins.{plugin_info['name']}.plugin"
            spec = importlib.util.spec_from_file_location(
                module_name,
                plugin_info["path"],
            )
            if spec is None or spec.loader is None:
                logger.error(
                    f"Kunde inte skapa spec för {plugin_info['name']}"
                )
                return False

            # Om modulen redan importerats (t.ex. för att en annan plugin
            # ärver den) återanvänds den i stället för att köras igen.
            module = sys.modules.get(module_name)
            if module is None or getattr(module, "Plugin", None) is None:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

            plugin_class = getattr(module, "Plugin", None)
            if plugin_class is None:
                logger.error(
                    f"Ingen Plugin-klass i {plugin_info['name']}"
                )
                return False

            if not issubclass(plugin_class, BasePlugin):
                logger.error(
                    f"Plugin {plugin_info['name']} ärver inte BasePlugin"
                )
                return False

            # Hoppa över plugins som inaktiverats i Inställningar (v2.3.0)
            plugin_meta = getattr(module, "PLUGIN_INFO", {}) or {}
            settings_name = plugin_meta.get("name", plugin_info["name"])
            try:
                entry = self._settings_manager.get_plugin_info(settings_name)
                if entry and entry.get("enabled") is False:
                    logger.info(
                        f"Pluginen '{settings_name}' är inaktiverad "
                        f"i Inställningar – hoppar över"
                    )
                    return False
            except Exception as e:  # pragma: no cover – defensivt
                logger.warning(f"Kunde inte läsa plugin-status: {e}")

            plugin_instance = plugin_class(
                self._event_bus,
                self._settings_manager,
            )
            self.plugins[plugin_info["name"]]     = plugin_instance
            self.plugin_order.append(plugin_info["name"])

            logger.info(
                f"Laddade plugin: {plugin_info['name']} "
                f"({plugin_instance.get_name()} "
                f"v{plugin_instance.get_version()})"
            )

            self._event_bus.emit("plugin:loaded", {
                "name":    plugin_instance.get_name(),
                "version": plugin_instance.get_version(),
                "id":      plugin_info["name"],
            })
            return True

        except Exception as e:
            logger.error(
                f"Kunde inte ladda plugin {plugin_info['name']}: {e}"
            )
            self._event_bus.emit("plugin:error", {
                "name":  plugin_info.get("name", "unknown"),
                "error": str(e),
            })
            return False

    def initialize_all(self) -> None:
        """Initiera alla laddade plugins."""
        for name in self.plugin_order:
            try:
                plugin  = self.plugins[name]
                success = plugin.initialize()
                if success:
                    logger.info(f"Initierade: {plugin.get_name()}")
                else:
                    logger.warning(
                        f"Initiering misslyckades: {plugin.get_name()}"
                    )
            except Exception as e:
                logger.error(f"Fel vid initiering av {name}: {e}")

    def shutdown_all(self) -> None:
        """Stäng ner alla plugins (omvänd ordning)."""
        for name in reversed(self.plugin_order):
            try:
                self.plugins[name].shutdown()
                logger.info(f"Nedstängd: {name}")
            except Exception as e:
                logger.error(f"Fel vid nedstängning av {name}: {e}")

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Hämta en specifik plugin."""
        return self.plugins.get(name)

    def get_all_plugins(self) -> Dict[str, BasePlugin]:
        """Returnera alla laddade plugins."""
        return dict(self.plugins)

    def get_plugin_order(self) -> List[str]:
        """Returnera plugin-ordningen."""
        return list(self.plugin_order)


# ══════════════════════════════════════════════════════════
# MAIN WINDOW
# ══════════════════════════════════════════════════════════

class StartupUpdateChecker(QObject):
    """
    Söker efter en nyare release i bakgrunden vid start (v2.9.0).

    Tråden rör aldrig Qt direkt – resultatet skickas som signaler som
    levereras i GUI-tråden. Fel sväljs (loggas) så att en start utan
    nätverk aldrig påverkar appen.
    """

    found  = Signal(str, str)   # (version, url)
    failed = Signal(str)        # felmeddelande

    def __init__(self, local_version: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._local_version = local_version

    def start(self) -> None:
        """Starta kontrollen i en egen tråd."""
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            info = updater.check_for_update(self._local_version)
        except Exception as exc:  # noqa: BLE001 – nätet får aldrig stoppa appen
            logger.info("Uppdateringskontroll vid start misslyckades: %s", exc)
            self.failed.emit(str(exc))
            return

        if info.available:
            self.found.emit(
                info.version,
                info.html_url or updater.github_release_url(),
            )
        else:
            logger.info(
                "Ingen uppdatering: senaste versionen är %s", info.version
            )


class MainWindow(QMainWindow):
    """
    Applikationens huvudfönster.

    Hanterar:
    - QTabWidget för plugins (tabbar)
    - Menyrad: Arkiv, Visa, Utseende, Hjälp
    - Autostart-menyval i Arkiv (checkable)
    - Visa/Dölj tabbar dynamiskt
    - Högerklick på tabb → Dölj
    - Mushjulsscroll på tabbar
    - Spara/återställ fönsterposition
    """

    window_shown = Signal()

    def __init__(
        self,
        app:              QApplication,
        event_bus:        EventBus,
        settings_manager: SettingsManager,
        theme_manager:    ThemeManager,
        plugin_manager:   PluginManager,
        lock:             SingleInstanceLock,
    ):
        """
        Initiera huvudfönstret.

        Args:
            app:              QApplication-instansen.
            event_bus:        Applikationens EventBus.
            settings_manager: Applikationens SettingsManager.
            theme_manager:    Applikationens ThemeManager.
            plugin_manager:   Applikationens PluginManager.
            lock:             SingleInstanceLock (för autostart).
        """
        super().__init__()

        self._app:              QApplication    = app
        self._event_bus:        EventBus        = event_bus
        self._settings_manager: SettingsManager = settings_manager
        self._theme_manager:    ThemeManager    = theme_manager
        self._plugin_manager:   PluginManager   = plugin_manager
        self._lock:             SingleInstanceLock = lock

        # Tabbar
        self._tab_widget:    Optional[QTabWidget]     = None
        self._tab_actions:   Dict[str, QAction]       = {}
        self._tab_widgets:   Dict[str, QWidget]       = {}
        self._tab_positions: Dict[str, int]           = {}
        self._visa_menu:     Optional[QMenu]          = None

        # Autostart-action (referens för uppdatering)
        self._autostart_action: Optional[QAction] = None
        self._settings_action:  Optional[QAction] = None

        # Menyer och systemfält (referenser för språkbyte, v2.3.0)
        self._arkiv_menu:   Optional[QMenu] = None
        self._visa_menu:    Optional[QMenu] = None
        self._theme_actions: Dict[str, QAction] = {}
        self._tray_manager: Optional[Any] = None

        # Bygg UI
        self._init_ui()

        # Ladda plugins som tabbar
        self._load_plugin_tabs()

        # Återställ fönsterposition
        self._restore_window_state()

        # Koppla events
        self._event_bus.on("plugin:loaded", self._on_plugin_loaded)
        self._event_bus.on("settings:changed", self._on_settings_changed)

        # Språkbyte (v2.3.0) – bygg om alla texter utan omstart
        i18n.get_translator().language_changed.connect(self._on_language_changed)

    # ──────────────────────────────────────────────────────
    # UI-uppbyggnad
    # ──────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        """Bygg hela gränssnittet."""
        self.setWindowTitle(
            self._settings_manager.get("app_name", "Semesterlista")
        )

        # Appikon (v2.7.0) – samma ikon i fönster, systemfält och aktivitetsfält
        try:
            self.setWindowIcon(app_icon())
        except Exception as exc:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte sätta fönsterikon: {exc}")

        self.setMinimumSize(520, 420)

        central     = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        # ── TabWidget ────────────────────────────────────
        self._tab_widget = QTabWidget()
        self._tab_widget.setMovable(True)
        self._tab_widget.setTabsClosable(False)
        self._tab_widget.setUsesScrollButtons(True)
        self._tab_widget.setElideMode(Qt.TextElideMode.ElideRight)
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Mushjulsscroll på tabbar
        tab_bar = self._tab_widget.tabBar()
        tab_bar.installEventFilter(self)

        # Högerklick på tabbar
        tab_bar.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        tab_bar.customContextMenuRequested.connect(
            self._on_tab_context_menu
        )

        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self._tab_widget, stretch=1)

        # ── StatusBar ────────────────────────────────────
        self._statusbar   = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._status_label = QLabel(i18n.t("status.ready"))
        self._statusbar.addWidget(self._status_label)

        # ── Menyrad ──────────────────────────────────────
        self._init_menu_bar()

    def _app_name(self) -> str:
        """Applikationens namn (används i menytexter och dialoger)."""
        return self._settings_manager.get("app_name", "Semesterlista")

    def _tab_index(self, plugin_id: str) -> int:
        """Index för en tabb i QTabWidget, eller -1 om den är dold."""
        if self._tab_widget is None or plugin_id not in self._tab_widgets:
            return -1
        return self._tab_widget.indexOf(self._tab_widgets[plugin_id])

    def _init_menu_bar(self) -> None:
        """
        Bygg menyraden på aktuellt språk.

        Anropas vid start OCH vid språkbyte (_on_language_changed),
        därför börjar metoden med att tömma menyraden.

        Arkiv:
          Inställningar...            (språk, tema, helgdagar, plugins m.m.)
          Autostart vid inloggning    (checkable)
          ─────────────────────────────────────
          Avsluta  Ctrl+Q

        Visa:
          (dynamisk – en post per plugin/tabb)

        Utseende:
          ● Mörkt tema
          ○ Ljust tema
          ○ System-tema

        Hjälp:
          Om Semesterlista...
        """
        menubar = self.menuBar()
        menubar.clear()

        # ══════════════════════════════════════════════════
        # ARKIV
        # ══════════════════════════════════════════════════
        self._arkiv_menu = menubar.addMenu(i18n.t("menu.file"))

        # Inställningar (v2.3.0: riktig dialog)
        settings_action = QAction(i18n.t("menu.file.settings"), self)
        settings_action.triggered.connect(self._open_settings)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        if SettingsDialog is None:  # v2.8.0 – saknad modul
            settings_action.setEnabled(False)
            settings_action.setToolTip(
                i18n.t(
                    "log.file_missing",
                    module="core/settings_dialog.py",
                    feature=i18n.t("settings.title"),
                )
            )
        self._settings_action = settings_action
        self._arkiv_menu.addAction(settings_action)

        self._arkiv_menu.addSeparator()

        # Autostart
        self._autostart_action = QAction(i18n.t("menu.file.autostart"), self)
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(self._lock.get_autostart())
        self._autostart_action.setToolTip(
            i18n.t("menu.file.autostart_tooltip", app=self._app_name())
            + "\n"
            + self._lock.get_autostart_info()
        )
        self._autostart_action.triggered.connect(self._on_autostart_toggle)
        self._arkiv_menu.addAction(self._autostart_action)

        self._arkiv_menu.addSeparator()

        # Avsluta
        quit_action = QAction(i18n.t("menu.file.quit"), self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self._quit_application)
        self._arkiv_menu.addAction(quit_action)

        # ══════════════════════════════════════════════════
        # VISA (dynamisk)
        # ══════════════════════════════════════════════════
        self._visa_menu = menubar.addMenu(i18n.t("menu.view"))
        self._rebuild_view_menu()

        # ══════════════════════════════════════════════════
        # UTSEENDE (3 teman)
        # ══════════════════════════════════════════════════
        utseende_menu = menubar.addMenu(i18n.t("menu.appearance"))
        theme_group   = QActionGroup(self)
        theme_group.setExclusive(True)

        current_theme = self._theme_manager.get_current_theme()
        self._theme_actions = {}

        for theme_id, theme_key in (
            ("dark",   "theme.dark"),
            ("light",  "theme.light"),
            ("system", "theme.system"),
            ("contrast", "theme.contrast"),
        ):
            action = QAction(i18n.t(theme_key), self)
            action.setCheckable(True)
            action.setChecked(theme_id == current_theme)
            action.setData(theme_id)
            action.triggered.connect(
                lambda checked, t=theme_id: self._on_theme_action(t)
            )
            theme_group.addAction(action)
            utseende_menu.addAction(action)
            self._theme_actions[theme_id] = action

        # ══════════════════════════════════════════════════
        # HJÄLP
        # ══════════════════════════════════════════════════
        hjalp_menu = menubar.addMenu(i18n.t("menu.help"))

        # Uppdatering från GitHub (v2.9.0)
        self._update_action = QAction(
            i18n.t("menu.help.check_updates"), self
        )
        self._update_action.triggered.connect(
            lambda: self._open_settings(check_updates=True)
        )
        hjalp_menu.addAction(self._update_action)
        hjalp_menu.addSeparator()

        about_action = QAction(
            i18n.t("menu.help.about", app=self._app_name()), self
        )
        about_action.triggered.connect(self._show_about)
        hjalp_menu.addAction(about_action)

    # ──────────────────────────────────────────────────────
    # Visa-menyn (dynamisk – en post per tabb)
    # ──────────────────────────────────────────────────────

    def _rebuild_view_menu(self) -> None:
        """Bygg om Visa-menyn med en post per registrerad tabb."""
        if self._visa_menu is None:
            return

        self._visa_menu.clear()
        self._tab_actions = {}

        for plugin_id in self._plugin_manager.get_plugin_order():
            plugin = self._plugin_manager.get_plugin(plugin_id)
            if plugin is None or plugin_id not in self._tab_widgets:
                continue

            # escape_mnemonics: annars göms & i menyn (v2.3.0)
            display_name = i18n.plugin_display_name_qt(plugin.get_name())
            action = QAction(display_name, self)
            action.setCheckable(True)
            action.setChecked(self._tab_index(plugin_id) >= 0)
            action.setData(plugin_id)
            action.triggered.connect(
                lambda checked, pid=plugin_id: self._toggle_tab(pid, checked)
            )
            self._visa_menu.addAction(action)
            self._tab_actions[plugin_id] = action

    # ──────────────────────────────────────────────────────
    # Språkbyte (v2.3.0)
    # ──────────────────────────────────────────────────────

    @Slot(str)
    def _on_language_changed(self, language: str = "") -> None:
        """
        Bygg om gränssnittets texter när språket ändras.

        Uppdaterar menyrad, tabbrubriker, statusrad och systemfält samt
        meddelar pluginarna via EventBus ("language:changed") så att
        deras vyer kan uppdatera sina texter utan omstart.
        """
        self._retranslate_ui()
        self._event_bus.emit("language:changed", {
            "language": language or i18n.current_language(),
        })

    def _retranslate_ui(self) -> None:
        """Uppdatera alla statiska texter i huvudfönstret."""
        self._init_menu_bar()

        if self._tab_widget is not None:
            for plugin_id, widget in self._tab_widgets.items():
                plugin = self._plugin_manager.get_plugin(plugin_id)
                if plugin is None:
                    continue
                idx = self._tab_widget.indexOf(widget)
                if idx >= 0:
                    # escape_mnemonics: annars göms & i flikrubriken
                    self._tab_widget.setTabText(
                        idx,
                        i18n.plugin_display_name_qt(plugin.get_name()),
                    )

        self.set_status(i18n.t("status.ready"))

        if self._tray_manager is not None:
            self._tray_manager.retranslate()

    def attach_tray(self, tray: Any) -> None:
        """Koppla systemfältet till huvudfönstret (för språkbyte)."""
        self._tray_manager = tray

    # ──────────────────────────────────────────────────────
    # Autostart (v2.2.0)
    # ──────────────────────────────────────────────────────

    @Slot()
    def _on_autostart_toggle(self) -> None:
        """
        Hantera aktivering/avaktivering av autostart.

        Uppdaterar OS-specifik autostart-registrering via
        SingleInstanceLock.set_autostart() och sparar
        inställningen i settings.json.
        """
        if self._autostart_action is None:
            return

        enabled = self._autostart_action.isChecked()
        success = self._lock.set_autostart(enabled)

        if success:
            self._settings_manager.set("advanced.autostart", enabled)
            status_text = i18n.t(
                "autostart.status_on" if enabled else "autostart.status_off"
            )
            self.set_status(f"{i18n.t('autostart.title')}: {status_text}")
            logger.info(f"Autostart {status_text}")
        else:
            # Återställ checkmark vid fel
            self._autostart_action.setChecked(not enabled)
            QMessageBox.warning(
                self,
                i18n.t("autostart.title"),
                i18n.t(
                    "autostart.error",
                    action=i18n.t(
                        "autostart.enable" if enabled else "autostart.disable"
                    ),
                )
                + "\n\n"
                + i18n.t(
                    "autostart.location",
                    path=self._lock.get_autostart_info(),
                ),
            )

    # ──────────────────────────────────────────────────────
    # Plugin-tabbar
    # ──────────────────────────────────────────────────────

    def _load_plugin_tabs(self) -> None:
        """
        Skapa tabbar för alla laddade plugins.

        v2.5.0: flikarna sorteras på pluginets TAB_ORDER (Hyra = 10,
        Semesterlista = 20, Fordon = 30) så att ordningen blir densamma
        oavsett i vilken ordning mapparna hittas.
        """
        for name in self._sorted_plugin_names():
            plugin = self._plugin_manager.get_plugin(name)
            if plugin is None:
                continue
            try:
                widget = plugin.get_tab_widget()
                if widget is not None:
                    self._register_tab(
                        widget,
                        i18n.plugin_display_name_qt(plugin.get_name()),
                        name,
                    )
            except Exception as e:
                logger.error(f"Kunde inte skapa tabb för {name}: {e}")

    def _sorted_plugin_names(self) -> List[str]:
        """
        Plugin-namn sorterade på TAB_ORDER, sedan på namn.

        Returns:
            List[str]: namn i den ordning flikarna ska skapas.
        """
        def order_key(plugin_name: str) -> tuple:
            plugin = self._plugin_manager.get_plugin(plugin_name)
            order = getattr(plugin, "TAB_ORDER", 100)
            try:
                order = int(order)
            except (TypeError, ValueError):
                order = 100
            return (order, plugin_name.casefold())

        return sorted(self._plugin_manager.get_plugin_order(), key=order_key)

    def _register_tab(
        self,
        widget:    QWidget,
        tab_name:  str,
        plugin_id: str,
    ) -> None:
        """
        Registrera en tabb i QTabWidget och Visa-menyn.

        Args:
            widget:    Widgeten som visas i tabben.
            tab_name:  Visningsnamn.
            plugin_id: Internt plugin-ID (mappnamn).
        """
        if self._tab_widget is None:
            return

        from core.ui_layout import scroll_page
        widget = scroll_page(widget)
        idx = self._tab_widget.addTab(widget, tab_name)
        self._tab_widgets[plugin_id]   = widget
        self._tab_positions[plugin_id] = idx

        # Visa-menyn byggs om så att nya tabbar får en menyrad
        self._rebuild_view_menu()

    def _toggle_tab(self, plugin_id: str, visible: bool) -> None:
        """Toggla visa/dölj för en tabb."""
        if visible:
            self._show_tab(plugin_id)
        else:
            self._hide_tab(plugin_id)

    def _show_tab(self, plugin_id: str) -> None:
        """
        Visa en tidigare dold tabb.

        Om tabben redan visas görs ingenting (v2.3.0: förhindrar
        dubbletter av samma widget i QTabWidget).
        """
        if plugin_id not in self._tab_widgets:
            return

        if self._tab_index(plugin_id) >= 0:
            if plugin_id in self._tab_actions:
                self._tab_actions[plugin_id].setChecked(True)
            return

        widget  = self._tab_widgets[plugin_id]
        plugin  = self._plugin_manager.get_plugin(plugin_id)
        tab_name = (
            i18n.plugin_display_name_qt(plugin.get_name())
            if plugin else plugin_id
        )

        from core.ui_layout import scroll_page
        widget = scroll_page(widget)
        idx = self._tab_widget.addTab(widget, tab_name)
        self._tab_positions[plugin_id] = idx

        if plugin_id in self._tab_actions:
            self._tab_actions[plugin_id].setChecked(True)

        self._event_bus.emit("tab:shown", {"name": plugin_id})
        self.set_status(i18n.t("status.tab_shown", name=tab_name))

    def _hide_tab(self, plugin_id: str) -> None:
        """Dölj en tabb."""
        if self._tab_widget is None:
            return
        if plugin_id not in self._tab_widgets:
            return

        widget = self._tab_widgets[plugin_id]

        for i in range(self._tab_widget.count()):
            if self._tab_widget.widget(i) is widget:
                self._tab_widget.removeTab(i)
                break

        if plugin_id in self._tab_actions:
            self._tab_actions[plugin_id].setChecked(False)

        plugin   = self._plugin_manager.get_plugin(plugin_id)
        tab_name = (
            i18n.plugin_display_name(plugin.get_name())
            if plugin else plugin_id
        )

        self._event_bus.emit("tab:hidden", {"name": plugin_id})
        self.set_status(i18n.t("status.tab_hidden", name=tab_name))

    def _on_tab_context_menu(self, pos) -> None:
        """Högerklick på tabb → kontextmeny."""
        if self._tab_widget is None:
            return

        tab_bar = self._tab_widget.tabBar()
        index   = tab_bar.tabAt(pos)

        if index < 0:
            return

        widget    = self._tab_widget.widget(index)
        plugin_id = None
        for pid, w in self._tab_widgets.items():
            if w is widget:
                plugin_id = pid
                break

        if plugin_id is None:
            return

        plugin   = self._plugin_manager.get_plugin(plugin_id)
        tab_name = (
            i18n.plugin_display_name(plugin.get_name())
            if plugin else i18n.t("menu.unknown_tab")
        )

        menu            = QMenu(self)
        # escape_mnemonics krävs även i menytexten
        hide_action     = menu.addAction(i18n.escape_mnemonics(
            i18n.t("menu.view.hide_tab", name=tab_name)
        ))
        menu.addSeparator()
        show_all_action = menu.addAction(i18n.t("menu.view.show_all"))

        action = menu.exec(tab_bar.mapToGlobal(pos))

        if action == hide_action:
            self._hide_tab(plugin_id)
        elif action == show_all_action:
            # Visa alla dolda tabbar (_show_tab hoppar över de som redan syns)
            for pid in list(self._tab_widgets.keys()):
                self._show_tab(pid)

    def _on_tab_changed(self, index: int) -> None:
        """Hantera byte av aktiv tabb."""
        if self._tab_widget is None or index < 0:
            return
        tab_name = self._tab_widget.tabText(index)
        self.set_status(i18n.t("status.active_tab", name=tab_name))

    # ──────────────────────────────────────────────────────
    # Tema
    # ──────────────────────────────────────────────────────

    def _on_theme_action(self, theme: str) -> None:
        """Hantera tema-byte från meny."""
        try:
            self._theme_manager.set_theme(theme)
            theme_key = {
                "dark":   "theme.dark.name",
                "light":  "theme.light.name",
                "system": "theme.system.name",
                "contrast": "theme.contrast.name",
            }.get(theme, "theme.system.name")
            self.set_status(
                i18n.t("status.theme", name=i18n.t(theme_key))
            )
        except ValueError as e:
            logger.error(f"Ogiltigt tema: {e}")

    # ──────────────────────────────────────────────────────
    # Fönsterhantering
    # ──────────────────────────────────────────────────────

    def _save_window_state(self) -> None:
        """Spara fönstrets geometri till SettingsManager."""
        geom = self.geometry()
        self._settings_manager.set("window.x",         geom.x())
        self._settings_manager.set("window.y",         geom.y())
        self._settings_manager.set("window.width",     geom.width())
        self._settings_manager.set("window.height",    geom.height())
        self._settings_manager.set("window.maximized", self.isMaximized())

    def _screen_rects(self) -> list:
        """
        Skärmarnas synliga ytor som (x, y, bredd, höjd).

        Används för att kontrollera att fönstret hamnar inom skärmen även om
        inställningarna sparades med en annan skärmuppsättning (v2.11.0).
        """
        rects = []
        try:
            for screen in QGuiApplication.screens():
                geometry = screen.availableGeometry()
                rects.append(
                    (geometry.x(), geometry.y(), geometry.width(), geometry.height())
                )
        except Exception as exc:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte läsa skärmarnas storlek: {exc}")
        return rects

    def _restore_window_state(self) -> None:
        """
        Återställ fönstrets geometri från SettingsManager.

        v2.11.0: geometrin klampas mot skärmarna, så att fönstret aldrig
        startar utanför en bortkopplad skärm ("appen syns inte"-buggen).
        """
        x         = self._settings_manager.get("window.x",         100)
        y         = self._settings_manager.get("window.y",         100)
        w         = self._settings_manager.get("window.width",    1200)
        h         = self._settings_manager.get("window.height",    800)
        maximized = self._settings_manager.get("window.maximized", False)

        x, y, w, h = clamp_geometry(x, y, w, h, self._screen_rects())
        self.setGeometry(x, y, w, h)
        if maximized:
            self.showMaximized()

    # ──────────────────────────────────────────────────────
    # Event-filter (mushjul på tabbar)
    # ──────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        """
        Fånga mushjuls-events på QTabBar för horisontell scroll.
        """
        if (
            self._tab_widget is not None
            and obj is self._tab_widget.tabBar()
            and event.type() == QEvent.Type.Wheel
        ):
            delta   = event.angleDelta().y()
            current = self._tab_widget.currentIndex()
            count   = self._tab_widget.count()

            if count == 0:
                return True

            if delta < 0:
                new_idx = (current + 1) % count
            else:
                new_idx = (current - 1) % count

            self._tab_widget.setCurrentIndex(new_idx)
            return True

        return super().eventFilter(obj, event)

    # ──────────────────────────────────────────────────────
    # closeEvent
    # ──────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """
        Fånga stängning (X-knapp).

        Om close_to_tray=True → minimera till systray.
        Annars → avsluta.
        """
        if self._settings_manager.get("systray.close_to_tray", True):
            event.ignore()
            self.hide()
            self._event_bus.emit("window:hidden", None)
        else:
            self._quit_application()

    # ──────────────────────────────────────────────────────
    # Publika metoder
    # ──────────────────────────────────────────────────────

    def show_application(self) -> None:
        """Visa och aktivera fönstret."""
        self.show()
        self.raise_()
        self.activateWindow()
        self._event_bus.emit("window:shown", None)
        self.window_shown.emit()

    def hide_application(self) -> None:
        """
        Dölj fönstret till systemfältet.

        Geometrin sparas redan här (v2.11.0), så att storlek och placering
        finns kvar även om appen avslutas från systemfältet utan att
        fönstret visats igen.
        """
        self._save_window_state()
        self.hide()
        self._event_bus.emit("window:hidden", None)

    def set_status(self, message: str) -> None:
        """Uppdatera statusraden."""
        self._status_label.setText(message)

    def _quit_application(self) -> None:
        """
        Faktiskt avsluta programmet.

        Sparar tillstånd, stänger plugins, frigör resurser.
        """
        self._save_window_state()

        # Smart cache: rensa det som renderats under körningen (v2.11.0)
        if self._settings_manager.get("advanced.clear_cache_on_exit", True):
            try:
                result = get_cache().purge()
                logger.info(i18n.t("log.cache_cleared", summary=result.summary()))
            except Exception as exc:  # pragma: no cover – får inte stoppa avslutet
                logger.warning(f"Kunde inte rensa cachen: {exc}")

        self._event_bus.emit("app:shutting_down", None)
        self._plugin_manager.shutdown_all()
        self._settings_manager.set(
            "tabs.order",
            self._plugin_manager.get_plugin_order(),
        )
        QApplication.quit()

    # ──────────────────────────────────────────────────────
    # Dialoger
    # ──────────────────────────────────────────────────────

    def _open_settings(self, check_updates: bool = False) -> None:
        """
        Öppna inställningsdialogen (v2.3.0).

        Dialogen hanterar språk (svenska/engelska), tema,
        helgdagsval (Sverige/USA), fönster/systemfält, plugins
        och avancerade inställningar.
        """
        if SettingsDialog is None:  # v2.8.0 – filen kunde inte importeras
            QMessageBox.warning(
                self,
                i18n.t("settings.title"),
                i18n.t(
                    "log.file_missing",
                    module="core/settings_dialog.py",
                    feature=i18n.t("settings.title"),
                )
                + f"\n\n{LOG_FILE or ''}",
            )
            return

        logger.info("Öppnar inställningsdialogen")
        dialog = SettingsDialog(
            settings_manager=self._settings_manager,
            theme_manager=self._theme_manager,
            lock=self._lock,
            plugin_manager=self._plugin_manager,
            event_bus=self._event_bus,
            parent=self,
            app_version=APP_VERSION,
        )

        if check_updates:
            # Öppna Avancerat-fliken och sök direkt (Hjälp → Sök efter uppdatering)
            dialog.show_update_check()

        result = dialog.exec()
        logger.info(
            "Inställningsdialogen stängd (resultat=%s, språk=%s, tema=%s)",
            result,
            i18n.current_language(),
            self._settings_manager.get("theme", "system"),
        )

        # Autostart kan ha ändrats i dialogen
        if self._autostart_action is not None:
            self._autostart_action.setChecked(self._lock.get_autostart())

    def _show_about(self) -> None:
        """
        Visa Om-dialog med dynamiskt copyright-år.
        """
        app_name = self._app_name()
        log_file = get_log_file()

        body = i18n.t(
            "about.body",
            app=app_name,
            version=APP_VERSION,
            py_major=sys.version_info.major,
            py_minor=sys.version_info.minor,
            year=COPYRIGHT_YEAR,
        )
        if log_file:
            # Loggfilens väg i Om-rutan gör felsökning mycket enklare (v2.8.0)
            body += f"\n\n{i18n.t('settings.log_file')} {log_file}"

        QMessageBox.about(self, i18n.t("about.title", app=app_name), body)
        logger.info("Om-dialogen visad (loggfil: %s)", log_file or "—")

    # ──────────────────────────────────────────────────────
    # EventBus-lyssnare
    # ──────────────────────────────────────────────────────

    def _on_plugin_loaded(self, data: Any = None) -> None:
        """Hantera att en plugin laddats dynamiskt – skapa tabb."""
        if not data or not isinstance(data, dict):
            return

        plugin_id   = data.get("id")
        plugin_name = data.get("name", plugin_id)

        if plugin_id is None:
            return

        plugin = self._plugin_manager.get_plugin(plugin_id)
        if plugin is None:
            return

        try:
            widget = plugin.get_tab_widget()
            if widget is not None and plugin_id not in self._tab_widgets:
                self._register_tab(widget, plugin_name, plugin_id)
        except Exception as e:
            logger.error(f"Kunde inte skapa tabb för {plugin_id}: {e}")

    def _on_settings_changed(self, data: Any = None) -> None:
        """Hantera ändrade inställningar."""
        if not data or not isinstance(data, dict):
            return
        key = data.get("key", "")
        # Synka autostart-checkmark om inställningen ändrats externt
        if key == "advanced.autostart" and self._autostart_action:
            value = data.get("value", False)
            self._autostart_action.setChecked(bool(value))
        # Språk kan ha ändrats utanför dialogen (v2.3.0)
        elif key == "language":
            value = data.get("value", i18n.DEFAULT_LANGUAGE)
            i18n.set_language(str(value))


# ══════════════════════════════════════════════════════════
# SYSTRAY MANAGER
# ══════════════════════════════════════════════════════════

class SystrayManager:
    """
    Hanterar systemfältsikonen och dess interaktioner.

    Enkelklick (vänster) → visa/dölj fönster
    Högerklick           → meny (v2.10.0):
                             Visa / Dölj      – speglar fönstrets läge
                             Inställningar…
                             Sök efter uppdatering…
                             Om {app} v{version}…
                             Avsluta
    Tooltip              → f"{app_name} v{APP_VERSION}"

    v2.11.0: Smart cache – rastrerade logotyper städas vid avslut (se
             core/cache.py, styrs av advanced.clear_cache_on_exit).

    v2.3.0: Alla texter hämtas via core/i18n.py och kan byggas om
            direkt vid språkbyte (retranslate()).
    """

    def __init__(self, app: QApplication, main_window: MainWindow):
        """
        Initiera systemfältshanteraren.

        v2.7.0: Använder appikonen från assets/ikon (samma som fönstret
                och aktivitetsfältet) i stället för en egenritad bokstav.
        """
        self._app:         QApplication = app
        self._main_window: MainWindow   = main_window

        # Samma ikon överallt (assets/ikon, annars programmatiskt ritad)
        icon = app_icon()

        self._app_name: str = main_window._app_name()

        # Skapa systemfältsikon
        self._tray_icon = QSystemTrayIcon(icon, app)
        self._tray_icon.setToolTip(f"{self._app_name} v{APP_VERSION}")

        # Tray-meny
        self._tray_menu = QMenu()

        self._show_action = self._tray_menu.addAction(
            i18n.t("tray.show", app=self._app_name)
        )
        self._show_action.triggered.connect(
            self._main_window.show_application
        )

        self._hide_action = self._tray_menu.addAction(i18n.t("tray.hide"))
        self._hide_action.triggered.connect(
            self._main_window.hide_application
        )

        self._tray_menu.addSeparator()

        # Inställningar och uppdatering direkt från systemfältet (v2.10.0)
        self._settings_action = self._tray_menu.addAction(
            i18n.t("tray.settings")
        )
        self._settings_action.triggered.connect(
            lambda: self._main_window._open_settings()
        )

        self._update_action = self._tray_menu.addAction(
            i18n.t("tray.check_updates")
        )
        self._update_action.triggered.connect(
            lambda: self._main_window._open_settings(check_updates=True)
        )

        self._about_action = self._tray_menu.addAction(
            i18n.t("tray.about", app=self._app_name, version=APP_VERSION)
        )
        self._about_action.triggered.connect(self._main_window._show_about)

        self._tray_menu.addSeparator()

        self._quit_action = self._tray_menu.addAction(i18n.t("tray.quit"))
        self._quit_action.triggered.connect(
            self._main_window._quit_application
        )

        # Visa/Dölj speglar fönstrets läge när menyn öppnas
        self._tray_menu.aboutToShow.connect(self._sync_actions)

        self._tray_icon.setContextMenu(self._tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def retranslate(self) -> None:
        """
        Uppdatera systemfältets texter till aktuellt språk (v2.3.0).

        Anropas av MainWindow._retranslate_ui() vid språkbyte.
        """
        self._app_name = self._main_window._app_name()
        self._tray_icon.setToolTip(f"{self._app_name} v{APP_VERSION}")
        self._show_action.setText(i18n.t("tray.show", app=self._app_name))
        self._hide_action.setText(i18n.t("tray.hide"))
        self._settings_action.setText(i18n.t("tray.settings"))
        self._update_action.setText(i18n.t("tray.check_updates"))
        self._about_action.setText(
            i18n.t("tray.about", app=self._app_name, version=APP_VERSION)
        )
        self._quit_action.setText(i18n.t("tray.quit"))

    def _sync_actions(self) -> None:
        """
        Anpassa menyn efter fönstrets läge (v2.10.0).

        Är fönstret synligt är *Visa* overksamt och tvärtom, så att menyn
        alltid visar vad som faktiskt går att göra. *Visa* är dessutom
        menyns standardval (fet stil).
        """
        visible = self._main_window.isVisible()
        self._show_action.setEnabled(not visible)
        self._hide_action.setEnabled(visible)
        self._tray_menu.setDefaultAction(
            self._hide_action if visible else self._show_action
        )

    def _on_tray_activated(self, reason) -> None:
        """
        Hantera klick på systemfältsikonen.

        Trigger (vänsterklick) = toggla visa/dölj.
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._main_window.isVisible():
                self._main_window.hide_application()
            else:
                self._main_window.show_application()

    def show_notification(
        self,
        title:       str,
        message:     str,
        duration_ms: int = 3000,
    ) -> None:
        """Visa en systemnotifikation."""
        self._tray_icon.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            duration_ms,
        )


# ══════════════════════════════════════════════════════════
# MAIN – Entry point
# ══════════════════════════════════════════════════════════

def main() -> None:
    """
    Huvudfunktion – startar hela applikationen.

    Steg:
     1. Dölj terminalfönster (Windows)
     2. Kolla single-instance-lock
     3. Skapa QApplication (inkl. hög DPI)
     4. Skapa SettingsManager
     4b. Initiera i18n (språk från settings.json)   ← NY v2.3.0
     5. Skapa EventBus
     6. Skapa ThemeManager + applicera tema
     7. Skapa PluginManager + ladda plugins
     8. Skapa MainWindow (visas EJ – minimerat)
     9. Applicera tema på QApplication
    10. Koppla single-instance-signal
    11. Skapa SystrayManager
    12. Emittera app:started
    13. Starta Qt event-loop
    """
    # ──────────────────────────────────────────────────
    # Detaljerad stegloggning (v2.8.0)
    # ──────────────────────────────────────────────────
    # Varje steg loggas med tid sedan föregående steg, så att en långsam
    # eller hängande uppstart syns direkt i data/app.log.
    t_start = time.perf_counter()
    _last = {"t": t_start}

    def step(number: str, text: str, detail: str = "") -> None:
        """Logga ett uppstartssteg med tidsåtgång."""
        now = time.perf_counter()
        logger.info(
            "STEG %-3s %-40s %6.0f ms (totalt %5.0f ms)%s",
            number,
            text,
            (now - _last["t"]) * 1000,
            (now - t_start) * 1000,
            f"  {detail}" if detail else "",
        )
        _last["t"] = now

    logger.info("=" * 64)
    logger.info("  Semesterlista startar – version %s", APP_VERSION)
    logger.info("=" * 64)

    # 1. Dölj terminal
    hide_console_window()
    step("1", "Dölj terminalfönster")

    # 2. Single-instance
    app_name = "Semesterlista"
    lock     = SingleInstanceLock(app_name)

    if lock.is_running():
        logger.warning(
            "En instans körs redan – skickar 'visa fönster' till den och avslutar"
        )
        lock.send_to_existing()
        print(f"{app_name} körs redan. Visar befintlig instans.")
        sys.exit(0)
    step("2", "Single-instance-lås", f"pid={os.getpid()}")

    # 3. QApplication
    # Hög DPI måste ställas in **innan** QApplication skapas – annars varnar
    # Qt: "setHighDpiScaleFactorRoundingPolicy must be called before creating
    # the QGuiApplication instance" (fixat efter loggen 2026-11-03).
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:  # pragma: no cover – Qt-version utan stödet
        logger.debug("Kunde inte ställa in hög DPI-policy", exc_info=True)

    app = QApplication(sys.argv)
    app.setApplicationName(app_name)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Rickard Längkvist")
    app.setApplicationDisplayName(app_name)

    # Qt:s egna meddelanden (varningar, plugin-fel) → loggen
    if install_qt_message_handler is not None:
        try:
            install_qt_message_handler()
        except Exception:
            logger.exception("Kunde inte installera Qt-meddelandehanteraren")

    # Miljöinformation (Python, Qt, OS, sökvägar) i loggen
    if log_startup_context is not None:
        try:
            log_startup_context(PROJECT_ROOT)
        except Exception:
            logger.exception("Kunde inte logga uppstartsmiljön")

    def _on_crash(traceback_text: str) -> None:
        """Visa felruta med loggfilens sökväg vid ett ohanterat fel."""
        try:
            last_line = (traceback_text.strip().splitlines() or [""])[-1]
            QMessageBox.critical(
                None,
                i18n.t("log.crash_title"),
                i18n.t(
                    "log.crash_body",
                    error=last_line,
                    log=str(LOG_FILE or "—"),
                ),
            )
        except Exception:  # pragma: no cover – får aldrig kasta vidare
            logger.exception("Kunde inte visa kraschdialogen")

    if install_excepthook is not None:
        install_excepthook(_on_crash)

    # Appikon överallt (v2.7.0): aktivitetshanterare/fält, tray, fönster.
    # AppUserModelID måste sättas innan fönstret skapas (Windows).
    set_windows_app_user_model_id()
    apply_app_icon(app)

    step("3", "QApplication, appikon, Qt-loggning")

    # 4. SettingsManager
    settings_manager = SettingsManager(str(PROJECT_ROOT))
    step(
        "4",
        "SettingsManager",
        f"data={settings_manager.get_data_path()}",
    )

    # 4b. Språk (i18n) – läses från settings.json innan UI byggs (v2.3.0)
    i18n.init(settings_manager)
    logger.info(f"  Språk: {i18n.current_language()}")
    step("4b", "i18n initierat", f"språk={i18n.current_language()}")

    # 4c. Smart cache – rensa gammalt skräp, resten städas vid avslut (v2.11.0)
    try:
        cache = get_cache()
        stale = cache.clean_stale()
        if settings_manager.get("advanced.clear_cache_on_exit", True):
            cache.register_exit_cleanup()
        step(
            "4c",
            "cache kontrollerad",
            f"{stale.summary()} | kvar={cache.size() / 1024:.0f} kB",
        )
    except Exception as exc:  # pragma: no cover – cachen får aldrig stoppa start
        logger.warning(f"Kunde inte kontrollera cachen: {exc}")

    # 5. EventBus
    event_bus = EventBus()
    step("5", "EventBus")

    # 6. ThemeManager
    theme_manager = ThemeManager(settings_manager)
    saved_theme   = settings_manager.get("theme", "system")
    if saved_theme in theme_manager.VALID_THEMES:
        theme_manager._current_theme = saved_theme
    step("6", "ThemeManager", f"tema={saved_theme}")

    # 7. PluginManager
    plugin_manager = PluginManager(event_bus, settings_manager)
    plugins_dir    = PROJECT_ROOT / "plugins"
    discovered     = plugin_manager.discover_plugins(plugins_dir)

    logger.info("  Hittade %d plugin-mappar i %s", len(discovered), plugins_dir)
    step("7", "Plugin-sökning", f"{len(discovered)} hittade")

    for plugin_info in discovered:
        name = str(plugin_info.get("name", "?"))
        t_plugin = time.perf_counter()
        loaded = plugin_manager.load_plugin(plugin_info)
        plugin = plugin_manager.plugins.get(name)
        if loaded and plugin is not None:
            logger.info(
                "  ✓ %-28s v%-8s %5.0f ms",
                plugin.get_name(),
                getattr(plugin, "VERSION", "?"),
                (time.perf_counter() - t_plugin) * 1000,
            )
        else:
            logger.error("  ✗ %-28s kunde inte laddas", name)

    t_init = time.perf_counter()
    plugin_manager.initialize_all()
    step(
        "7b",
        "Plugins laddade",
        f"{len(plugin_manager.plugins)} st, init {int((time.perf_counter() - t_init) * 1000)} ms",
    )

    # 8. MainWindow – visas EJ (startar minimerat)
    main_window = MainWindow(
        app=app,
        event_bus=event_bus,
        settings_manager=settings_manager,
        theme_manager=theme_manager,
        plugin_manager=plugin_manager,
        lock=lock,
    )
    tab_count = (
        main_window._tab_widget.count()
        if main_window._tab_widget is not None
        else 0
    )
    step("8", "MainWindow", f"flikar={tab_count}")

    # 9. Applicera tema
    def _apply_theme(_: str = "") -> None:
        """Applicera QSS från ThemeManager på hela applikationen."""
        try:
            qss = theme_manager.get_button_tab_stylesheet()
            app.setStyleSheet(qss)
            logger.debug("Tema applicerat (%d tecken QSS)", len(qss))
        except Exception:
            logger.exception("Kunde inte applicera temat")

    theme_manager.theme_changed.connect(_apply_theme)
    _apply_theme()  # Applicera direkt vid start
    step("9", "Tema applicerat")

    # 10. Koppla single-instance-signal → visa fönster
    lock.instance_started.connect(main_window.show_application)
    step("10", "Single-instance-signal kopplad")

    # 11. SystrayManager
    systray = SystrayManager(app, main_window)
    main_window.attach_tray(systray)   # så att språkbytet når systemfältet
    step("11", "Systray", f"visas={systray._tray_icon.isVisible()}")

    # Synka autostart från sparad inställning
    saved_autostart = settings_manager.get("advanced.autostart", False)
    if saved_autostart != lock.get_autostart():
        logger.info("Synkar autostart till %s", saved_autostart)
        lock.set_autostart(bool(saved_autostart))

    # 12. Notifiera att appen är redo
    event_bus.emit("app:started", {
        "version": APP_VERSION,
        "app_name": app_name,
    })

    # Visa notifikation i systray
    systray.show_notification(
        app_name,
        i18n.t("tray.started_message", version=APP_VERSION),
        duration_ms=settings_manager.get(
            "systray.notification_duration_ms", 3000
        ),
    )
    step("12", "app:started emitterat")

    # 12b. Sök efter uppdatering i bakgrunden (v2.9.0)
    update_checker: Optional[StartupUpdateChecker] = None
    if settings_manager.get("advanced.check_updates", True):
        def _notify_update(version: str, url: str) -> None:
            """Visa att en nyare version finns (ändrar inget automatiskt)."""
            logger.info("Ny version finns på GitHub: %s – %s", version, url)
            systray.show_notification(
                i18n.t("update.tray_title"),
                i18n.t(
                    "update.tray_body", version=version, current=APP_VERSION
                ),
                duration_ms=settings_manager.get(
                    "systray.notification_duration_ms", 3000
                ),
            )

        update_checker = StartupUpdateChecker(APP_VERSION)
        update_checker.found.connect(_notify_update)
        update_checker.start()
        step("12b", "Uppdateringskontroll", "startad i bakgrunden")

    logger.info(
        "%s är redo – uppstart klar på %.0f ms",
        app_name,
        (time.perf_counter() - t_start) * 1000,
    )
    logger.info("Loggfil: %s", LOG_FILE or "—")
    logger.info("Fellogg: %s", get_error_log_file() or "—")

    # 13. Event-loop
    # OBS: main_window.show() anropas EJ → startar minimerat!
    exit_code = 0
    try:
        exit_code = app.exec()
    except Exception:
        logger.exception("Ohanterat fel i event-loopen")
        exit_code = 1
    finally:
        logger.info("Stänger ned – exit-kkod %s", exit_code)
        try:
            plugin_manager.shutdown_all()
        except Exception:
            logger.exception("Fel vid avstängning av plugins")
        lock.release()
        event_bus.clear_all()
        logger.info(
            "%s avslutat efter %.1f s.",
            app_name,
            time.perf_counter() - t_start,
        )
        logging.shutdown()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
