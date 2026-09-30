"""
Bas-klass som alla plugins ärver från.

Detta modul definierar den abstrakta basklassen BasePlugin som ALLA
plugins MÅSTE ärva från. Den definierar kontraktet för plugin-gränssnittet
inklusive nödvändiga abstrakta metoder, inställningshantering och
hjälpmetoder för EventBus-kommunikation.

UPPDATERAD v2.2.0: Synkad med plugin.py v2.2.0, settings_manager.py v2.2.0,
                   single_instance.py v2.2.0 och event_bus.py v2.2.0.
                   Dokumentation uppdaterad med v2.2.0-events
                   (spans_year_boundary, range_label, start_year, end_year).
                   Kända plugins uppdaterade till v2.2.0.

Användning:
    from plugins.base_plugin import BasePlugin
    from PySide6.QtWidgets import QWidget, QLabel

    class MittPlugin(BasePlugin):
        NAME = "MittPlugin"
        VERSION = "1.0.0"

        def get_name(self) -> str:
            return self.NAME

        def get_version(self) -> str:
            return self.VERSION

        def get_tab_widget(self) -> QWidget:
            return QLabel("Hej från MittPlugin!")

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, TYPE_CHECKING

from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.settings_manager import SettingsManager


class BasePlugin(ABC):
    """
    Abstrakt basklass för alla plugins.

    Varje plugin MÅSTE implementera:
        - get_name()        → Returnerar plugin-namn (unik identifierare)
        - get_version()     → Returnerar versionssträng
        - get_tab_widget()  → Returnerar QWidget som visas som tabb

    Klassen tillhandahåller:
        - Automatisk EventBus-hantering (subscribe, unsubscribe, emit)
        - JSON-baserad inställningshantering via SettingsManager
        - Livscykelmetoder: initialize(), shutdown()
        - Spårning av prenumerationer för automatisk cleanup

    Kända plugins och deras inställningsnycklar (v2.2.0):
        "Hyresfakturering":
            year, last_file, last_used
        "Semesterlista & Limokörning":
            default_mode, auto_open_pdf, last_file,
            months_per_page, start_month, default_year, last_used
            (start_month: 0=Standard/jan–dec valt år,
                          1–12=explicit startmånad,
                          12=December → kan gå till Jan nästa år)
    """

    # ──────────────────────────────────────────────────────────
    # Plugin-metadata (överskrid i subklass)
    # ──────────────────────────────────────────────────────────

    NAME:         str       = "Unnamed Plugin"
    VERSION:      str       = "1.0.0"
    DESCRIPTION:  str       = ""
    AUTHOR:       str       = ""
    DEPENDENCIES: List[str] = []  # Plugin-namn (NAME) som krävs

    # ──────────────────────────────────────────────────────────
    # Konstruktor
    # ──────────────────────────────────────────────────────────

    def __init__(
        self,
        event_bus:        "EventBus",
        settings_manager: "SettingsManager",
    ):
        """
        Initiera pluginen med delade kärnresurser.

        Args:
            event_bus:        Applikationens EventBus-instans för pub/sub.
            settings_manager: Applikationens SettingsManager för
                              JSON-inställningar (settings.json + plugins.json).
        """
        self._event_bus:        "EventBus"        = event_bus
        self._settings_manager: "SettingsManager" = settings_manager
        self._is_initialized:   bool              = False
        self._subscriptions:    List[tuple]       = []
        # _subscriptions: [(event_name, callback), ...] för automatisk cleanup

    # ──────────────────────────────────────────────────────────
    # Abstrakta metoder (MÅSTE implementeras av varje plugin)
    # ──────────────────────────────────────────────────────────

    @abstractmethod
    def get_name(self) -> str:
        """
        Returnera pluginens unika namn.

        Används som identifierare i hela applikationen
        (tabb-namn, inställningar, event-namn, etc.).
        Måste vara unikt bland alla laddade plugins.

        Returns:
            str: Plugin-namn, t.ex. "Semesterlista & Limokörning".
        """
        ...

    @abstractmethod
    def get_version(self) -> str:
        """
        Returnera pluginens versionssträng.

        Semantisk versionering: MAJOR.MINOR.PATCH.

        Returns:
            str: Version, t.ex. "2.2.0".
        """
        ...

    @abstractmethod
    def get_tab_widget(self) -> QWidget:
        """
        Returnera den QWidget som visas som tabb i huvudfönstret.

        Widgeten läggs till som en flik i MainApp's QTabWidget.

        Returns:
            QWidget: Pluginens huvud-UI.

        Exempel:
            def get_tab_widget(self) -> QWidget:
                widget = QWidget()
                layout = QVBoxLayout(widget)
                layout.addWidget(QLabel("Min Plugin UI"))
                return widget
        """
        ...

    # ──────────────────────────────────────────────────────────
    # Livscykelmetoder (kan överskridas)
    # ──────────────────────────────────────────────────────────

    def initialize(self) -> bool:
        """
        Initiera pluginen efter att den laddats.

        Anropas av MainApp efter instantiering men innan
        tabb-widget visas. Använd för att:
        - Prenumerera på EventBus-events
        - Ladda data från filer eller API:er
        - Skapa interna datastrukturer

        Returns:
            bool: True om initieringen lyckades.
                  False → pluginen avlastas.

        Exempel:
            def initialize(self) -> bool:
                self.subscribe("theme:changed", self._on_theme_changed)
                self.subscribe("app:shutting_down", self._on_shutdown)
                self._load_data()
                self._is_initialized = True
                return True
        """
        self._is_initialized = True
        return True

    def shutdown(self) -> None:
        """
        Städa upp pluginen vid avlastning/avslut.

        Anropas av MainApp vid:
        - Applikationsavslut
        - Manuell avlastning
        - Krasch-cleanup

        Standardimplementationen:
        1. Avprenumererar ALLA EventBus-prenumerationer automatiskt
        2. Rensar _subscriptions-listan
        3. Sätter _is_initialized = False

        Överskrid och anropa ALLTID super().shutdown():

        Exempel:
            def shutdown(self) -> None:
                self._save_settings()
                self._close_connections()
                super().shutdown()
        """
        for event_name, callback in self._subscriptions:
            try:
                self._event_bus.off(event_name, callback)
            except Exception:
                pass  # Tyst fel – stör ej nedstängning

        self._subscriptions.clear()
        self._is_initialized = False

    def is_initialized(self) -> bool:
        """
        Kolla om pluginen har initierats korrekt.

        Returns:
            bool: True om initialize() anropats och lyckats.
        """
        return self._is_initialized

    # ──────────────────────────────────────────────────────────
    # Inställningshantering
    # ──────────────────────────────────────────────────────────

    def get_settings(self) -> Dict[str, Any]:
        """
        Hämta plugin-specifika inställningar från SettingsManager.

        Läser från plugins.json under pluginens namn.
        SettingsManager._merge_plugin_defaults() (v2.2.0) säkerställer
        att alla standard-fält alltid finns.

        Returns:
            Dict[str, Any]: Pluginens inställningar.

        Exempel:
            settings    = self.get_settings()
            start_month = settings.get("start_month", 0)
            # 0  = Standard (jan–dec valt år)
            # 12 = December → kan gå till jan nästa år
            months      = settings.get("months_per_page", 3)
            last_file   = settings.get("last_file", "")
        """
        plugin_name = self.get_name()
        return self._settings_manager.get_plugin_settings(plugin_name)

    def save_settings(self, settings: Dict[str, Any]) -> None:
        """
        Spara plugin-specifika inställningar till SettingsManager.

        Sparas i plugins.json under pluginens namn.
        Atomär skrivning via SettingsManager._save_atomic().

        Args:
            settings: Dict med inställningar att spara.

        Exempel:
            self.save_settings({
                "default_mode":    "Semesterlista",
                "auto_open_pdf":   True,
                "months_per_page": 3,
                "start_month":     12,  ← December → Dec→Jan nästa år
                "last_file":       "Anställda.txt",
                "last_used":       datetime.now().isoformat(),
            })
        """
        plugin_name = self.get_name()
        self._settings_manager.save_plugin_settings(plugin_name, settings)

    # ──────────────────────────────────────────────────────────
    # EventBus-hjälpmetoder
    # ──────────────────────────────────────────────────────────

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """
        Prenumerera på ett EventBus-event.

        Spåras automatiskt i _subscriptions för cleanup vid shutdown().

        Standard-events:
            "app:started"        → Appen startad
            "app:shutting_down"  → Appen stängs
            "theme:changed"      → {"theme": "dark|light|system"}
            "tab:shown"          → {"name": "plugin_id"}
            "tab:hidden"         → {"name": "plugin_id"}
            "settings:changed"   → {"key": "...", "value": "..."}
            "plugin:loaded"      → {"name": "...", "version": "..."}
            "plugin:unloaded"    → {"name": "..."}
            "plugin:error"       → {"name": "...", "error": "..."}
            "window:shown"       → Fönstret visas
            "window:hidden"      → Fönstret döljs

        Plugin-specifika events (v2.2.0):
            "semesterlista:pdf_generated" → {
                filename, year, mode, items_count,
                months_per_page, start_month,
                range_label,           ← t.ex. "Dec 2026 – Nov 2027"
                spans_year_boundary,   ← True om över årsskifte
                start_year,            ← t.ex. 2026
                end_year,              ← t.ex. 2027
            }
            "semesterlista:settings_changed" → {settings dict}
            "semesterlista:view_shown"       → {mode}
            "semesterlista:folder_opened"    → {path}
            "hyresfakturering:pdf_generated" → {filename, year,
                                                monthly_count,
                                                quarterly_count}
            "hyresfakturering:file_opened"   → {file}
            "hyresfakturering:data_reloaded" → {monthly_count,
                                                quarterly_count}

        Args:
            event_name: Event-namn (t.ex. "theme:changed").
            callback:   callback(data: Any) → None

        Exempel:
            self.subscribe("theme:changed",     self._on_theme_changed)
            self.subscribe("app:shutting_down", self._on_app_shutdown)
        """
        self._event_bus.on(event_name, callback)
        self._subscriptions.append((event_name, callback))

    def unsubscribe(
        self,
        event_name: str,
        callback:   Optional[Callable] = None,
    ) -> None:
        """
        Avprenumerera från ett EventBus-event.

        Args:
            event_name: Event-namn.
            callback:   Specifik callback, eller None = ta bort alla.

        Exempel:
            self.unsubscribe("theme:changed", self._on_theme_changed)
            self.unsubscribe("theme:changed")  # Ta bort alla
        """
        self._event_bus.off(event_name, callback)

        if callback is None:
            self._subscriptions = [
                (ev, cb) for ev, cb in self._subscriptions
                if ev != event_name
            ]
        else:
            self._subscriptions = [
                (ev, cb) for ev, cb in self._subscriptions
                if not (ev == event_name and cb == callback)
            ]

    def emit(self, event_name: str, data: Any = None) -> None:
        """
        Emittera ett event via EventBus.

        Namnkonvention: 'plugin_namn:händelse'.

        Args:
            event_name: Event-namn.
            data:       Data att skicka med (valfritt).

        Exempel:
            self.emit("semesterlista:pdf_generated", {
                "filename":            "semesterlista_2026_12-2027_11.pdf",
                "year":                2026,
                "mode":                "Semesterlista",
                "items_count":         12,
                "months_per_page":     3,
                "start_month":         12,
                "range_label":         "December 2026 – November 2027",
                "spans_year_boundary": True,
                "start_year":          2026,
                "end_year":            2027,
            })
        """
        self._event_bus.emit(event_name, data)

    # ──────────────────────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────────────────────

    @property
    def event_bus(self) -> "EventBus":
        """Read-only access till applikationens EventBus."""
        return self._event_bus

    @property
    def settings_manager(self) -> "SettingsManager":
        """Read-only access till applikationens SettingsManager."""
        return self._settings_manager

    # ──────────────────────────────────────────────────────────
    # Dunder-metoder
    # ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """Debug-representation av pluginen."""
        name   = self.get_name() if self._is_initialized else self.NAME
        status = "initialized" if self._is_initialized else "not initialized"
        subs   = len(self._subscriptions)
        return (
            f"<{self.__class__.__name__}: "
            f"{name} v{self.VERSION} "
            f"({status}, {subs} subscriptions)>"
        )

    def __str__(self) -> str:
        """Läsbar representation."""
        return f"{self.NAME} v{self.VERSION}"