# Semesterlista

<!--
═══════════════════════════════════════════════════════════════════════════════
║  SPECIFIKATION – Plugin-baserad Desktop App med Modern UI & Systray        ║
║  Version: 2.11.0                                                            ║
║  Datum: 2026-11-03                                                          ║
║  Python: 3.12+                                                              ║
║  UI-ramverk: PySide6 (Qt for Python)                                        ║
║  Copyright: Rickard Längkvist 2025 – dynamiskt år                          ║
═══════════════════════════════════════════════════════════════════════════════
-->

# 📋 SPECIFIKATION

## Projekt: Semesterlista – Plugin-baserad Desktop App med Modern UI, Systray & Event-System

---

## INNEHÅLLSFÖRTECKNING

1.  Programmets Syfte & Övergripande Mål
2.  Mappstruktur (Fullständig – Faktisk)
3.  Teknisk Översikt – Teknikval & Beroenden
4.  Alla Filer – Funktioner, Importer & Ansvar (Detaljerad)
    - 4.1  main.py
    - 4.2  core/__init__.py
    - 4.3  core/event_bus.py
    - 4.4  core/settings_manager.py
    - 4.5  core/single_instance.py
    - 4.6  core/theme_manager.py
    - 4.7  core/plugin_base.py (brygga)
    - 4.8  plugins/__init__.py
    - 4.9  plugins/base_plugin.py
    - 4.10 plugins/hyra/__init__.py
    - 4.11 plugins/hyra/plugin.py
    - 4.12 plugins/lista/__init__.py
    - 4.13 plugins/lista/plugin.py
    - 4.14 core/roster.py
    - 4.15 core/list_editor_dialog.py
    - 4.16 core/pdf_assets.py
    - 4.17 plugins/fordon/plugin.py
    - 4.18 core/app_icon.py
    - 4.19 core/logging_setup.py
    - 4.20 core/settings_dialog.py
    - 4.21 core/updater.py
    - 4.22 core/logo_picker.py
5.  Detaljerad Funktionalitet
6.  Temahantering (Endast 3 Teman)
7.  Tabbar – Visa/Dölj (Dynamiskt)
8.  Single-Instance-Lock
9.  Systray & Minimering
10. Event-System (EventBus)
11. Inställningar – JSON-Struktur
12. Färgkodning av Dagar – Exakt Definition
13. Manuellt Val av Startmånad & Årsskifte
14. Autostart med OS
15. Sammanfattning – Vad Har Gjorts
16. Vad Som Är Kvar Att Göra
17. Checklista (50 Punkter)
18. Kända Fel/Buggar & Åtgärdsplan
19. Framtidsplan
20. Hantering av Listor – Anställda, Fordon & Hyresgäster (v2.4.0)
22. Loggning & Felsökning (v2.8.0)
23. Uppdatering från GitHub (v2.9.0)
21. Flikar & Logotyp i PDF (v2.5.0)
24. Logotyp-Dropdown & Automatisk Storlek (v2.10.0)
25. Smart Cache (v2.11.0)
26. Lediga dagar i listfilen (v2.11.0)

---

## 1. PROGRAMMETS SYFTE & ÖVERGRIPANDE MÅL

<!--
Plugin-baserad desktopapplikation byggd i Python för hantering av
semesterlistor, limokörningsscheman och hyresfakturering.
-->

| Egenskap                  | Beskrivning                                                                                                      |
|---------------------------|------------------------------------------------------------------------------------------------------------------|
| Plugin-arkitektur         | Kärna (core/) + fristående plugins (plugins/hyra/, plugins/lista/) via pub/sub EventBus                          |
| Modern UI                 | PySide6, dynamiskt anpassat för alla fönsterstorlekar/skärmar                                                    |
| Endast 3 Teman            | Mörkt, Ljust, System – inga andra                                                                                |
| Tydliga knappar/tabbar    | Ljust tema → mörkgrå knappar (#3D3D3D) med VIT FET text. Mörkt → ljusgrå (#E8E8E8) med SVART FET text         |
| Inverterade knappar       | Knappar/tabbar inverteras alltid mot bakgrunden för maximal synlighet                                            |
| Dynamiska tabbar          | Visa/dölj individuellt via "Visa"-meny, högerklick på tabb för att dölja                                        |
| Scroll via mushjul        | Alla vyer + QTabBar (horisontell scroll)                                                                         |
| Single-instance-lock      | Endast en instans. Vid dubbelstart → befintlig instans visas (bring-to-front)                                    |
| Alltid minimerad start    | Startar i systemfältet, utan terminalfönster (även .py)                                                          |
| Systray-ikon              | Programmatiskt skapad (64×64 blå rundad "S"), öppna via enkelklick                                              |
| JSON-inställningar        | Alla inställningar i JSON-filer. Ingen databas                                                                   |
| Ingen profilhantering     | App-till-app kommunikation. Användaren säger till om det behövs                                                  |
| PDF månader per blad      | Val av 2 eller 3 månader per blad vid generering. Alltid centrerat på liggande A4                               |
| Manuell startmånad        | Dropdown: Standard=jan–dec valt år. Manuellt val=12 mån från vald månad, kan gå över årsskifte (Dec→Jan)        |
| Korrekt färgkodning       | Röda=officiella helgdagar+söndagar. Gröna=halvdagar (inkl. midsommarafton). Blå=lördagar                        |
| Autostart med OS          | Arkiv → Autostart vid inloggning (checkable). Windows/macOS/Linux plattformsspecifikt                           |
| Dynamiskt copyright-år    | © {datetime.now().year} Rickard Längkvist – uppdateras automatiskt                                              |
| Listhantering             | Anställda/fordon/hyresgäster redigeras i appen. Kommentarer, cp1252-fallback, dubblettkontroll, backup och atomär skrivning |

---

## 2. MAPPSTRUKTUR (Fullständig – Faktisk)

<!--
Komplett mappstruktur för projektet.
-->
Semesterlista/ ← Rotmapp
│
├── main.py ← Entry point (PySide6)
├── main.pyw ← Windows no-console variant
├── config.json ← Rot-config
│
├── core/ ← Applikationskärna
│ ├── init.py ← Lazy loading, exporter
│ ├── event_bus.py ← Pub/Sub-event-system
│ ├── settings_manager.py ← JSON-inställningshantering
│ ├── single_instance.py ← Single-instance-lock + AutostartManager
│ ├── theme_manager.py ← 3 teman + QSS-generator
│ ├── roster.py ← Listor: anställda/fordon/hyresgäster ← NY v2.4.0
│ ├── list_editor_dialog.py ← Redigera listorna i appen ← NY v2.4.0
│ ├── pdf_assets.py ← Logotyper från assets/ till PDF ← NY v2.5.0
│ ├── logo_picker.py ← Dropdown för logotypen i vyerna ← NY v2.10.0
│ ├── cache.py ← Smart cache som städas vid avslut ← NY v2.11.0
│ ├── version.py ← Versionen på ett ställe ← NY v2.11.0
│ ├── window_state.py ← Fönstret hålls inom skärmen ← NY v2.11.0
│ ├── app_icon.py ← Appikonen (fönster/tray/aktivitetsfält) ← NY v2.7.0
│ ├── logging_setup.py ← Detaljerad loggning + felhakar ← NY v2.8.0
│ ├── settings_dialog.py ← Inställningar (4 flikar) ← NY v2.8.0
│ ├── updater.py ← Uppdatering från GitHub Releases ← NY v2.9.0
│ └── plugin_base.py ← Bakåtkompatibel brygga
│
├── plugins/ ← Plugin-katalog
│ ├── init.py ← Lazy loading, BasePlugin-export
│ ├── base_plugin.py ← Abstrakt basklass (ABC)
│ ├── hyra/ ← Hyresfakturering
│ │ ├── init.py
│ │ └── plugin.py ← Hyreslista-PDF
│ ├── lista/ ← Semesterlista
│ │ ├── init.py
│ │ └── plugin.py ← Semesterlista-PDF
│ └── fordon/ ← Fordon (limokörning) ← NY v2.5.0
│   ├── init.py
│   └── plugin.py ← Ärver lista-pluginets vy, låst läge
│
├── data/ ← JSON-datafiler
│ ├── settings.json ← Huvudinställningar
│ ├── plugins.json ← Plugin-inställningar
│ ├── loggar/   ← Loggar (v2.12.0): app.log, fel.log, arkiv/
│ └── crash.log ← Hårda krascher via faulthandler ← NY v2.8.0
│
├── Anställda.txt ← Indata: anställda (skapas vid behov)
├── Fordon.txt ← Indata: fordon (skapas vid behov)
├── Hyresgäster.txt ← Indata: hyresgäster (skapas vid behov)
│
├── assets/ ← Bilder: ikon + logotyper ← NY v2.5.0
│ ├── README.md ← Så används bilderna
│ ├── ikon/ ← Appikon (fönster, tray, aktivitetsfält) ← NY v2.7.0
│ │ ├── appikon.svg
│ │ ├── appikon-16…256.png
│ │ └── appikon.ico
│ └── logotyper/ ← Egna undermappar läses rekursivt
│   └── exempel-logotyp.svg
│
├── tools/ ← Hjälpskript ← NY v2.7.0
│ └── make_icons.py ← Bygger om PNG/ICO från appikon.svg
│
├── tests/ ← Enhetstester (unittest) ← NY v2.4.0
│ ├── test_roster.py ← Listor, format, validering, skrivning
│ ├── test_pdf_assets.py ← Logotyper, skalning, PDF-ritning
│ ├── test_pdf_layout.py ← Sidlayout & månader per blad
│ ├── test_app_icon.py ← Appikonen (SVG/PNG/ICO)
│ ├── test_logging_setup.py ← Loggning, rotering, felhakar ← NY v2.8.0
│ ├── test_settings_dialog.py ← Inställningsdialogen ← NY v2.8.0
│ ├── test_hyra_view.py ← Årbytet i Hyra-fliken ← NY v2.8.1
│ └── test_updater.py ← Uppdatering från GitHub ← NY v2.9.0
├── requirements.txt ← Python-beroenden
└── spec.md ← Denna fil

text


---

## 3. TEKNISK ÖVERSIKT – TEKNIKVAL & BEROENDEN

<!--
Alla tekniska val och beroenden listade.
-->

| Komponent        | Teknik/Modul                             | Beskrivning                              |
|------------------|------------------------------------------|------------------------------------------|
| UI-ramverk       | PySide6                                  | Qt for Python                            |
| Systemfält       | PySide6.QtWidgets.QSystemTrayIcon        | Systray                                  |
| Teman            | QSS + QPalette                           | 3 teman (dark/light/system)              |
| Inställningar    | json                                     | Allt i JSON, atomär skrivning            |
| Kommunikation    | EventBus (Pub/Sub)                       | Plugin ↔ Kärna, trådsäkert              |
| Single-instance  | QSharedMemory + QLocalServer             | Lås + bring-to-front                     |
| Autostart        | AutostartManager                         | Windows/macOS/Linux OS-autostart         |
| PDF-generering   | reportlab                                | Semesterlistor, limokörning, hyra        |
| Helgdagar        | get_swedish_holidays() (intern)          | Svenska helgdagar, egen implementation   |
| Trådsäkerhet     | threading.Lock                           | EventBus + SettingsManager               |
| Loggning         | logging + RotatingFileHandler            | data/loggar/app.log, 2 MB × 5, INFO/DEBUG |
| Kraschlogg       | faulthandler                             | data/crash.log (hårda fel)               |
| Uppdatering      | urllib + zipfile (stdlib)                | GitHub Releases API, zipball             |
| Python-version   | 3.12+                                    |                                          |
| Plattformar      | Windows, macOS, Linux                    |                                          |

<!--
requirements.txt innehåll:
  PySide6>=6.7.0
  reportlab>=4.0
-->

---

## 4. ALLA FILER – FUNKTIONER, IMPORTER & ANSVAR

<!--
EXTREMT DETALJERAT – klistra in i ny chatt för att se vad som ska matchas.
Varje fils exakta importer, funktioner och ansvar listas.
Alla filer i samma mapp uppdateras innan nästa mapp påbörjas.
-->

---

### 4.1 `main.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    main.py / main.pyw                                   │
│ ANSVAR: Entry point. Startar minimerat i systray.            │
│         Inget terminalfönster. All UI via PySide6.           │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~650                                                 │
└──────────────────────────────────────────────────────────────┘

KONSTANTER:
  APP_VERSION:    str = "2.2.0"       ← En enda källa, används överallt
  COPYRIGHT_YEAR: str = str(datetime.now().year)  ← Dynamiskt år

IMPORTER:
  Standard:      sys, os, ctypes, importlib, importlib.util, json,
                 logging, pathlib.Path, datetime.datetime,
                 typing (Dict, List, Any, Optional, TYPE_CHECKING)
  PySide6.QtWidgets:
                 QApplication, QMainWindow, QTabWidget, QTabBar,
                 QMenu, QMenuBar, QWidget, QVBoxLayout, QHBoxLayout,
                 QStatusBar, QLabel, QPushButton, QMessageBox,
                 QSizePolicy, QFrame, QSystemTrayIcon
  PySide6.QtCore:
                 Qt, QEvent, QTimer, QSize, Signal, Slot
  PySide6.QtGui:
                 QAction, QActionGroup, QIcon, QFont, QPalette,
                 QColor, QMouseEvent, QWheelEvent, QKeySequence,
                 QShortcut, QPainter, QPixmap
  Kärnmoduler:   core.event_bus.EventBus
                 core.settings_manager.SettingsManager
                 core.theme_manager.ThemeManager
                 core.single_instance.SingleInstanceLock, AutostartManager
                 plugins.base_plugin.BasePlugin

FUNKTIONER (modulnivå):
  hide_console_window()
    → Döljer terminalfönster på Windows (ctypes.windll)

  main()
    → 13 steg:
        1.  hide_console_window()
        2.  SingleInstanceLock – kolla + send_to_existing + exit
        3.  QApplication + setHighDpiScaleFactorRoundingPolicy
        4.  SettingsManager
        5.  EventBus
        6.  ThemeManager (applicerar sparat tema)
        7.  PluginManager discover + load + initialize_all
        8.  MainWindow (visas EJ – startar minimerat)
        9.  _apply_theme() kopplas till theme_changed-signal
        10. lock.instance_started → main_window.show_application
        11. SystrayManager
        12. Synk autostart från settings
        13. event_bus.emit("app:started") + systray-notifikation
        14. app.exec() → sys.exit(exit_code)

KLASSER:

  PluginManager:
    __init__(event_bus, settings_manager)
    discover_plugins(plugins_dir) → List[Dict]
      → Skannar plugins/-mappen efter undermappar med plugin.py
      → Ignorerar mappar som börjar med _
    load_plugin(plugin_info) → bool
      → Dynamisk import, hittar Plugin-klass, ärver BasePlugin,
        instantierar, sparar i self.plugins
    initialize_all()
      → Anropar plugin.initialize() för alla laddade plugins
    shutdown_all()
      → Omvänd ordning, anropar plugin.shutdown()
    get_plugin(name) → Optional[BasePlugin]
    get_all_plugins() → Dict[str, BasePlugin]
    get_plugin_order() → List[str]

  MainWindow(QMainWindow):
    window_shown = Signal()
    __init__(app, event_bus, settings_manager, theme_manager,
             plugin_manager, lock)   ← lock=SingleInstanceLock (v2.2.0)
    _init_ui()
      → Central widget, QTabWidget (movable, scroll-buttons),
        QStatusBar, installerar eventFilter på QTabBar
    _init_menu_bar()
      → Arkiv:
          Inställningar...
          Autostart vid inloggning (checkable QAction)  ← NY v2.2.0
          ─────────────────
          Avsluta  Ctrl+Q
        Visa (dynamisk – fylls av _register_tab)
        Utseende (dark/light/system – QActionGroup exclusive)
        Hjälp (Om)
    _load_plugin_tabs()
      → Itererar plugin_order, anropar plugin.get_tab_widget(),
        registrerar varje tabb
    _register_tab(widget, tab_name, plugin_id)
      → Lägger till i QTabWidget + checkable QAction i Visa-meny
    _toggle_tab(plugin_id, visible)
    _show_tab(plugin_id) → återlägger tabb, uppdaterar meny
    _hide_tab(plugin_id) → tar bort tabb, uppdaterar meny
    _on_tab_context_menu(pos)
      → Högerklick: "Dölj [namn]" + "Visa alla dolda tabbar"
    _on_tab_changed(index) → uppdaterar statusrad
    _on_theme_action(theme) → ThemeManager.set_theme()
    _on_autostart_toggle() [Slot]  ← NY v2.2.0
      → lock.set_autostart(enabled)
      → settings_manager.set("advanced.autostart", enabled)
      → QMessageBox.warning vid fel
    _on_settings_changed(data)  ← NY v2.2.0
      → Synkar autostart-checkmark om inställningen ändras externt
    _save_window_state() → SettingsManager.set(window.*)
    _restore_window_state() → SettingsManager.get(window.*)
    eventFilter(obj, event)
      → Fångar QEvent.Wheel på QTabBar → horisontell tabb-scroll
    closeEvent(event)
      → Om close_to_tray=True: ignorera + hide()
        Annars: _quit_application()
    show_application() → show() + raise_() + activateWindow()
    hide_application() → hide()
    set_status(message) → statusrad
    _quit_application()
      → _save_window_state → emit app:shutting_down →
        shutdown_all → save tabs.order → QApplication.quit()
    _open_settings()
      → QMessageBox med data-path, tema, autostart-status och -info
    _show_about()
      → QMessageBox.about med APP_VERSION + COPYRIGHT_YEAR (dynamiskt)
    _on_plugin_loaded(data) → skapar tabb om ej redan registrerad

  SystrayManager:
    __init__(app, main_window)
      → Skapar QPixmap (64×64, blå rundad fyrkant med "S"),
        QPainter.RenderHint.Antialiasing för skarpare ikon,
        QSystemTrayIcon, tray-meny (Visa/Dölj/Avsluta),
        tooltip = f"Semesterlista v{APP_VERSION}"
    _on_tray_activated(reason)
      → Trigger (vänsterklick) = toggla visa/dölj
    show_notification(title, message, duration_ms)
-->

---

### 4.2 `core/__init__.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    core/__init__.py                                     │
│ ANSVAR: Gör core/ till Python-paket med lazy loading.        │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~90                                                  │
└──────────────────────────────────────────────────────────────┘

IMPORTER: importlib

FUNKTIONER:
  __getattr__(name: str)
    → Lazy loading via _import_map
    → Förhindrar cirkulära importer

VARIABLER:
  __all__ = ["EventBus", "MainApp", "SettingsManager",
             "SingleInstanceLock", "AutostartManager",
             "check_single_instance", "send_to_existing",
             "SystrayManager", "ThemeManager"]
  __version__     = "2.2.0"
  __author__      = "Rickard Längkvist"
  __description__ = "Kärnmoduler för plugin-baserad desktopapplikation"
  _import_map: Dict[str, str]
    → "EventBus"              → "core.event_bus"
    → "SettingsManager"       → "core.settings_manager"
    → "SingleInstanceLock"    → "core.single_instance"
    → "AutostartManager"      → "core.single_instance"   ← NY v2.2.0
    → "check_single_instance" → "core.single_instance"
    → "send_to_existing"      → "core.single_instance"
    → "ThemeManager"          → "core.theme_manager"
-->

---

### 4.3 `core/event_bus.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    core/event_bus.py                                    │
│ ANSVAR: Pub/Sub-event-system. Trådsäkert.                    │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~260                                                 │
│ MODULE_VERSION = "2.2.0"                                     │
└──────────────────────────────────────────────────────────────┘

IMPORTER:
  logging
  typing:      Callable, Dict, List, Any, Optional
  collections: defaultdict
  threading:   Lock

KONSTANTER:
  MODULE_VERSION: str = "2.2.0"

KLASS: EventBus – 11 metoder
  __init__(self)
    → self._subscribers: defaultdict(list)
    → self._once_subscribers: defaultdict(list)
    → self._emit_count: defaultdict(int)
    → self._lock: Lock

  on(event_name, callback) → None      → Prenumerera (beständig)
  once(event_name, callback) → None    → Prenumerera (en gång)
  off(event_name, callback=None) → None → Avprenumerera
  emit(event_name, data=None) → None
    → Anropar alla prenumeranter (logger.error per callback)
    → Räknar emit-anrop, trådsäkert via Lock
  get_subscribers(event_name) → List[Callable]
  has_subscribers(event_name) → bool
  subscriber_count(event_name) → int
  get_emit_count(event_name) → int
  list_all_events() → List[str]
  clear_all() → None
  __repr__() → inkluderar MODULE_VERSION + total_emits
-->

---

### 4.4 `core/settings_manager.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    core/settings_manager.py                             │
│ ANSVAR: JSON-baserad inställningshantering.                  │
│         Atomär skrivning, trådsäkert, punktnotation.         │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~580                                                 │
│ MODULE_VERSION = "2.2.0"                                     │
└──────────────────────────────────────────────────────────────┘

IMPORTER:
  json, os, shutil
  pathlib: Path
  threading: Lock
  typing: Any, Dict, List, Optional, Union

KONSTANTER:
  MODULE_VERSION: str = "2.2.0"

KLASS: SettingsManager – 22+ metoder

  DEFAULT_SETTINGS: Dict
    → app_name, version (MODULE_VERSION), theme, language,
      window{x,y,width,height,maximized,min_size},
      tabs{visible,hidden,order},
      systray{minimize_to_tray,start_minimized,show_notifications,
              notification_duration_ms,close_to_tray},
      plugins{enabled,disabled,auto_load},
      advanced{debug_mode,log_to_file,log_path,check_updates,
               autostart}   ← NY v2.2.0

  DEFAULT_PLUGIN_SETTINGS: Dict  ← NY v2.2.0
    → "Hyresfakturering": {version, enabled, settings{year, last_file}}
    → "Semesterlista & Limokörning": {version, enabled,
        settings{default_mode, auto_open_pdf, last_file,
                 months_per_page, start_month}}

  __init__(base_path)
    → Skapar data/-mapp
    → Laddar settings.json + plugins.json
    → Anropar _merge_plugin_defaults()  ← NY v2.2.0

  _load_or_create(file_path, defaults) → Dict
    → Merge:ar defaults + uppdaterar version till MODULE_VERSION
  _save_atomic(file_path, data)
    → Skriver till .tmp → rename (atomärt)
  _merge_plugin_defaults() → NY v2.2.0
    → Säkerställer att alla fält i DEFAULT_PLUGIN_SETTINGS finns
    → Lägger till saknade fält (t.ex. start_month) i befintliga filer
    → Validerar start_month (0–12) för lista-plugin
    → Uppdaterar version-fält till "2.2.0"
    → Sparar om något ändrades

  load(file_name) → Dict
  save(file_name, data)
  get(key, default=None) → Any     → Punktnotation
  set(key, value) → auto-spara
  get_all() → Dict
  reset_defaults()
    → Återställer BÅDE settings.json OCH plugins.json
  get_version() → str

  get_plugin_settings(plugin_name) → Dict
  save_plugin_settings(plugin_name, data)
    → Sparar + sätter last_updated timestamp
  get_plugin_info(plugin_name) → Dict
  set_plugin_enabled(plugin_name, enabled)
  list_plugins() → List[str]
  remove_plugin(plugin_name) → bool

  import_settings(data) / export_settings() → Dict
  _get_nested(keys, default) / _set_nested(keys, value)
  reload()
    → Laddar om från disk + _merge_plugin_defaults()
  get_data_path() → str

  __repr__() → inkluderar MODULE_VERSION
  __contains__(key) / __getitem__(key) / __setitem__(key, value)
-->

---

### 4.5 `core/single_instance.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    core/single_instance.py                              │
│ ANSVAR: Single-instance-lock + bring-to-front.              │
│         AutostartManager – OS-autostart. (NY v2.2.0)        │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~700                                                 │
│ MODULE_VERSION = "2.2.0"                                     │
└──────────────────────────────────────────────────────────────┘

IMPORTER:
  sys, os, socket, hashlib, platform, subprocess
  pathlib: Path
  typing: Optional, TYPE_CHECKING
  PySide6.QtCore: QObject, Signal, Slot, QSharedMemory
  PySide6.QtNetwork: QLocalServer, QLocalSocket

KONSTANTER:
  MODULE_VERSION: str = "2.2.0"
  AUTOSTART_APP_NAME:    str = "Semesterlista"
  AUTOSTART_MACOS_PLIST: str = "com.semesterlista.plist"
  AUTOSTART_LINUX_FILE:  str = "semesterlista.desktop"
  AUTOSTART_WIN_REG_KEY: str = r"Software\Microsoft\...\Run"
  _HAS_SHARED_MEMORY: bool (try/except import)

HJÄLPFUNKTIONER (modulnivå):
  _get_app_key(app_name) → str        → MD5-hash
  _get_lock_file_path(app_name) → Path
  _find_available_port(start, max) → int
  _get_socket_port(app_name) → int    → Port 49152–65535
  _get_executable_path() → str
    → Fryst app: sys.executable
    → Windows: pythonw.exe om tillgängligt
    → Annars: python + skript

KLASS: AutostartManager – NY v2.2.0
  __init__(app_name)
  is_enabled() → bool
  enable() → bool
  disable() → bool
  set(enabled) → bool
  get_status_text() → str    → "Aktiverad"/"Avaktiverad"/"Ej tillgänglig"
  get_platform_info() → str  → Var autostart lagras

  Windows:
    _is_enabled_windows() → winreg HKCU Run
    _enable_windows()     → winreg SetValueEx
    _disable_windows()    → winreg DeleteValue

  macOS:
    _get_macos_plist_path() → Path
    _is_enabled_macos()     → plist exists
    _enable_macos()         → Skapa plist + launchctl load
    _disable_macos()        → launchctl unload + ta bort

  Linux (XDG Autostart):
    _get_linux_desktop_path() → Path
    _is_enabled_linux()       → .desktop exists + ej Hidden=true
    _enable_linux()           → Skapa .desktop
    _disable_linux()          → Ta bort .desktop

KLASS: SingleInstanceLock(QObject) – 19+ metoder
  instance_started = Signal()
    → Koppla: lock.instance_started.connect(window.show_application)

  __init__(app_name)
    → Skapar AutostartManager(app_name)  ← NY v2.2.0
  _setup_lock()
  _setup_shared_memory()
  _setup_socket_lock()
  _start_local_server()
  _on_new_connection() [Slot]
  _write_lock_file() / _remove_lock_file()
  is_running() → bool
  get_version() → str
  send_to_existing() → bool
  _try_qlocal_socket() → bool
  _try_tcp_socket() → bool
  _cleanup_stale_lock()
  _is_pid_alive(pid) → bool [staticmethod]
  release()

  get_autostart() → bool               ← NY v2.2.0
  set_autostart(enabled) → bool        ← NY v2.2.0
  get_autostart_info() → str           ← NY v2.2.0
  get_autostart_status_text() → str    ← NY v2.2.0
  autostart_manager (property)         ← NY v2.2.0

  __del__() / __repr__()
    → Inkluderar MODULE_VERSION + autostart=on/off

FRISTÅENDE FUNKTIONER:
  check_single_instance(app_name) → bool
  send_to_existing(app_name) → bool
-->

---

### 4.6 `core/theme_manager.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    core/theme_manager.py                                │
│ ANSVAR: 3 teman (dark/light/system) + QSS-generator.        │
│         Inverterade knappar/tabbar med FET text.             │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~900                                                 │
│ MODULE_VERSION = "2.2.0"                                     │
└──────────────────────────────────────────────────────────────┘

IMPORTER:
  os, platform, subprocess
  pathlib: Path
  typing: Dict, Optional, Tuple, TYPE_CHECKING
  PySide6.QtWidgets: QApplication
  PySide6.QtGui: QPalette, QColor
  PySide6.QtCore: QObject, Signal

KONSTANTER:
  MODULE_VERSION: str = "2.2.0"

KLASS: ThemeManager(QObject) – 22+ metoder
  theme_changed = Signal(str)

  DARK_THEME   = "dark"
  LIGHT_THEME  = "light"
  SYSTEM_THEME = "system"
  VALID_THEMES = (DARK_THEME, LIGHT_THEME, SYSTEM_THEME)

  LIGHT_COLORS (26 nycklar):
    Princip: Ljus bakgrund → MÖRKA knappar med VIT text
    button_bg=#3D3D3D,     button_fg=#FFFFFF (mörkgrå+vit FET)
    button_hover_bg=#555555, button_pressed_bg=#2A2A2A
    tab_bg=#4A4A4A,        tab_fg=#FFFFFF
    tab_selected_bg=#0078D4, tab_selected_fg=#FFFFFF
    window_bg=#FAFAFA,     window_fg=#1A1A1A
    accent=#0078D4, + scrollbar, menu, statusbar, input-färger

  DARK_COLORS (26 nycklar):
    Princip: Mörk bakgrund → LJUSA knappar med SVART text
    button_bg=#E8E8E8,     button_fg=#000000 (ljusgrå+svart FET)
    button_hover_bg=#FFFFFF, button_pressed_bg=#C8C8C8
    tab_bg=#D0D0D0,        tab_fg=#000000
    tab_selected_bg=#0078D4, tab_selected_fg=#FFFFFF
    window_bg=#1A1A1A,     window_fg=#E8E8E8
    accent=#0078D4, + scrollbar, menu, statusbar, input-färger

  __init__(settings_manager)
    → Laddar sparat tema, sätter _current_colors

  get_current_theme() → str
  get_version() → str
  is_dark() → bool
  set_theme(theme)
    → Validerar → _apply_current_theme → save → emit theme_changed
  refresh()

  _apply_current_theme()
    → _get_effective_theme → dark/light → setPalette
    → app.setStyleSheet(get_button_tab_stylesheet())
    → Om extern QSS-fil: kombinieras med stylesheet
  _get_effective_theme() → str
  _apply_dark_theme(app) / _apply_light_theme(app)
    → _current_colors = DARK/LIGHT_COLORS
    → _get_base_palette(is_dark)
    → Kombinerar ev. extern QSS med get_button_tab_stylesheet()

  _detect_system_theme() → str
  _detect_windows_theme() → winreg AppsUseLightTheme
  _detect_macos_theme()   → defaults read AppleInterfaceStyle
  _detect_linux_theme()   → gsettings / KDE kdeglobals fallback

  get_button_color() → (bg, fg, border)
  get_tab_color()    → (bg, fg)
  get_color(key)     → str
  get_all_colors()   → Dict

  _get_base_palette(is_dark) → QPalette
    → Sätter 13 QPalette.ColorRole inkl. Disabled-grupp
    → Button/ButtonText synkade med DARK/LIGHT_COLORS

  get_button_tab_stylesheet() → str
    → Komplett QSS (20 widget-typer, font-weight:bold överallt):
      QPushButton (alla tillstånd: normal/hover/pressed/disabled/checked)
      QToolButton (alla tillstånd)
      QTabBar::tab (normal/hover/selected/disabled)
      QTabWidget::pane, QTabBar::scroller
      QScrollBar (v+h)
      QMenu, QMenuBar
      QStatusBar
      QGroupBox
      QLineEdit/QSpinBox/QDoubleSpinBox/QComboBox
      QCheckBox
      QLabel (normal/heading/link)
      QFrame[card]
      QProgressBar
      QDialog, QDialogButtonBox
      QMessageBox
      QMainWindow/QWidget
      QToolTip
    → color: {button_fg} explicit på hover/pressed/disabled
    → Inkluderar "v{MODULE_VERSION}" i QSS-kommentaren

  _load_qss_file(filename) → Optional[str]
    → Letar i resources/themes/{filename}
-->

---

### 4.7 `core/plugin_base.py` (brygga) ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    core/plugin_base.py                                  │
│ ANSVAR: Bakåtkompatibel brygga.                              │
│         Re-exporterar BasePlugin från plugins.base_plugin.   │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~15                                                  │
└──────────────────────────────────────────────────────────────┘

IMPORTER: from plugins.base_plugin import BasePlugin

VARIABLER:
  PluginBase = BasePlugin   ← alias för bakåtkompatibilitet
  __all__ = ["BasePlugin", "PluginBase"]
-->

---

### 4.8 `plugins/__init__.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    plugins/__init__.py                                  │
│ ANSVAR: Plugin-paket med lazy loading.                       │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~65                                                  │
└──────────────────────────────────────────────────────────────┘

IMPORTER: importlib

FUNKTIONER: __getattr__(name) → lazy loading

VARIABLER:
  __all__         = ["BasePlugin"]
  __version__     = "2.2.0"
  __author__      = "Rickard Längkvist"
  __description__ = "Plugin-paket"
-->

---

### 4.9 `plugins/base_plugin.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    plugins/base_plugin.py                               │
│ ANSVAR: Abstrakt basklass (ABC). EventBus + SettingsManager. │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~340                                                 │
└──────────────────────────────────────────────────────────────┘

IMPORTER:
  from __future__ import annotations
  abc: ABC, abstractmethod
  typing: Dict, Any, Optional, List, Callable, TYPE_CHECKING
  PySide6.QtWidgets: QWidget
  (TYPE_CHECKING): core.event_bus.EventBus
                   core.settings_manager.SettingsManager

KLASS: BasePlugin(ABC) – 15 metoder

  Kända plugins v2.2.0:
    "Hyresfakturering":
      year, last_file, last_used
    "Semesterlista & Limokörning":
      default_mode, auto_open_pdf, last_file,
      months_per_page, start_month, default_year, last_used
      start_month: 0=Standard(jan–dec valt år),
                   1–12=explicit,
                   12=December→kan gå till Jan nästa år

  NAME, VERSION, DESCRIPTION, AUTHOR: str = ""
  DEPENDENCIES: List[str] = []

  __init__(event_bus, settings_manager)
  @abstractmethod get_name() → str
  @abstractmethod get_version() → str
  @abstractmethod get_tab_widget() → QWidget
  initialize() → bool
  shutdown()    → Avprenumererar alla _subscriptions automatiskt
  is_initialized() → bool
  get_settings() → Dict
  save_settings(settings)
  subscribe(event_name, callback)
  unsubscribe(event_name, callback=None)
  emit(event_name, data=None)
  event_bus (property) → EventBus
  settings_manager (property) → SettingsManager
  __repr__() → inkl. antal subscriptions
  __str__()
-->

---

### 4.10 `plugins/hyra/__init__.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    plugins/hyra/__init__.py                             │
│ ANSVAR: Plugin-paket för hyresfakturering.                   │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~12                                                  │
└──────────────────────────────────────────────────────────────┘

VARIABLER: __all__ = ["Plugin"]
-->

---

### 4.11 `plugins/hyra/plugin.py` ✅ v2.2.0 (fixad v2.8.1)

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    plugins/hyra/plugin.py                               │
│ ANSVAR: Hyresfakturering – generera hyreslistor som PDF.     │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~650                                                 │
└──────────────────────────────────────────────────────────────┘

IMPORTER:
  os, platform, webbrowser, logging
  datetime: date, datetime
  pathlib: Path
  typing: List, Dict, Any, Optional, TYPE_CHECKING
  PySide6.QtWidgets:
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QGroupBox, QSpinBox, QFrame,
    QMessageBox, QSizePolicy
  PySide6.QtCore: Qt, Signal, Slot
  PySide6.QtGui: QFont
  reportlab.platypus: SimpleDocTemplate, Table, TableStyle,
                      Paragraph, Spacer
  reportlab.lib.pagesizes: A4
  reportlab.lib: colors
  reportlab.lib.styles: getSampleStyleSheet, ParagraphStyle
  reportlab.lib.units: mm
  plugins.base_plugin: BasePlugin
  (TYPE_CHECKING): core.event_bus.EventBus
                   core.settings_manager.SettingsManager

KONSTANTER:
  PLUGIN_INFO: Dict         ← id, name, version="2.2.0", author, desc
  DEFAULT_TENANT_FILE: str  ← "Hyresgäster.txt"
  SEPARATOR: str            ← "-------"
  MONTHS: Dict[int, str]    ← 12 månader på svenska (förkortade)
  QUARTER_INVOICE_DATES: Dict[int, str]
  QUARTER_INFO: Dict[int, dict]

HJÄLPFUNKTIONER (modulnivå):
  get_documents_folder() → str
  get_app_folder()       → str
  get_all_quarter_invoice_info(year) → List[Dict]
  calculate_text_width(text, font_size) → float

KLASSER:

  TenantManager – 9 metoder:
    __init__()
    _load_tenants()         → Läser Hyresgäster.txt (separator: -------)
    _create_example_file()
    reload()
    get_monthly_tenants()   → List[str]
    get_quarterly_tenants() → List[str]
    get_year() / set_year(year)
    get_max_name_length()   → int

  HyraMainView(QWidget) – 13 metoder:
    year_changed     = Signal(int)
    reload_requested = Signal()
    __init__(tenant_manager, plugin_ref, parent)
    _init_ui()
    _create_top_panel()       → titel + år-väljare
    _create_file_info_row()   → fil-info + Redigera + Ladda om
    _create_quarter_info_panel() → färgkodade QFrame-kort per kvartal
    _create_tenant_overview() → månads + kvartalslista sida vid sida
    _create_tenant_group(title, tenants)
    _create_button_bar()      → Generera PDF + Redigera
    _on_year_change(value)
    _reload()
    _refresh_ui()
    _clear_layout(layout) [staticmethod]

  PDFGenerator – 5 metoder:
    __init__(plugin)
    generate() → bool
    _add_quarter_info(elements, styles)
    _create_monthly_table(tenants) → Table
    _create_quarterly_table(tenants) → Table

  Plugin(BasePlugin) – 13 metoder:
    NAME    = "Hyresfakturering"
    VERSION = "2.2.0"
    DESCRIPTION / AUTHOR

    __init__(event_bus, settings_manager)
      → Återställer sparat år från settings
    get_name() / get_version() / get_tab_widget()
    initialize()   → subscribe app:shutting_down, settings:changed
    shutdown()     → Sparar year + last_file + last_used
    _on_app_shutdown(data)
    _on_settings_changed(data)
    _generate_pdf()
    _open_tenant_file()   → subprocess check=False
    _reload_tenants()
    main_view (property) → HyraMainView
-->

---

### 4.12 `plugins/lista/__init__.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    plugins/lista/__init__.py                            │
│ ANSVAR: Plugin-paket för semesterlista & limokörning.        │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~12                                                  │
└──────────────────────────────────────────────────────────────┘

VARIABLER: __all__ = ["Plugin"]
-->

---

### 4.13 `plugins/lista/plugin.py` ✅ v2.2.0

<!--
┌──────────────────────────────────────────────────────────────┐
│ FIL:    plugins/lista/plugin.py                              │
│ ANSVAR: Semesterlista & Limokörning – PDF med färgkodade     │
│         dagar, helgdagar, halvdagar, veckolinjer.            │
│         Val av 2 eller 3 månader per blad.                   │
│         Manuell startmånad – kan gå över årsskifte           │
│         (Dec 2026 → Jan 2027).                               │
│         Alltid centrerat och anpassat för liggande A4.       │
│         KORRIGERAD färgkodning: midsommarafton = GRÖN.       │
│ STATUS: ✅ KLAR v2.2.0                                       │
│ RADER:  ~950                                                 │
└──────────────────────────────────────────────────────────────┘

IMPORTER:
  from __future__ import annotations
  os, json, calendar, platform, webbrowser, logging
  datetime: date, datetime, timedelta
  pathlib: Path
  typing: List, Dict, Any, Optional, Set, TYPE_CHECKING
  PySide6.QtWidgets:
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QGroupBox, QSpinBox, QComboBox, QLineEdit,
    QCheckBox, QMessageBox, QFileDialog,
    QDialog, QDialogButtonBox, QSizePolicy
  PySide6.QtCore: Qt, Signal, Slot
  PySide6.QtGui: QFont
  reportlab.platypus:
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, PageBreak
  reportlab.lib.pagesizes: landscape, A4
  reportlab.lib: colors
  reportlab.lib.styles: getSampleStyleSheet
  reportlab.lib.units: mm
  plugins.base_plugin: BasePlugin
  (TYPE_CHECKING): core.event_bus.EventBus
                   core.settings_manager.SettingsManager

KONSTANTER:
  TABLE_WIDTH_MM    = 270.0
  TABLE_WIDTH_PT    = 270.0 * mm
  NAME_COL_WIDTH    = 70
  MIN_DAY_COL_WIDTH = 8
  FONT_SIZE         = 7
  PLUGIN_INFO: Dict  ← version="2.2.0"

  MONTHS_SV: Dict[int, str]
    → {1: "Januari", ..., 12: "December"}

  MONTH_OPTIONS: List[str]  ← 14 alternativ
    → ["Standard (Januari)", "Januari", ..., "December"]
    → Index 0 = standard (jan–dec valt år)
    → Index 1–12 = explicit startmånad

HJÄLPFUNKTIONER (modulnivå):

  get_documents_folder() → str
  get_plugin_data_folder() → str

  get_easter(year) → date
    → Gauss algoritm

  get_swedish_holidays(year) → Set[date]
    → OFFICIELLA röda dagar (13 st):
        Nyårsdagen, Trettondedag jul, Långfredag, Påskdagen,
        Annandag påsk, Första maj, Kristi himmelsfärd, Pingstdagen,
        Nationaldagen, Midsommardagen (lördag), Alla helgons dag (lördag),
        Juldagen, Annandag jul
    → INTE röda: Midsommarafton, Julafton, Nyårsafton

  get_half_days(year) → Set[date]
    → GRÖNA halvdagar (6 st):
        Skärtorsdag, Valborg (30/4), Midsommarafton (fredag ← GRÖN EJ röd),
        Dag före Alla helgons dag (fredag), Julafton (24/12), Nyårsafton (31/12)

KLASSER:

  SettingsDialog(QDialog) – 4 metoder:
    __init__(parent, plugin)
    _init_ui()
      → auto_open_pdf (QCheckBox)
      → default_mode (QComboBox)
      → months_per_page (QComboBox: 2/3)
      → start_month_combo (QComboBox: MONTH_OPTIONS)
    _load_settings()
    _save() → sparar inkl. start_month

  TestRunner – 3 metoder:
    __init__(parent, plugin)
    run() → 10 automatiska tester:
      1.  Ogiltigt år
      2.  År utanför intervall
      3.  Ogiltigt läge
      4.  Skottårshantering
      5.  Svenska helgdagar – korrekthet
      6.  Midsommarafton = GRÖN (ej röd)
      7.  Julafton = grön
      8.  Påskberäkning 2024
      9.  Standardläge = jan–dec samma år
      10. December → januari över årsskifte
    _show_results(results) → QDialog

  PDFGenerator – 9 metoder:
    __init__(plugin)

    generate(year_str, file_path, mode, months_per_page,
             start_month=None) → bool
      → start_month: None/0 = standardläge (jan–dec valt år)
      → 1–12 = 12 sammanhängande månader från vald månad
      → Kan gå över årsskifte

    _validate_inputs(year_str, file_path, mode) → List[str]
    _read_list_from_file(file_path) → List[str]
    _create_legend_with_colors() → Table
      → "Röd = Helgdag eller söndag"
      → "Grön = Halvdag (midsommarafton, julafton m.fl.)"

    _calc_column_widths(days_in_month) → (float, float)
    _apply_table_scaling(table)
      → Garanterar exakt 270mm via ReportLab wrap()

    _build_month_sequence(base_year, start_month) → List[(year, month)]
      → None → [(2026,1),...,(2026,12)]
      → 12   → [(2026,12),(2027,1),...,(2027,11)]

    _chunk_months(sequence, chunk_size) → List[List]
    _format_range_label(sequence) → str
    _format_page_title(prefix, page_months) → str
    _build_output_filename(documents_path, mode, sequence) → str
      → Standard: semesterlista_2026.pdf
      → Manuell: semesterlista_2026_12-2027_11.pdf

    _generate_pdf(data_list, year, mode, months_per_page,
                  start_month=None) → bool
      → Beräknar years_in_sequence (kan vara 2 år)
      → Hämtar helgdagar/halvdagar per år (official_holidays_by_year)
      → Liggande A4, 13.5mm marginal, 270mm tabell
      → Färgprioritet: röd > grön > blå
      → Orange LINEBEFORE vid ny vecka
      → emit semesterlista:pdf_generated inkl. spans_year_boundary

  SemesterlistaView(QWidget) – 10 metoder:
    generate_requested = Signal(str, str, str, int, int)

    __init__(plugin, parent)
    _init_ui()
    _create_form_group() → QGroupBox
      → Rad 0: Läge          [Semesterlista ▼]
      → Rad 1: År            [2026 ↑↓]
      → Rad 2: Startmånad    [Standard (Januari) ▼]
      → Rad 3: Månader/blad  [3 ▼]
      → Rad 4: Fil           [Anställda.txt] [Bläddra...]
    _create_button_bar() → Generera PDF, Kör tester, Öppna Dokument
    _create_legend_group() → färgförklaring med uppdaterad text
    _on_mode_change(mode) [Slot]
    _on_start_month_change(index) [Slot] → sparar index
    _browse_file()
    _generate_pdf()
      → index=0 → start_month=None (standard)
      → index=1–12 → start_month=index
    _run_tests()
    _open_documents()

  Plugin(BasePlugin) – 14 metoder:
    NAME        = "Semesterlista & Limokörning"
    VERSION     = "2.2.0"
    DESCRIPTION / AUTHOR

    __init__(event_bus, settings_manager)
    get_name() / get_version() / get_tab_widget()
    _load_settings() → Dict
      → default: months_per_page=3, auto_open_pdf=True,
                 default_mode="Semesterlista", start_month=0
    _save_settings()
    initialize()   → subscribe app:shutting_down, theme:changed
    shutdown()     → Sparar start_month
    _on_app_shutdown(data)
    _on_theme_changed(data)
    _show_main_view()
    _show_settings() → SettingsDialog
    _open_documents_folder() → subprocess check=False
    main_view (property) → SemesterlistaView
-->

---


### 4.14 `core/roster.py` ✅ v2.4.0

```text
┌─────────────────────────────────────────────────────────────┐
│ MODULE_VERSION = "2.4.0"                                    │
│ Ansvar: EN gemensam inläsare/skrivare för alla textlistor   │
│         (Anställda.txt, Fordon.txt, Hyresgäster.txt)        │
└─────────────────────────────────────────────────────────────┘

IMPORTER
  codecs, os, shutil, unicodedata, dataclasses, pathlib, typing

KLASSER
  RosterIssue        – ett problem i listan
    level ("error" | "warning"), message, section, entry
    is_error / is_warning

  RosterFile         – en lista (1..n sektioner)
    load(path, name, base, create, default_sections)
    reload()
    sections / entries / section(i) / entry_count() / is_empty()
    all_entries() / duplicates(index)
    add(value, index, position)    → normaliserat värde
    rename(position, value, index)
    remove(position, index) / move(position, delta, index)
    sort(index, reverse) / clear(index) / set_entries(entries, index)
    validate() → List[RosterIssue]
    has_errors() / as_text() / save(backup=True) / backup_path

  RosterError        – fel vid läsning/redigering/skrivning

FUNKTIONER
  app_root()                       – appens rotmapp
  resolve_path(path, base)         – relativa namn mot appens rotmapp
  normalize_entry(value)           – trim + kollapsa blanksteg + styrtecken
  sort_key(value)                  – svensk sortering (Å, Ä, Ö efter Z)
  is_separator(line)               – rad med minst 3 streck
  is_comment(line)                 – # eller ;
  decode_bytes(raw)                – UTF-8 → cp1252 → latin-1
  read_names(path, base)           – genväg för PDF-generatorn
  ensure_file(path, name, ...)     – skapar filen om den saknas
  open_in_editor(path)             – öppna i OS:ets textredigerare

FILFORMAT
  # Kommentar som ignoreras
  Anna Andersson
  -------                          ← sektionsbrytare (hyresgäster)
  Företag AB

SÄKERHET / ROBUSTHET
  - läser UTF-8 (med/utan BOM), cp1252 och latin-1
  - tar bort tomma rader, normaliserar blanksteg och dubbletter
  - validerar före sparning (tom post, > 80 tecken, dubblett)
  - sparar atomärt (tmp → rename) med backup *.bak, UTF-8 + CRLF
```

### 4.15 `core/list_editor_dialog.py` ✅ v2.4.0

```text
┌─────────────────────────────────────────────────────────────┐
│ MODULE_VERSION = "2.4.0"                                    │
│ Ansvar: GUI för att redigera listorna i appen               │
└─────────────────────────────────────────────────────────────┘

IMPORTER
  PySide6.QtWidgets (QDialog, QListWidget, QTabWidget, QInputDialog,
  QMessageBox, QPushButton …), core.i18n, core.roster

KLASSER
  SectionEditor(QWidget)
    changed (Signal)
    set_entries(entries) / entries()
    _on_add() / _on_edit() / _on_remove() / _on_move(delta)
    _on_paste()  – klistra in flera rader samtidigt
    _on_sort()   – sortering med svenska regler
    Knappar: Lägg till, Ändra, Ta bort, Upp, Ner, Sortera, Klistra in flera

  ListEditorDialog(QDialog)
    __init__(path, name, parent, section_titles, base, create)
    roster (property/attribut) – sparad lista efter Spara
    En flik per sektion (Hyresgäster.txt → Månad + Kvartal)
    _on_save() – validerar (fel blockerar, varningar frågar), sparar
    _on_open_in_editor() – öppna samma fil i Anteckningar/TextEdit
    reject()/close – frågar om osparade ändringar
    edit(path, name, parent, section_titles, base) → bool (klassmetod)
```

### 4.16 `core/pdf_assets.py` ✅ v2.5.0

**Ansvar:** Hitta bilder i `assets/` (rekursivt) och rita dem i PDF:en.

| Funktion | Beskrivning |
|----------|-------------|
| `assets_root(base=None)` | `assets/` i appens rotmapp |
| `ensure_assets_dir(base=None)` | Skapar mappen om den saknas |
| `scan_assets(root=None, suffixes=..., recursive=True)` | Alla bilder, sorterade på relativ sökväg |
| `find_asset(namn, root=None)` | Sök på relativ sökväg, filnamn eller stam |
| `PdfLogo.load(path, max_width_mm=35, max_height_mm=16)` | Laddar SVG/PNG/JPG, bevarar proportioner |
| `PdfLogo.draw_on(canvas, x, y)` | Ritar på en reportlab-canvas |
| `PdfLogo.auto_size(page_w, page_h, …)` | Automatisk storlek för sidan, proportionerna behålls (v2.10.0) |
| `PdfLogo.draw_corner(canvas, doc, margin_mm=8, corner="right", auto_size=True)` | Övre högra hörnet, automatiskt skalad (v2.10.0) |
| `make_logo_canvas(logo, ...)` | Canvas-klass som ritar logotypen på **varje** sida |
| `make_page_logo_drawer(logo, ...)` | onPage-callback (för reportlab-versioner som stöder det) |
| `logo_for_settings(settings, key="logo_svg")` | Läser vald logotyp från inställningarna |

**Automatisk storlek (v2.10.0):** logotypen ritas i en ruta som är
15 % av sidans bredd och 8 % av höjden, med taket 60 × 25 mm och en
minsta ruta på 36 × 12 pt. Rutan skalas alltid proportionellt – både upp
och ned – så att logotypen aldrig förvrängs, oavsett om sidan är
liggande eller stående.

**SVG-hantering (två vägar):**
1. `svglib` installerat → `svg2rlg()` → vektorgrafik i PDF:en (bäst kvalitet).
2. Annars → `QSvgRenderer` (PySide6) → PNG i 300 dpi, cachas i
   `%TEMP%/Semesterlista/logotyper/`. Kräver inga extra beroenden.

Misslyckas båda kastas `AssetError` med tydligt meddelande – PDF:en
genereras ändå, utan logotyp (felet loggas som varning).

**Varför `canvasmaker`:** `onFirstPage`/`onLaterPages` är inte giltiga
argument i alla reportlab-versioner (de ignoreras då tyst). Genom att
ärva `Canvas` och rita i `showPage()` hamnar logotypen på varje sida i
alla versioner.

---

### 4.17 `plugins/fordon/plugin.py` ✅ v2.5.0

**Ansvar:** Egen flik för fordon/limokörning.

Ärver `plugins/lista/plugin.py::Plugin` och ändrar bara:

| Attribut | Värde | Effekt |
|----------|-------|--------|
| `NAME` | `"Fordon"` | Egen nyckel i `data/plugins.json` |
| `FIXED_MODE` | `"Limokörning"` | Lägesväljaren döljs, PDF:en blir limokörningsschema |
| `DEFAULT_LIST_FILE` | `"Fordon.txt"` | Standardlista |
| `TAB_ORDER` | `30` | Fliken hamnar sist (Hyra 10, Semesterlista 20) |

Vyn, PDF-generatorn, listredigeraren och logotypvalet återanvänds utan
kopior. `Plugin._load_settings()` migrerar automatiskt gamla
limo-inställningar (fil, startmånad, månader/blad) från den tidigare
kombinerade fliken om den pekade på en fordonsfil.

Inställningarna sparas i en egen lokal fil
(`.../plugins/lista/settings-fordon.json`) så att flikarna inte skriver
över varandra.

---

### 4.18 `core/app_icon.py` ✅ v2.7.0

**Ansvar:** En och samma ikon överallt i appen.

| Funktion | Beskrivning |
|----------|-------------|
| `icon_dir()` | `assets/ikon` (relativt appens rot) |
| `icon_files()` | Befintliga filer: PNG 16–256, `.ico`, `.svg` (i den ordningen) |
| `app_icon(force_reload=False)` | `QIcon` med alla storlekar (cachas) |
| `fallback_icon()` | Ritar ikonen med `QPainter` om bilderna saknas |
| `apply_app_icon(app=None)` | Sätter applikationens ikon (+ `setDesktopFileName` på Linux) |
| `set_windows_app_user_model_id()` | AppUserModelID på Windows – rätt ikon/gruppering i aktivitetsfält och aktivitetshanterare |
| `clear_cache()` | Rensar cachen (tester) |

**Var ikonen används**

- `main.pyw`: `apply_app_icon(app)` direkt efter `QApplication` skapas;
  `set_windows_app_user_model_id()` innan fönstret skapas.
- `MainWindow._init_ui()`: `self.setWindowIcon(app_icon())`.
- `SystrayManager`: `QSystemTrayIcon(app_icon(), app)` (tidigare en egenritad
  blå ruta med "S").
- Dialoger: listredigeraren, logotypväljaren och pluginets
  inställningsdialog sätter samma ikon; `QMessageBox` ärver appens ikon.

**Filer & återbyggnad**

| Fil | Roll |
|-----|------|
| `assets/ikon/appikon.svg` | källa (redigeras) |
| `assets/ikon/appikon-16…256.png` | Qt väljer storlek per yta (tray, fönster, HiDPI) |
| `assets/ikon/appikon.ico` | Windows: aktivitetsfält, genvägar, aktivitetshanteraren |

`python tools/make_icons.py` rastrerar om SVG:n med `QSvgRenderer` och bygger
`.ico` (7 storlekar, PNG-baserad) – bara PySide6 behövs.

---

### 4.19 `core/logging_setup.py` ✅ v2.8.0

**Ansvar:** Detaljerad loggning som sätts upp *före* PySide6 och plugins
importeras, så att även importfel hamnar i fil.

```python
LOG_FILE = setup_logging(PROJECT_ROOT)   # → data/loggar/app.log
install_excepthook(on_crash)             # valfri callback → felruta
install_faulthandler()                   # → data/crash.log
install_qt_message_handler()             # efter QApplication
log_startup_context(PROJECT_ROOT)        # miljöinfo
```

| Funktion | Beskrivning |
|----------|-------------|
| `setup_logging(base_dir, level, to_file, to_console, file_name)` | Sätter rot-loggern, roterande fil + konsol (hoppas över i pythonw) |
| `log_file_path(base_dir, file_name)` | `data/loggar/app.log` (eller eget namn) |
| `get_log_file()` / `is_configured()` | Aktiv loggfil / om setup körts |
| `startup_context()` / `log_startup_context()` | Python, Qt, OS, cwd, pid, argv m.m. |
| `install_excepthook(on_crash)` | Huvudtråd + `threading.excepthook`; `KeyboardInterrupt` släpps igenom |
| `last_crash()` | Senaste ohanterade felet som text |
| `install_faulthandler()` | `crash.log` – fångar även segmenteringsfel |
| `install_qt_message_handler()` | `qInstallMessageHandler` → logger `qt` |
| `tail_log(lines)` | Sista raderna (används av inställningsdialogen) |
| `log_summary()` | Fil, nivå, antal handlers, senaste krasch |
| `reset_logging()` | Städar handlers, faulthandler och excepthook (tester) |

**Format & nivåer**

```
[2026-11-02 13:33:08] INFO     main:189 – Loggning startad … (nivå=INFO, fil=…)
[2026-11-02 13:33:08] DEBUG    plugins.lista.plugin:1128 – PDF-start: läge=…
```

| Inställning | Standard |
|-------------|----------|
| Fil | `data/loggar/app.log` (reserv: `%TEMP%/Semesterlista/app.log`, sedan `~/.semesterlista/`) |
| Rotering | 2 MB × 5 filer (`app.log.1` … `app.log.5`) |
| Nivå | `INFO`; `DEBUG` om `SEMESTERLISTA_DEBUG` är satt |
| Format | `[tid] NIVÅ-8 modul:rad – meddelande` |
| Loggers | `main`, `main.startup`, `crash`, `qt`, `warnings` |

**Var det loggas**

- `main.pyw`: steg för steg (`STEG 1 … STEG 12`) med ms per steg, plugins
  med version, flikantal, tray-status, exit-kod och total körtid.
- `plugins/lista/plugin.py`: PDF-parametrar före bygget och antal
  månader/sidor, filstorlek och tidsåtgång efter.
- `MainWindow._open_settings()`: öppning/stängning, språk och tema.

---

### 4.20 `core/settings_dialog.py` ✅ v2.8.0

**Ansvar:** Inställningsdialogen bakom **Arkiv → Inställningar** (Ctrl+,).

```python
SettingsDialog(
    settings_manager=…, theme_manager=…, lock=…,
    plugin_manager=…, event_bus=…, parent=self,
).exec()
```

| Flik | Innehåll | Sparas som |
|------|----------|------------|
| Allmänt | Språk (sv/en), tema (system/ljust/mörkt), helgdagsregion (sv/us) | `language`, `theme`, `holiday_region` |
| Fönster | Autostart, starta minimerad, minimera/stäng till systemfältet, aviseringar + varaktighet | `advanced.autostart`, `systray.*` |
| Plugins | Kryssruta per plugin (kräver omstart) | `plugins.json` → `enabled` |
| Avancerat | Felsökningsläge, loggning till fil, uppdateringskontroll, loggfilens väg, **Öppna loggmapp** och **Kopiera senaste loggen** | `advanced.debug_mode`, `advanced.log_to_file`, `advanced.check_updates` |

| Metod | Beskrivning |
|-------|-------------|
| `apply_settings()` | Skriver alla fält till `SettingsManager` utan dialogruta (används av testerna) |
| `_load_settings()` | Läser in nuvarande värden; okända värden faller tillbaka på standard |
| `_save()` | `apply_settings()` + bekräftelseruta + `accept()` |
| `_plugin_names()` | Plugins från `plugins.json` **och** laddade plugins (id → visningsnamn) |
| `_open_log_folder()` / `_copy_log_tail()` | Öppnar loggmappen i filhanteraren / kopierar `tail_log(60)` |

**Robusthet:** alla komponenter utom `settings_manager` är valfria. Saknas
`core/settings_dialog.py` startar appen ändå – menyvalet inaktiveras och
orsaken skrivs till loggen (se `SETTINGS_DIALOG_ERROR` i `main.pyw`).

---

### 4.21 `core/updater.py` ✅ v2.9.0

**Ansvar:** Hämta, jämföra och installera nya versioner från GitHub
Releases – helt utan externa beroenden (bara `urllib`, `json`, `zipfile`).

```python
from core import updater

info = updater.check_for_update("2.9.0")        # → UpdateInfo
if info.available:
    zip_path = updater.download_release(info, tmp / "release.zip")
    result   = updater.install_from_zip(zip_path, app_dir, local_version="2.9.0")
    print(result.version, result.file_count, result.backup)
```

| Funktion | Beskrivning |
|----------|-------------|
| `check_for_update(local, timeout)` | `GET /releases/latest` + `GET /contents/config.json?ref=<tagg>` → `UpdateInfo` |
| `fetch_latest_release()` | Rå JSON från GitHub (404/403 ger `UpdateError`) |
| `fetch_version_at_tag(tag)` | Läser `version` ur `config.json` vid taggen (fallback: taggen själv) |
| `download_release(info, target, progress)` | Laddar ner `zipball_url`, rapporterar byte, max 80 MB |
| `safe_extract(zip, dest)` | Packar upp och stoppar `../`- och absoluta sökvägar |
| `verify_payload(root)` | Kräver `main.pyw`, `config.json`, `core/`, `plugins/` |
| `install_from_zip(zip, app_dir, local_version)` | Säkerhetskopierar, skriver filerna atomiskt, returnerar `InstallResult` |
| `restart_command(app_dir)` | `[python(w).exe, main.pyw]` för omstart |
| `parse_version()` / `is_newer()` | `"v2.9"` → `(2, 9)`; `2.9` > `2.8.9` |
| `github_release_url()` | Länk till senaste releasen |

**Vad som aldrig skrivs över**

| Hoppas över | Orsak |
|-------------|-------|
| `data/` (settings.json, plugins.json, loggar, backup) | Användarens inställningar och historik |
| `Anställda.txt`, `Fordon.txt`, `Hyresgäster.txt` | Användarens listor |
| `.git/`, `__pycache__/`, `.venv/`, `build/`, `dist/` | Repo och byggartefakter |
| `*.pyc`, `*.bak`, `*.tmp`, `*.log` | Skräp och säkerhetskopior |

**Säkerhetskopia:** innan något skrivs sparas de filer som ersätts i
`data/backup/uppdatering-<gammal>-till-<ny>-<datum>.zip`.

**Felhantering:** nätverksfel, 404 (ingen release), 415, för stor fil,
trasig zip, osäkra sökvägar, saknade filer i releasen och låsta filer ger
alla `UpdateError` med ett begripligt meddelande – appen fortsätter köra.

---

### 4.22 `core/logo_picker.py` ✅ v2.10.0

**Ansvar:** En liten widget som ersätter den gamla logotypdialogen
(`core/logo_dialog.py` togs bort i v2.10.0): dropdown + knappar +
förhandsgranskning som skalar sig själv.

```python
from core.logo_picker import LogoPicker

self.logo_picker = LogoPicker(current=settings.get("logo_svg", ""), parent=self)
self.logo_picker.changed.connect(self._on_logo_changed)   # (str) → sökväg
```

| Medlem | Beskrivning |
|--------|-------------|
| `combo` | `QComboBox` – post 0 = **"Ingen logotyp"** (`data=""`), sedan alla **SVG-logotyper** i `assets/` **och undermappar** med relativ sökväg som text (andra bildformat listas inte) |
| `insert_button` | 🖼️ **Infoga SVG…** – väljer en bild även utanför `assets/` (läggs då till i listan med markeringen *(utanför assets)*) |
| `rescan_button` | **Uppdatera lista** – läser om mappen |
| `preview` | `QLabel` som visar bilden i `PREVIEW_HEIGHT` (56 px) höjd; skalas med `KeepAspectRatio` vid `resizeEvent`/`showEvent` |
| `changed = Signal(str)` | Ny sökväg (`""` = ingen logotyp) |
| `refresh(emit=False)` | Bygger om listan, behåller valet |
| `set_current(path, emit=True, add_missing=True)` | Markerar en sökväg i listan |
| `clear()` | Tillbaka till "Ingen logotyp" |
| `current_path()` / `assets()` | Vald sökväg / hittade bilder |

Vyn sparar valet direkt i `plugin.settings["logo_svg"]` (relativ eller
absolut sökväg). PDF:en skalar sedan logotypen automatiskt för varje
sida via `PdfLogo.auto_size()`.

`show_preview=False` används av **Hyra**-vyn, som visar väljaren i
verktygsraden där det inte finns plats för en förhandsgranskning.

---

## 5. DETALJERAD FUNKTIONALITET

<!--
Startsekvens och övrig funktionalitet.
-->

### 5.1 Startsekvens
hide_console_window() → Dölj terminal (Windows)
SingleInstanceLock → Kolla + send_to_existing() + sys.exit(0)
QApplication → Skapa + setHighDpiScaleFactorRoundingPolicy
SettingsManager → Laddar settings.json + plugins.json
EventBus → Skapa
ThemeManager → Applicerar sparat tema
PluginManager → discover + load + initialize_all
MainWindow → Skapa (show() anropas EJ)
_apply_theme() → Kopplas till theme_changed-signal
lock.instance_started → Kopplas till main_window.show_application
SystrayManager → Ikon visas i systemfältet
Synk autostart → Från settings → lock.set_autostart()
event_bus.emit("app:started") → {version, app_name}
systray-notifikation
app.exec() → Qt event-loop
text


### 5.2 Fönsterhantering
Min storlek: 800×600
Dynamisk layout: QVBoxLayout, QHBoxLayout, QSizePolicy.Expanding
Spara/återställ geometri i settings.json (window.x/y/width/height/maximized)
text


### 5.3 Mushjulsscroll
QTabBar: eventFilter fångar QEvent.Wheel → horisontell tabb-scroll
QScrollBar: QSS-stylad för alla scrollbara ytor
text


### 5.4 Start utan terminalfönster
Windows: ctypes.windll.user32.ShowWindow(GetConsoleWindow(), 0)
Alternativ: pythonw.exe eller .pyw-extension
_get_executable_path() väljer pythonw.exe automatiskt om tillgängligt
text


### 5.5 PDF – Sidlayout, månader per blad + manuell startmånad

**Sidlayout (v2.6.0) – väljs i vyn, sparas per flik**

| Layout | Sidstorlek | Marginal | Tabellbredd | När den passar |
|--------|-----------|----------|-------------|----------------|
| Liggande (standard) | A4 297 × 210 mm | 13,5 mm | 270 mm | breda dagkolumner, få personer |
| Stående | A4 210 × 297 mm | 10 mm | 190 mm | pärm/arkivet, många rader |

`page_geometry(orientation)` ger `(pagesize_pt, tabellbredd_pt)`;
`_calc_column_widths(dagar, bredd)` och `_apply_table_scaling(tabell,
bredd)` räknar om kolumnerna så att tabellen fyller exakt rätt bredd.
Färgförklaringen skalas på samma sätt. Ogiltig/okänd layout faller
tillbaka på liggande (`normalize_orientation()`).

**Månader per blad (v2.6.0): 1, 2 eller 3**

| Val | Blad för 12 månader | Kommentar |
|-----|--------------------|-----------|
| 1 | 12 | störst tabeller, en månad per sida |
| 2 | 6 | två månader per sida |
| 3 | 4 | standard, tre månader per sida |

`MONTHS_PER_PAGE_OPTIONS = [1, 2, 3]`, `DEFAULT_MONTHS_PER_PAGE = 3`.
Validering: andra värden avvisas med "Månader per blad måste vara 1, 2, 3".

**Startmånad**

Standardläge: start_month=None → jan–dec valt år
Manuellt val: 12 sammanhängande månader, kan gå över årsskifte
Exempel: Dec 2026 → Jan 2027 → ... → Nov 2027

**Filnamn**

Standard: semesterlista_2026.pdf
Manuell: semesterlista_2026_12-2027_11.pdf
Limokörning: limokorning_2026.pdf


---

## 6. TEMAHANTERING (Endast 3 Teman)

<!--
Exakt definition av alla tre teman.
Knappar/tabbar inverteras mot bakgrunden för maximal synlighet.
-->
LJUST TEMA (ljus bakgrund → MÖRKA knappar med VIT text):
Knapp-bakgrund: #3D3D3D (mörkgrå)
Knapp-text: #FFFFFF (vit) FET
Knapp-border: #222222
Knapp-hover: #555555
Tabb-bakgrund: #4A4A4A (mörkgrå)
Tabb-text: #FFFFFF (vit) FET
Tabb-active: #0078D4 (blå) + vit text

MÖRKT TEMA (mörk bakgrund → LJUSA knappar med SVART text):
Knapp-bakgrund: #E8E8E8 (ljusgrå)
Knapp-text: #000000 (svart) FET
Knapp-border: #AAAAAA
Knapp-hover: #FFFFFF
Tabb-bakgrund: #D0D0D0 (ljusgrå)
Tabb-text: #000000 (svart) FET
Tabb-active: #0078D4 (blå) + vit text

SYSTEM-TEMA:
Följer OS: Windows (register), macOS (defaults), Linux (gsettings/KDE)

QSS täcker 20 widget-typer:
QPushButton, QToolButton, QTabBar::tab, QTabWidget::pane,
QTabBar::scroller, QScrollBar (v+h), QMenu, QMenuBar,
QStatusBar, QGroupBox, QLineEdit/QSpinBox/QComboBox,
QCheckBox, QLabel, QFrame[card], QProgressBar,
QDialog, QDialogButtonBox, QMessageBox,
QMainWindow/QWidget, QToolTip

text


---

## 7. TABBAR – VISA/DÖLJ (Dynamiskt)
"Visa"-meny: checkable QActions per tabb – bock = synlig
Högerklick på tabb → kontextmeny: "Dölj [namn]" + "Visa alla dolda tabbar"
Dolda tabbar sparas i _tab_widgets dict, kan återställas
Dynamiskt – fungerar med plugins som laddas/avlastas
Tabb-ordning sparas i settings.json → tabs.order
Scroll via mushjul på QTabBar (eventFilter)

v2.5.0 – tre flikar med fast ordning:
  Hyra (TAB_ORDER 10) → Semesterlista (20) → Fordon (30)
  Ordningen styrs av pluginets TAB_ORDER (BasePlugin, standard 100)
  och sorteras i MainWindow._sorted_plugin_names() – oberoende av i
  vilken ordning mapparna hittas.
text


---

## 8. SINGLE-INSTANCE-LOCK
QSharedMemory (primär) + QLocalServer/QLocalSocket (IPC)
TCP-socket fallback om Qt ej tillgängligt
Lock-fil med PID för stale cleanup
bring-to-front: skickar "show" → befintlig instans visar fönstret
check_single_instance() + send_to_existing() – fristående
text


---

## 9. SYSTRAY & MINIMERING

v2.7.0: Systemfältsikonen är appens riktiga ikon (assets/ikon) – samma som
fönstret och aktivitetsfältet. På Windows sätts AppUserModelID
("Tokke2.Semesterlista") innan fönstret skapas, så aktivitetsfältet och
aktivitetshanteraren visar appens ikon i stället för Python-ikonen.
Startar ALLTID minimerat – main_window.show() anropas EJ i main()
Enkelklick (vänster) på ikon → toggla visa/dölj
Högerklick → meny (v2.10.0):
  Visa <app>                → standardval (fet); inaktiverat när fönstret syns
  Dölj                      → inaktiverat när fönstret är dolt
  ─────────
  Inställningar…            → öppnar Inställningar (Ctrl+,)
  Sök efter uppdatering…    → Inställningar → Avancerat + söker direkt
  Om <app> v<version>…      → samma Om-ruta som Hjälp-menyn
  ─────────
  Avsluta
Statusraden (Visa/Dölj) uppdateras i aboutToShow → _sync_actions()
closeEvent (X-knapp) → minimera till systray, avsluta EJ
Ikon: QPainter.RenderHint.Antialiasing, blå rundad "S" (64×64 px)
Tooltip: f"Semesterlista v{APP_VERSION}"
Notifikation vid start: "v{APP_VERSION} – Körs i systemfältet"
text


---

## 10. EVENT-SYSTEM (EventBus)

<!--
Alla events som används i applikationen.
-->

### Standard-Events
app:started → {"version": "2.2.0", "app_name": "Semesterlista"}
app:shutting_down
theme:changed → {"theme": "dark|light|system"}
tab:shown → {"name": "plugin_id"}
tab:hidden → {"name": "plugin_id"}
plugin:loaded → {"name": "...", "version": "...", "id": "..."}
plugin:unloaded → {"name": "..."}
plugin:error → {"name": "...", "error": "..."}
window:shown
window:hidden
settings:changed → {"key": "...", "value": "..."}

text


### Plugin-specifika Events
hyresfakturering:pdf_generated → {filename, year,
monthly_count, quarterly_count}
hyresfakturering:file_opened → {file}
hyresfakturering:data_reloaded → {monthly_count, quarterly_count}

semesterlista:pdf_generated → {filename, year, mode, items_count,
months_per_page, start_month,
range_label, spans_year_boundary,
start_year, end_year}
semesterlista:view_shown → {mode}
semesterlista:settings_changed → {settings dict}
semesterlista:folder_opened → {path}

text


### EventBus API
on(event, cb) prenumerera (beständig)
once(event, cb) prenumerera (en gång)
off(event, cb=None) avprenumerera
emit(event, data=None) publicera
get_subscribers(event) → List[Callable]
has_subscribers(event) → bool
subscriber_count(event) → int
get_emit_count(event) → int
list_all_events() → List[str]
clear_all() → None

text


---

## 11. INSTÄLLNINGAR – JSON-STRUKTUR

<!--
Exakt JSON-struktur för alla inställningsfiler.
-->

### data/settings.json
```json
{
  "app_name": "Semesterlista",
  "version": "2.2.0",
  "theme": "system",
  "language": "sv",
  "window": {
    "x": 95,
    "y": 42,
    "width": 1200,
    "height": 800,
    "maximized": false,
    "min_size": {"width": 800, "height": 600}
  },
  "tabs": {
    "visible": [],
    "hidden": [],
    "order": ["hyra", "lista"]
  },
  "systray": {
    "minimize_to_tray": true,
    "start_minimized": true,
    "show_notifications": true,
    "notification_duration_ms": 3000,
    "close_to_tray": true
  },
  "plugins": {
    "enabled": [],
    "disabled": [],
    "auto_load": true
  },
  "advanced": {
    "debug_mode": false,
    "log_to_file": false,
    "log_path": "data/app.log",
    "check_updates": true,
    "autostart": false
  }
}
data/plugins.json
JSON

{
  "Hyresfakturering": {
    "version": "2.2.0",
    "enabled": true,
    "settings": {
      "year": 2026,
      "last_file": "Hyresgäster.txt",
      "last_used": "2026-06-05T10:07:36.623543"
    },
    "last_updated": "2026-06-05T10:07:36.623543"
  },
  "Semesterlista & Limokörning": {
    "version": "2.2.0",
    "enabled": true,
    "settings": {
      "default_mode": "Semesterlista",
      "auto_open_pdf": true,
      "default_year": 2026,
      "last_file": "Anställda.txt",
      "months_per_page": 3,
      "start_month": 0,
      "last_used": "2026-06-05T10:07:36.622580"
    },
    "last_updated": "2026-06-05T10:07:36.622580"
  }
}
config.json (rot)
JSON

{
  "app_name": "Semesterlista",
  "version": "2.2.0",
  "description": "Plugin-baserad desktopapplikation för semesterlistor och hyresfakturering",
  "author": "Rickard Längkvist",
  "copyright": "Rickard Längkvist 2025",
  "python_min": "3.12",
  "framework": "PySide6",
  "data_path": "data",
  "plugins_path": "plugins",
  "log_path": "data/app.log",
  "debug": false
}
12. FÄRGKODNING AV DAGAR – EXAKT DEFINITION
<!-- KRITISKT AVSNITT – Korrekt färgkodning av dagar i PDF. Midsommarafton är GRÖN (halvdag), INTE röd (officiell helgdag). -->
Röda dagar (RED) – Officiella helgdagar + Söndagar
text

RÖDA dagar = officiell helgdag (get_swedish_holidays) ELLER söndag (weekday==6)

Officiella (13 st):
  Nyårsdagen, Trettondedag jul, Långfredag, Påskdagen,
  Annandag påsk, Första maj, Kristi himmelsfärd, Pingstdagen,
  Nationaldagen, Midsommardagen (lördag närmast 24/6),
  Alla helgons dag (lördag 31/10–6/11), Juldagen, Annandag jul

EJ röda (vanliga misstag):
  Midsommarafton  ← GRÖN halvdag
  Julafton        ← GRÖN halvdag
  Nyårsafton      ← GRÖN halvdag
  Påskafton       ← Ej officiell
  Pingstafton     ← Ej officiell
Gröna dagar (GREEN) – Halvdagar
text

GRÖNA dagar = get_half_days() (6 st):
  Skärtorsdag               Dagen före Långfredag
  Valborg                   30 april
  Midsommarafton            Fredagen närmast 24/6  ← GRÖN, EJ röd
  Dag före Alla helgons dag Fredagen före Alla helgons dag
  Julafton                  24 december
  Nyårsafton                31 december
Blå dagar (BLUE) – Lördagar
text

BLÅA dagar = lördag (weekday==5) som EJ är officiell helgdag
OBS: Midsommardagen/Alla helgons dag är lördagar → RÖDA (helgdag trumfar)
Orange linje – Veckoskifte
text

ORANGE LINEBEFORE = ny vecka (ny ISO-vecka börjar)
Oberoende av bakgrundsfärg, gäller alla rader
Prioritetsordning
text

1. RÖD   – Officiell helgdag (trumfar allt)
2. RÖD   – Söndag (weekday==6)
3. GRÖN  – Halvdag (get_half_days)
4. BLÅ   – Lördag (weekday==5)
5. INGEN – Vanlig vardag
+ ORANGE – Veckoskifte (oberoende)
13. MANUELLT VAL AV STARTMÅNAD & ÅRSSKIFTE
<!-- Fullständig beskrivning av startmånad och stöd för årsskifte. -->
Beteende
text

QComboBox i SemesterlistaView (MONTH_OPTIONS, 14 alternativ):
  Index 0:  "Standard (Januari)" → start_month=None → jan–dec valt år
  Index 1:  "Januari"            → start_month=1
  Index 6:  "Juni"               → start_month=6
  Index 12: "December"           → start_month=12 → Dec→Jan nästa år

Valt index sparas i plugin.settings["start_month"] (0–12)
Återställs vid nästa start.
Sidberäkning
text

_build_month_sequence(base_year, start_month):

  start_month=None (standard), base_year=2026:
    [(2026,1),...,(2026,12)]

  start_month=12, base_year=2026:
    [(2026,12),(2027,1),(2027,2),...,(2027,11)]
    → Spänner över två år!
    → Helgdagar hämtas för BÅDA åren

  start_month=6, months_per_page=2:
    Sida 1: Jun 2026, Jul 2026
    Sida 2: Aug 2026, Sep 2026
    Sida 3: Okt 2026, Nov 2026
    Sida 4: Dec 2026, Jan 2027   ← Blandad sida möjlig!
    Sida 5: Feb 2027, Mar 2027
    ...
Filnamn
text

Standard (jan–dec):  semesterlista_2026.pdf
Manuell/årsskifte:   semesterlista_2026_12-2027_11.pdf
Gränssnittsplacering
text

QGroupBox "Inställningar":
  Rad 0: Läge          [Semesterlista ▼]
  Rad 1: År            [2026 ↑↓]
  Rad 2: Startmånad    [Standard (Januari) ▼]
  Rad 3: Månader/blad  [3 ▼]
  Rad 4: Fil           [Anställda.txt] [Bläddra...]
14. AUTOSTART MED OS
<!-- Fullständig beskrivning av autostart-funktionen. -->
Menyplacering
text

Arkiv-menyn:
  Inställningar...
  ✓ Autostart vid inloggning   ← Checkable QAction
  ─────────────────────────────
  Avsluta  Ctrl+Q
Plattformsspecifik implementation
text

Windows:
  Lagras i: HKCU\Software\Microsoft\Windows\CurrentVersion\Run
  Nyckel: "Semesterlista" = "<sökväg till exe>"
  pythonw.exe väljs automatiskt om tillgängligt (inga terminal)

macOS:
  Lagras i: ~/Library/LaunchAgents/com.semesterlista.plist
  launchctl load/unload vid aktivering/avaktivering
  RunAtLoad=true, KeepAlive=false

Linux (XDG Autostart):
  Lagras i: ~/.config/autostart/semesterlista.desktop
  X-GNOME-Autostart-enabled=true
  X-GNOME-Autostart-Delay=5
  Terminal=false
API
text

lock.get_autostart()          → bool
lock.set_autostart(enabled)   → bool
lock.get_autostart_info()     → str (plats på disk/register)
lock.get_autostart_status_text() → "Aktiverad"/"Avaktiverad"
lock.autostart_manager        → AutostartManager (property)

AutostartManager:
  is_enabled() → bool
  enable()     → bool
  disable()    → bool
  set(bool)    → bool
  get_status_text()   → str
  get_platform_info() → str
JSON-synk
text

settings_manager.set("advanced.autostart", True/False)
Synkas vid start: saved_autostart != lock.get_autostart() → lock.set_autostart()
15. SAMMANFATTNING – VAD HAR GJORTS
text

┌──────────────────────────────────────────────────────────────────┐
│               UTFÖRT ARBETE – ALLA SESSIONER                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SESSION 1 – GRUNDLÄGGANDE KONVERTERING (v1.3.0)                │
│   1. core/event_bus.py           Trådsäkert, 11 metoder          │
│   2. core/__init__.py            Lazy loading                    │
│   3. core/settings_manager.py   Atomär JSON, punktnotation       │
│   4. core/single_instance.py    QSharedMemory + socket           │
│   5. core/theme_manager.py      3 teman, QSS                     │
│   6. core/plugin_base.py        Brygga                           │
│   7. plugins/base_plugin.py     ABC                              │
│   8. plugins/hyra/plugin.py     tkinter→PySide6                 │
│   9. plugins/lista/plugin.py    tkinter→PySide6, 270mm, wrap()   │
│  10. main.py                    MainWindow, SystrayManager        │
│  11. data/settings.json         Standardvärden                   │
│  12. data/plugins.json          Plugin-inställningar              │
│  13. config.json (rot)                                           │
│                                                                  │
│  SESSION 2 – SPEC v2.1.0                                        │
│  14. Manuell startmånad spec                                     │
│  15. Korrigerad färgkodning spec (midsommarafton=grön)           │
│  16. Sektion 12 + 13 tillagda i spec                            │
│                                                                  │
│  SESSION 3 – KOD + SPEC v2.2.0                                  │
│  17. plugins/lista/plugin.py  start_month kod + färgfix          │
│       _build_month_sequence() – stöd för årsskifte               │
│       get_swedish_holidays()  – korrekt implementation           │
│       get_half_days()         – midsommarafton=grön              │
│       10 automatiska tester                                      │
│       Filnamn: semesterlista_2026_12-2027_11.pdf                 │
│  18. plugins/lista/__init__.py  v2.2.0                           │
│  19. plugins/hyra/plugin.py     v2.2.0, last_file sparas         │
│  20. plugins/hyra/__init__.py   v2.2.0                           │
│  21. plugins/base_plugin.py     v2.2.0, fullständig docstring    │
│  22. plugins/__init__.py        v2.2.0, AutostartManager export  │
│  23. core/single_instance.py    v2.2.0, AutostartManager klass   │
│       Windows/macOS/Linux autostart                              │
│       _get_executable_path() – pythonw.exe                       │
│  24. core/theme_manager.py      v2.2.0, inverterade knappar      │
│       Ljust=mörka knappar+vit text, Mörkt=ljusa+svart text       │
│       20 widget-typer i QSS                                      │
│  25. core/settings_manager.py   v2.2.0                           │
│       DEFAULT_PLUGIN_SETTINGS, _merge_plugin_defaults()          │
│       autostart i advanced-settings                              │
│  26. core/event_bus.py          v2.2.0, logging istället print   │
│  27. core/__init__.py           v2.2.0, AutostartManager export  │
│  28. core/plugin_base.py        v2.2.0, fullständig docstring    │
│  29. main.py                    v2.2.0, AutostartManager i meny  │
│       Autostart-menyval, COPYRIGHT_YEAR dynamiskt                │
│       Hög DPI, lock=SingleInstanceLock som parameter             │
│  30. data/settings.json         v2.2.0, autostart=false          │
│  31. data/plugins.json          v2.2.0, start_month=0            │
│  32. config.json (rot)          v2.2.0                           │
│  33. Anställda.txt              Exempelfil                        │
│                                                                  │
│  TOTALT: 33 levererade komponenter                              │
│  VERSIONER: Synkade till v2.2.0 i samtliga moduler              │
└──────────────────────────────────────────────────────────────────┘
16. VAD SOM ÄR KVAR ATT GÖRA
text

┌─────┬──────────────────────────────────────────────────┬──────────┐
│  #  │ Uppgift                                          │ Status   │
├─────┼──────────────────────────────────────────────────┼──────────┤
│  1  │ requirements.txt                                 │ ❌       │
│  2  │ Fordon.txt (exempeldatafil)                      │ ❌       │
│  3  │ Hyresgäster.txt (exempeldatafil)                 │ ❌       │
│  4  │ resources/icons/ (app-ikoner 16/32/48/256px)     │ ❌       │
│  5  │ resources/themes/ (dark.qss, light.qss)          │ ❌       │
│  6  │ Testning på Windows med pythonw.exe              │ ❌       │
│  7  │ Wayland-fallback för systray (Linux)             │ ❌       │
└─────┴──────────────────────────────────────────────────┴──────────┘
17. CHECKLISTA (50 Punkter)
text

[✔]  1. main.py – Entry point, dubbelklickbar, inget terminalfönster
[✔]  2. main.py – hide_console_window() på Windows
[✔]  3. main.py – Single-instance-lock innan QApplication skapas
[✔]  4. main.py – Startar ALLTID minimerat (show() anropas ej)
[✔]  5. core/__init__.py – Paket-initiering, exporterar nyckelklasser
[✔]  6. main.py – MainWindow(QMainWindow) med komplett UI
[✔]  7. main.py – _init_ui(): central widget, tabwidget, statusbar
[✔]  8. main.py – _init_menu_bar(): Arkiv, Visa, Utseende, Hjälp
[✔]  9. main.py – _load_plugins(): dynamisk laddning från plugins/
[✔] 10. main.py – Visa/Dölj tabbar via "Visa"-meny (checkboxes)
[✔] 11. main.py – Högerklick på tabb → "Dölj [namn]"
[✔] 12. main.py – Mushjulsscroll på QTabWidget (eventFilter)
[✔] 13. main.py – Dynamisk storlek (fungerar på alla skärmar)
[✔] 14. main.py – _save_window_state() / _restore_window_state()
[✔] 15. main.py – closeEvent → minimera till systray (inte avsluta)
[✔] 16. main.py – Avsluta ENDAST via "Avsluta" i meny/systray
[✔] 17. core/event_bus.py – Alla 11 metoder + logging
[✔] 18. core/settings_manager.py – JSON load/save atomärt
[✔] 19. core/settings_manager.py – Punktnotation nästlade settings
[✔] 20. core/settings_manager.py – Plugin-specifika inställningar
[✔] 21. core/settings_manager.py – DEFAULT_PLUGIN_SETTINGS + merge
[✔] 22. core/single_instance.py – QSharedMemory + QLocalServer
[✔] 23. core/single_instance.py – bring-to-front vid dubbelstart
[✔] 24. core/single_instance.py – Fallback socket-metod
[✔] 25. core/single_instance.py – AutostartManager (Win/Mac/Linux)
[✔] 26. main.py – QSystemTrayIcon med ikon (Antialiasing)
[✔] 27. main.py – Enkelklick = visa/dölj fönster
[✔] 28. main.py – Högerklick = meny (Visa, Dölj, Avsluta)
[✔] 29. main.py – Notifikationer vid start
[ ] 30. main.py – Fallback om systray ej tillgänglig (Wayland)
[✔] 31. main.py – Autostart-menyval (Arkiv → Autostart)
[✔] 32. core/theme_manager.py – 3 teman: dark, light, system
[✔] 33. core/theme_manager.py – Mörkt: ljusa knappar + svart FET
[✔] 34. core/theme_manager.py – Ljust: mörka knappar + vit FET
[✔] 35. core/theme_manager.py – Inverterade knappar/tabbar
[✔] 36. core/theme_manager.py – System-tema följer OS
[✔] 37. core/theme_manager.py – QSS 20 widget-typer, alla tillstånd
[✔] 38. plugins/base_plugin.py – Abstrakt basklass (ABC)
[✔] 39. plugins/base_plugin.py – get_name/version/tab_widget
[ ] 40. resources/ – Ikoner (16/32/48/256px)
[ ] 41. resources/ – dark.qss och light.qss
[✔] 42. data/ – settings.json med standardvärden + autostart
[✔] 43. data/ – plugins.json med plugin-inställningar + start_month
[✔] 44. config.json (rot) – korrekt format v2.2.0
[ ] 45. requirements.txt – PySide6>=6.7.0, reportlab
[✔] 46. lista/plugin.py – Val av 2 eller 3 månader per blad
[✔] 47. lista/plugin.py – Autoskalning _apply_table_scaling()
[✔] 48. lista/plugin.py – Manuell startmånad + årsskifte
[✔] 49. lista/plugin.py – Midsommarafton = grön (ej röd)
[✔] 50. lista/plugin.py – 10 automatiska tester

STATUS: 44 av 50 klara (88%)
18. KÄNDA FEL/BUGGAR & ÅTGÄRDSPLAN
text

┌─────┬──────────────────────────────────────┬───────┬──────────────────────────────┐
│  #  │ Bug/Fel                              │ Allv. │ Åtgärdsplan                  │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  1  │ Terminalfönster vid .py-start        │ MED   │ pythonw.exe / .pyw /         │
│     │ (Windows)                            │       │ ctypes HideWindow ✅          │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  2  │ QSystemTrayIcon på Wayland (Linux)   │ HÖG   │ AyatanaAppIndicator3         │
│     │ fungerar ej                          │       │ eller visa fönster normalt   │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  3  │ QSharedMemory kvar efter krasch      │ LÅG   │ _cleanup_stale_lock() ✅     │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  4  │ Plugin med syntaxfel                 │ HÖG   │ try/except i load_plugin ✅  │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  5  │ Temabyte tappar custom QSS           │ MED   │ _apply_theme() kopplas till  │
│     │                                      │       │ theme_changed signal ✅       │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  6  │ Högerklick på tabb – fel index       │ LÅG   │ tabBar().tabAt(pos) ✅       │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  7  │ JSON-korruption vid avbruten skrivn. │ LÅG   │ Atomär .tmp→rename ✅        │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  8  │ EventBus callback exceptions         │ LÅG   │ logger.error + exc_info ✅   │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│  9  │ EventBus race conditions             │ MED   │ threading.Lock ✅            │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│ 10  │ Hög DPI – suddiga widgets            │ MED   │ PassThrough policy ✅        │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│ 11  │ HTML-artefakter vid copy/paste       │ HÖG   │ ⚠️ Använd copy-knappen      │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│ 12  │ Midsommarafton felaktigt röd         │ HÖG   │ Fixat i v2.2.0 ✅            │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│ 13  │ Ingen manuell startmånad             │ MED   │ Implementerat i v2.2.0 ✅    │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│ 14  │ Autostart ej tillgängligt            │ LÅG   │ Implementerat i v2.2.0 ✅    │
│     │                                      │       │ Win/macOS/Linux              │
├─────┼──────────────────────────────────────┼───────┼──────────────────────────────┤
│ 15  │ Knappar osynliga vid temabyte        │ HÖG   │ Fixat i v2.2.0 ✅            │
│     │                                      │       │ Inverterade knappar alltid   │
└─────┴──────────────────────────────────────┴───────┴──────────────────────────────┘
19. FRAMTIDSPLAN
text

Version 2.2.0 – KLAR (88%)
  [✔] EventBus + logging
  [✔] Autostart Win/macOS/Linux
  [✔] Manuell startmånad + stöd för årsskifte
  [✔] Korrigerad färgkodning (midsommarafton=grön)
  [✔] Inverterade knappar (alltid tydliga)
  [✔] 20 widget-typer i QSS
  [✔] DEFAULT_PLUGIN_SETTINGS + auto-merge
  [✔] Dynamiskt copyright-år
  [✔] Hög DPI

Version 2.3.0 – FÖRBÄTTRINGAR
  [ ] requirements.txt
  [ ] Fordon.txt + Hyresgäster.txt (exempelfiler)
  [ ] Wayland-fallback (Linux systray)
  [ ] resources/icons/ (16/32/48/256px)
  [ ] resources/themes/ (dark.qss, light.qss)
  [ ] Export/Import av inställningar (UI)
  [ ] Loggning till fil (log_to_file=true)
  [ ] First-run wizard
  [ ] Snabbkommandon (QShortcut)

Version 2.4.0 – AVANCERAT
  [✔] Hantering av anställda/fordon/hyresgäster (core/roster.py)
  [✔] Listredigerare i appen (core/list_editor_dialog.py)
  [✔] Enhetstester för listorna (tests/test_roster.py)
  [✔] Fler språk (i18n)
  [ ] Plugin-sandbox
  [ ] Prestandaövervakning
  [ ] Crash reporter
  [ ] Plugin-paketering (zip)

Version 3.0.0 – FRAMTID
  [ ] Webbgränssnitt (FastAPI + React)
  [ ] Molnsynkronisering
  [ ] Plugin-marknad
  [ ] Profil-/användarhantering (på begäran)

---

## 20. HANTERING AV LISTOR – ANSTÄLLDA, FORDON & HYRESGÄSTER (v2.4.0)

<!--
Allt som rör textlistorna: format, inläsning, redigering och skrivning.
-->

### 20.1 Varför

Tidigare lästes listorna på tre olika sätt:

| Fil | Tidigare | Problem |
|-----|----------|---------|
| `Anställda.txt` / `Fordon.txt` | `open(..., encoding="utf-8")` och rad för rad | kraschade/tappade tecken vid cp1252, kommentarer blev "namn", dubbletter gick rakt in i PDF:en, ingen möjlighet att redigera i appen |
| `Hyresgäster.txt` | egen `split("-------")` med `encoding="utf-8"` | samma brister, plus att filen skrevs icke-atomärt |

Nu finns **en** implementation (`core/roster.py`) som alla tre listorna
använder, och en gemensam redigerare (`core/list_editor_dialog.py`).

### 20.2 Filformat

```text
# Anställda – en post per rad
# Rader som börjar med # eller ; ignoreras
Anna Andersson
Bertil Bengtsson

-------
# Hyresgäster: allt efter strecken blir sektion 2
Företag AB
Konsult & Co
```

| Regel | Beteende |
|-------|----------|
| Kommentar | rad som börjar med `#` eller `;` ignoreras (sparas som rubrik) |
| Tom rad | ignoreras |
| Sektionsbrytare | rad med minst 3 streck (`---`, `-------`) |
| Blanksteg | trimmas, flera blanksteg slås ihop, hårt mellanslag blir vanligt |
| Dubbletter | tas bort vid inläsning (skiftlägesokänsligt) och rapporteras |
| Teckenkodning | UTF-8 (med/utan BOM) → cp1252 → latin-1 |
| Spara | UTF-8 utan BOM, CRLF, atomärt (tmp → rename) + `*.bak` |

### 20.3 Redigering i appen

```text
Semesterlista & Limokörning:
    Fil: [Anställda.txt] [Bläddra...] [📝 Hantera lista…]
    8 poster i filen

Hyresfakturering:
    [📝 Hantera hyresgäster…] [🔄 Ladda om]
```

Redigeraren visar en lista per sektion (Hyresgäster.txt får två flikar) med:

| Knapp | Funktion |
|-------|----------|
| Lägg till | ny post (QInputDialog, max 80 tecken) |
| Ändra | dubbelklick eller knapp – dubbletter avvisas |
| Ta bort | markerade poster (bekräftas vid flera) |
| Upp / Ner | ändra ordning (påverkar PDF:ens radordning) |
| Sortera A–Ö | svensk sortering, Å/Ä/Ö efter Z |
| Klistra in flera… | klistra in en lista, en post per rad |
| Öppna i textredigerare | samma fil i Anteckningar/TextEdit |
| Spara | validerar, skriver atomärt och skapar backup |

### 20.4 Validering

| Nivå | Exempel | Effekt |
|------|---------|--------|
| error | dubblett, tom post, > 80 tecken | sparning blockeras, felet visas |
| warning | post > 40 tecken (trång i PDF), listan tom | fråga "Vill du spara ändå?" |

### 20.5 Bakåtkompatibilitet

- Befintliga filer fungerar oförändrat (samma enkel-radsformat).
- Filer som sparats i cp1252 läses korrekt och sparas som UTF-8 nästa gång.
- `Hyresgäster.txt` skapas fortfarande med exempelposter första gången;
  `Anställda.txt` och `Fordon.txt` skapas tomma (med rubrik) när man
  öppnar redigeraren.
- Kommentarer som låg mitt i listan flyttas till filens rubrik vid sparning.

### 20.6 Tester

```bash
python -m unittest discover -s tests -v      # 165 tester
```

`tests/test_roster.py` täcker inläsning (kommentarer, BOM, CRLF, cp1252,
dubbletter, sektioner), redigering (lägg till/ändra/ta bort/flytta/sortera),
validering och skrivning (UTF-8, CRLF, backup, tmp-städning).

---

## 21. FLIKAR & LOGOTYP I PDF (v2.5.0)

### 21.1 Flikar – hyra, semester, fordon

| Flik | Plugin | Läge | Standardfil | Tabb |
|------|--------|------|-------------|------|
| 🏠 Hyra | `plugins/hyra` | – | `Hyresgäster.txt` | 1 |
| 📅 Semesterlista | `plugins/lista` | `Semesterlista` (låst) | `Anställda.txt` | 2 |
| 🚗 Fordon | `plugins/fordon` | `Limokörning` (låst) | `Fordon.txt` | 3 |

- Lägesväljaren ("Semesterlista"/"Limokörning") döljs när fliken har ett
  fast läge – fel lista kan inte skrivas ut av misstag.
- Flikarna kan fortfarande döljas/visas via **Visa**-menyn och
  högerklick på fliken; inställning görs i `data/plugins.json`
  (`enabled: false`).
- Namnen översätts: sv *Hyra/Semesterlista/Fordon*, en *Rent/Vacation
  Schedule/Vehicles*.

### 21.2 Logotyp i PDF

1. Lägg bilden i `assets/` eller en undermapp (t.ex.
   `assets/logotyper/`). SVG rekommenderas.
2. Klicka **🖼️ Välj logotyp…** i fliken och välj fil
   (förhandsgranskning + **Använd**).
3. Logotypen ritas i övre högra hörnet på **varje sida** vid export –
   både i Hyreslistan och i Semester-/Fordonslistan.
4. **Ta bort** tar bort logotypen igen.

Lagring: `data/plugins.json` → respektive plugin → `settings.logo_svg`
(tom sträng = ingen logotyp). Relativa sökvägar tolkas mot appens rot.

Storlek: max 35 × 16 mm (Semesterlista/Fordon), 30 × 12 mm (Hyra);
proportionerna bevaras alltid.

### 21.3 Felsökning

| Symptom | Orsak / åtgärd |
|---------|----------------|
| "Inga bilder hittades i assets-mappen" | Mappen saknas/tom – lägg en SVG eller PNG där |
| "Saknas: filnamn" i fliken | Filen är flyttad – välj logotyp igen |
| SVG syns men blir suddig | `svglib` saknas → rasteriseras i 300 dpi; installera `svglib` för vektor |
| Logotypen syns inte i PDF:en | Kontrollera att rätt flik valts – inställningen sparas per flik |

### 21.4 Tester

```bash
python -m unittest discover -s tests -v      # 165 tester
```

`tests/test_pdf_assets.py` täcker sökning i undermappar, dolda filer,
filtrering på ändelse, skalning/proportioner, PNG-ritning i PDF,
logotyp på varje sida via `canvasmaker` samt felhantering (`AssetError`).

---

## 22. LOGGNING & FELSÖKNING (v2.8.0)

### 22.1 Vad som loggas

| Händelse | Nivå | Exempel |
|----------|------|---------|
| Uppstart, steg för steg | INFO | `STEG 7b  Plugins laddade  12 ms (totalt 480 ms) 3 st` |
| Miljö (Python, Qt, OS) | INFO | `python = 3.12.4 …`, `platform = Windows-11…` |
| Plugin laddad | INFO | `✓ Semesterlista & Limokörning v2.8.0  9 ms` |
| Plugin misslyckad | ERROR | `✗ fordon  kunde inte laddas` |
| PDF skapad | INFO | `… 12 månader, 6 sidor, 84 kB, 210 ms` |
| Inställningar sparade | INFO | `språk=sv, tema=light, plugins={…}` |
| Ohanterat fel | CRITICAL | traceback + `Loggfil: …/data/loggar/app.log` (även i `fel.log`) |
| Qt-varningar | WARNING | `qt: QWidget::setLayout: …` |

### 22.2 Felsökningsläge

```bash
set SEMESTERLISTA_DEBUG=1     # Windows (cmd)
export SEMESTERLISTA_DEBUG=1  # macOS/Linux
python main.pyw
```

…eller **Arkiv → Inställningar → Avancerat → Felsökningsläge** (sparas som
`advanced.debug_mode`). `data/loggar/app.log` får då även DEBUG-rader; appens
loggmoduler (`main`, `core`, `plugins`) loggar alltid INFO.

### 22.3 Vanliga fel

| Symptom | Trolig orsak | Åtgärd |
|---------|--------------|--------|
| Appen startar inte alls (pythonw) | Importfel – ingen konsol att se felet i | Läs `data/loggar/app.log`, kör `python main.pyw` i terminal |
| `ModuleNotFoundError: core.settings_dialog` | Filen saknas/är inte synkad | `git pull`; menyvalet är inaktiverat men appen startar |
| Ingen `data/loggar/app.log` | `data/` är inte skrivbar | Loggen hamnar i `%TEMP%/Semesterlista/app.log` |
| Krasch utan traceback | Fel i Qt/C++ | Läs `data/crash.log` (faulthandler) |
| Loggen är tom | `advanced.log_to_file` av | Slå på i Avancerat-fliken |

### 22.4 Loggarna har en egen mapp (v2.12.0)

```
data/loggar/
├── app.log          aktuell dag (roterar vid 2 MB, 5 filer: app.log.1–5)
├── fel.log          alla ERROR/CRITICAL – arkiveras aldrig
└── arkiv/
    ├── app-2026-11-02.log
    └── app-2026-11-03.log
```

| Regel | Beteende |
|-------|----------|
| **Egen undermapp** | Allt hamnar i `data/loggar/` i stället för direkt i `data/` |
| **Dagarkivering** | Vid start (och vid midnatt om appen är igång) flyttas en `app.log` vars **ändringsdatum** är en tidigare dag till `arkiv/app-<dag>.log`. En ny, tom `app.log` skapas. Flera omstarter samma dag lägger till i samma arkivfil |
| **Egen fellogg** | Endast **ERROR** och **CRITICAL** hamnar i `fel.log`. Filen arkiveras aldrig – felen ligger kvar tills de är åtgärdade |
| **Rensa felloggen** | Inställningar → Avancerat → *Rensa felloggen* (bekräftelse krävs). Filen töms men finns kvar |
| **Reservplats** | Går `data/` inte att skriva i hamnar loggen i `%TEMP%/Semesterlista/loggar/` (arkivering och fellogg följer med) |

Koden: `archive_previous_days()`, `archive_target()`, `DailyArchiveFileHandler`,
`_RotatingDailyFileHandler` (storleksrotering + dagarkivering), `_setup_error_log()`,
`error_log_path()`, `tail_error_log()`, `error_log_lines()`, `clear_error_log()`.

`data/loggar/**` står i `.gitignore` och rörs aldrig av uppdateraren
(`.log`-filer hoppas över, hela `data/` bevaras).


### 22.5 Årbytet i Hyra-fliken (fixat i v2.8.1)

**Symptom:** när man bytte år i **Hyra**-fliken blev hela sidan tom.

**Orsak:** `_on_year_change()` → `_refresh_quarter_panel()` → `_refresh_ui()`
anropade `_init_ui()`, som gjorde `QVBoxLayout(self)` på nytt. Widgeten hade
redan en layout, och Qt vägrar då installera den nya
(`QLayout: Attempting to add QLayout … which already has a layout`). Den nya
layouten hamnade utanför widgeten – kvar blev en tom sida (0 layoutobjekt).

**Åtgärd:**

| Före | Efter |
|------|-------|
| Ny `QVBoxLayout(self)` vid varje ombyggnad | Rotlayouten `self._main_layout` skapas en gång och återanvänds |
| Hela vyn revs vid årbyte | Bara kvartalskorten byts med `layout.replaceWidget()` – fokus ligger kvar i årväljaren |
| Gamla widgetar låg kvar som barn | `hide()` + `setParent(None)` + `deleteLater()` kopplar loss dem direkt |
| `_clear_layout()` användes på widgetens layout | Används bara på rotlayoutens innehåll, aldrig på widgeten själv |

Regressionstester: `tests/test_hyra_view.py` (8 tester) – årbytet behåller
layouten, korten uppdateras, panelen dupliceras inte, ingen
”already has a layout”-varning och ”Ladda om” fungerar fortfarande.

### 22.6 Tester

```bash
python -m unittest discover -s tests -v      # 165 tester
```

`tests/test_logging_setup.py` (24 tester) täcker sökvägsval, reservplats,
format, nivåer, `SEMESTERLISTA_DEBUG`, rotering, `tail_log`/`log_summary`,
excepthook (inkl. `KeyboardInterrupt`), faulthandler och `reset_logging`.
`tests/test_settings_dialog.py` (22 tester, offscreen) täcker de fyra
flikarna, inläsning, sparande, språk-/temabyte, autostart, plugin-status
och att dialogen fungerar utan valfria komponenter.

---

### 22.4 Varningar som åtgärdats (2026-11-03)

Loggen från en riktig körning (Windows 11, Python 3.14) visade två varningar
som nu är rättade:

| Varning | Orsak | Åtgärd |
|---------|-------|--------|
| `SyntaxWarning: "\S" is an invalid escape sequence` (`core/single_instance.py:14` och `:852`) | Windows-sökvägarna `HKCU\Software\…` låg i vanliga docsträngar | Docsträngarna är **råa** (`r"""`); `tests/test_no_warnings.py` kompilerar alla moduler med `SyntaxWarning` som fel |
| `setHighDpiScaleFactorRoundingPolicy must be called before creating the QGuiApplication instance` | Anropet låg **efter** `QApplication(...)` i `main.pyw` | Anropet flyttat till radan före `QApplication(sys.argv)` (i `try/except` för äldre Qt) |

Kvarstår: `QFont::setPointSize: Point size <= 0 (-1)` kommer inte från appens
kod (ingen `setPointSize` finns i repot) utan från Qt:s egen stilmall – den är
ofarlig och påverkar inte PDF:en.

## 23. UPPDATERING FRÅN GITHUB (v2.9.0)

### 23.1 Knappen

Uppdateringen finns på två ställen:

| Ställe | Vad som händer |
|--------|----------------|
| **Hjälp → Sök efter uppdatering…** | Öppnar Inställningar på fliken **Avancerat** och söker direkt |
| **Inställningar → Avancerat → Uppdatering** | Knapparna *Sök efter uppdatering*, *Uppdatera nu* och *Öppna release-sidan* |

Gruppen visar nuvarande version, senaste versionens publiceringsdatum och
de första raderna ur release-anteckningarna.

### 23.2 Flöde

1. **Sök** – `GET /repos/Tokke2/Semesterlista/releases/latest`, sedan
   `GET /contents/config.json?ref=<tagg>` för att få appens version.
   Sker i en bakgrundstråd; knappen är avstängd under tiden.
2. **Jämför** – `is_newer("2.9.1", "2.9.0")` → *Uppdatera nu* aktiveras
   bara om releasen är nyare.
3. **Bekräfta** – fråga: *Uppdatera från 2.9.0 till 2.9.1?*
4. **Ladda ner** – zipball (≈350 kB) med procent i statusraden.
5. **Installera** – säkerhetskopia → filerna skrivs via `.new`-temp + `os.replace`.
6. **Starta om** – fråga; *Ja* startar om appen med `QProcess.startDetached`.

### 23.3 Release-rutin (krav)

Varje kodändring ska publiceras som en ny release, annars når den inte
användarna – uppdateraren tittar bara på **senaste releasen**.

| Steg | Kommando / åtgärd |
|------|-------------------|
| 1 | `python -m unittest discover -s tests` – grönt |
| 2 | `python tools/bump_version.py <ny version>` (19 ställen, bl.a. `config.json`) |
| 3 | `python tools/bump_version.py --check` – ”Alla ställen är synkade.” |
| 4 | commit + push till branchen |
| 5 | `git tag v0.0.x -m "Semesterlista <version>"` och `git push origin v0.0.x` |
| 6 | `gh release create v0.0.x --title … --notes-file …` |

Taggens `config.json` är det som jämförs med appens `APP_VERSION`, så
versionen måste vara höjd **före** taggen. Release-anteckningarna syns i
uppdateringsrutan och via *Öppna release-sidan*.

### 23.4 Automatisk kontroll vid start

Om **Avancerat → Sök efter uppdatering vid start** är ikryssad
(`advanced.check_updates`, standard på) söker `StartupUpdateChecker` i
bakgrunden efter `app:started`. Hittas en nyare version visas en avisering i
systemfältet – inget installeras automatiskt. Utan nät loggas felet och
appen startar som vanligt.

### 23.5 Felsökning

| Symptom | Orsak | Åtgärd |
|---------|-------|--------|
| ”Ingen release hittades” | Ingen publik release på GitHub | Skapa en release, eller använd *Öppna release-sidan* |
| ”GitHub nekade åtkomst (403)” | Rate limit (60 anrop/timme) | Vänta en stund |
| ”Kunde inte skriva … filen kan vara låst” | Filen är låst (Windows) | Stäng appen och försök igen |
| ”Releasen (x) är inte nyare” | Samma eller äldre version | Inget att göra |
| Ingen avisering vid start | `advanced.check_updates` av eller inget nät | Slå på i Inställningar |

Allt loggas till `data/loggar/app.log` (se kap. 22).

### 23.6 Tester

`tests/test_updater.py` (24 tester, helt offline): versionstolkning,
jämförelse, sökning med mockat API, fallback till taggen, nätverksfel,
uppackning (inkl. `../`-skydd och trasig zip), verifiering av innehåll,
installation mot en temporär appmapp (programfiler uppdateras, `data/` och
listorna orörda, säkerhetskopia skapad), torrkörning, vägran av äldre
release samt omstarts-kommandot. Uppdateringsdelen i inställningsdialogen
täcks av 7 tester i `tests/test_settings_dialog.py`.

---

## 24. LOGOTYP-DROPDOWN & AUTOMATISK STORLEK (v2.10.0)

### 24.1 Knappen

Logotypen väljs i en dropdown som listar **alla SVG-logotyper i appens mapp
`assets/` och dess undermappar** (t.ex. `logotyper/exempel-logotyp.svg`).
Andra bildformat (PNG/JPG) listas inte, men kan fortfarande infogas med
*Infoga SVG…* och ritas då som vanligt i PDF:en.
Widgeten är `core/logo_picker.py::LogoPicker` och finns i två vyer:

| Vy | Placering | Förhandsgranskning |
|----|-----------|--------------------|
| **Semesterlista / Limokörning** | Egen rad i inställningsrutan, under *Fil med anställda* | Ja (56 px hög, skalas med fönstret) |
| **Hyra** | I verktygsraden före *Hantera hyresgäster…* | Nej (`show_preview=False`) |

Knappar: **🖼️ Infoga SVG…** (välj bild utanför `assets/`), **Uppdatera
lista** (läs om mappen). Valet sparas direkt som `logo_svg` i pluginets
inställningar – ingen separat *Spara*-knapp.

### 24.2 Automatisk storlek i PDF:en

`PdfLogo.auto_size(page_w, page_h)` räknar ut storleken för **varje sida**:

| Regel | Värde |
|-------|-------|
| Ruta – bredd | 15 % av sidans bredd |
| Ruta – höjd | 8 % av sidans höjd |
| Tak | 60 × 25 mm (gäller även stora sidor) |
| Minsta ruta | 36 × 12 pt (gäller även små sidor) |
| Proportioner | Bevaras alltid – skalas både upp och ned |

Resultat för A4 (exempellogotyp 2,5:1):

| Sidlayout | Sida (pt) | Logotyp (pt) | Logotyp (mm) |
|-----------|-----------|--------------|--------------|
| Liggande | 842 × 595 | 119,0 × 47,6 | 42,0 × 16,8 |
| Stående | 595 × 842 | 89,2 × 35,7 | 31,5 × 12,6 |

Marginalen till sidkanten är 6 mm i Semesterlista och 8 mm i Hyra.
`draw_corner(..., auto_size=False)` finns kvar för att rita logotypen i
sin naturliga storlek (används av testerna).

### 24.3 Tester

`tests/test_logo_picker.py` (16 tester): listan fylls med **endast SVG** från
`assets/` + undermappar (även djupt liggande filer), post 0 = *Ingen
logotyp*, val/`clear()`/`refresh()` och `changed`-signalen, fil utanför
`assets/`, trasig fil → feltext, förhandsgranskningen skalas proportionellt
och följer ytan.

`tests/test_pdf_assets.py::PdfLogoAutoSizeTests` (7 tester): liggande och
stående A4, extremt breda/höga logotyper, tak och minsta ruta, samt
`draw_corner` med `auto_size` av/på.

`tests/test_systray.py` (10 tester): menyns innehåll och ordning,
*Inställningar…*/*Sök efter uppdatering…*/*Om …* kopplade till rätt
metoder, *Visa*/*Dölj* som speglar fönstrets läge (även standardvalet) och
att texterna följer språkbytet.

---

## 25. SMART CACHE (v2.11.0)

### 25.1 Varför

SVG-logotyper rastreras till PNG (300 dpi) första gången de används, så att
samma logotyp bara behöver renderas en gång per körning. Filerna hamnade
tidigare i `%TEMP%/Semesterlista/logotyper/` och **städades aldrig** – på en
dator där appen används dagligen växer mappen i det tysta.

### 25.2 Hur den fungerar

`core/cache.py` äger appens temp-mapp och städar den **smart**:

| När | Vad som händer |
|-----|----------------|
| **Vid start** | `clean_stale()` tar bort cachefiler äldre än 1 timme. Färska filer behålls, så en snabb omstart inte tvingar fram nya renderingar. |
| **Vid avslut** | `purge()` tar bort hela appens cache (logotyper + kvarlämnade `semesterlista_uppdatering_*`-mappar från kraschade uppdateringar) och loggar `Cache rensad: 12 filer, 0 mappar, 0.4 MB frigjort`. |
| **Alltid** | Endast `%TEMP%/Semesterlista` och `semesterlista_*`-rester rörs. Låsta filer (t.ex. öppna i en PDF-läsare) hoppas över och loggas som debug. |

Inställningen **Avancerat → Rensa cache vid avslut** (`advanced.clear_cache_on_exit`,
standard **på**) styr städningen vid avslut. Under rutan visas aktuell
cachestorlek ("Cache: 13 kB"). Slås den av ligger filerna kvar till nästa
start, då `clean_stale()` tar dem när de är äldre än en timme.

### 25.3 Tester

`tests/test_cache.py` (16 tester): sökvägarna, `purge()` (inkl. filer i bruk,
torrkörning, låsta filer och att andra programs temp-filer aldrig rörs),
`clean_stale()` (färska filer behålls, gamla tas bort, egen tröskel),
storleksberäkning och att `atexit`-krokens städning är idempotent och aldrig
kastar fel. Dessutom två tester i `tests/test_settings_dialog.py` för
kryssrutan och att valet sparas.

---

## 26. LEDIGA DAGAR I LISTFILEN (v2.11.0)

### 26.1 Varför

Semesterlistan visar när alla är på plats – men inte när någon är **borta**.
Semester, föräldraledighet och tjänstledighet fick tidigare markeras för hand
efter utskriften. Nu skrivs frånvaron direkt i `Anställda.txt`, på samma rad
som namnet, och PDF:en markerar dagarna automatiskt.

### 26.2 Så skrivs det

```
# Anställda.txt
Anna Andersson ; 18/12 - 7/1
Roland: 18/12-7/1
Bertil Bengtsson
Cecilia Carlsson | 6/7 - 20/7, 3/8 - 17/8
```

Namncellen i PDF:en innehåller **bara namnet** – frånvaron syns som kryss i
dagcellerna och aldrig som text i listan.

| Del | Regel |
|-----|-------|
| **Avskiljare** | `;`, `\|` eller `:` mellan namn och frånvaro (valfritt mellanslag runt). `;`/`\|` delar alltid raden; `:` delar bara när det följer ett datum, så `Avdelning: Ekonomi` fortsätter vara ett namn |
| **Period** | `start - slut`, flera perioder separeras med `,` **eller** ordet `och` (**även `;`** inuti frånvaron) |
| **Datumformat** | `18/12`, `18/12/2026`, `2026-12-18` (ISO) |
| **Saknat år** | listans år; om slutet ligger före starten menas **nästa år** (så `18/12 - 7/1` blir rätt) |
| **Enstaka datum** | `18/12` markerar bara den dagen – ingen veckosnäppning |

**Veckosnäppning** – perioden blir alltid en eller flera hela veckor:

| Datum | Blir |
|-------|------|
| **Start:** måndag–torsdag | måndagen **före** (torsdag ligger 3 dagar efter måndagen) |
| **Start:** fredag–söndag | måndagen **efter** |
| **Slut:** torsdag–söndag | söndagen **efter** (torsdag ligger 3 dagar före söndagen) |
| **Slut:** måndag–onsdag | söndagen **före** |

Exempel: `18/12 - 7/1` (fredag → måndag, torsdag → söndag) blir
**21/12 2026 – 10/1 2027**, alltså tre hela veckor. Snäppningen gäller även
`18/12/2026` och `2026-12-18`.

Två skyddsnät: en **enstaka dag** (`18/12`, eller `6/7 - 6/7`) rörs inte, och
om slutet skulle hamna före starten efter snäppningen (t.ex. `6/7 - 7/7`,
mån–tis) behålls de exakta datumen – en kort ledighet försvinner aldrig.

En rad som **börjar** med `;` är fortfarande en kommentar (se kap 20), och
raden får vara högst `MAX_ENTRY_LENGTH` (80) tecken inklusive frånvaron.

### 26.3 `core/leave.py`

| Funktion / klass | Gör |
|------------------|-----|
| `snap_to_monday(day)` | Flyttar ett datum till närmaste måndag (periodens **start**) |
| `snap_to_sunday(day)` | Flyttar ett datum till närmaste söndag (periodens **slut**) |
| `snap_range(start, end)` | måndag → söndag, med skydd för enstaka dagar och korta perioder |
| `parse_leave(text, default_year=None, snap=True)` | Text → `list[LeaveRange]`; höjer `LeaveError` vid skräp |
| `split_entry(line)` | `"Anna ; 18/12 - 7/1"` → `("Anna", "18/12 - 7/1")`, `"Roland: 18/12-7/1"` → `("Roland", "18/12-7/1")` |
| `looks_like_leave(text)` | True om texten innehåller ett datum (används av `:`) |
| `format_leave(ranges)` | Tillbaka till `21/12-4/1, 3/8-17/8` |
| `LeaveRange` | Fryst dataclass: `contains()`, `days()`, `overlaps_month()`, `str()` = `2026-12-21 – 2027-01-04` |
| `LeaveCalendar` | `from_lines()`, `add_line()`, `ranges_for()`, `is_off(namn, datum)`, `off_dates()`, `names_with_leave()`, `errors`, `len()` |

Namnmatchningen är skiftlägesokänslig och normaliserar blanksteg, så
`ANNA  ANDERSSON` hittar samma person som `Anna Andersson`. Rader som inte
går att tolka **stoppar inte** PDF:en – de loggas som varning och hamnar i
`errors`.

### 26.4 Kopplingen till listan och PDF:en

- `core/roster.py`: ny **`read_entries()`** ger `(namn, frånvaro)` per rad.
  `read_names()` returnerar fortsatt bara namnen – frånvaron tas bort, så
  alla andra flikar (Fordon, Hyra) påverkas inte.
- `plugins/lista/plugin.py`: `_read_list_from_file()` fyller
  `self._leave_calendar`; `_generate_pdf(..., leave=None)` tar emot en
  kalender (standard: den inlästa).
- **PDF:** lediga dagar skrivs som ett **fet kryss** (×) i en **gråblå** cell
  (`LEAVE_COLOR = 0.35, 0.38, 0.45`, vit `Helvetica-Bold` i
  `LEAVE_FONT_SIZE` = celltexten + 3 punkter). Markeringen ligger överst i
  färgprioriteringen, så en ledig lördag blir grå – inte blå. Tecknet `×`
  (U+00D7) finns i Latin-1 och fungerar med Helvetica.
- **Förklaringar:** PDF-legendens femte ruta (`lista.pdf.legend.leave`,
  ”Grå = Ledig”) och vyns färgförklaring (`lista.legend.leave`).
- **Listredigeraren** visar en hjälptext överst (`roster.leave.hint`) med
  exemplet `Anna Andersson ; 18/12 - 7/1`. Redigeraren sparar raden orörd,
  så frånvaron försvinner inte när listan ändras.

### 26.5 Färgprioritet i tabellen

1. Röd – helgdag eller söndag
2. Grön – halvdag
3. Blå – lördag
4. **Grå med × – ledig (vinner över 1–3 för den personens rad)**
5. Orange linje – ny vecka

### 26.6 Tester

| Fil | Antal | Innehåll |
|-----|-------|----------|
| `tests/test_leave.py` | 57 | veckosnäppning till måndag **och** söndag (alla veckodagar), årskifte, ISO/explicit år, flera perioder, `split_entry` (alla tre avskiljarna), `looks_like_leave`, `is_off`, `off_dates`, felhantering |
| `tests/test_pdf_leave.py` | 11 | cellmarkering i december/januari (fångar tabelldata), namncell utan frånvaro, kryssets storlek, ingen markering utan frånvaro, legendens fem rutor, Latin-1, inläsning från fil (även `:`-formatet) |
| `tests/test_list_editor.py` | 3 | hjälptexten (sv/en) och att raden behålls orörd |
| `tests/test_roster.py` | +4 | `read_names()` tar bort frånvaro, `read_entries()`, kolon som bara delar vid datum |

Svitens total: **370 tester**.


---

## 27. Layout som anpassas till listan (v2.11.0)

PDF:en får aldrig visa en tabell som klipps av eller delas mitt i. Sedan
v2.11.0 mäts innehållet **före** ritning och layouten anpassas efter listans
längd.

### 27.1 Färgförklaringen på en rad

`_create_legend_with_colors()` bygger en tabell med **tio celler** (fem
färgrutor + fem etiketter). Etiketterna är `Paragraph` med stilen
`LegendLabel` (7 pt) och proportionella kolumnbredder, så långa texter som
”Grön = Halvdag (midsommarafton, julafton m.fl.)” **radbryts** i stället för
att klippas eller skriva över nästa ruta.

### 27.2 Månader per blad mäts fram

| Steg | Vad som händer |
|------|----------------|
| 1 | `page_geometry()` + marginaler ger `frame_width` och `available_height` (ramens 6 pt luft räknas bort, `FRAME_PADDING`) |
| 2 | `_estimate_header_height()` mäter rubrik + färgförklaring |
| 3 | `_estimate_month_height()` bygger en provtabell med samma kolumnbredder, typsnitt och luft och mäter den |
| 4 | `_fit_layout()` provar kandidaterna `(3,16) (3,12) (2,12) (2,8) (1,8) (1,4) (0,4) (0,2)` = (radluft, mellanrum). Först när ingen radluft räcker sänks antalet månader |
| 5 | Budgeten är `available_height − PAGE_SAFETY` (8 pt) |

Resultat för 12 månader (start oktober 2026, liggande A4):

| Anställda | 3 mån/blad | 2 mån/blad |
|-----------|------------|------------|
| 3–9 | **4 sidor** (3 mån/blad) | 6 sidor |
| 10–16 | **6 sidor** (2 mån/blad, anpassat) | 6 sidor |

Antalet som faktiskt används syns i loggen, i ”Klart”-rutan och i
`semesterlista:pdf_generated`.

### 27.3 Sidbrytning utan klippta tabeller

- Varje månad får plats mätas före `elements.append(table)`. Räcker inte
  utrymmet läggs en `PageBreak()` och **samma rubrik + färgförklaring byggs
  om för den nya sidan** (`build_header(months)`).
- `repeatRows=3` upprepar vecko-, dag- och veckodagsraderna om reportlab ändå
  delar en tabell.
- Rubriken ”Anställd” ligger i den lokala variabeln `page_header`, så att den
  aldrig skuggar rubriklistan (fel som gav tabeller utanför ramen).

### 27.4 Trånga kolumner

Dagnamnen (`Mån` … `Sön`) får **6 pt** i stället för 7 pt när dagkolumnen är
smalare än 18 pt (stående A4), så att etiketterna inte går i varandra.

### 27.5 Tester

| Fil | Antal | Innehåll |
|-----|-------|----------|
| `tests/test_pdf_layout.py` | 23 | sidantal för 6/16 anställda, `_fit_layout` (kort, lång, mycket lång lista), radhöjdens beroende av rader och radluft, legendens fullständiga etiketter och bredd |
| `tests/test_pdf_leave.py` | 11 | legendens fem rutor (även att etiketterna är hela texter) |


---

## 28. Logotyp: SVG, EPS och PDF + storleksreglage (v2.11.0)

### 28.1 Format som kan infogas

| Format | Hur det läses | Krav |
|--------|---------------|------|
| **SVG** | svglib → vektor i PDF:en, annars Qt-rasterisering (300 dpi) | – |
| **EPS** | Ghostscript → PNG (600 dpi), sedan bild | **Ghostscript** |
| **PDF** | första sidan rastreras med PyMuPDF (600 dpi) | **PyMuPDF** (frivilligt paket, ingår inte i `requirements.txt`) |
| **PNG/JPG** | `reportlab` `ImageReader` | – |

Dropdown-listan visar **fortfarande bara SVG** i `assets/` (v2.10.0). Allt annat
infogas med **Infoga logotyp…** och hamnar då i listan med texten
*(utanför assets)*, så att valet syns och kan tas bort.

### 28.2 Ghostscript och felhantering

`find_ghostscript()` letar i den här ordningen:

1. miljövariabeln `SEMESTERLISTA_GHOSTSCRIPT` (bra för företag som har
   Ghostscript på en egen sökväg),
2. `gswin64c`, `gswin32c` och `gs` i `PATH`,
3. vanliga installationsmappar (`C:\Program Files\gs\gs*\bin\gswin64c.exe`,
   `/usr/local/bin/gs`, `/opt/homebrew/bin/gs`, `/usr/bin/gs`).

Saknas Ghostscript kastar `convert_eps_to_png()` ett `AssetError` med
`ghostscript_hint()`: *”EPS kräver Ghostscript … spara logotypen som SVG eller
PDF i stället.”* Förhandsgranskningen visar texten i rött, och PDF-exporten
loggar en varning och ritar ingen logotyp – **PDF:en blir alltid klar**.

Saknas PyMuPDF kastar `convert_pdf_to_png()` ett `AssetError` med samma
hantering: förklaring i väljaren, varning i loggen, PDF utan logotyp.

Både EPS- och PDF-konverteringen **cachas** i logotypcachen (samma mapp som de
rastrerade SVG-filerna, städas vid avslut): nyckeln är filens sökväg,
ändringstid, typ och upplösning.

### 28.3 Storleksreglage (25–300 %)

| Del | Beteende |
|-----|----------|
| Inställning | `logo_scale` (procent) per flik, standard **100** |
| `PdfLogo.load(..., scale=)` | Skalar max-storleken innan bilden laddas |
| `PdfLogo.auto_size(..., scale=)` | Skalar rutan på sidan; proportionerna låses |
| `logo_for_settings()` | Läser `logo_scale`, klampar till 25–300 % |
| Reglaget | `QSpinBox` 25–300 %, steg 5, signalen `scale_changed(int)` |

**Tak:** logotypen får aldrig bli högre än 8 % av sidan eller bredare än 25 %
(`SCALE_MAX_HEIGHT_RATIO` / `SCALE_MAX_WIDTH_RATIO`). Då kan den aldrig hamna
över tabellen eller färgförklaringen, hur reglaget än ställs. Förhandsgranskningen
visar reglaget direkt: 50 % ritar logotypen i halva rutan, 100 % fyller rutan.

### 28.4 Filer som ändrats

| Fil | Ändring |
|-----|---------|
| `core/pdf_assets.py` | `EPS_SUFFIXES`, `PDF_SUFFIXES`, `IMPORT_SUFFIXES`, `find_ghostscript()`, `convert_eps_to_png()`, `convert_pdf_to_png()`, `ghostscript_hint()`, `PdfLogo._load_converted()`, `scale` i `load()`/`auto_size()`, `logo_for_settings(scale_key=…)` |
| `core/logo_picker.py` | `scale_changed`, `scale()`/`set_scale()`, `QSpinBox`-rad, `file_filter()`, `_pixmap_for()` (EPS/PDF i förhandsgranskningen) |
| `core/i18n.py` | `logo.size_label`, `logo.size_hint`, `logo.size_tooltip`, `logo.filter_*`; knappen heter nu **Infoga logotyp…** (sv/en) |
| `core/settings_manager.py` | `logo_scale: 100` i alla tre flikarna |
| `plugins/lista`, `plugins/hyra` | Reglaget sparas direkt (`_on_logo_scale_changed`), värdet skickas till väljaren |
| `plugins/fordon` | `logo_scale` i standardinställningarna |

### 28.5 Tester

| Fil | Antal | Innehåll |
|-----|-------|----------|
| `tests/test_pdf_assets.py` | +13 | Ghostscript i `PATH`/miljövariabel, saknad Ghostscript (förklaring), EPS → PNG med cache, felutskrift vid misslyckad konvertering, EPS bevarar originalets sökväg, PDF rastreras + cache, skalans inverkan på storlek och `auto_size`, taken, `logo_for_settings` (procent, standard, klamning) |
| `tests/test_logo_picker.py` | +7 | importfiltret (SVG/EPS/PDF/PNG/JPG), knapptexten, reglagets standard och gränser, `scale_changed`, storlek i konstruktorn, förhandsgranskningen krymper, EPS utan Ghostscript visar förklaringen |

Svitens total: **370 tester**.

---

## 29. Region, uppdelning och sammanhållna A4-blad (v2.12.0)

Detta kapitel ersätter tidigare manuella layoutval och automatisk minskning
av antalet månader per blad i kapitel 27.

- Semesterlista och Fordon använder `core.holidays` och den globala
  `holiday_region` via `SettingsManager`: Sverige (`sv`) eller USA (`us`).
  Amerikanska federala helger markeras på observed-datum; inga amerikanska
  halvdagar läggs till. Okänd region faller tillbaka på Sverige.
- 1 månad per blad ger stående A4, 2–3 månader ger liggande A4. Gamla sparade
  orienteringsval styr inte längre exporten. UI visar orienteringen automatiskt.
- Valda månader per blad behålls även för långa listor. Radluft minskas först;
  därefter skalas sidans hela innehåll proportionerligt med `KeepInFrame`.
  Inga månadsblock delas. Mycket långa listor får mindre text, inte fler blad.
  Tolv månader ger exakt 12, 6 eller 4 blad. Startmånad och årsskifte bevaras.
- Scheman har företagsnamn överst, utskriftsdatum och ”Sida X av Y” nederst.
  Företagsnamnet sparas per flik som `company_name` via flikens inställningar.
  Tomt namn utelämnas; långa namn begränsas till vänstra halvan av sidhuvudet.
  Befintlig logotypcanvas behålls. Hyra-exportens layout ändras inte.
- `plugins/lista/plugin.py` behåller Plugin och kompatibla exporter.
  `pdf.py` ansvarar för PDF, `view.py` för vy/dialog/självtest,
  `list_io.py` för listinläsning/frånvaro, `common.py` för delade funktioner.
  Fordon ärver fortfarande samma Plugin-klass.
- 383 tester: kalenderfall (påsk, midsommar, halvdagar, USA observed inklusive
  årsskifte), global region i PDF-generatorn, Fordonsarv och faktiska PDF:er.
  Exportkontroller omfattar båda schemalägen, 1/2/3 månader, 6/80 namn,
  årsskifte, alla namn/månader, sidfot och text innanför sidkanterna.
  CI installerar PyMuPDF för att köra innehållskontrollerna.

<!-- ═══════════════════════════════════════════════════════════════════════════════ ║ SLUT PÅ SPECIFIKATION ║ ║ Version: 2.11.0 | Datum: 2026-11-03 | Status: 50/50 (100%) ║ ║ Copyright: Rickard Längkvist 2025 – dynamiskt år ║ ═══════════════════════════════════════════════════════════════════════════════ -->

## 30. Inställningslayout (v2.12.1)

Alla inställningsflikar omges av QScrollArea. Innehållets minimistorlek
bevaras så att kontroller inte klipps när dialogen krymps eller releasetext
tillkommer. Spara/Avbryt ligger utanför rullområdet. Startstorleken är högst
720 × 780 logiska pixlar, begränsad av skärmens tillgängliga arbetsyta.
Uppdateringsknappar visas vertikalt och datamappens sökväg radbryts.
385 tester, inklusive liten dialog (560 × 420), långa releasenoteringar
och åtkomliga knappar på svenska och engelska.


## 31. Bekräfta hittad uppdatering (v2.12.2)

Manuell sökning via Inställningar, Hjälp eller systemfältet öppnar direkt
en Ja/Nej-dialog när en ny version med nedladdningslänk hittas. Dialogen
visar gammal/ny version och information om säkerhetskopiering. Nej är
förvalt. Ja startar installationen en gång utan ytterligare bekräftelse.
Nej behåller möjligheten att senare välja Uppdatera nu. Fel, senaste
version och saknad nedladdningslänk ger ingen installationsfråga.
Den automatiska startkontrollen fortsätter endast visa en avisering.
Regressionstester täcker Ja, Nej och utebliven fråga när installation
inte är möjlig. Testsviten omfattar nu 388 tester.


## 32. Veckounderhåll i befintlig Python (v2.13.1)

Ersätter startunderhållet i v2.13.0. Ingen egen virtuell miljö skapas eller
används. Befintlig Python hittas via launcher/PATH/Store/register och dess
basinterpreter används. Gamla .venv-mappar lämnas orörda men väljs inte.
Python uppgraderas bara inom sin serie via winget; installation är endast
tillåten när Python saknas. Paket uppdateras med samma interpreters pip.
Detta kan påverka andra program som använder samma paketmiljö.

Windows Schemaläggaren får uppgiften "Semesterlista - veckounderhall",
för inloggad användare utan begärd elevation, måndag 08:00 lokal tid och
StartWhenAvailable. Registrering sker vid första start efter uppdatering.
Schemat kör underhåll utan att öppna appen. Missad körning/nekad registrering
hanteras vid nästa appstart. Vanliga starter gör inget paket-/versionsunderhåll.
Första användningen utan veckostatus kör ett försök direkt.

Mutex skyddar appen: om den är igång skjuts underhåll upp till nästa start.
Veckans försök sparas atomiskt i data/runtime-weekly.json före underhåll,
även nätfel räknas som ett försök. Veckogränsen är måndag 08:00, inte midnatt.
Ordinarie appuppdatering via GitHub påverkas inte av Python-schemat.

Tester täcker delad interpreter, ingen venv, normal start utan paketkontroll,
schemakörning utan appstart, offline/fel och veckogränser/persistens i Windows.


## 33. Varning för liten PDF-text och avgränsning (v2.13.2)

Semesterlista/Fordon mäter varje sidgrupp med ReportLabs verkliga
KeepInFrame-skala innan målfilen öppnas. Om kalendertexten understiger
6 punkter visas en enda Ja/Nej-fråga med minsta storlek och berörda sidor.
Nej är förvalt och avbryter utan att skapa/skriva över PDF eller skicka
pdf_generated. Ja behåller valt antal månader och befintlig A4-layout.
Texten finns på svenska och engelska. Hyra-exporten ändras inte.

Fastställd omfattning: anställda endast semester, fordon endast körning,
hyresgäster endast månads-/kvartalsfakturering. Framtida kalenderbilder
ska hämtas ur lokal mapp, inte genereras med AI. Kalenderfunktion och
bildval ingår inte i denna läsbarhetsändring.


## 34. Semesterkalender, årssumma och kvartalsplanering (v2.14.0)

Semesterlistans knapp Semesterkalender öppnar anställda från vald listfil.
Användaren väljer person, start- och slutdatum i två kalendrar (alltid måndag
som veckostart), lägger till/tar bort perioder och sparar. Avbryt skriver
inte till fil. Kalenderns datum lagras exakt med = framför ISO-perioden i
Anställda.txt. Gamla manuellt skrivna perioder behåller sin veckosnäppning.
Sparade perioder används av samma LeaveCalendar som PDF-exporten.

Årsöversikten visar antal semesterdagar per person: unika måndag–fredag-datum
inom valt år, med officiella helgdagar enligt sv/us borttagna. Halvdagar
räknas som en hel arbetsdag. Detta är en planeringssumma, inte en beräkning
för lön/semesteravtal eller individuella arbetsscheman. Perioder över
årsskifte delas mellan årens summor. Datumval flyttas inte till måndag:
veckostart och valda semesterdagar är separata saker.

Listfilen sparas via ordinarie atomära sparning med .bak. Externa ändringar
sedan dialogen öppnades stoppar sparningen. Namnets längdgräns kvarstår men
giltig semestermetadata får innehålla flera perioder utan 80-teckensgränsen.

Hyresdelen är planering/avprickning – inga fakturor skapas. Kvartalskort och
PDF visar utskick senast 1 december året före Q1, sedan 1 mars/juni/september,
och betald senast 1 januari/april/juli/oktober i valt år. Det är kvartalets
början som visas även när datumet är helgdag; ingen bankdagsjustering görs.


## 35. Fristående kalender, gemensamt utseende och säsongs-PDF (v2.15.0)

- Kalender är en separat plugin, helt utan koppling till anställda eller semester.
  Flikordning: Kalender, Semesterlista, Fordon, Hyra. Veckostart är alltid måndag.
- `core/calendar_data.py` delar datum, ISO-veckogrupper och regionala helgdagsnamn/
  klassificering mellan kalender på skärmen och kalender-/lista-/fordons-PDF.
  Semester-/fordons-PDF visar dessutom helgdagsnamn som text under respektive månad.
- Kalender väljer år och exportmånader. 1/2/3 månader per blad ger för helår
  12/6/4 sidor, stående för en månad och liggande för två/tre.
- `core/ui_layout.py`: gemensamma spacing-/marginalvärden, brytande knapprader,
  scrollbar-wrapper och designregler. Flikernas huvudåtgärder ligger sist.
  Dialogernas Spara/Avbryt ligger utanför rullningsytan.
- Mörkt tema har mörka kontroll-/meny-/kalenderytor, tydliga disabled-färger och
  pil-/bockikoner. Högkontrasttema har svart/vitt och gul fokusmarkering.
  Hyresstatus har kvar text, kalenderhelgdagar har namn, säsongsband har årstidsnamn.
- Fyra valbara lokala PNG/JPEG-bilder, en per årstid, används i en egen bildyta
  högst 48 pt före skalning. Bilderna överlagrar aldrig tabeller. Saknad bild
  ger textfallback och loggvarning; data exporteras ändå. Inga nätanrop för bilder.
- Ljus PDF är oberoende av UI-tema. Valbar gråskala gäller vektorfärger,
  säsongsbilder och rasterlogotyper; även Hyra erbjuder gråskaleutskrift.
- Gemensam läsbarhetskontroll före export varnar under 6 pt, standardval Nej.
  Kalenderns fil ersätts atomiskt först när rendering lyckats.
- Regressionstester täcker veckostart, skottår, region, lokala bilder i samtliga
  tre exporttyper, 1/2/3-månaderssidantal, gråskalepixlar, avbruten/misslyckad
  export, kompakt knapplayout och högkontrast.
