"""
Kärnmoduler för plugin-systemet.

Detta paket innehåller applikationens kärnmoduler:
- EventBus: Pub/Sub-event-system för plugin-kommunikation
- MainApp: Huvudfönster med UI, tabbar, menyer, teman
- SettingsManager: JSON-baserad inställningshantering
- SingleInstanceLock: Lås för att endast tillåta en instans
- AutostartManager: Autostart med OS (Windows/macOS/Linux)
- SystrayManager: Systemfältshantering (ikon, meny, minimering)
- ThemeManager: Temahantering (endast 3 teman: mörk/ljus/system)

Användning:
    from core import EventBus, SettingsManager
    from core.event_bus import EventBus
    from core.settings_manager import SettingsManager
    from core.single_instance import SingleInstanceLock, AutostartManager
    from core.theme_manager import ThemeManager

copyright Rickard Längkvist 2025 – dynamiskt år
"""

# ──────────────────────────────────────────────────────────
# Publika exporter – dessa klasser är tillgängliga via
# `from core import X`
# ──────────────────────────────────────────────────────────

__all__ = [
    # Event-system
    "EventBus",

    # Huvudapplikation
    "MainApp",

    # Inställningar
    "SettingsManager",

    # Single-instance + Autostart
    "SingleInstanceLock",
    "AutostartManager",
    "check_single_instance",
    "send_to_existing",

    # Systemfält
    "SystrayManager",

    # Teman
    "ThemeManager",
]

# ──────────────────────────────────────────────────────────
# Lazy imports – moduler laddas först när de behövs.
# Förhindrar cirkulära importer och snabbar upp start.
# ──────────────────────────────────────────────────────────

def __getattr__(name: str):
    """
    Lazy loading av core-moduler.

    Moduler importeras först när de faktiskt efterfrågas,
    vilket förhindrar cirkulära beroenden och påskyndar start.

    Args:
        name: Namn på klassen/funktionen som efterfrågas.

    Returns:
        Den efterfrågade klassen/funktionen.

    Raises:
        AttributeError: Om namnet inte finns i core-paketet.
    """
    _import_map = {
        # Event-system
        "EventBus":              "core.event_bus",

        # Huvudapplikation
        "MainApp":               "core.app",

        # Inställningar
        "SettingsManager":       "core.settings_manager",

        # Single-instance + Autostart (v2.2.0)
        "SingleInstanceLock":    "core.single_instance",
        "AutostartManager":      "core.single_instance",
        "check_single_instance": "core.single_instance",
        "send_to_existing":      "core.single_instance",

        # Systemfält
        "SystrayManager":        "core.systray_manager",

        # Teman
        "ThemeManager":          "core.theme_manager",
    }

    if name in _import_map:
        import importlib
        module = importlib.import_module(_import_map[name])
        return getattr(module, name)

    raise AttributeError(f"module 'core' has no attribute '{name}'")


# ──────────────────────────────────────────────────────────
# Paket-metadata
# ──────────────────────────────────────────────────────────

__version__     = "2.2.0"
__author__      = "Rickard Längkvist"
__description__ = "Kärnmoduler för plugin-baserad desktopapplikation"