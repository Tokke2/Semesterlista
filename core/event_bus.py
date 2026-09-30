"""
Event-system för kommunikation mellan plugins och app-kärna.

Detta modul tillhandahåller ett Pub/Sub-event-system (EventBus) som används
av både applikationskärnan och alla plugins för att kommunicera utan att
vara direkt beroende av varandra.

UPPDATERAD v2.2.0: Synkad med plugin.py v2.2.0, settings_manager.py v2.2.0,
                   single_instance.py v2.2.0 och theme_manager.py v2.2.0.
                   Tillagt: logging istället för print vid callback-fel.
                   Tillagt: emit_count exponeras via __repr__.

Användning:
    from core.event_bus import EventBus

    bus = EventBus()

    # Prenumerera
    bus.on("semesterlista:pdf_generated", lambda data: print(data))

    # Emittera
    bus.emit("semesterlista:pdf_generated", {
        "filename": "semesterlista_2026.pdf",
        "year": 2026,
        "mode": "Semesterlista",
        "items_count": 12,
        "months_per_page": 3,
        "start_month": 0,
    })

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Any, Optional
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.2.0"


class EventBus:
    """
    Pub/Sub event-system.

    Plugins kan prenumerera på och emittera events. Systemet är trådsäkert
    och stödjer både permanenta och engångs-prenumerationer.

    Egenskaper:
    - Trådsäkert via threading.Lock
    - Typade callbacks (Callable)
    - Engångs-prenumerationer (once)
    - Felhantering i callbacks (logging, ej crash)
    - Debug-stöd (subscriber_count, has_subscribers, emit-statistik)

    Standard-events i applikationen:
        "app:started"           → Appen startad
        "app:shutting_down"     → Appen stängs
        "theme:changed"         → {"theme": "dark|light|system"}
        "tab:shown"             → {"name": "plugin_id"}
        "tab:hidden"            → {"name": "plugin_id"}
        "plugin:loaded"         → {"name": "...", "version": "..."}
        "plugin:unloaded"       → {"name": "..."}
        "plugin:error"          → {"name": "...", "error": "..."}
        "window:shown"          → Fönstret visas
        "window:hidden"         → Fönstret döljs
        "settings:changed"      → {"key": "...", "value": "..."}

    Plugin-specifika events:
        "semesterlista:pdf_generated"    → {filename, year, mode,
                                            items_count, months_per_page,
                                            start_month, range_label,
                                            spans_year_boundary}
        "semesterlista:settings_changed" → {settings dict}
        "semesterlista:view_shown"       → {mode}
        "semesterlista:folder_opened"    → {path}
        "hyresfakturering:pdf_generated" → {filename, year}
        "hyresfakturering:file_opened"   → {path}
        "hyresfakturering:data_reloaded" → {}
    """

    def __init__(self):
        """Initierar EventBus med tomma prenumerationslistor och lås."""
        self._subscribers:      Dict[str, List[Callable]] = defaultdict(list)
        self._once_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock:             Lock                       = Lock()
        self._emit_count:       Dict[str, int]            = defaultdict(int)

    # ──────────────────────────────────────────────────────────
    # Prenumeration
    # ──────────────────────────────────────────────────────────

    def on(self, event_name: str, callback: Callable) -> None:
        """
        Prenumerera på ett event (permanent).

        Callbacken anropas varje gång eventet emitteras tills
        prenumerationen avslutas via off().

        Args:
            event_name: Namn på eventet (t.ex. "semesterlista:pdf_generated").
                        Namnkonvention: "domän:händelse".
            callback:   Funktion som anropas när eventet inträffar.
                        Signatur: callback(data: Any) → None

        Exempel:
            bus.on("app:shutting_down", self._on_shutdown)
            bus.on("theme:changed", self._on_theme_changed)
        """
        with self._lock:
            self._subscribers[event_name].append(callback)

    def once(self, event_name: str, callback: Callable) -> None:
        """
        Prenumerera på ett event en enda gång.

        Callbacken tas automatiskt bort efter första anropet.

        Args:
            event_name: Namn på eventet.
            callback:   Funktion som anropas en gång vid nästa emit.

        Exempel:
            bus.once("app:started", self._on_first_start)
        """
        with self._lock:
            self._once_subscribers[event_name].append(callback)

    def off(
        self,
        event_name: str,
        callback: Optional[Callable] = None,
    ) -> None:
        """
        Avsluta prenumeration på ett event.

        Args:
            event_name: Namn på eventet.
            callback:   Specifik callback att ta bort.
                        Om None → ALLA prenumerationer på eventet tas bort.

        Exempel:
            bus.off("theme:changed")                  # Ta bort alla
            bus.off("theme:changed", self._handler)   # Ta bort specifik
        """
        with self._lock:
            if callback is None:
                self._subscribers[event_name].clear()
                self._once_subscribers[event_name].clear()
            else:
                subs = self._subscribers[event_name]
                if callback in subs:
                    subs.remove(callback)
                once_subs = self._once_subscribers[event_name]
                if callback in once_subs:
                    once_subs.remove(callback)

    # ──────────────────────────────────────────────────────────
    # Emittering
    # ──────────────────────────────────────────────────────────

    def emit(self, event_name: str, data: Any = None) -> None:
        """
        Emittera ett event till alla prenumeranter.

        Alla permanenta och engångs-prenumeranter anropas i ordning.
        Engångs-prenumeranter tas bort efter anrop.
        Callback-undantag loggas men kraschar INTE applikationen.

        Args:
            event_name: Namn på eventet att emittera.
            data:       Data att skicka med eventet (valfritt, Any).

        Exempel:
            bus.emit("app:shutting_down")
            bus.emit("theme:changed", {"theme": "dark"})
            bus.emit("semesterlista:pdf_generated", {
                "filename":             "semesterlista_2026.pdf",
                "year":                 2026,
                "mode":                 "Semesterlista",
                "items_count":          12,
                "months_per_page":      3,
                "start_month":          0,
                "range_label":          "2026",
                "spans_year_boundary":  False,
            })
        """
        # Kopiera listor under lås för att undvika race conditions
        with self._lock:
            subscribers      = self._subscribers[event_name].copy()
            once_subscribers = self._once_subscribers[event_name].copy()
            # Töm engångslistan omedelbart
            self._once_subscribers[event_name].clear()

        # Räkna emits per event (statistik)
        self._emit_count[event_name] += 1

        # Anropa permanenta prenumeranter
        for callback in subscribers:
            try:
                callback(data)
            except Exception as e:
                logger.error(
                    f"[EventBus] Callback-fel vid event '{event_name}': {e}",
                    exc_info=True,
                )

        # Anropa engångs-prenumeranter
        for callback in once_subscribers:
            try:
                callback(data)
            except Exception as e:
                logger.error(
                    f"[EventBus] Once-callback-fel vid event '{event_name}': {e}",
                    exc_info=True,
                )

    # ──────────────────────────────────────────────────────────
    # Information & Debug
    # ──────────────────────────────────────────────────────────

    def get_subscribers(self, event_name: str) -> List[Callable]:
        """
        Returnera kopia av listan med permanenta prenumeranter.

        Args:
            event_name: Namn på eventet.

        Returns:
            List[Callable]: Kopia av prenumerationslistan.
        """
        with self._lock:
            return self._subscribers[event_name].copy()

    def has_subscribers(self, event_name: str) -> bool:
        """
        Kolla om ett event har prenumeranter.

        Args:
            event_name: Namn på eventet.

        Returns:
            bool: True om minst en prenumerant finns.
        """
        with self._lock:
            return (
                len(self._subscribers[event_name]) > 0
                or len(self._once_subscribers[event_name]) > 0
            )

    def subscriber_count(self, event_name: str) -> int:
        """
        Returnera totala antalet prenumeranter för ett event.

        Args:
            event_name: Namn på eventet.

        Returns:
            int: Antal prenumeranter (permanenta + engångs).
        """
        with self._lock:
            return (
                len(self._subscribers[event_name])
                + len(self._once_subscribers[event_name])
            )

    def get_emit_count(self, event_name: str) -> int:
        """
        Returnera antalet gånger ett event har emitterats.

        Args:
            event_name: Namn på eventet.

        Returns:
            int: Antal emits sedan EventBus skapades.
        """
        return self._emit_count.get(event_name, 0)

    def list_all_events(self) -> List[str]:
        """
        Returnera sorterad lista över alla registrerade event-namn.

        Returns:
            List[str]: Alla event-namn med minst en prenumerant.
        """
        with self._lock:
            all_events = (
                set(self._subscribers.keys())
                | set(self._once_subscribers.keys())
            )
            return sorted(all_events)

    def clear_all(self) -> None:
        """
        Rensa ALLA prenumerationer och emit-statistik.

        Används vid nedstängning av applikationen.
        """
        with self._lock:
            self._subscribers.clear()
            self._once_subscribers.clear()
            self._emit_count.clear()

    # ──────────────────────────────────────────────────────────
    # Dunder-metoder
    # ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """Debug-representation av EventBus."""
        total_subs  = sum(len(v) for v in self._subscribers.values())
        total_once  = sum(len(v) for v in self._once_subscribers.values())
        total_emits = sum(self._emit_count.values())
        total_events = len(
            set(self._subscribers.keys())
            | set(self._once_subscribers.keys())
        )
        return (
            f"<EventBus v{MODULE_VERSION}: "
            f"{total_events} events, "
            f"{total_subs} permanent, "
            f"{total_once} once, "
            f"{total_emits} total emits>"
        )