#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semesterlista – Plugin-baserad Desktop App (PySide6)

Entry point för applikationen. Startar minimerat i systemfältet,
laddar plugins som tabbar och hanterar all UI via PySide6.

Körs utan terminalfönster (använd pythonw.exe eller .pyw på Windows).

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
import ctypes
import importlib
import importlib.util
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING

# ──────────────────────────────────────────────────────────
# PySide6 – Modern GUI
# ──────────────────────────────────────────────────────────
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QTabBar,
    QMenu,
    QMenuBar,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStatusBar,
    QLabel,
    QPushButton,
    QMessageBox,
    QSizePolicy,
    QFrame,
    QSystemTrayIcon,
)
from PySide6.QtCore import (
    Qt,
    QEvent,
    QTimer,
    QSize,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QIcon,
    QFont,
    QPalette,
    QColor,
    QMouseEvent,
    QWheelEvent,
    QKeySequence,
    QShortcut,
    QPainter,
    QPixmap,
)

# ──────────────────────────────────────────────────────────
# Kärnmoduler
# ──────────────────────────────────────────────────────────
from core.event_bus import EventBus
from core.settings_manager import SettingsManager
from core.theme_manager import ThemeManager
from core.single_instance import SingleInstanceLock, AutostartManager
from plugins.base_plugin import BasePlugin

if TYPE_CHECKING:
    pass

# ──────────────────────────────────────────────────────────
# Projekt-root
# ──────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ──────────────────────────────────────────────────────────
# Loggning
# ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# ──────────────────────────────────────────────────────────
# Applikationsversion – EN källa för alla versioner
# ──────────────────────────────────────────────────────────
APP_VERSION: str = "2.2.0"

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

        # Bygg UI
        self._init_ui()

        # Ladda plugins som tabbar
        self._load_plugin_tabs()

        # Återställ fönsterposition
        self._restore_window_state()

        # Koppla events
        self._event_bus.on("plugin:loaded", self._on_plugin_loaded)
        self._event_bus.on("settings:changed", self._on_settings_changed)

    # ──────────────────────────────────────────────────────
    # UI-uppbyggnad
    # ──────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        """Bygg hela gränssnittet."""
        self.setWindowTitle(
            self._settings_manager.get("app_name", "Semesterlista")
        )
        self.setMinimumSize(800, 600)

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
        self._status_label = QLabel("Redo")
        self._statusbar.addWidget(self._status_label)

        # ── Menyrad ──────────────────────────────────────
        self._init_menu_bar()

    def _init_menu_bar(self) -> None:
        """
        Skapa menyraden.

        Arkiv:
          Inställningar...
          Autostart vid inloggning (checkable)  ← NY v2.2.0
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

        # ══════════════════════════════════════════════════
        # ARKIV
        # ══════════════════════════════════════════════════
        arkiv_menu = menubar.addMenu("&Arkiv")

        # Inställningar
        settings_action = QAction("&Inställningar...", self)
        settings_action.triggered.connect(self._open_settings)
        arkiv_menu.addAction(settings_action)

        arkiv_menu.addSeparator()

        # Autostart (v2.2.0)
        self._autostart_action = QAction(
            "&Autostart vid inloggning", self
        )
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(
            self._lock.get_autostart()
        )
        self._autostart_action.setToolTip(
            f"Starta Semesterlista automatiskt vid inloggning.\n"
            f"{self._lock.get_autostart_info()}"
        )
        self._autostart_action.triggered.connect(self._on_autostart_toggle)
        arkiv_menu.addAction(self._autostart_action)

        arkiv_menu.addSeparator()

        # Avsluta
        quit_action = QAction("&Avsluta", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self._quit_application)
        arkiv_menu.addAction(quit_action)

        # ══════════════════════════════════════════════════
        # VISA (dynamisk)
        # ══════════════════════════════════════════════════
        self._visa_menu = menubar.addMenu("&Visa")

        # ══════════════════════════════════════════════════
        # UTSEENDE (3 teman)
        # ══════════════════════════════════════════════════
        utseende_menu = menubar.addMenu("&Utseende")
        theme_group   = QActionGroup(self)
        theme_group.setExclusive(True)

        current_theme = self._theme_manager.get_current_theme()

        for theme_id, theme_label in [
            ("dark",   "&Mörkt tema"),
            ("light",  "&Ljust tema"),
            ("system", "&System-tema"),
        ]:
            action = QAction(theme_label, self)
            action.setCheckable(True)
            action.setChecked(theme_id == current_theme)
            action.setData(theme_id)
            action.triggered.connect(
                lambda checked, t=theme_id: self._on_theme_action(t)
            )
            theme_group.addAction(action)
            utseende_menu.addAction(action)

        # ══════════════════════════════════════════════════
        # HJÄLP
        # ══════════════════════════════════════════════════
        hjalp_menu = menubar.addMenu("&Hjälp")

        about_action = QAction("&Om Semesterlista...", self)
        about_action.triggered.connect(self._show_about)
        hjalp_menu.addAction(about_action)

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
            status_text = "aktiverad" if enabled else "avaktiverad"
            self.set_status(f"Autostart {status_text}")
            logger.info(f"Autostart {status_text}")
        else:
            # Återställ checkmark vid fel
            self._autostart_action.setChecked(not enabled)
            QMessageBox.warning(
                self,
                "Autostart",
                f"Kunde inte {'aktivera' if enabled else 'avaktivera'} "
                f"autostart.\n\n"
                f"Plats: {self._lock.get_autostart_info()}",
            )

    # ──────────────────────────────────────────────────────
    # Plugin-tabbar
    # ──────────────────────────────────────────────────────

    def _load_plugin_tabs(self) -> None:
        """Skapa tabbar för alla laddade plugins."""
        for name in self._plugin_manager.get_plugin_order():
            plugin = self._plugin_manager.get_plugin(name)
            if plugin is None:
                continue
            try:
                widget = plugin.get_tab_widget()
                if widget is not None:
                    self._register_tab(widget, plugin.get_name(), name)
            except Exception as e:
                logger.error(f"Kunde inte skapa tabb för {name}: {e}")

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

        idx = self._tab_widget.addTab(widget, tab_name)
        self._tab_widgets[plugin_id]   = widget
        self._tab_positions[plugin_id] = idx

        if self._visa_menu is not None:
            action = QAction(tab_name, self)
            action.setCheckable(True)
            action.setChecked(True)
            action.setData(plugin_id)
            action.triggered.connect(
                lambda checked, pid=plugin_id: self._toggle_tab(
                    pid, checked
                )
            )
            self._visa_menu.addAction(action)
            self._tab_actions[plugin_id] = action

    def _toggle_tab(self, plugin_id: str, visible: bool) -> None:
        """Toggla visa/dölj för en tabb."""
        if visible:
            self._show_tab(plugin_id)
        else:
            self._hide_tab(plugin_id)

    def _show_tab(self, plugin_id: str) -> None:
        """Visa en tidigare dold tabb."""
        if plugin_id not in self._tab_widgets:
            return

        widget  = self._tab_widgets[plugin_id]
        plugin  = self._plugin_manager.get_plugin(plugin_id)
        tab_name = plugin.get_name() if plugin else plugin_id

        idx = self._tab_widget.addTab(widget, tab_name)
        self._tab_positions[plugin_id] = idx

        if plugin_id in self._tab_actions:
            self._tab_actions[plugin_id].setChecked(True)

        self._event_bus.emit("tab:shown", {"name": plugin_id})
        self.set_status(f"Visade: {tab_name}")

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
        tab_name = plugin.get_name() if plugin else plugin_id

        self._event_bus.emit("tab:hidden", {"name": plugin_id})
        self.set_status(f"Dolde: {tab_name}")

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
        tab_name = plugin.get_name() if plugin else "Okänd"

        menu            = QMenu(self)
        hide_action     = menu.addAction(f'Dölj "{tab_name}"')
        menu.addSeparator()
        show_all_action = menu.addAction("Visa alla dolda tabbar")

        action = menu.exec(tab_bar.mapToGlobal(pos))

        if action == hide_action:
            self._hide_tab(plugin_id)
        elif action == show_all_action:
            for pid in list(self._tab_widgets.keys()):
                if pid not in [
                    self._tab_widgets.get(self._tab_widget.widget(i))
                    for i in range(self._tab_widget.count())
                ]:
                    self._show_tab(pid)
            # Visa alla (enkel variant)
            for pid in list(self._tab_widgets.keys()):
                self._show_tab(pid)

    def _on_tab_changed(self, index: int) -> None:
        """Hantera byte av aktiv tabb."""
        if self._tab_widget is None or index < 0:
            return
        tab_name = self._tab_widget.tabText(index)
        self.set_status(f"Aktiv: {tab_name}")

    # ──────────────────────────────────────────────────────
    # Tema
    # ──────────────────────────────────────────────────────

    def _on_theme_action(self, theme: str) -> None:
        """Hantera tema-byte från meny."""
        try:
            self._theme_manager.set_theme(theme)
            self.set_status(f"Tema: {theme}")
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

    def _restore_window_state(self) -> None:
        """Återställ fönstrets geometri från SettingsManager."""
        x         = self._settings_manager.get("window.x",         100)
        y         = self._settings_manager.get("window.y",         100)
        w         = self._settings_manager.get("window.width",    1200)
        h         = self._settings_manager.get("window.height",    800)
        maximized = self._settings_manager.get("window.maximized", False)

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
        """Dölj fönstret till systemfältet."""
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

    def _open_settings(self) -> None:
        """
        Öppna inställningsdialog.

        Visar data-sökväg och autostart-status.
        """
        autostart_status = self._lock.get_autostart_status_text()
        autostart_info   = self._lock.get_autostart_info()

        QMessageBox.information(
            self,
            "Inställningar",
            f"<b>Inställningar sparas i:</b><br>"
            f"{self._settings_manager.get_data_path()}<br><br>"
            f"<b>Tema:</b> {self._theme_manager.get_current_theme()}<br><br>"
            f"<b>Autostart:</b> {autostart_status}<br>"
            f"<small>{autostart_info}</small><br><br>"
            f"Använd <b>Arkiv → Autostart</b> för att ändra autostart.<br>"
            f"Använd <b>Utseende</b>-menyn för att byta tema.",
        )

    def _show_about(self) -> None:
        """
        Visa Om-dialog med dynamiskt copyright-år.
        """
        app_name = self._settings_manager.get("app_name", "Semesterlista")
        QMessageBox.about(
            self,
            f"Om {app_name}",
            f"<b>{app_name}</b> v{APP_VERSION}<br><br>"
            f"Plugin-baserad desktopapplikation<br>"
            f"för semesterlistor, limokörning &amp; hyresfakturering.<br><br>"
            f"Byggd med Python "
            f"{sys.version_info.major}.{sys.version_info.minor} "
            f"och PySide6.<br><br>"
            f"&copy; {COPYRIGHT_YEAR} Rickard Längkvist",
        )

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


# ══════════════════════════════════════════════════════════
# SYSTRAY MANAGER
# ══════════════════════════════════════════════════════════

class SystrayManager:
    """
    Hanterar systemfältsikonen och dess interaktioner.

    Enkelklick (vänster) → visa/dölj fönster
    Högerklick           → meny (Visa, Dölj, Avsluta)
    Tooltip              → f"Semesterlista v{APP_VERSION}"
    """

    def __init__(self, app: QApplication, main_window: MainWindow):
        """
        Initiera systemfältshanteraren.

        Skapar ikon programmatiskt: blå rundad fyrkant med "S" (64×64 px).
        """
        self._app:         QApplication = app
        self._main_window: MainWindow   = main_window

        # Skapa ikon programmatiskt
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#0078D4"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Arial", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "S",
        )
        painter.end()

        icon = QIcon(pixmap)

        # Skapa systemfältsikon
        self._tray_icon = QSystemTrayIcon(icon, app)
        self._tray_icon.setToolTip(f"Semesterlista v{APP_VERSION}")

        # Tray-meny
        self._tray_menu = QMenu()

        show_action = self._tray_menu.addAction("Visa Semesterlista")
        show_action.triggered.connect(self._main_window.show_application)

        hide_action = self._tray_menu.addAction("Dölj")
        hide_action.triggered.connect(self._main_window.hide_application)

        self._tray_menu.addSeparator()

        quit_action = self._tray_menu.addAction("Avsluta")
        quit_action.triggered.connect(
            self._main_window._quit_application
        )

        self._tray_icon.setContextMenu(self._tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

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
    # 1. Dölj terminal
    hide_console_window()

    # 2. Single-instance
    app_name = "Semesterlista"
    lock     = SingleInstanceLock(app_name)

    if lock.is_running():
        lock.send_to_existing()
        print(f"{app_name} körs redan. Visar befintlig instans.")
        sys.exit(0)

    # 3. QApplication
    app = QApplication(sys.argv)
    app.setApplicationName(app_name)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Rickard Längkvist")

    # Hög DPI-stöd
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 4. SettingsManager
    settings_manager = SettingsManager(str(PROJECT_ROOT))

    # 5. EventBus
    event_bus = EventBus()

    # 6. ThemeManager
    theme_manager = ThemeManager(settings_manager)
    saved_theme   = settings_manager.get("theme", "system")
    if saved_theme in theme_manager.VALID_THEMES:
        theme_manager._current_theme = saved_theme

    # 7. PluginManager
    plugin_manager = PluginManager(event_bus, settings_manager)
    plugins_dir    = PROJECT_ROOT / "plugins"
    discovered     = plugin_manager.discover_plugins(plugins_dir)

    logger.info(f"{'='*50}")
    logger.info(f"  {app_name} v{APP_VERSION}")
    logger.info(f"{'='*50}")
    logger.info(f"  Laddar plugins...")

    for plugin_info in discovered:
        plugin_manager.load_plugin(plugin_info)

    plugin_manager.initialize_all()

    logger.info(
        f"  {len(plugin_manager.plugins)} plugins laddade"
    )
    logger.info(f"{'='*50}")

    # 8. MainWindow – visas EJ (startar minimerat)
    main_window = MainWindow(
        app=app,
        event_bus=event_bus,
        settings_manager=settings_manager,
        theme_manager=theme_manager,
        plugin_manager=plugin_manager,
        lock=lock,
    )

    # 9. Applicera tema
    def _apply_theme(_: str = "") -> None:
        """Applicera QSS från ThemeManager på hela applikationen."""
        qss = theme_manager.get_button_tab_stylesheet()
        app.setStyleSheet(qss)

    theme_manager.theme_changed.connect(_apply_theme)
    _apply_theme()  # Applicera direkt vid start

    # 10. Koppla single-instance-signal → visa fönster
    lock.instance_started.connect(main_window.show_application)

    # 11. SystrayManager
    systray = SystrayManager(app, main_window)

    # Synka autostart från sparad inställning
    saved_autostart = settings_manager.get("advanced.autostart", False)
    if saved_autostart != lock.get_autostart():
        lock.set_autostart(bool(saved_autostart))

    # 12. Notifiera att appen är redo
    event_bus.emit("app:started", {
        "version": APP_VERSION,
        "app_name": app_name,
    })

    # Visa notifikation i systray
    systray.show_notification(
        f"{app_name}",
        f"v{APP_VERSION} – Körs i systemfältet",
        duration_ms=settings_manager.get(
            "systray.notification_duration_ms", 3000
        ),
    )

    # 13. Event-loop
    # OBS: main_window.show() anropas EJ → startar minimerat!
    try:
        exit_code = app.exec()
    finally:
        lock.release()
        event_bus.clear_all()
        logger.info(f"{app_name} avslutat.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()