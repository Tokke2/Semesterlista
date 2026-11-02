# FIL: plugins/lista/plugin.py

"""
Semesterlista & Limokörning Plugin – UPPDATERAD (PySide6 + BasePlugin)
======================================================================

Plugin för att generera semesterlistor och limokörningsscheman i PDF-format.

NYTT v2.8.0:
  - Detaljerad loggning: PDF-genereringen loggar läge, år, startmånad,
    månader per blad, layout, antal poster/sidor, filnamn, storlek och
    tidsåtgång till data/app.log.

NYTT v2.7.0:
  - Inställningsdialogen använder appikonen (core/app_icon.py) så att
    fönster, systemfält och aktivitetsfält visar samma ikon.

NYTT v2.6.0:
  - Sidlayout: liggande (standard, 270 mm tabell) eller stående A4
    (190 mm tabell) – väljs i vyn och sparas i inställningarna.
  - Månader per blad: 1, 2 eller 3 (tidigare bara 2 och 3).
  - Startmånad väljs som förut (Standard = jan–dec, eller valfri månad
    som kan gå över årsskifte).
  - Validering av layout och månadsval innan PDF:en skapas.

NYTT v2.5.0:
  - Fliken visar ett LÅST läge (Semesterlista). Limokörning har fått en
    egen flik: plugins/fordon (FIXED_MODE = "Limokörning").
  - Logotyp i PDF:en: knappen "Välj logotyp…" hämtar en SVG/PNG/JPG från
    appens assets-mapp (även undermappar) via core/logo_dialog.py och
    core/pdf_assets.py. Logotypen ritas på varje sida.
  - Inställningarna sparas per plugin (settings-fordon.json för Fordon)
    så att flikarna inte skriver över varandra.

NYTT v2.4.0:
  - Listorna (Anställda.txt / Fordon.txt) läses via core/roster.py:
    kommentarer, blandade teckenkodningar, tomma rader och dubbletter
    hanteras automatiskt.
  - Knappen "Hantera lista…" öppnar core/list_editor_dialog.py så att
    namn/fordon kan läggas till, ändras, tas bort och sorteras i appen.
  - Antal poster i vald fil visas under filväljaren.

NYTT v2.2.0:
  - Manuellt val av startmånad via QComboBox
    "Standard (Januari)" = standardläge
    Om inget väljs används standardläge:
      → jan–dec för valt år
    Om månad väljs manuellt:
      → 12 sammanhängande månader från vald månad
      → kan gå över årsskifte
      Exempel:
        December 2026 → Dec 2026, Jan 2027, Feb 2027, ... Nov 2027
  - KAN skriva ut perioder som innehåller Dec/Jan över årsskifte
    t.ex. Dec 2026 / Jan 2027
  - KORRIGERAD färgkodning:
    Midsommarafton = GRÖN (halvdag), EJ röd
    get_swedish_holidays() returnerar ENBART officiella röda dagar
    get_half_days() returnerar halvdagar inkl. midsommarafton
  - Prioritetsordning: röd > röd(söndag) > grön > blå > ingen
  - 10 automatiska tester
    inkl. midsommarafton-test och årsskifte Dec→Jan-test
  - start_month sparas i settings och återställs vid nästa start

NYTT v1.3.0:
  - Nästan hela liggande A4 används (270mm tabellbredd)
  - Automatisk skalning via ReportLab wrap()
  - 2 mån/blad → stora dagrutor
  - 3 mån/blad → centrerad & skalad automatiskt

Konverterad från tkinter till PySide6 enligt specifikationen:
- Ärver från plugins.base_plugin.BasePlugin
- Använder EventBus för kommunikation
- Använder SettingsManager för JSON-inställningar
- PySide6-baserat UI (QWidget, QDialog, QComboBox, etc.)
- Behåller ALL ursprunglig funktionalitet inklusive:
  - Semesterlista-generering med färgkodade dagar
  - Limokörningsschema-generering
  - Helgdagar via get_swedish_holidays() + egen påskberäkning
  - Halvdagar/klämdagar (Julafton, Midsommarafton, etc.)
  - Färgförklaring i PDF (röd/blå/grön/orange)
  - Inställningsdialog (inkl. startmånad)
  - Test-runner med 10 automatiska tester
  - Val av 2 eller 3 månader per blad
  - RÄTT kolumnbredder – 270mm tabell på liggande A4 med autoskalning

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import os
import json
import calendar
import platform
import webbrowser
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QSpinBox,
    QComboBox, QLineEdit, QCheckBox, QMessageBox, QFileDialog,
    QDialog, QDialogButtonBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, PageBreak,
)
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm

from core import i18n
from core.pdf_assets import AssetError, PdfLogo, logo_for_settings, make_logo_canvas
from core.roster import RosterError, read_names, resolve_path

from plugins.base_plugin import BasePlugin

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# KONSTANTER FÖR PDF-LAYOUT
# ══════════════════════════════════════════════════════════
# Liggande A4: 297mm × 210mm
# Tabellbredd: 270mm – nästan hela sidan (13.5mm marginal per sida)
# Namnkolumn: 70pt (~24.7mm)
# Minsta dagkolumn: 8pt
TABLE_WIDTH_MM = 270.0
TABLE_WIDTH_PT = TABLE_WIDTH_MM * mm
NAME_COL_WIDTH = 70
MIN_DAY_COL_WIDTH = 8
FONT_SIZE = 7

# ── Sidlayout (v2.6.0) ─────────────────────────────────
# Användaren väljer liggande (standard) eller stående A4.
ORIENTATION_LANDSCAPE: str = "Liggande"
ORIENTATION_PORTRAIT: str = "Stående"
ORIENTATIONS: List[str] = [ORIENTATION_LANDSCAPE, ORIENTATION_PORTRAIT]
DEFAULT_ORIENTATION: str = ORIENTATION_LANDSCAPE

#: Marginal (mm) och tabellbredd (mm) per layout
LAYOUT_SETTINGS: Dict[str, Dict[str, float]] = {
    # Liggande A4: 297 × 210 mm
    ORIENTATION_LANDSCAPE: {
        "side_margin_mm": 13.5,
        "top_margin_mm": 12.0,
        "table_width_mm": 270.0,
    },
    # Stående A4: 210 × 297 mm
    ORIENTATION_PORTRAIT: {
        "side_margin_mm": 10.0,
        "top_margin_mm": 12.0,
        "table_width_mm": 190.0,
    },
}

#: Antal månader per blad som går att välja (v2.6.0)
MONTHS_PER_PAGE_OPTIONS: List[int] = [1, 2, 3]
DEFAULT_MONTHS_PER_PAGE: int = 3

PLUGIN_INFO = {
    "id": "semesterlista",
    "name": "Semesterlista & Limokörning",
    "version": "2.8.0",
    "author": "Din Organisation",
    "description": "Genererar semesterlistor och limokörningsscheman i PDF-format",
}

# ══════════════════════════════════════════════════════════
# MÅNADSNAMN – används i dropdown och PDF-titlar
# ══════════════════════════════════════════════════════════
MONTHS_SV: Dict[int, str] = {
    1: "Januari",
    2: "Februari",
    3: "Mars",
    4: "April",
    5: "Maj",
    6: "Juni",
    7: "Juli",
    8: "Augusti",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "December",
}

# Index 0 = standardläge
# Index 1–12 = explicit startmånad
MONTH_OPTIONS: List[str] = [
    "Standard (Januari)",
    "Januari",
    "Februari",
    "Mars",
    "April",
    "Maj",
    "Juni",
    "Juli",
    "Augusti",
    "September",
    "Oktober",
    "November",
    "December",
]


# ══════════════════════════════════════════════════════════
# HJÄLPFUNKTIONER (modulnivå)
# ══════════════════════════════════════════════════════════

def normalize_orientation(orientation: Any) -> str:
    """
    Returnera en giltig sidlayout.

    Okända värden (t.ex. gamla inställningar) blir liggande.
    """
    value = str(orientation or "").strip()
    return value if value in LAYOUT_SETTINGS else DEFAULT_ORIENTATION


def page_geometry(orientation: str) -> tuple[tuple[float, float], float]:
    """
    Sidstorlek och tabellbredd för vald layout.

    Args:
        orientation: "Liggande" eller "Stående".

    Returns:
        (pagesize_pt, tabellbredd_pt) – t.ex. ((841.89, 595.27), 765.35).

    Exempel:
        page_geometry("Stående")   # A4 porträtt, 190 mm tabell
        page_geometry("Liggande")  # A4 landskap, 270 mm tabell
    """
    layout = LAYOUT_SETTINGS[normalize_orientation(orientation)]
    pagesize = (
        A4 if normalize_orientation(orientation) == ORIENTATION_PORTRAIT
        else landscape(A4)
    )
    return pagesize, layout["table_width_mm"] * mm


def orientation_label(orientation: Any) -> str:
    """
    Översatt etikett för en sidlayout.

    Exempel: orientation_label("Stående") → "Stående (A4)".
    """
    value = normalize_orientation(orientation)
    key = (
        "lista.orientation.landscape"
        if value == ORIENTATION_LANDSCAPE
        else "lista.orientation.portrait"
    )
    try:
        return i18n.t(key)
    except Exception:  # pragma: no cover – i18n saknas
        return value


def get_documents_folder() -> str:
    """Returnerar sökvägen till användarens Dokument-mapp."""
    path = Path.home() / "Documents"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_plugin_data_folder() -> str:
    """Returnerar sökvägen till plugin-data-mapp (plattformsoberoende)."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    path = base / "SemesterlistaApp" / "plugins" / "lista"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_easter(year: int) -> date:
    """
    Beräkna påskdagen för ett givet år (Gauss algoritm).

    Returns:
        date: Påskdagen (alltid en söndag).
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l_val = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_val) // 451
    month = (h + l_val - 7 * m + 114) // 31
    day = ((h + l_val - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_swedish_holidays(year: int) -> Set[date]:
    """
    Returnera SET med OFFICIELLA svenska helgdagar (röda dagar).

    Dessa visas som RÖDA i PDF-tabellen.

    Officiella helgdagar:
        Nyårsdagen          1 januari
        Trettondedag jul    6 januari
        Långfredag          Påskberoende (fredagen före påsk)
        Påskdagen           Påskberoende (söndagen)
        Annandag påsk       Påskberoende (måndagen)
        Första maj          1 maj
        Kristi himmelsfärd  Påskberoende (torsdagen, 39 dagar efter påsk)
        Pingstdagen         Påskberoende (söndagen, 49 dagar efter påsk)
        Nationaldagen       6 juni
        Midsommardagen      Lördagen närmast 24 juni
        Alla helgons dag    Lördagen 31 okt–6 nov
        Juldagen            25 december
        Annandag jul        26 december

    OBS – dessa är INTE röda:
        Påskafton
        Pingstafton
        Midsommarafton
        Julafton
        Nyårsafton

    Returns:
        Set[date]: Alla officiella helgdagar för året.
    """
    holidays: Set[date] = set()
    easter = get_easter(year)

    # Fasta helgdagar
    holidays.add(date(year, 1, 1))
    holidays.add(date(year, 1, 6))
    holidays.add(date(year, 5, 1))
    holidays.add(date(year, 6, 6))
    holidays.add(date(year, 12, 25))
    holidays.add(date(year, 12, 26))

    # Påskberoende helgdagar
    holidays.add(easter - timedelta(days=2))   # Långfredag
    holidays.add(easter)                       # Påskdagen
    holidays.add(easter + timedelta(days=1))   # Annandag påsk
    holidays.add(easter + timedelta(days=39))  # Kristi himmelsfärds dag
    holidays.add(easter + timedelta(days=49))  # Pingstdagen

    # Midsommardagen – lördagen närmast 24 juni (20–26 juni)
    for day_num in range(20, 27):
        current = date(year, 6, day_num)
        if current.weekday() == 5:
            holidays.add(current)
            break

    # Alla helgons dag – lördagen 31 okt–6 nov
    found = False
    try:
        d_oct_31 = date(year, 10, 31)
        if d_oct_31.weekday() == 5:
            holidays.add(d_oct_31)
            found = True
    except ValueError:
        pass

    if not found:
        for day_num in range(1, 7):
            current = date(year, 11, day_num)
            if current.weekday() == 5:
                holidays.add(current)
                break

    return holidays


def get_half_days(year: int) -> Set[date]:
    """
    Returnera SET med halvdagar/klämdagar (GRÖNA dagar i PDF).

    Halvdagar:
        Skärtorsdag
        Valborg / Valborgsmässoafton (30 april)
        Midsommarafton
        Dag före Alla helgons dag
        Julafton
        Nyårsafton

    VIKTIGT:
        Midsommarafton är GRÖN (halvdag), EJ röd.

    Returns:
        Set[date]: Alla halvdagar för året.
    """
    half_days: Set[date] = set()
    easter = get_easter(year)

    # Skärtorsdag
    half_days.add(easter - timedelta(days=3))

    # Valborg
    half_days.add(date(year, 4, 30))

    # Midsommarafton – fredagen närmast 24 juni (19–25 juni)
    for day_num in range(19, 26):
        current = date(year, 6, day_num)
        if current.weekday() == 4:
            half_days.add(current)
            break

    # Dag före Alla helgons dag = fredagen före Alla helgons dag
    found = False
    try:
        d_oct_31 = date(year, 10, 31)
        if d_oct_31.weekday() == 5:
            half_days.add(d_oct_31 - timedelta(days=1))
            found = True
    except ValueError:
        pass

    if not found:
        for day_num in range(1, 7):
            current = date(year, 11, day_num)
            if current.weekday() == 5:
                half_days.add(current - timedelta(days=1))
                break

    # Julafton & Nyårsafton
    half_days.add(date(year, 12, 24))
    half_days.add(date(year, 12, 31))

    return half_days


# ══════════════════════════════════════════════════════════
# INSTÄLLNINGSDIALOG
# ══════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    """
    Inställningsdialog för Semesterlista-pluginet.

    v2.2.0:
      - Startmånad kan vara standard eller manuell
      - Standard = jan–dec valt år
      - Manuellt val = 12 månader från vald månad, kan gå över årsskifte
    """

    def __init__(self, parent: QWidget, plugin: "Plugin"):
        super().__init__(parent)
        self.plugin: "Plugin" = plugin
        self.setWindowTitle("Inställningar – Semesterlista")
        self.setFixedSize(460, 360)

        # Samma appikon som huvudfönstret (v2.7.0)
        try:
            from core.app_icon import app_icon

            self.setWindowIcon(app_icon())
        except Exception:  # pragma: no cover – defensivt
            pass
        self.setModal(True)
        self._init_ui()
        self._load_settings()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        auto_row = QHBoxLayout()
        auto_row.addWidget(QLabel("Öppna PDF automatiskt:"))
        auto_row.addStretch()
        self.auto_open_check = QCheckBox()
        auto_row.addWidget(self.auto_open_check)
        main_layout.addLayout(auto_row)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Standardläge:"))
        mode_row.addStretch()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Semesterlista", "Limokörning"])
        self.mode_combo.setMinimumWidth(220)
        mode_row.addWidget(self.mode_combo)
        main_layout.addLayout(mode_row)

        months_row = QHBoxLayout()
        months_row.addWidget(QLabel("Månader per blad:"))
        months_row.addStretch()
        self.months_per_page_combo = QComboBox()
        self.months_per_page_combo.addItems(
            [str(value) for value in MONTHS_PER_PAGE_OPTIONS]
        )
        self.months_per_page_combo.setMinimumWidth(220)
        self.months_per_page_combo.setToolTip(
            "1, 2 eller 3 månader per blad i PDF:en."
        )
        months_row.addWidget(self.months_per_page_combo)
        main_layout.addLayout(months_row)

        # Sidlayout (v2.6.0)
        orientation_row = QHBoxLayout()
        orientation_row.addWidget(QLabel("Sidlayout:"))
        orientation_row.addStretch()
        self.orientation_combo = QComboBox()
        for value in ORIENTATIONS:
            self.orientation_combo.addItem(orientation_label(value), value)
        self.orientation_combo.setMinimumWidth(220)
        self.orientation_combo.setToolTip(
            "Liggande = breda tabeller (standard).\n"
            "Stående = vanlig A4 för pärm/utskrift."
        )
        orientation_row.addWidget(self.orientation_combo)
        main_layout.addLayout(orientation_row)

        start_row = QHBoxLayout()
        start_label = QLabel("Standardstartmånad:")
        start_label.setToolTip(
            "Standard (Januari) = jan–dec valt år.\n"
            "Väljer du en månad manuellt genereras 12 månader från den månaden\n"
            "och perioder kan gå över årsskifte, t.ex. dec 2026 → jan 2027."
        )
        start_row.addWidget(start_label)
        start_row.addStretch()
        self.start_month_combo = QComboBox()
        self.start_month_combo.addItems(MONTH_OPTIONS)
        self.start_month_combo.setMinimumWidth(220)
        self.start_month_combo.setToolTip(
            "Standard (Januari) = jan–dec valt år.\n"
            "Exempel: December 2026 ger en period som börjar i dec 2026\n"
            "och fortsätter in i 2027."
        )
        start_row.addWidget(self.start_month_combo)
        main_layout.addLayout(start_row)

        main_layout.addStretch()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _load_settings(self) -> None:
        self.auto_open_check.setChecked(
            self.plugin.settings.get("auto_open_pdf", True)
        )

        default_mode = self.plugin.settings.get("default_mode", "Semesterlista")
        idx = self.mode_combo.findText(default_mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)

        months_per_page = str(
            self.plugin.settings.get(
                "months_per_page", DEFAULT_MONTHS_PER_PAGE
            )
        )
        idx2 = self.months_per_page_combo.findText(months_per_page)
        if idx2 >= 0:
            self.months_per_page_combo.setCurrentIndex(idx2)

        orientation_idx = self.orientation_combo.findData(
            normalize_orientation(self.plugin.settings.get("orientation"))
        )
        if orientation_idx >= 0:
            self.orientation_combo.setCurrentIndex(orientation_idx)

        saved_start = self.plugin.settings.get("start_month", 0)
        if isinstance(saved_start, int) and 0 <= saved_start <= 12:
            self.start_month_combo.setCurrentIndex(saved_start)
        else:
            self.start_month_combo.setCurrentIndex(0)

    def _save(self) -> None:
        self.plugin.settings["auto_open_pdf"] = self.auto_open_check.isChecked()
        self.plugin.settings["default_mode"] = self.mode_combo.currentText()
        self.plugin.settings["months_per_page"] = int(
            self.months_per_page_combo.currentText()
        )
        self.plugin.settings["start_month"] = self.start_month_combo.currentIndex()
        self.plugin.settings["orientation"] = self.orientation_combo.currentData()
        self.plugin._save_settings()
        QMessageBox.information(self, "Info", "Inställningar sparade!")
        self.accept()


# ══════════════════════════════════════════════════════════
# TESTRUNNER
# ══════════════════════════════════════════════════════════

class TestRunner:
    """
    Kör automatiska tester för Semesterlista-pluginet.

    v2.2.0:
      1. Ogiltigt år
      2. År utanför intervall
      3. Ogiltigt läge
      4. Skottårshantering
      5. Svenska helgdagar
      6. Midsommarafton = grön, ej röd
      7. Julafton = grön
      8. Påskberäkning 2024
      9. Standardläge = jan–dec samma år
      10. Manuellt decemberval = dec→jan över årsskifte
    """

    def __init__(self, parent: QWidget, plugin: "Plugin"):
        self.parent: QWidget = parent
        self.plugin: "Plugin" = plugin
        self.generator: "PDFGenerator" = PDFGenerator(plugin)

    def run(self) -> None:
        results: List[tuple[str, str]] = []

        errors = self.generator._validate_inputs("abc", "test.txt", "Semesterlista")
        results.append(("1. Ogiltigt år", "✅ OK" if errors else "❌ Fel"))

        errors = self.generator._validate_inputs("1800", "test.txt", "Semesterlista")
        results.append(("2. År utanför intervall", "✅ OK" if errors else "❌ Fel"))

        errors = self.generator._validate_inputs("2024", "test.txt", "OgiltigtLäge")
        results.append(("3. Ogiltigt läge", "✅ OK" if errors else "❌ Fel"))

        try:
            feb_2024 = calendar.monthrange(2024, 2)[1]
            feb_2025 = calendar.monthrange(2025, 2)[1]
            ok = feb_2024 == 29 and feb_2025 == 28
            results.append(("4. Skottårshantering", "✅ OK" if ok else "❌ Fel"))
        except Exception:
            results.append(("4. Skottårshantering", "❌ Fel"))

        try:
            holidays_2024 = get_swedish_holidays(2024)
            midsommarafton_2024 = date(2024, 6, 21)
            ok_national = date(2024, 6, 6) in holidays_2024
            ok_not_red = midsommarafton_2024 not in holidays_2024
            ok_count = len(holidays_2024) >= 13
            ok = ok_national and ok_not_red and ok_count
            results.append(("5. Svenska helgdagar", "✅ OK" if ok else "❌ Fel"))
        except Exception:
            results.append(("5. Svenska helgdagar", "❌ Fel"))

        try:
            holidays_2024 = get_swedish_holidays(2024)
            half_days_2024 = get_half_days(2024)
            midsommarafton_2024 = date(2024, 6, 21)
            is_green = midsommarafton_2024 in half_days_2024
            is_not_red = midsommarafton_2024 not in holidays_2024
            ok = is_green and is_not_red
            results.append(("6. Midsommarafton = grön (ej röd)", "✅ OK" if ok else "❌ Fel"))
        except Exception:
            results.append(("6. Midsommarafton = grön (ej röd)", "❌ Fel"))

        try:
            half_days_2024 = get_half_days(2024)
            ok = date(2024, 12, 24) in half_days_2024
            results.append(("7. Julafton = grön", "✅ OK" if ok else "❌ Fel"))
        except Exception:
            results.append(("7. Julafton = grön", "❌ Fel"))

        try:
            ok = get_easter(2024) == date(2024, 3, 31)
            results.append(("8. Påskberäkning 2024", "✅ OK" if ok else "❌ Fel"))
        except Exception:
            results.append(("8. Påskberäkning 2024", "❌ Fel"))

        try:
            seq = self.generator._build_month_sequence(2026, None)
            ok = (
                len(seq) == 12
                and seq[0] == (2026, 1)
                and seq[-1] == (2026, 12)
            )
            results.append(("9. Standardläge = jan–dec samma år", "✅ OK" if ok else "❌ Fel"))
        except Exception:
            results.append(("9. Standardläge = jan–dec samma år", "❌ Fel"))

        try:
            seq = self.generator._build_month_sequence(2026, 12)
            ok = (
                len(seq) == 12
                and seq[0] == (2026, 12)
                and seq[1] == (2027, 1)
                and seq[2] == (2027, 2)
                and seq[-1] == (2027, 11)
            )
            results.append(("10. December → januari över årsskifte", "✅ OK" if ok else "❌ Fel"))
        except Exception:
            results.append(("10. December → januari över årsskifte", "❌ Fel"))

        self._show_results(results)

    def _show_results(self, results: List[tuple[str, str]]) -> None:
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Testresultat")
        dialog.setMinimumSize(560, 420)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(4)

        title = QLabel("Testresultat – Semesterlista & Limokörning v2.2.0")
        title.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addSpacing(12)

        for test_name, result in results:
            row = QHBoxLayout()
            name_label = QLabel(test_name)
            name_label.setFont(QFont("Helvetica", 10))
            name_label.setMinimumWidth(360)
            row.addWidget(name_label)

            result_label = QLabel(result)
            result_label.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
            row.addWidget(result_label)

            row.addStretch()
            layout.addLayout(row)

        layout.addStretch()

        close_btn = QPushButton("Stäng")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        dialog.exec()


# ══════════════════════════════════════════════════════════
# PDF-GENERATOR
# ══════════════════════════════════════════════════════════

class PDFGenerator:
    """
    Hanterar PDF-generering för semesterlistor och limokörningsscheman.

    v2.2.0:
      - Standardläge:
        start_month=None eller 0 → jan–dec för valt år
      - Manuellt val:
        start_month=1..12 → 12 sammanhängande månader från vald månad
        och perioden kan gå över årsskifte
      - Exempel:
        year=2026, start_month=12 → Dec 2026, Jan 2027, ... Nov 2027

      - KORRIGERAD färgkodning:
        Röd  = officiell helgdag (get_swedish_holidays) ELLER söndag
        Grön = halvdag (get_half_days), inkl. midsommarafton
        Blå  = lördag (ej officiell helgdag)
        Prioritet: röd > grön > blå
    """

    def __init__(self, plugin: "Plugin"):
        self.plugin: "Plugin" = plugin

    def generate(
        self,
        year_str: str,
        file_path: str,
        mode: str,
        months_per_page: int = DEFAULT_MONTHS_PER_PAGE,
        start_month: Optional[int] = None,
        orientation: str = DEFAULT_ORIENTATION,
    ) -> bool:
        """
        Generera PDF.

        Args:
            year_str:        Årstal som sträng, t.ex. "2026"
            file_path:       Sökväg till txt-fil
            mode:            "Semesterlista" eller "Limokörning"
            months_per_page: 1, 2 eller 3 månader per blad
            start_month:     None/0 = standardläge (jan–dec valt år)
                             1–12 = manuell startmånad
            orientation:     "Liggande" (standard) eller "Stående"
        """
        if start_month is not None and start_month != 0:
            if start_month < 1 or start_month > 12:
                start_month = None
        else:
            start_month = None

        orientation = normalize_orientation(orientation)

        errors = self._validate_inputs(
            year_str, file_path, mode, months_per_page, orientation
        )
        if errors:
            QMessageBox.critical(None, "Fel", "\n".join(errors))
            return False

        year = int(year_str)
        data = self._read_list_from_file(file_path)
        if not data:
            QMessageBox.information(
                None,
                "Information",
                f"Ingen data hittades i {file_path}",
            )
            return False

        try:
            return self._generate_pdf(
                data_list=data,
                year=year,
                mode=mode,
                months_per_page=months_per_page,
                start_month=start_month,
                orientation=orientation,
            )
        except Exception as e:
            logger.error(f"Fel vid PDF-generering: {e}")
            QMessageBox.critical(None, "Fel", f"Fel vid PDF-generering: {e}")
            return False

    def _page_logo(self) -> Optional[PdfLogo]:
        """
        Ladda logotypen som valts i inställningarna (v2.4.0).

        Returnerar None om ingen logotyp är vald eller om filen inte kan
        läsas – PDF:en genereras ändå, utan logotyp.
        """
        try:
            return logo_for_settings(self.plugin.settings, key="logo_svg")
        except AssetError as exc:
            logger.warning(f"Logotypen kunde inte laddas: {exc}")
            return None

    def _validate_inputs(
        self,
        year_str: str,
        file_path: str,
        mode: str,
        months_per_page: int = DEFAULT_MONTHS_PER_PAGE,
        orientation: str = DEFAULT_ORIENTATION,
    ) -> List[str]:
        """Validera indata innan PDF-generering."""
        errors: List[str] = []

        if months_per_page not in MONTHS_PER_PAGE_OPTIONS:
            errors.append(
                "Månader per blad måste vara "
                + ", ".join(str(value) for value in MONTHS_PER_PAGE_OPTIONS)
            )

        if orientation not in ORIENTATIONS:
            errors.append("Sidlayout måste vara Liggande eller Stående")

        try:
            year = int(year_str)
            if year < 1900 or year > 2100:
                errors.append("År måste vara mellan 1900 och 2100")
        except ValueError:
            errors.append("Ogiltigt år. Ange ett giltigt heltal")

        if not file_path:
            errors.append("Filnamn får inte vara tomt")
        elif not resolve_path(file_path).exists():
            errors.append(f"Filen '{file_path}' finns inte")

        if mode not in ["Semesterlista", "Limokörning"]:
            errors.append("Ogiltigt läge")

        return errors

    def _read_list_from_file(self, file_path: str) -> List[str]:
        """
        Läs lista med namn/fordon från txt-fil (via core.roster).

        Kommentarer (# eller ;), tomma rader, dubbletter och blandade
        teckenkodningar hanteras automatiskt av core/roster.py.
        """
        try:
            return read_names(resolve_path(file_path))
        except RosterError as exc:
            logger.error(f"Fel vid läsning av fil: {exc}")
            QMessageBox.critical(
                None,
                i18n.t("roster.error.title"),
                i18n.t("lista.error.read", error=exc),
            )
            return []

    def _create_legend_with_colors(
        self,
        table_width_pt: float = TABLE_WIDTH_PT,
    ) -> Table:
        """Skapa färgförklaringstabell för PDF (skalas till sidbredden)."""
        light_coral = colors.Color(0.94, 0.5, 0.5)
        light_blue = colors.Color(0.68, 0.85, 0.9)
        light_green = colors.Color(0.56, 0.93, 0.56)
        orange = colors.Color(1, 0.65, 0)

        legend_data = [[
            "", "Röd = Helgdag eller söndag",
            "", "Blå = Lördag",
            "", "Grön = Halvdag (midsommarafton, julafton m.fl.)",
            "", "Orange = Ny vecka",
        ]]

        legend_table = Table(
            legend_data,
            colWidths=[15, 120, 15, 70, 15, 200, 15, 75],
        )
        legend_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (0, 0), light_coral),
            ("BACKGROUND", (2, 0), (2, 0), light_blue),
            ("BACKGROUND", (4, 0), (4, 0), light_green),
            ("BACKGROUND", (6, 0), (6, 0), orange),
            ("BOX", (0, 0), (0, 0), 0.5, colors.black),
            ("BOX", (2, 0), (2, 0), 0.5, colors.black),
            ("BOX", (4, 0), (4, 0), 0.5, colors.black),
            ("BOX", (6, 0), (6, 0), 0.5, colors.black),
        ]))
        self._apply_table_scaling(legend_table, table_width_pt)
        return legend_table

    @staticmethod
    def _calc_column_widths(
        days_in_month: int,
        table_width_pt: float = TABLE_WIDTH_PT,
    ) -> tuple[float, float]:
        """
        Beräkna kolumnbredder baserat på antal dagar i månaden.

        Args:
            days_in_month:  Antal dagar (28–31).
            table_width_pt: Tillgänglig tabellbredd i punkter
                            (270 mm liggande, 190 mm stående).

        Returns:
            (namnkolumn_bredd, dagkolumn_bredd) i punkter.
        """
        available = table_width_pt - NAME_COL_WIDTH
        day_width = available / days_in_month
        return float(NAME_COL_WIDTH), float(day_width)

    @staticmethod
    def _apply_table_scaling(
        table: Table,
        table_width_pt: float = TABLE_WIDTH_PT,
    ) -> None:
        """
        Skala tabellen så att den exakt fyller angiven bredd.

        Args:
            table:          reportlab-tabell.
            table_width_pt: Mål-bredd i punkter (270 mm liggande,
                            190 mm stående).
        """
        table.wrap(0, 0)
        current_width = sum(table._colWidths)
        if current_width > 0:
            scale = table_width_pt / current_width
            table._argW = [w * scale for w in table._colWidths]

    @staticmethod
    def _build_month_sequence(
        base_year: int,
        start_month: Optional[int],
    ) -> List[tuple[int, int]]:
        """
        Bygg månadssekvens.

        Standardläge:
            start_month=None → jan–dec samma år

        Manuellt val:
            start_month=1..12 → 12 sammanhängande månader från vald månad,
            kan gå över årsskifte.

        Exempel:
            base_year=2026, start_month=None
                → [(2026,1), (2026,2), ... (2026,12)]

            base_year=2026, start_month=12
                → [(2026,12), (2027,1), (2027,2), ... (2027,11)]
        """
        if start_month is None or start_month == 0:
            return [(base_year, month_num) for month_num in range(1, 13)]

        sequence: List[tuple[int, int]] = []
        current_year = base_year
        current_month = start_month

        for _ in range(12):
            sequence.append((current_year, current_month))
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

        return sequence

    @staticmethod
    def _chunk_months(
        sequence: List[tuple[int, int]],
        chunk_size: int,
    ) -> List[List[tuple[int, int]]]:
        """
        Dela upp månadsekvens i blad om 1, 2 eller 3 månader.
        """
        return [
            sequence[i:i + chunk_size]
            for i in range(0, len(sequence), chunk_size)
        ]

    @staticmethod
    def _format_range_label(sequence: List[tuple[int, int]]) -> str:
        """
        Formatera en läsbar etikett för hela perioden.
        """
        start_year, start_month = sequence[0]
        end_year, end_month = sequence[-1]

        if start_year == end_year and start_month == 1 and end_month == 12:
            return str(start_year)

        if start_year == end_year:
            return f"{MONTHS_SV[start_month]}–{MONTHS_SV[end_month]} {start_year}"

        return f"{MONTHS_SV[start_month]} {start_year} – {MONTHS_SV[end_month]} {end_year}"

    @staticmethod
    def _format_page_title(
        title_prefix: str,
        page_months: List[tuple[int, int]],
    ) -> str:
        """
        Formatera sidtitel för en grupp månader.
        """
        start_year, start_month = page_months[0]
        end_year, end_month = page_months[-1]

        if len(page_months) == 1:
            return f"{title_prefix} {MONTHS_SV[start_month]} {start_year}"

        if start_year == end_year:
            return f"{title_prefix} {MONTHS_SV[start_month]}–{MONTHS_SV[end_month]} {start_year}"

        return (
            f"{title_prefix} "
            f"{MONTHS_SV[start_month]} {start_year} – "
            f"{MONTHS_SV[end_month]} {end_year}"
        )

    @staticmethod
    def _build_output_filename(
        documents_path: str,
        mode: str,
        sequence: List[tuple[int, int]],
    ) -> str:
        """
        Bygg filnamn för PDF.

        Standardläge (jan–dec samma år):
            semesterlista_2026.pdf

        Manuella / årsskiftande perioder:
            semesterlista_2026_12-2027_11.pdf
        """
        prefix = "semesterlista" if mode == "Semesterlista" else "limokorning"

        start_year, start_month = sequence[0]
        end_year, end_month = sequence[-1]

        if start_year == end_year and start_month == 1 and end_month == 12:
            return os.path.join(documents_path, f"{prefix}_{start_year}.pdf")

        return os.path.join(
            documents_path,
            f"{prefix}_{start_year}_{start_month:02d}-{end_year}_{end_month:02d}.pdf",
        )

    def _generate_pdf(
        self,
        data_list: List[str],
        year: int,
        mode: str,
        months_per_page: int = DEFAULT_MONTHS_PER_PAGE,
        start_month: Optional[int] = None,
        orientation: str = DEFAULT_ORIENTATION,
    ) -> bool:
        """
        Generera PDF med färgkodade kalendertabeller.

        Layout (v2.6.0):
            orientation="Liggande" → A4 liggande, 270 mm tabell (standard)
            orientation="Stående"  → A4 stående, 190 mm tabell
            months_per_page=1/2/3  → antal månader per blad

        Standardläge:
            start_month=None → jan–dec valt år

        Manuellt val:
            start_month=1..12 → 12 sammanhängande månader från vald månad,
            kan gå över årsskifte

        Exempel:
            year=2026, start_month=None
                → jan–dec 2026
            year=2026, start_month=12
                → dec 2026 – nov 2027
                → första sida kan innehålla dec 2026 / jan 2027
        """
        documents_path = get_documents_folder()
        month_sequence = self._build_month_sequence(year, start_month)
        pages = self._chunk_months(month_sequence, months_per_page)
        range_label = self._format_range_label(month_sequence)
        filename = self._build_output_filename(documents_path, mode, month_sequence)

        # Detaljerad loggning (v2.8.0)
        from time import perf_counter

        started = perf_counter()
        logger.info(
            "PDF-start: läge=%s, år=%s, startmånad=%s, %s mån/blad, "
            "layout=%s, %s poster, %s sidor, fil=%s",
            mode,
            year,
            start_month if start_month is not None else "standard",
            months_per_page,
            orientation,
            len(data_list),
            len(pages),
            filename,
        )

        if mode == "Semesterlista":
            title_prefix = "Semesterlista"
            header = "Anställd"
        else:
            title_prefix = "Limokörningsschema"
            header = "Fordon"

        # Sidlayout (v2.6.0) – liggande (standard) eller stående A4
        orientation = normalize_orientation(orientation)
        layout = LAYOUT_SETTINGS[orientation]
        pagesize, table_width_pt = page_geometry(orientation)
        side_margin = layout["side_margin_mm"]
        top_margin = layout["top_margin_mm"]

        # Logotyp (v2.4.0) – ritas i övre högra hörnet på varje sida.
        # Används som canvasmaker eftersom onFirstPage/onLaterPages inte
        # stöds av alla reportlab-versioner.
        logo_canvas = make_logo_canvas(self._page_logo(), margin_mm=6.0)
        build_kwargs: Dict[str, Any] = {}
        if logo_canvas is not None:
            build_kwargs["canvasmaker"] = logo_canvas

        doc = SimpleDocTemplate(
            filename,
            pagesize=pagesize,
            rightMargin=side_margin * mm,
            leftMargin=side_margin * mm,
            topMargin=top_margin * mm,
            bottomMargin=top_margin * mm,
        )

        styles = getSampleStyleSheet()
        elements: List[Any] = []

        # Samla alla år som förekommer i sekvensen
        years_in_sequence = sorted({month_year for month_year, _ in month_sequence})
        official_holidays_by_year: Dict[int, Set[date]] = {
            month_year: get_swedish_holidays(month_year)
            for month_year in years_in_sequence
        }
        half_days_by_year: Dict[int, Set[date]] = {
            month_year: get_half_days(month_year)
            for month_year in years_in_sequence
        }

        # Färger
        light_coral = colors.Color(0.94, 0.5, 0.5)
        light_blue = colors.Color(0.68, 0.85, 0.9)
        light_green = colors.Color(0.56, 0.93, 0.56)
        orange = colors.Color(1, 0.65, 0)

        day_names: Dict[int, str] = {
            0: "Mån",
            1: "Tis",
            2: "Ons",
            3: "Tor",
            4: "Fre",
            5: "Lör",
            6: "Sön",
        }

        for page_index, page_months in enumerate(pages):
            page_title = self._format_page_title(title_prefix, page_months)
            elements.append(Paragraph(page_title, styles["Title"]))
            elements.append(Spacer(1, 3))
            elements.append(self._create_legend_with_colors(table_width_pt))
            elements.append(Spacer(1, 6))

            for month_year, month_num in page_months:
                days_in_month = calendar.monthrange(month_year, month_num)[1]
                name_w, day_w = self._calc_column_widths(
                    days_in_month, table_width_pt
                )

                official_holidays = official_holidays_by_year[month_year]
                half_days = half_days_by_year[month_year]

                week_numbers: List[str] = []
                for day_num in range(1, days_in_month + 1):
                    current = date(month_year, month_num, day_num)
                    if day_num == 1:
                        week_numbers.append("v" + str(current.isocalendar()[1]))
                    else:
                        prev = date(month_year, month_num, day_num - 1)
                        if current.isocalendar()[1] != prev.isocalendar()[1]:
                            week_numbers.append("v" + str(current.isocalendar()[1]))
                        else:
                            week_numbers.append("")

                day_texts = [
                    day_names[date(month_year, month_num, day_num).weekday()]
                    for day_num in range(1, days_in_month + 1)
                ]

                header_row1 = [f"{MONTHS_SV[month_num]} {month_year}"] + week_numbers
                header_row2 = [header] + list(map(str, range(1, days_in_month + 1)))
                header_row3 = [""] + day_texts
                table_data = [header_row1, header_row2, header_row3]

                for item in data_list:
                    table_data.append([item] + ["" for _ in range(days_in_month)])

                col_widths = [name_w] + [day_w] * days_in_month
                table = Table(table_data, colWidths=col_widths)

                style = TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ("BACKGROUND", (0, 0), (0, 0), colors.lightgrey),
                    ("BACKGROUND", (0, 1), (0, 1), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (-1, 2), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), FONT_SIZE),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ])

                # Färglägg dagar – prioritet:
                # 1. Röd: officiell helgdag
                # 2. Röd: söndag
                # 3. Grön: halvdag
                # 4. Blå: lördag
                for day_num in range(1, days_in_month + 1):
                    current_date = date(month_year, month_num, day_num)
                    col_idx = day_num
                    weekday = current_date.weekday()

                    if current_date in official_holidays or weekday == 6:
                        style.add(
                            "BACKGROUND",
                            (col_idx, 3), (col_idx, len(table_data) - 1),
                            light_coral,
                        )
                        style.add(
                            "TEXTCOLOR",
                            (col_idx, 3), (col_idx, len(table_data) - 1),
                            colors.white,
                        )
                        style.add(
                            "FONTNAME",
                            (col_idx, 1), (col_idx, 1),
                            "Helvetica-Bold",
                        )
                        style.add(
                            "TEXTCOLOR",
                            (col_idx, 1), (col_idx, 2),
                            colors.red,
                        )
                    elif current_date in half_days:
                        style.add(
                            "BACKGROUND",
                            (col_idx, 3), (col_idx, len(table_data) - 1),
                            light_green,
                        )
                        style.add(
                            "TEXTCOLOR",
                            (col_idx, 3), (col_idx, len(table_data) - 1),
                            colors.black,
                        )
                        style.add(
                            "FONTNAME",
                            (col_idx, 1), (col_idx, 1),
                            "Helvetica-Bold",
                        )
                        style.add(
                            "TEXTCOLOR",
                            (col_idx, 1), (col_idx, 2),
                            colors.green,
                        )
                    elif weekday == 5:
                        style.add(
                            "BACKGROUND",
                            (col_idx, 3), (col_idx, len(table_data) - 1),
                            light_blue,
                        )
                        style.add(
                            "TEXTCOLOR",
                            (col_idx, 3), (col_idx, len(table_data) - 1),
                            colors.black,
                        )
                        style.add(
                            "FONTNAME",
                            (col_idx, 1), (col_idx, 1),
                            "Helvetica-Bold",
                        )
                        style.add(
                            "TEXTCOLOR",
                            (col_idx, 1), (col_idx, 2),
                            colors.blue,
                        )

                # Orange veckolinjer
                current_week: Optional[int] = None
                for day_num in range(1, days_in_month + 1):
                    week = date(month_year, month_num, day_num).isocalendar()[1]
                    if week != current_week:
                        style.add(
                            "LINEBEFORE",
                            (day_num, 0), (day_num, -1),
                            1.5,
                            orange,
                        )
                        current_week = week

                table.setStyle(style)
                self._apply_table_scaling(table, table_width_pt)
                elements.append(table)

                if (month_year, month_num) != page_months[-1]:
                    elements.append(Spacer(1, 12))

            if page_index < len(pages) - 1:
                elements.append(PageBreak())

        doc.build(elements, **build_kwargs)

        selected_start_value = 0 if start_month is None else start_month
        start_text = (
            "Standard (Januari)"
            if start_month is None
            else f"{MONTHS_SV[start_month]} {year}"
        )

        # Storlek och tidsåtgång (v2.8.0)
        try:
            size_kb = Path(filename).stat().st_size / 1024
        except OSError:
            size_kb = 0.0

        logger.info(
            f"{title_prefix} genererad: {range_label} "
            f"({months_per_page} mån/blad, start={start_text}, "
            f"layout={orientation}) – {len(month_sequence)} månader, "
            f"{len(pages)} sidor, {size_kb:.0f} kB, "
            f"{(perf_counter() - started) * 1000:.0f} ms"
        )

        QMessageBox.information(
            None,
            "Klart",
            f"{title_prefix} har genererats!\n\n"
            f"Period: {range_label}\n"
            f"Fil: {filename}\n"
            f"Startval: {start_text}\n"
            f"Månader per blad: {months_per_page}\n"
            f"Sidlayout: {orientation}",
        )

        if self.plugin.settings.get("auto_open_pdf", True):
            webbrowser.open(filename)

        self.plugin.emit("semesterlista:pdf_generated", {
            "filename": filename,
            "year": year,
            "mode": mode,
            "items_count": len(data_list),
            "months_per_page": months_per_page,
            "orientation": orientation,
            "start_month": selected_start_value,
            "range_label": range_label,
            "spans_year_boundary": any(
                month_year != year for month_year, _ in month_sequence
            ),
            "start_year": month_sequence[0][0],
            "end_year": month_sequence[-1][0],
        })
        return True


# ══════════════════════════════════════════════════════════
# HUVUDVY
# ══════════════════════════════════════════════════════════

class SemesterlistaView(QWidget):
    """
    Huvudvy för Semesterlista & Limokörning.

    v2.2.0:
      - Standardläge om inget väljs
      - Manuellt val av startmånad kan gå över årsskifte
      - generate_requested skickar start_month_index
        0 = standard, 1–12 = explicit månad
    """

    generate_requested = Signal(str, str, str, int, int)
    # (year_str, file_path, mode, months_per_page, start_month_index)

    def __init__(
        self,
        plugin: "Plugin",
        parent: Optional[QWidget] = None,
        mode: Optional[str] = None,
        file_name: str = "",
    ):
        """
        Skapa vyn.

        Args:
            plugin:    Pluginet som äger vyn.
            parent:    Förälder-widget.
            mode:      Låst läge ("Semesterlista"/"Limokörning"). None =
                       användaren kan välja läge i listan.
            file_name: Standardfil när inget annat sparats.
        """
        super().__init__(parent)
        self.plugin: "Plugin" = plugin
        self._fixed_mode: Optional[str] = mode or plugin.FIXED_MODE
        self._default_file: str = file_name or plugin.DEFAULT_LIST_FILE
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        is_vehicle = (self._fixed_mode or "Semesterlista") != "Semesterlista"
        title = QLabel(i18n.t("fordon.title") if is_vehicle else i18n.t("lista.title"))
        title.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        main_layout.addWidget(title)

        desc = QLabel(
            i18n.t("fordon.description") if is_vehicle else i18n.t("lista.description")
        )
        desc.setFont(QFont("Helvetica", 10))
        desc.setStyleSheet("color: #666;")
        main_layout.addWidget(desc)
        main_layout.addSpacing(8)

        main_layout.addWidget(self._create_form_group())
        main_layout.addLayout(self._create_button_bar())
        main_layout.addWidget(self._create_legend_group())
        main_layout.addStretch()

    def _create_form_group(self) -> QGroupBox:
        """
        Skapa formulärgrupp med alla inställningar.

        Rad 1: Läge          [Semesterlista ▼]
        Rad 2: År            [2026 ↑↓]
        Rad 3: Startmånad    [Standard (Januari) ▼]
        Rad 4: Månader/blad  [1/2/3 ▼]
        Rad 5: Sidlayout     [Liggande/Stående ▼]   ← v2.6.0
        Rad 6: Fil           [Anställda.txt] [Bläddra...]
        Rad 7: Antal poster
        Rad 8: Logotyp
        """
        group = QGroupBox("Inställningar")
        form_layout = QGridLayout(group)
        form_layout.setContentsMargins(15, 20, 15, 15)
        form_layout.setSpacing(10)

        self.mode_label = QLabel("Läge:")
        self.mode_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(self.mode_label, 0, 0)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Semesterlista", "Limokörning"])
        default_mode = self._fixed_mode or self.plugin.settings.get(
            "default_mode", "Semesterlista"
        )
        idx = self.mode_combo.findText(default_mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.currentTextChanged.connect(self._on_mode_change)
        form_layout.addWidget(self.mode_combo, 0, 1)

        if self._fixed_mode:
            # Fliken har ett fast läge (t.ex. Fordon) – ingen väljare behövs
            self.mode_label.setVisible(False)
            self.mode_combo.setVisible(False)

        year_label = QLabel("År:")
        year_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(year_label, 1, 0)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setMinimumWidth(120)
        form_layout.addWidget(self.year_spin, 1, 1)

        start_label = QLabel("Startmånad:")
        start_label.setFont(QFont("Helvetica", 10))
        start_label.setToolTip(
            "Om inget väljs används standard:\n"
            "jan–dec för valt år.\n\n"
            "Väljer du en månad manuellt genereras 12 månader från den månaden.\n"
            "Exempel: December 2026 → Dec 2026, Jan 2027, ... Nov 2027."
        )
        form_layout.addWidget(start_label, 2, 0)

        self.start_month_combo = QComboBox()
        self.start_month_combo.addItems(MONTH_OPTIONS)
        self.start_month_combo.setToolTip(
            "Standard (Januari) = jan–dec valt år.\n"
            "Manuellt val = 12 sammanhängande månader från vald månad,\n"
            "och det kan gå över årsskifte."
        )
        saved_start = self.plugin.settings.get("start_month", 0)
        if isinstance(saved_start, int) and 0 <= saved_start <= 12:
            self.start_month_combo.setCurrentIndex(saved_start)
        else:
            self.start_month_combo.setCurrentIndex(0)
        self.start_month_combo.currentIndexChanged.connect(self._on_start_month_change)
        form_layout.addWidget(self.start_month_combo, 2, 1)

        months_label = QLabel("Månader/blad:")
        months_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(months_label, 3, 0)

        # 1, 2 eller 3 månader per blad (v2.6.0)
        self.months_per_page_combo = QComboBox()
        self.months_per_page_combo.addItems(
            [str(value) for value in MONTHS_PER_PAGE_OPTIONS]
        )
        self.months_per_page_combo.setToolTip(
            "Antal månader som ritas på samma blad i PDF:en:\n"
            "1 = en månad per sida (störst tabeller)\n"
            "2 = två månader per sida\n"
            "3 = tre månader per sida (standard)"
        )
        default_months = str(
            self.plugin.settings.get(
                "months_per_page", DEFAULT_MONTHS_PER_PAGE
            )
        )
        idx_m = self.months_per_page_combo.findText(default_months)
        if idx_m >= 0:
            self.months_per_page_combo.setCurrentIndex(idx_m)
        form_layout.addWidget(self.months_per_page_combo, 3, 1)

        # Sidlayout: liggande eller stående A4 (v2.6.0)
        layout_label = QLabel("Sidlayout:")
        layout_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(layout_label, 4, 0)

        self.orientation_combo = QComboBox()
        for value in ORIENTATIONS:
            self.orientation_combo.addItem(orientation_label(value), value)
        self.orientation_combo.setToolTip(
            "Liggande (A4) = breda tabeller, 270 mm (standard)\n"
            "Stående (A4) = vanlig A4 för pärm/utskrift, 190 mm tabell"
        )
        orientation_idx = self.orientation_combo.findData(
            normalize_orientation(self.plugin.settings.get("orientation"))
        )
        if orientation_idx >= 0:
            self.orientation_combo.setCurrentIndex(orientation_idx)
        form_layout.addWidget(self.orientation_combo, 4, 1)

        self.file_label = QLabel("Fil med anställda:")
        self.file_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(self.file_label, 5, 0)

        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setText(
            self.plugin.settings.get("last_file") or self._default_file
        )
        self.file_edit.setMinimumWidth(250)
        self.file_edit.editingFinished.connect(self._update_list_count)
        file_row.addWidget(self.file_edit)

        browse_btn = QPushButton(i18n.t("lista.button.browse"))
        browse_btn.setToolTip(i18n.t("lista.file.browse_tooltip"))
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)

        # Redigera listan direkt i programmet (v2.4.0)
        self.manage_btn = QPushButton("📝 " + i18n.t("lista.manage_list"))
        self.manage_btn.setToolTip(i18n.t("lista.manage_list.tooltip"))
        self.manage_btn.clicked.connect(self._manage_list)
        file_row.addWidget(self.manage_btn)

        form_layout.addLayout(file_row, 5, 1)

        self.count_label = QLabel("")
        self.count_label.setFont(QFont("Helvetica", 9))
        form_layout.addWidget(self.count_label, 6, 0, 1, 2)

        # Logotyp i PDF:en (v2.4.0) – väljs från assets-mappen
        logo_label = QLabel(i18n.t("logo.label"))
        logo_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(logo_label, 7, 0)

        logo_row = QHBoxLayout()
        self.logo_status = QLabel("")
        self.logo_status.setFont(QFont("Helvetica", 9))
        self.logo_status.setStyleSheet("color: #666;")
        logo_row.addWidget(self.logo_status, 1)

        self.logo_btn = QPushButton("🖼️ " + i18n.t("logo.choose"))
        self.logo_btn.setToolTip(i18n.t("logo.dialog_hint"))
        self.logo_btn.clicked.connect(self._choose_logo)
        logo_row.addWidget(self.logo_btn)

        self.logo_clear_btn = QPushButton(i18n.t("logo.clear"))
        self.logo_clear_btn.clicked.connect(self._clear_logo)
        logo_row.addWidget(self.logo_clear_btn)

        form_layout.addLayout(logo_row, 7, 1)

        self._update_logo_label()
        self._on_mode_change(self.mode_combo.currentText())
        self._update_list_count()
        return group

    def _create_button_bar(self) -> QHBoxLayout:
        """Skapa knappraden."""
        layout = QHBoxLayout()
        layout.setSpacing(10)

        generate_btn = QPushButton("🖨️ Generera PDF")
        generate_btn.setMinimumHeight(36)
        generate_btn.clicked.connect(self._generate_pdf)
        layout.addWidget(generate_btn)

        test_btn = QPushButton("🧪 Kör tester")
        test_btn.setMinimumHeight(36)
        test_btn.clicked.connect(self._run_tests)
        layout.addWidget(test_btn)

        folder_btn = QPushButton("📁 Öppna Dokument")
        folder_btn.setMinimumHeight(36)
        folder_btn.clicked.connect(self._open_documents)
        layout.addWidget(folder_btn)

        layout.addStretch()
        return layout

    def _create_legend_group(self) -> QGroupBox:
        """Skapa färgförklaringsruta."""
        group = QGroupBox("Färgförklaring i PDF")
        legend_layout = QVBoxLayout(group)
        legend_layout.setContentsMargins(15, 20, 15, 15)
        legend_layout.setSpacing(6)

        for color_hex, text in [
            (
                "#F08080",
                "Röd = Helgdagar och söndagar "
                "(Nyår, Påsk, Midsommardagen, Jul, etc.)",
            ),
            (
                "#ADD8E6",
                "Blå = Lördagar",
            ),
            (
                "#90EE90",
                "Grön = Halvdagar "
                "(Midsommarafton, Julafton, Nyårsafton, "
                "Skärtorsdag, Valborg, dag före Alla helgons dag)",
            ),
            (
                "#FFA500",
                "Orange linje = Ny vecka",
            ),
        ]:
            row = QHBoxLayout()
            box = QLabel("    ")
            box.setFixedSize(24, 18)
            box.setStyleSheet(
                f"background-color: {color_hex}; border: 1px solid #999;"
            )
            row.addWidget(box)
            row.addWidget(QLabel(text))
            row.addStretch()
            legend_layout.addLayout(row)

        return group

    @Slot(str)
    def _on_mode_change(self, mode: str) -> None:
        """Uppdatera fil-etikett, default-filnamn och antal poster."""
        if self._fixed_mode:
            mode = self._fixed_mode

        if mode == "Semesterlista":
            self.file_label.setText(i18n.t("lista.file.employees"))
            if not self.file_edit.text() or self.file_edit.text() == "Fordon.txt":
                self.file_edit.setText("Anställda.txt")
        else:
            self.file_label.setText(i18n.t("lista.file.vehicles"))
            if not self.file_edit.text() or self.file_edit.text() == "Anställda.txt":
                self.file_edit.setText("Fordon.txt")

        self._update_list_count()

    @Slot(int)
    def _on_start_month_change(self, index: int) -> None:
        """
        Spara valt index.

        0 = standard (jan–dec valt år)
        1–12 = explicit startmånad
        """
        self.plugin.settings["start_month"] = index
        self.plugin._save_settings()

    # ──────────────────────────────────────────────────────
    # Logotyp
    # ──────────────────────────────────────────────────────

    def _logo_path(self) -> str:
        """Sökvägen till vald logotyp ('' om ingen är vald)."""
        return str(self.plugin.settings.get("logo_svg") or "")

    def _update_logo_label(self) -> None:
        """Visa vald logotyp i formuläret."""
        if not hasattr(self, "logo_status"):
            return

        value = self._logo_path()
        if not value:
            self.logo_status.setStyleSheet("color: #666;")
            self.logo_status.setText(i18n.t("logo.no_logo"))
            return

        path = resolve_path(value)
        if not path.exists():
            self.logo_status.setStyleSheet("color: #c0392b;")
            self.logo_status.setText(i18n.t("logo.missing_file", path=path.name))
            return

        self.logo_status.setStyleSheet("color: #666;")
        self.logo_status.setText(i18n.t("logo.selected", name=path.name))

    def _choose_logo(self) -> None:
        """Öppna logotypväljaren (assets-mappen + undermappar)."""
        from core.logo_dialog import choose_logo

        changed, path = choose_logo(self, current=self._logo_path())
        if not changed:
            return

        self.plugin.settings["logo_svg"] = path
        self.plugin._save_settings()
        self._update_logo_label()

    def _clear_logo(self) -> None:
        """Ta bort logotypen från PDF-exporten."""
        if not self._logo_path():
            return

        self.plugin.settings["logo_svg"] = ""
        self.plugin._save_settings()
        self._update_logo_label()

    def _browse_file(self) -> None:
        """Öppna filväljardialog."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Välj fil",
            "",
            "Textfiler (*.txt);;Alla filer (*.*)",
        )
        if filename:
            self.file_edit.setText(filename)
            self._update_list_count()

    def _current_list_path(self) -> Path:
        """Sökväg till vald lista (relativa namn tolkas mot appens rotmapp)."""
        name = self.file_edit.text().strip()
        if not name:
            mode = self._fixed_mode or self.mode_combo.currentText()
            name = self._default_file if mode == "Limokörning" else "Anställda.txt"
        return resolve_path(name)

    def _manage_list(self) -> None:
        """
        Öppna listredigeraren för vald lista (v2.4.0).

        Användaren kan lägga till, ändra, ta bort och sortera poster
        direkt i programmet – ingen extern textredigerare behövs.
        """
        from core.list_editor_dialog import ListEditorDialog

        path = self._current_list_path()
        if ListEditorDialog.edit(path, name=path.stem, parent=self):
            self.file_edit.setText(str(path))
            self.plugin.settings["last_file"] = str(path)
            self.plugin._save_settings()
            self._update_list_count()

    def _update_list_count(self) -> None:
        """Visa antal poster i vald fil (varning om filen inte kan läsas)."""
        if not hasattr(self, "count_label"):
            return

        path = self._current_list_path()
        try:
            count = len(read_names(path))
        except RosterError as exc:
            self.count_label.setStyleSheet("color: #c0392b;")
            self.count_label.setText(i18n.t("lista.error.read", error=exc))
            return

        self.count_label.setStyleSheet("")
        if not path.exists():
            self.count_label.setText(i18n.t("lista.list_missing", file=path.name))
            return
        self.count_label.setText(i18n.t("lista.list_count", count=count))

    def _generate_pdf(self) -> None:
        """
        Hämta inställningar och starta PDF-generering.

        Om inget väljs i startmånad:
            start_index = 0
            start_month = None
            → standardläge (jan–dec valt år)

        Om t.ex. December väljs:
            start_index = 12
            start_month = 12
            → 12 månader från december, över årsskifte vid behov
        """
        year_str = str(self.year_spin.value())
        file_path = self.file_edit.text()
        mode = self.mode_combo.currentText()
        months_per_page = int(self.months_per_page_combo.currentText())
        orientation = normalize_orientation(
            self.orientation_combo.currentData()
        )
        start_index = self.start_month_combo.currentIndex()

        start_month: Optional[int]
        if start_index == 0:
            start_month = None
        else:
            start_month = start_index

        self.plugin.settings["last_file"] = file_path
        self.plugin.settings["default_mode"] = mode
        self.plugin.settings["months_per_page"] = months_per_page
        self.plugin.settings["orientation"] = orientation
        self.plugin.settings["start_month"] = start_index
        self.plugin._save_settings()

        generator = PDFGenerator(self.plugin)
        success = generator.generate(
            year_str=year_str,
            file_path=file_path,
            mode=mode,
            months_per_page=months_per_page,
            start_month=start_month,
            orientation=orientation,
        )

        if success:
            self.generate_requested.emit(
                year_str,
                file_path,
                mode,
                months_per_page,
                start_index,
            )

    def _run_tests(self) -> None:
        """Starta TestRunner."""
        TestRunner(self, self.plugin).run()

    def _open_documents(self) -> None:
        """Öppna dokumentmappen."""
        self.plugin._open_documents_folder()


# ══════════════════════════════════════════════════════════
# PLUGIN-KLASS
# ══════════════════════════════════════════════════════════

class Plugin(BasePlugin):
    """
    Semesterlista & Limokörning Plugin.

    v2.2.0:
      - Standardläge om ingen månad väljs
      - Manuellt val av startmånad över årsskifte
      - Exempel: Dec 2026 → Jan 2027
    """

    NAME: str = PLUGIN_INFO["name"]
    VERSION: str = "2.8.0"
    DESCRIPTION: str = PLUGIN_INFO["description"]
    AUTHOR: str = PLUGIN_INFO["author"]

    #: Flikens läge. None = användaren väljer mellan semester och limo.
    #: Fordonspluginet ärver denna klass och sätter "Limokörning".
    FIXED_MODE: Optional[str] = "Semesterlista"

    #: Standardfil när inget annat sparats
    DEFAULT_LIST_FILE: str = "Anställda.txt"

    #: Ordning bland flikarna i huvudfönstret (lägre = längre vänster)
    TAB_ORDER: int = 20

    def __init__(
        self,
        event_bus: "EventBus",
        settings_manager: "SettingsManager",
    ):
        super().__init__(event_bus, settings_manager)
        self.settings: Dict[str, Any] = self._load_settings()
        self._main_view: Optional[SemesterlistaView] = None

    def get_name(self) -> str:
        return self.NAME

    def get_version(self) -> str:
        return self.VERSION

    def get_tab_widget(self) -> QWidget:
        if self._main_view is None:
            self._main_view = SemesterlistaView(
                plugin=self,
                mode=self.FIXED_MODE,
                file_name=self.DEFAULT_LIST_FILE,
            )
        return self._main_view

    def _load_settings(self) -> Dict[str, Any]:
        """
        Ladda inställningar från SettingsManager + lokal JSON.

        Defaults:
            default_mode:    "Semesterlista"
            auto_open_pdf:   True
            default_year:    innevarande år
            last_file:       ""
            months_per_page: 3
            start_month:     0  (0=Standard/Januari, 1–12=explicit månad)
        """
        default_settings: Dict[str, Any] = {
            "default_mode": "Semesterlista",
            "auto_open_pdf": True,
            "default_year": datetime.now().year,
            "last_file": "",
            "months_per_page": DEFAULT_MONTHS_PER_PAGE,
            "orientation": DEFAULT_ORIENTATION,
            "start_month": 0,
            "logo_svg": "",
        }

        if self.FIXED_MODE:
            default_settings["default_mode"] = self.FIXED_MODE
            default_settings["last_file"] = self.DEFAULT_LIST_FILE

        try:
            saved = self.get_settings()
            if saved:
                default_settings.update(saved)
                return default_settings
        except Exception:
            pass

        settings_file = self._settings_file()
        try:
            if os.path.exists(settings_file):
                with open(settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
        except Exception as e:
            logger.error(f"Fel vid laddning av inställningar: {e}")

        return default_settings

    def _settings_file(self) -> str:
        """
        Sökväg till pluginets lokala JSON-inställningsfil (v2.4.0).

        Huvudpluginet behåller "settings.json" för bakåtkompatibilitet;
        ärvda plugins (t.ex. Fordon) får en egen fil så att de inte
        skriver över varandras inställningar.
        """
        folder = get_plugin_data_folder()
        if self.get_name() == PLUGIN_INFO["name"]:
            return os.path.join(folder, "settings.json")

        safe = "".join(
            char for char in self.get_name().casefold() if char.isalnum()
        ) or "plugin"
        return os.path.join(folder, f"settings-{safe}.json")

    def _save_settings(self) -> None:
        """Spara inställningar till SettingsManager + lokal JSON."""
        try:
            self.save_settings(self.settings)
        except Exception:
            pass

        settings_file = self._settings_file()
        try:
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            logger.info("Inställningar sparade")
        except Exception as e:
            logger.error(f"Fel vid sparande av inställningar: {e}")

    def initialize(self) -> bool:
        logger.info(f"Initierar {self.NAME} v{self.VERSION}")
        self.subscribe("app:shutting_down", self._on_app_shutdown)
        self.subscribe("theme:changed", self._on_theme_changed)
        self._is_initialized = True
        self.emit("plugin:loaded", {
            "name": self.get_name(),
            "version": self.get_version(),
        })
        return True

    def shutdown(self) -> None:
        logger.info(f"Stänger ner {self.NAME}")
        self._save_settings()
        try:
            self.save_settings({
                "default_mode": self.settings.get("default_mode", "Semesterlista"),
                "auto_open_pdf": self.settings.get("auto_open_pdf", True),
                "last_file": self.settings.get("last_file", ""),
                "months_per_page": self.settings.get("months_per_page", 3),
                "start_month": self.settings.get("start_month", 0),
                "last_used": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error(f"Kunde inte spara inställningar: {e}")

        if self._main_view is not None:
            self._main_view.deleteLater()
            self._main_view = None

        super().shutdown()

    def _on_app_shutdown(self, data: Any = None) -> None:
        self.shutdown()

    def _on_theme_changed(self, data: Any = None) -> None:
        theme = (
            data.get("theme", "unknown")
            if isinstance(data, dict)
            else "unknown"
        )
        logger.info(f"Tema ändrat till: {theme}")

    def _show_main_view(self) -> None:
        _ = self.get_tab_widget()
        self.emit("semesterlista:view_shown", {
            "mode": self.settings.get("default_mode", "Semesterlista"),
        })

    def _show_settings(self) -> None:
        if self._main_view is not None:
            dialog = SettingsDialog(self._main_view, self)
            dialog.exec()
            self.emit("semesterlista:settings_changed", self.settings)

    def _open_documents_folder(self) -> None:
        path = get_documents_folder()
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                import subprocess
                subprocess.run(["open", path], check=False)
            else:
                import subprocess
                subprocess.run(["xdg-open", path], check=False)
            self.emit("semesterlista:folder_opened", {"path": path})
        except Exception as e:
            QMessageBox.critical(None, "Fel", f"Kunde inte öppna mapp:\n{e}")

    @property
    def main_view(self) -> Optional[SemesterlistaView]:
        return self._main_view