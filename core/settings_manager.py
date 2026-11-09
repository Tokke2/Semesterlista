"""
Inställningshantering – JSON-baserad (SettingsManager).

Detta modul tillhandahåller en central inställningshanterare som
läser och skriver ALLA applikationsinställningar i JSON-format.

UPPDATERAD v2.2.0: Synkad med plugin.py v2.2.0.
                   Tillagt: start_month=0 som default (0=Standard).
                   Tillagt: version bumpat till 2.2.0.
                   Tillagt: DEFAULT_PLUGIN_SETTINGS version→2.2.0.
                   Tillagt: start_month i _merge_plugin_defaults.

Egenskaper:
- Atomär skrivning (temp-fil → rename) förhindrar korrupt data
- Trådsäkert via threading.Lock
- Stöd för punktnotation i nycklar ("window.width", "tabs.visible")
- Automatisk skapande av data/-mapp och standardfiler
- Separat hantering av plugin-specifika inställningar (plugins.json)

Användning:
    from core.settings_manager import SettingsManager

    sm = SettingsManager("/path/to/app")
    theme = sm.get("theme", "system")
    sm.set("theme", "dark")

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
import shutil
from pathlib import Path
from threading import Lock

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.2.0"


class SettingsManager:
    """
    JSON-baserad inställningshanterare.

    Hanterar två filer:
    - settings.json – Huvudinställningar (tema, fönster, tabbar, systray, etc.)
    - plugins.json  – Plugin-specifika inställningar

    All skrivning är atomär: data skrivs först till en .tmp-fil
    som sedan byter namn till målfilen. Detta förhindrar korrupt
    data vid krascher eller strömavbrott.
    """

    # ──────────────────────────────────────────────────────────
    # Standardinställningar (fabriksinställningar)
    # ──────────────────────────────────────────────────────────

    DEFAULT_SETTINGS: Dict[str, Any] = {
        "app_name": "Semesterlista",
        "version": MODULE_VERSION,          # ← synkad automatiskt
        "theme": "system",
        "language": "sv",
        "window": {
            "x": 100,
            "y": 100,
            "width": 1200,
            "height": 800,
            "maximized": False,
            "min_size": {
                "width": 800,
                "height": 600,
            },
        },
        "tabs": {
            "visible": [],
            "hidden": [],
            "order": [],
        },
        "systray": {
            "minimize_to_tray": True,
            "start_minimized": True,
            "show_notifications": True,
            "notification_duration_ms": 3000,
            "close_to_tray": True,
        },
        "plugins": {
            "enabled": [],
            "disabled": [],
            "auto_load": True,
        },
        "advanced": {
            "debug_mode": False,
            "log_to_file": False,
            "log_path": "data/app.log",
            "check_updates": True,
            # Smart cache: rensa rastrerade logotyper när appen avslutas (v2.11.0)
            "clear_cache_on_exit": True,
        },
    }

    # ──────────────────────────────────────────────────────────
    # Standard plugin-inställningar (fabriksinställningar)
    # Används som fallback om plugins.json saknas eller saknar plugin.
    # ──────────────────────────────────────────────────────────

    DEFAULT_PLUGIN_SETTINGS: Dict[str, Any] = {
        "Hyresfakturering": {
            "version": "2.20.1",
            "enabled": True,
            "settings": {
                "year": 2026,
                "last_file": "Hyresgäster.txt",
                # Logotyp i PDF:en (v2.5.0) – relativ till appens assets-mapp
                "logo_svg": "",
                # Storlek i procent (v2.11.0) – 100 = automatisk
                "logo_scale": 100,
            },
        },
        "Semesterlista & Limokörning": {
            "version": "2.20.1",
            "enabled": True,
            "settings": {
                "default_mode": "Semesterlista",
                "auto_open_pdf": True,
                "last_file": "Anställda.txt",
                "months_per_page": 3,
                # Sidlayout (v2.6.0): "Liggande" (standard) eller "Stående"
                "orientation": "Liggande",
                "start_month": 0,
                "logo_svg": "",
                "logo_scale": 100,  # procent, 100 = automatisk storlek (v2.11.0)
                # start_month: 0 = Standard (jan–dec valt år)
                # 1–12 = explicit startmånad
                # Manuellt val kan gå över årsskifte:
                #   year=2026, start_month=12 →
                #   Dec 2026, Jan 2027 ... Nov 2027
            },
        },
        # Egen flik för fordon/limokörning (v2.5.0)
        "Fordon": {
            "version": "2.20.1",
            "enabled": True,
            "settings": {
                "default_mode": "Limokörning",
                "auto_open_pdf": True,
                "last_file": "Fordon.txt",
                "months_per_page": 2,
                "orientation": "Liggande",
                "start_month": 0,
                "logo_svg": "",
                "logo_scale": 100,
            },
        },
    }

    # ──────────────────────────────────────────────────────────
    # Konstruktor
    # ──────────────────────────────────────────────────────────

    def __init__(self, base_path: str):
        """
        Initiera SettingsManager.

        Skapar data/-mappen om den inte finns och laddar
        befintliga inställningar (eller skapar standardfiler).

        Args:
            base_path: Sökväg till applikationens rotmapp
                       (där main.py ligger).
        """
        self._base_path: Path = Path(base_path)
        self._data_path: Path = self._base_path / "data"
        self._lock: Lock = Lock()

        # Säkerställ att data/-mappen finns
        self._data_path.mkdir(parents=True, exist_ok=True)

        # Sökvägar till JSON-filer
        self._settings_file: Path = self._data_path / "settings.json"
        self._plugins_file: Path  = self._data_path / "plugins.json"

        # Ladda inställningar (eller skapa defaults)
        self._settings: Dict[str, Any] = self._load_or_create(
            self._settings_file,
            self.DEFAULT_SETTINGS,
        )
        self._plugins: Dict[str, Any] = self._load_or_create(
            self._plugins_file,
            self.DEFAULT_PLUGIN_SETTINGS,
        )

        # Säkerställ att alla kända plugins har sina default-fält.
        # Merge:ar in nya fält om plugins.json är från äldre version.
        self._merge_plugin_defaults()

    # ──────────────────────────────────────────────────────────
    # Fil-operationer (interna)
    # ──────────────────────────────────────────────────────────

    def _load_or_create(
        self,
        file_path: Path,
        defaults: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Ladda JSON-fil eller skapa med standardvärden.

        Args:
            file_path: Sökväg till JSON-filen.
            defaults:  Standardvärden om filen saknas eller är korrupt.

        Returns:
            Dict: Inlästa inställningar (eller defaults).
        """
        if not file_path.exists():
            self._save_atomic(file_path, defaults)
            return dict(defaults)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Merge:a defaults så att nya fält alltid finns
            merged = dict(defaults)
            merged.update(data)
            # Uppdatera alltid versionsfältet till aktuell version
            if "version" in merged:
                merged["version"] = MODULE_VERSION
            return merged
        except (json.JSONDecodeError, OSError) as e:
            print(f"[SettingsManager] Korrupt JSON-fil '{file_path}': {e}")
            print("[SettingsManager] Återställer till standardinställningar")
            # Skapa backup av korrupt fil
            backup_path = file_path.with_suffix(".json.bak")
            try:
                shutil.copy2(file_path, backup_path)
            except OSError:
                pass
            # Spara defaults
            self._save_atomic(file_path, defaults)
            return dict(defaults)

    def _save_atomic(self, file_path: Path, data: Dict[str, Any]) -> None:
        """
        Spara data atomärt till JSON-fil.

        Skriver först till .tmp-fil, sedan rename. Detta förhindrar
        korrupt data om processen kraschar mitt i skrivningen.

        Args:
            file_path: Sökväg till JSON-filen.
            data:      Data att spara.
        """
        tmp_path = file_path.with_suffix(".json.tmp")
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomär rename (fungerar på alla plattformar)
            tmp_path.replace(file_path)
        except OSError as e:
            print(f"[SettingsManager] Kunde inte spara '{file_path}': {e}")
            # Försök städa temp-filen
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _merge_plugin_defaults(self) -> None:
        """
        Merge:a in standard plugin-inställningar för kända plugins.

        Säkerställer att alla fält i DEFAULT_PLUGIN_SETTINGS finns
        i den laddade plugins.json. Nya fält (t.ex. start_month)
        läggs till om de saknas i en befintlig installation.

        v2.2.0: Hanterar även start_month=0 som korrekt default.
                Kontrollerar att start_month inte är ett ogiltigt
                värde från en äldre version.

        Sparar automatiskt till plugins.json om något ändrades.
        """
        changed = False

        for plugin_name, plugin_defaults in self.DEFAULT_PLUGIN_SETTINGS.items():
            if plugin_name not in self._plugins:
                # Plugin saknas helt – lägg till med defaults
                self._plugins[plugin_name] = dict(plugin_defaults)
                changed = True
                continue

            plugin_entry = self._plugins[plugin_name]

            # Säkerställ att "settings"-nyckeln finns
            if "settings" not in plugin_entry:
                plugin_entry["settings"] = {}
                changed = True

            # Merge:a in saknade settings-fält
            default_settings = plugin_defaults.get("settings", {})
            for key, default_value in default_settings.items():
                if key not in plugin_entry["settings"]:
                    plugin_entry["settings"][key] = default_value
                    changed = True

            # Säkerställ att start_month är ett giltigt heltal (0–12)
            # Kan ha blivit None eller sträng i äldre versioner
            if plugin_name == "Semesterlista & Limokörning":
                sm_val = plugin_entry["settings"].get("start_month", 0)
                if not isinstance(sm_val, int) or sm_val < 0 or sm_val > 12:
                    plugin_entry["settings"]["start_month"] = 0
                    changed = True

            # Uppdatera version-fältet om det är äldre
            if plugin_entry.get("version") != "2.2.0":
                plugin_entry["version"] = "2.2.0"
                changed = True

        if changed:
            self._save_atomic(self._plugins_file, self._plugins)

    # ──────────────────────────────────────────────────────────
    # Publika metoder – Huvudinställningar
    # ──────────────────────────────────────────────────────────

    def load(self, file_name: str) -> Dict[str, Any]:
        """
        Ladda en JSON-fil från data/-mappen.

        Args:
            file_name: Filnamn (t.ex. "settings.json", "plugins.json").

        Returns:
            Dict: Inläst data, eller tom dict vid fel.
        """
        file_path = self._data_path / file_name
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def save(self, file_name: str, data: Dict[str, Any]) -> None:
        """
        Spara data till en JSON-fil i data/-mappen.

        Args:
            file_name: Filnamn (t.ex. "settings.json").
            data:      Data att spara.
        """
        file_path = self._data_path / file_name
        with self._lock:
            self._save_atomic(file_path, data)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Hämta en inställning med punktnotation.

        Stödjer nästlade nycklar:
            sm.get("window.width")
            sm.get("systray.minimize_to_tray")

        Args:
            key:     Inställningsnyckel med valfri punktnotation.
            default: Värde att returnera om nyckeln saknas.

        Returns:
            Det efterfrågade värdet, eller default.

        Exempel:
            width     = sm.get("window.width", 1200)
            start_min = sm.get("systray.start_minimized", True)
        """
        keys = key.split(".")
        value: Any = self._settings

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Sätt en inställning med punktnotation och auto-spara.

        Skapar nästlade dicts vid behov.

        Args:
            key:   Inställningsnyckel med valfri punktnotation.
            value: Värdet att sätta.

        Exempel:
            sm.set("theme", "dark")
            sm.set("window.width", 1400)
        """
        keys = key.split(".")

        with self._lock:
            target: Dict[str, Any] = self._settings
            for k in keys[:-1]:
                if k not in target or not isinstance(target[k], dict):
                    target[k] = {}
                target = target[k]

            target[keys[-1]] = value
            self._save_atomic(self._settings_file, self._settings)

    def get_all(self) -> Dict[str, Any]:
        """
        Returnera ALLA huvudinställningar som dict.

        Returns:
            Dict: Kopia av alla inställningar.
        """
        return dict(self._settings)

    def reset_defaults(self) -> None:
        """
        Återställ ALLA inställningar till fabriksvärden.

        Sparar omedelbart till settings.json och plugins.json.
        """
        with self._lock:
            self._settings = dict(self.DEFAULT_SETTINGS)
            self._plugins  = dict(self.DEFAULT_PLUGIN_SETTINGS)
            self._save_atomic(self._settings_file, self._settings)
            self._save_atomic(self._plugins_file, self._plugins)

    def get_version(self) -> str:
        """
        Returnera modulens versionsnummer.

        Returns:
            str: Versionssträng (t.ex. "2.2.0").
        """
        return MODULE_VERSION

    # ──────────────────────────────────────────────────────────
    # Plugin-inställningar
    # ──────────────────────────────────────────────────────────

    def get_plugin_settings(self, plugin_name: str) -> Dict[str, Any]:
        """
        Hämta inställningar för en specifik plugin från plugins.json.

        Args:
            plugin_name: Unikt plugin-namn (t.ex. "Hyresfakturering").

        Returns:
            Dict: Pluginens inställningar, eller tom dict.

        Exempel:
            settings = sm.get_plugin_settings("Hyresfakturering")
            year = settings.get("year", 2026)

            settings = sm.get_plugin_settings("Semesterlista & Limokörning")
            start_month     = settings.get("start_month", 0)
            months_per_page = settings.get("months_per_page", 3)
            # start_month: 0=standard (jan–dec valt år)
            #              1–12=explicit startmånad
            #              12=December → kan gå till Jan nästa år
        """
        with self._lock:
            plugin_data = self._plugins.get(plugin_name, {})
            if isinstance(plugin_data, dict):
                return plugin_data.get("settings", {})
            return {}

    def save_plugin_settings(
        self,
        plugin_name: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Spara inställningar för en specifik plugin till plugins.json.

        Args:
            plugin_name: Unikt plugin-namn.
            data:        Inställningar att spara.

        Exempel:
            sm.save_plugin_settings("Semesterlista & Limokörning", {
                "default_mode":    "Semesterlista",
                "auto_open_pdf":   True,
                "last_file":       "Anställda.txt",
                "months_per_page": 3,
                "start_month":     12,
                # 12 = December → PDF: Dec 2026, Jan 2027 ... Nov 2027
            })
        """
        with self._lock:
            if plugin_name not in self._plugins:
                self._plugins[plugin_name] = {}

            if not isinstance(self._plugins[plugin_name], dict):
                self._plugins[plugin_name] = {}

            self._plugins[plugin_name]["settings"] = data
            self._plugins[plugin_name]["last_updated"] = (
                __import__("datetime").datetime.now().isoformat()
            )

            self._save_atomic(self._plugins_file, self._plugins)

    def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """
        Hämta all metadata för en plugin (version, enabled, settings, etc.).

        Args:
            plugin_name: Unikt plugin-namn.

        Returns:
            Dict: Plugin-info eller tom dict.
        """
        with self._lock:
            return dict(self._plugins.get(plugin_name, {}))

    def set_plugin_enabled(self, plugin_name: str, enabled: bool) -> None:
        """
        Aktivera eller inaktivera en plugin.

        Args:
            plugin_name: Unikt plugin-namn.
            enabled:     True = aktiverad, False = inaktiverad.
        """
        with self._lock:
            if plugin_name not in self._plugins:
                self._plugins[plugin_name] = {}
            if not isinstance(self._plugins[plugin_name], dict):
                self._plugins[plugin_name] = {}

            self._plugins[plugin_name]["enabled"] = enabled
            self._save_atomic(self._plugins_file, self._plugins)

    def list_plugins(self) -> List[str]:
        """
        Returnera lista över alla kända plugin-namn.

        Returns:
            List[str]: Plugin-namn.
        """
        with self._lock:
            return list(self._plugins.keys())

    def remove_plugin(self, plugin_name: str) -> bool:
        """
        Ta bort en plugins inställningar helt.

        Args:
            plugin_name: Unikt plugin-namn.

        Returns:
            bool: True om pluginen togs bort, False om den inte fanns.
        """
        with self._lock:
            if plugin_name in self._plugins:
                del self._plugins[plugin_name]
                self._save_atomic(self._plugins_file, self._plugins)
                return True
            return False

    # ──────────────────────────────────────────────────────────
    # Bulk-operationer
    # ──────────────────────────────────────────────────────────

    def import_settings(self, data: Dict[str, Any]) -> None:
        """
        Importera och merge:a inställningar från extern dict.

        Args:
            data: Dict med inställningar att merge:a in.
        """
        with self._lock:
            self._settings.update(data)
            self._save_atomic(self._settings_file, self._settings)

    def export_settings(self) -> Dict[str, Any]:
        """
        Exportera ALLA inställningar som dict (för backup/delning).

        Returns:
            Dict: Alla inställningar.
        """
        with self._lock:
            return dict(self._settings)

    # ──────────────────────────────────────────────────────────
    # Hjälpmetoder
    # ──────────────────────────────────────────────────────────

    def _get_nested(self, keys: List[str], default: Any) -> Any:
        """
        Navigera genom nästlade dicts.

        Args:
            keys:    Lista med nycklar (från splittad punktnotation).
            default: Värde att returnera om sökvägen saknas.

        Returns:
            Värdet eller default.
        """
        value: Any = self._settings
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def _set_nested(self, keys: List[str], value: Any) -> None:
        """
        Sätt värde i nästlat dict, skapa mellanliggande nivåer.

        Args:
            keys:  Lista med nycklar.
            value: Värdet att sätta.
        """
        target: Dict[str, Any] = self._settings
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def reload(self) -> None:
        """
        Ladda om inställningar från disk (skriver över minnesbuffert).

        Används efter extern modifiering av JSON-filerna.
        Kör även _merge_plugin_defaults() efter omladdning.
        """
        with self._lock:
            self._settings = self._load_or_create(
                self._settings_file,
                self.DEFAULT_SETTINGS,
            )
            self._plugins = self._load_or_create(
                self._plugins_file,
                self.DEFAULT_PLUGIN_SETTINGS,
            )
        # Kör merge utanför lock – merge tar egna lock internt
        self._merge_plugin_defaults()

    def get_data_path(self) -> str:
        """
        Returnera sökvägen till data/-mappen.

        Returns:
            str: Absolut sökväg.
        """
        return str(self._data_path)

    # ──────────────────────────────────────────────────────────
    # Dunder-metoder
    # ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """Debug-representation."""
        return (
            f"<SettingsManager v{MODULE_VERSION}: "
            f"{len(self._settings)} huvudinställningar, "
            f"{len(self._plugins)} plugins>"
        )

    def __contains__(self, key: str) -> bool:
        """
        Stöd för 'in'-operator: "theme" in settings_manager.

        Args:
            key: Inställningsnyckel (toppnivå).

        Returns:
            bool: True om nyckeln finns.
        """
        return key in self._settings

    def __getitem__(self, key: str) -> Any:
        """
        Stöd för bracket-access: settings_manager["theme"].

        Args:
            key: Inställningsnyckel (toppnivå).

        Returns:
            Värdet.

        Raises:
            KeyError: Om nyckeln saknas.
        """
        if key in self._settings:
            return self._settings[key]
        raise KeyError(f"Inställning '{key}' finns inte")

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Stöd för bracket-assignment: settings_manager["theme"] = "dark".

        Args:
            key:   Inställningsnyckel (toppnivå).
            value: Värde att sätta.
        """
        self.set(key, value)