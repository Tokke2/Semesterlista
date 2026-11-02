"""
Hyresfakturering Plugin – UPPDATERAD (PySide6 + BasePlugin)
============================================================

Plugin för att generera hyreslistor med tomma kryssrutor för
månads- och kvartalshyresgäster.

FIXAT v2.8.1:     Årbytet tömde hela sidan. Vyn byggdes om med en ny
                   QVBoxLayout(self) trots att widgeten redan hade en layout,
                   vilket Qt vägrar – nu återanvänds rotlayouten och bara
                   kvartalskorten byts ut på plats (fokus ligger kvar i
                   årväljaren).

UPPDATERAD v2.5.0: Fliken heter "Hyra" (TAB_ORDER 10).
                   Logotyp i PDF:en: "Välj logotyp…" hämtar en bild från
                   appens assets-mapp (även undermappar) och ritar den i
                   övre högra hörnet på varje sida.
                   Inställningarna sparas per plugin (self.settings).

UPPDATERAD v2.2.0: Synkad med settings_manager.py v2.2.0,
                   base_plugin.py v2.2.0, event_bus.py v2.2.0
                   och theme_manager.py v2.2.0.
                   VERSION bumpat till 2.2.0.
                   PLUGIN_INFO version bumpat till 2.2.0.
                   shutdown() sparar nu last_file.
                   _open_tenant_file() använder subprocess check=False.
                   copyright tillagd.

Konverterad från tkinter till PySide6 enligt specifikationen:
- Ärver från plugins.base_plugin.BasePlugin
- Använder EventBus för kommunikation
- Använder SettingsManager för JSON-inställningar
- PySide6-baserat UI (QWidget, QTabWidget-kompatibelt)
- Behåller ALL ursprunglig funktionalitet

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import os
import platform
import webbrowser
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QSpinBox,
    QFrame,
    QScrollArea,
    QMessageBox,
    QSizePolicy,
    QFileDialog,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

from core import i18n
from core.pdf_assets import (
    AssetError,
    PdfLogo,
    logo_for_settings,
    make_logo_canvas,
)
from core.roster import RosterError, RosterFile, resolve_path

from plugins.base_plugin import BasePlugin

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# PLUGIN-METADATA
# ══════════════════════════════════════════════════════════

PLUGIN_INFO = {
    "id":          "hyresfakturering",
    "name":        "Hyresfakturering",
    "version":     "2.9.0",
    "author":      "Din Organisation",
    "description": "Generera hyreslistor med tomma kryssrutor",
}

DEFAULT_TENANT_FILE = "Hyresgäster.txt"
SEPARATOR           = "-------"

#: Exempelinnehåll när Hyresgäster.txt skapas första gången
EXAMPLE_MONTHLY_TENANTS: List[str] = [
    "Anna Andersson",
    "Bertil Bengtsson",
    "Cecilia Carlsson",
]
EXAMPLE_QUARTERLY_TENANTS: List[str] = [
    "Företag AB",
    "Konsult & Co",
]

MONTHS: Dict[int, str] = {
    1: "Jan",  2: "Feb",  3: "Mar",  4: "Apr",
    5: "Maj",  6: "Jun",  7: "Jul",  8: "Aug",
    9: "Sep", 10: "Okt", 11: "Nov", 12: "Dec",
}

QUARTER_INVOICE_DATES: Dict[int, str] = {
    1: "1 december",
    2: "1 mars",
    3: "1 juni",
    4: "1 september",
}

QUARTER_INFO: Dict[int, dict] = {
    1: {"period": "Januari – Mars",      "send_month": 12},
    2: {"period": "April – Juni",         "send_month": 3},
    3: {"period": "Juli – September",     "send_month": 6},
    4: {"period": "Oktober – December",   "send_month": 9},
}


# ══════════════════════════════════════════════════════════
# HJÄLPFUNKTIONER (modulnivå)
# ══════════════════════════════════════════════════════════

def get_documents_folder() -> str:
    """Returnerar sökvägen till användarens Dokument-mapp."""
    path = Path.home() / "Documents"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_app_folder() -> str:
    """Returnerar sökvägen till app-mappen (där main.py ligger)."""
    return str(Path(__file__).parent.parent.parent)


def get_all_quarter_invoice_info(year: int) -> List[Dict[str, Any]]:
    """
    Returnera info om alla kvartalsfakturor för ett år.

    Beräknar antal dagar till/från varje fakturadatum och
    sätter status: passerad, idag, brådskande, snart, kommande.
    """
    today           = date.today()
    quarters_info:  List[Dict[str, Any]] = []

    for q in range(1, 5):
        info = QUARTER_INFO[q]

        if q == 1:
            send_date = date(year - 1, info["send_month"], 1)
        else:
            send_date = date(year, info["send_month"], 1)

        days_diff = (send_date - today).days

        if days_diff < 0:
            status      = "passerad"
            status_text = "Passerad"
        elif days_diff == 0:
            status      = "idag"
            status_text = "IDAG!"
        elif days_diff <= 7:
            status      = "brådskande"
            status_text = f"{days_diff} dagar"
        elif days_diff <= 30:
            status      = "snart"
            status_text = f"{days_diff} dagar"
        else:
            status      = "kommande"
            status_text = f"{days_diff} dagar"

        quarters_info.append({
            "quarter":       q,
            "period":        info["period"],
            "send_date_str": QUARTER_INVOICE_DATES[q],
            "status":        status,
            "status_text":   status_text,
        })

    return quarters_info


def calculate_text_width(text: str, font_size: int = 10) -> float:
    """Beräkna ungefärlig textbredd i punkter."""
    avg_char_width = font_size * 0.5
    return len(str(text)) * avg_char_width + 10


# ══════════════════════════════════════════════════════════
# HYRESGÄSTHANTERARE
# ══════════════════════════════════════════════════════════

class TenantManager:
    """
    Hanterar hyresgästlistan (Hyresgäster.txt).

    v2.4.0: all inläsning sker via core/roster.py och listan kan
            redigeras direkt i appen (core/list_editor_dialog.py).

    Läsning och skrivning sker via core/roster.py, vilket ger:
      - kommentarer (# eller ;) ignoreras
      - en rad med streck (-------) skiljer månads- från kvartalshyresgäster
      - automatisk teckenkodning (UTF-8/cp1252), dubblettkontroll och
        normaliserade blanksteg
      - atomär skrivning med backup (*.bak)

    Textfilformat:
        # Kommentar
        Namn 1
        Namn 2
        -------
        # Kvartalshyresgäster
        Företag AB
    """

    def __init__(self, tenant_file: Optional[str] = None):
        """Initiera TenantManager och ladda hyresgäster."""
        self.tenant_file: str = str(
            tenant_file or os.path.join(get_app_folder(), DEFAULT_TENANT_FILE)
        )
        self.monthly_tenants:   List[str] = []
        self.quarterly_tenants: List[str] = []
        self.year:              int       = datetime.now().year
        self.load_issues:       List[str] = []
        self.roster:            RosterFile = RosterFile(path=Path(self.tenant_file),
                                                        name="Hyresgäster")
        self._load_tenants()

    # ──────────────────────────────────────────────────────
    # Inläsning
    # ──────────────────────────────────────────────────────

    def _load_tenants(self) -> None:
        """Läs hyresgäster via core.roster (skapar filen vid behov)."""
        try:
            self.roster = RosterFile.load(
                self.tenant_file,
                name="Hyresgäster",
                create=True,
                default_sections=[
                    EXAMPLE_MONTHLY_TENANTS,
                    EXAMPLE_QUARTERLY_TENANTS,
                ],
            )
        except RosterError as exc:
            logger.error(f"Fel vid läsning av hyresgästfil: {exc}")
            self.load_issues = [str(exc)]
            self.monthly_tenants = []
            self.quarterly_tenants = []
            return

        self.monthly_tenants   = list(self.roster.section(0))
        self.quarterly_tenants = list(self.roster.section(1))
        self.load_issues = [
            issue.message for issue in self.roster.load_issues
        ] + [
            issue.message for issue in self.roster.validate()
        ]

        for message in self.load_issues:
            logger.warning(f"Hyresgäster: {message}")

        logger.info(
            f"Laddade {len(self.monthly_tenants)} månadshyresgäster "
            f"och {len(self.quarterly_tenants)} kvartalshyresgäster"
        )

    def _create_example_file(self) -> None:
        """Skapa Hyresgäster.txt med exempelinnehåll om den saknas."""
        if Path(self.tenant_file).exists():
            return
        try:
            RosterFile.load(
                self.tenant_file,
                name="Hyresgäster",
                create=True,
                default_sections=[
                    EXAMPLE_MONTHLY_TENANTS,
                    EXAMPLE_QUARTERLY_TENANTS,
                ],
            )
            logger.info(f"Skapade exempelfil: {self.tenant_file}")
        except RosterError as exc:
            logger.error(f"Kunde inte skapa exempelfil: {exc}")

    def reload(self) -> None:
        """Ladda om hyresgäster från fil."""
        self.monthly_tenants   = []
        self.quarterly_tenants = []
        self._load_tenants()

    def get_monthly_tenants(self) -> List[str]:
        """Returnera lista med månadshyresgäster."""
        return self.monthly_tenants

    def get_quarterly_tenants(self) -> List[str]:
        """Returnera lista med kvartalshyresgäster."""
        return self.quarterly_tenants

    def get_year(self) -> int:
        """Returnera aktuellt år."""
        return self.year

    def set_year(self, year: int) -> None:
        """Sätt år för fakturering."""
        self.year = year

    def get_max_name_length(self) -> int:
        """Returnera längden på det längsta hyresgäst-namnet."""
        all_names = self.monthly_tenants + self.quarterly_tenants
        if not all_names:
            return 10
        return max(len(name) for name in all_names)


# ══════════════════════════════════════════════════════════
# HUVUDVY
# ══════════════════════════════════════════════════════════

class HyraMainView(QWidget):
    """
    Huvudvy för Hyresfakturering – PySide6-baserad.

    Innehåller:
      - Toppanel med titel + år-väljare
      - Fil-info-rad med Redigera + Ladda om
      - Kvartalsfaktura-panel (färgkodade kort)
      - Hyresgäst-översikt (månads + kvartal)
      - Knapprad (Generera PDF, Redigera fil)
    """

    year_changed     = Signal(int)
    reload_requested = Signal()

    def __init__(
        self,
        tenant_manager: TenantManager,
        plugin_ref:     "Plugin",
        parent:         Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.tm:     TenantManager = tenant_manager
        self.plugin: "Plugin"      = plugin_ref
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        # Rotlayouten skapas en gång och återanvänds vid uppdateringar.
        # Annars blir vyn tom: Qt vägrar sätta en ny layout på en widget som
        # redan har en (”QLayout: Attempting to add QLayout …”) – det var
        # felet när man bytte år (v2.8.1).
        self._main_layout:    Optional[QVBoxLayout] = None
        self._quarter_group:  Optional[QGroupBox]   = None
        self._init_ui()

    def _init_ui(self) -> None:
        """Bygg (eller bygg om) hela gränssnittet."""
        if self._main_layout is None:
            self._main_layout = QVBoxLayout(self)

        main_layout = self._main_layout
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        main_layout.addLayout(self._create_top_panel())
        main_layout.addLayout(self._create_file_info_row())
        self._update_logo_label()

        self._quarter_group = self._create_quarter_info_panel()
        main_layout.addWidget(self._quarter_group)

        main_layout.addWidget(self._create_tenant_overview(), stretch=1)
        main_layout.addLayout(self._create_button_bar())

    def _create_top_panel(self) -> QHBoxLayout:
        """Skapa toppanel med titel och år-väljare."""
        layout = QHBoxLayout()

        title = QLabel("🏠 Hyresfakturering")
        title.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()

        year_label = QLabel("År:")
        year_label.setFont(QFont("Helvetica", 10))
        layout.addWidget(year_label)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2050)
        self.year_spin.setValue(self.tm.get_year())
        self.year_spin.setFixedWidth(80)
        self.year_spin.valueChanged.connect(self._on_year_change)
        layout.addWidget(self.year_spin)

        return layout

    def _create_file_info_row(self) -> QHBoxLayout:
        """Skapa rad med fil-info, Redigera-knapp och Ladda om-knapp."""
        layout = QHBoxLayout()

        file_label = QLabel(f"📁 Fil: {DEFAULT_TENANT_FILE}")
        file_label.setFont(QFont("Helvetica", 9))
        layout.addWidget(file_label)
        layout.addStretch()

        # Logotyp i PDF:en (v2.4.0) – väljs från assets-mappen
        self.logo_status = QLabel("")
        self.logo_status.setFont(QFont("Helvetica", 9))
        self.logo_status.setStyleSheet("color: #666;")
        layout.addWidget(self.logo_status)

        self.logo_btn = QPushButton("🖼️ " + i18n.t("logo.choose"))
        self.logo_btn.setToolTip(i18n.t("logo.dialog_hint"))
        self.logo_btn.clicked.connect(self._choose_logo)
        layout.addWidget(self.logo_btn)

        self.logo_clear_btn = QPushButton(i18n.t("logo.clear"))
        self.logo_clear_btn.clicked.connect(self._clear_logo)
        layout.addWidget(self.logo_clear_btn)

        edit_btn = QPushButton("📝 " + i18n.t("hyra.manage_tenants"))
        edit_btn.clicked.connect(self.plugin._manage_tenants)
        edit_btn.setToolTip(i18n.t("hyra.manage_tenants.tooltip"))
        layout.addWidget(edit_btn)

        reload_btn = QPushButton("🔄 Ladda om")
        reload_btn.clicked.connect(self._reload)
        reload_btn.setToolTip("Ladda om hyresgäster från fil")
        layout.addWidget(reload_btn)

        return layout

    # ──────────────────────────────────────────────────────
    # Logotyp (v2.4.0)
    # ──────────────────────────────────────────────────────

    def _logo_path(self) -> str:
        """Sökvägen till vald logotyp ('' om ingen är vald)."""
        return str(self.plugin.settings.get("logo_svg") or "")

    def _update_logo_label(self) -> None:
        """Visa vald logotyp i fil-raden."""
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

    def _create_quarter_info_panel(self) -> QGroupBox:
        """Skapa färgkodad info-panel för kvartalsfakturor."""
        group = QGroupBox("📅 Kvartalsfakturor – Skicka senast")
        group_layout = QGridLayout(group)
        group_layout.setContentsMargins(10, 20, 10, 10)
        group_layout.setSpacing(4)

        year = self.tm.get_year()
        quarters_info = get_all_quarter_invoice_info(year)

        for i, info in enumerate(quarters_info):
            match info["status"]:
                case "passerad":
                    bg, fg = "#E0E0E0", "#666666"
                case "idag":
                    bg, fg = "#FF6666", "#FFFFFF"
                case "brådskande":
                    bg, fg = "#FFCCCC", "#000000"
                case "snart":
                    bg, fg = "#FFFFCC", "#000000"
                case _:
                    bg, fg = "#CCFFCC", "#000000"

            card = QFrame()
            card.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
            card.setStyleSheet(
                f"background-color: {bg}; "
                f"border: 1px solid #CCC; "
                f"border-radius: 4px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 8, 8, 8)
            card_layout.setSpacing(2)

            q_label = QLabel(f"Q{info['quarter']}")
            q_label.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
            q_label.setStyleSheet(
                f"color: {fg}; background: transparent; border: none;"
            )
            q_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(q_label)

            period_label = QLabel(info["period"])
            period_label.setFont(QFont("Helvetica", 8))
            period_label.setStyleSheet(
                f"color: {fg}; background: transparent; border: none;"
            )
            period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(period_label)

            send_label = QLabel(f"Skickas: {info['send_date_str']}")
            send_label.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
            send_label.setStyleSheet(
                f"color: {fg}; background: transparent; border: none;"
            )
            send_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(send_label)

            status_label = QLabel(info["status_text"])
            status_label.setFont(QFont("Helvetica", 9))
            status_label.setStyleSheet(
                f"color: {fg}; background: transparent; border: none;"
            )
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(status_label)

            group_layout.addWidget(card, 0, i)

        for col in range(4):
            group_layout.setColumnStretch(col, 1)

        return group

    def _create_tenant_overview(self) -> QWidget:
        """Skapa översiktspanel med månads- och kvartalshyresgäster."""
        container = QWidget()
        layout    = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        left_group = self._create_tenant_group(
            "Månadshyresgäster",
            self.tm.get_monthly_tenants(),
        )
        layout.addWidget(left_group, stretch=1)

        right_group = self._create_tenant_group(
            "Kvartalshyresgäster",
            self.tm.get_quarterly_tenants(),
        )
        layout.addWidget(right_group, stretch=1)

        return container

    def _create_tenant_group(
        self,
        title:   str,
        tenants: List[str],
    ) -> QGroupBox:
        """Skapa en gruppruta med lista av hyresgäster."""
        group        = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(2)

        if tenants:
            for i, name in enumerate(tenants):
                bg  = "#F5F5F5" if i % 2 == 0 else "#FFFFFF"
                lbl = QLabel(f"• {name}")
                lbl.setFont(QFont("Helvetica", 10))
                lbl.setStyleSheet(
                    f"background-color: {bg}; "
                    f"padding: 4px 8px; "
                    f"border-radius: 2px;"
                )
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
                group_layout.addWidget(lbl)
        else:
            empty = QLabel("Inga hyresgäster\n\nRedigera Hyresgäster.txt")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #888; padding: 20px;")
            group_layout.addWidget(empty)

        group_layout.addStretch()

        total = QLabel(f"Totalt: {len(tenants)} st")
        total.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
        group_layout.addWidget(total)

        return group

    def _create_button_bar(self) -> QHBoxLayout:
        """Skapa knapprad längst ner."""
        layout = QHBoxLayout()
        layout.setSpacing(8)

        pdf_btn = QPushButton("🖨️ Generera PDF")
        pdf_btn.setMinimumHeight(36)
        pdf_btn.clicked.connect(self.plugin._generate_pdf)
        pdf_btn.setToolTip("Generera hyreslista som PDF")
        layout.addWidget(pdf_btn)

        edit_btn = QPushButton("📝 " + i18n.t("hyra.manage_tenants"))
        edit_btn.setMinimumHeight(36)
        edit_btn.clicked.connect(self.plugin._manage_tenants)
        edit_btn.setToolTip(i18n.t("hyra.manage_tenants.tooltip"))
        layout.addWidget(edit_btn)

        layout.addStretch()
        return layout

    @Slot(int)
    def _on_year_change(self, value: int) -> None:
        """
        Hantera ändring av år i spinbox.

        Bara kvartalskorten byggs om – resten av vyn (inklusive spinboxen som
        användaren just klickar i) lämnas orörd, så fokus och sidan behålls.
        """
        self.tm.set_year(value)
        self.year_changed.emit(value)
        self._refresh_quarter_panel()

    def _reload(self) -> None:
        """Ladda om data och uppdatera UI."""
        self.tm.reload()
        self.reload_requested.emit()
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        """
        Uppdatera hela gränssnittet.

        Rotlayouten behålls – bara innehållet byts ut (v2.8.1).
        """
        if self._main_layout is not None:
            self._clear_layout(self._main_layout)
        self._quarter_group = None
        self._init_ui()

    def _refresh_quarter_panel(self) -> None:
        """
        Uppdatera kvartalskorten på plats (året ändrades).

        Widgeten byts med ``replaceWidget`` i stället för att hela vyn rivs,
        så att sidan aldrig blir tom och årsspinboxen behåller fokus.
        """
        new_group = self._create_quarter_info_panel()
        layout    = self._main_layout

        if layout is not None and self._quarter_group is not None:
            old_group = self._quarter_group
            layout.replaceWidget(old_group, new_group)
            # Koppla loss direkt – deleteLater() sker först i event-loopen
            old_group.hide()
            old_group.setParent(None)
            old_group.deleteLater()
            self._quarter_group = new_group
            return

        # Reservväg: inget att byta ut – bygg om hela vyn
        self._refresh_ui()

    @staticmethod
    def _clear_layout(layout) -> None:
        """Rekursivt rensa en layout från alla widgets."""
        if layout is None:
            return
        while layout.count():
            item   = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Ta bort direkt ur trädet så att inget gammalt ligger kvar
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                HyraMainView._clear_layout(item.layout())


# ══════════════════════════════════════════════════════════
# PDF-GENERATOR
# ══════════════════════════════════════════════════════════

class PDFGenerator:
    """
    Genererar PDF-rapport med tomma kryssrutor och dynamiska kolumner.

    Skapar:
      - Titelsida med år
      - Kvartalsfaktura-information
      - Månadstabell (Hyresgäst + Jan–Dec)
      - Kvartaltabell (Hyresgäst + Q1–Q4)
      - Footer med genereringsdatum
    """

    def __init__(self, plugin: "Plugin"):
        """Initiera PDFGenerator med plugin-referens."""
        self.plugin: "Plugin"        = plugin
        self.tm:     TenantManager   = plugin.tenant_manager

    def generate(self) -> bool:
        """Generera PDF och öppna den automatiskt."""
        year           = self.tm.get_year()
        documents_path = get_documents_folder()
        filename       = os.path.join(
            documents_path, f"hyreslista_{year}.pdf"
        )
        monthly    = self.tm.get_monthly_tenants()
        quarterly  = self.tm.get_quarterly_tenants()

        if not monthly and not quarterly:
            QMessageBox.warning(
                None,
                "Varning",
                "Inga hyresgäster!\n\nRedigera Hyresgäster.txt först.",
            )
            return False

        try:
            # Logotyp (v2.4.0) – ritas i övre högra hörnet på varje sida
            logo_canvas = make_logo_canvas(
                self._page_logo(), margin_mm=8.0, corner="right"
            )
            build_kwargs: Dict[str, Any] = {}
            if logo_canvas is not None:
                build_kwargs["canvasmaker"] = logo_canvas

            doc = SimpleDocTemplate(
                filename,
                pagesize=A4,
                rightMargin=10 * mm,
                leftMargin=10 * mm,
                topMargin=10 * mm,
                bottomMargin=10 * mm,
            )
            styles   = getSampleStyleSheet()
            elements: list = []

            # Titel
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=22,
                spaceAfter=10,
                alignment=1,
            )
            elements.append(Paragraph(f"Hyreslista {year}", title_style))
            elements.append(Spacer(1, 5))

            # Kvartalsinformation
            self._add_quarter_info(elements, styles)
            elements.append(Spacer(1, 15))

            # Månadstabell
            if monthly:
                section_style = ParagraphStyle(
                    "SectionTitle",
                    parent=styles["Heading2"],
                    fontSize=14,
                    spaceAfter=8,
                )
                elements.append(
                    Paragraph("Månadshyresgäster", section_style)
                )
                elements.append(self._create_monthly_table(monthly))
                elements.append(Spacer(1, 20))

            # Kvartaltabell
            if quarterly:
                section_style = ParagraphStyle(
                    "SectionTitle",
                    parent=styles["Heading2"],
                    fontSize=14,
                    spaceAfter=8,
                )
                elements.append(
                    Paragraph("Kvartalshyresgäster", section_style)
                )
                elements.append(self._create_quarterly_table(quarterly))

            # Footer
            elements.append(Spacer(1, 25))
            footer_style = ParagraphStyle(
                "Footer",
                fontSize=8,
                textColor=colors.grey,
                alignment=1,
            )
            elements.append(Paragraph(
                f"Genererad: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                footer_style,
            ))

            doc.build(elements, **build_kwargs)

            QMessageBox.information(
                None,
                "Klart",
                f"PDF genererad!\n\n{filename}",
            )
            webbrowser.open(filename)

            self.plugin.emit("hyresfakturering:pdf_generated", {
                "filename":        filename,
                "year":            year,
                "monthly_count":   len(monthly),
                "quarterly_count": len(quarterly),
            })
            return True

        except Exception as e:
            logger.error(f"Fel vid PDF-generering: {e}")
            QMessageBox.critical(
                None,
                "Fel",
                f"Kunde inte generera PDF:\n{e}",
            )
            return False

    def _page_logo(self) -> Optional[PdfLogo]:
        """Ladda vald logotyp (None om ingen är vald eller filen saknas)."""
        try:
            return logo_for_settings(
                self.plugin.settings,
                key="logo_svg",
                max_width_mm=30.0,
                max_height_mm=12.0,
            )
        except AssetError as exc:
            logger.warning(f"Logotypen kunde inte laddas: {exc}")
            return None

    def _add_quarter_info(self, elements: list, styles) -> None:
        """Lägg till kvartalsfaktura-information i PDF."""
        header_style = ParagraphStyle(
            "QuarterHeader",
            fontSize=11,
            spaceAfter=5,
            alignment=1,
            fontName="Helvetica-Bold",
        )
        elements.append(
            Paragraph("Kvartalsfakturor – Skicka senast:", header_style)
        )

        quarter_data = [[
            "Q1: 1 december\n(Jan–Mar)",
            "Q2: 1 mars\n(Apr–Jun)",
            "Q3: 1 juni\n(Jul–Sep)",
            "Q4: 1 september\n(Okt–Dec)",
        ]]
        quarter_table = Table(quarter_data)
        quarter_table.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("BACKGROUND",    (0, 0), (-1, -1), colors.Color(0.93, 0.93, 0.93)),
            ("BOX",           (0, 0), (-1, -1), 1, colors.Color(0.7, 0.7, 0.7)),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 15),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 15),
        ]))
        elements.append(quarter_table)

    def _create_monthly_table(self, tenants: List[str]) -> Table:
        """Skapa tabell för månadshyresgäster med dynamiska kolumner."""
        max_name_len = max(len(name) for name in tenants) if tenants else 10
        name_width   = max(max_name_len * 6 + 15, 80)
        month_width  = (190 * mm - name_width) / 12

        header = ["Hyresgäst"] + [MONTHS[m] for m in range(1, 13)]
        data   = [header]
        for name in tenants:
            data.append([name] + [""] * 12)

        col_widths = [name_width] + [month_width] * 12
        table      = Table(data, colWidths=col_widths)

        style_cmds = [
            ("BOX",           (0, 0), (-1, -1), 1, colors.Color(0.4, 0.4, 0.4)),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, colors.Color(0.7, 0.7, 0.7)),
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.Color(0.85, 0.85, 0.85)),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  9),
            ("ALIGN",         (0, 0), (0, -1),  "LEFT"),
            ("FONTNAME",      (0, 1), (0, -1),  "Helvetica"),
            ("FONTSIZE",      (0, 1), (0, -1),  9),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("FONTSIZE",      (1, 1), (-1, -1), 10),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_cmds.append((
                    "BACKGROUND",
                    (0, i), (-1, i),
                    colors.Color(0.96, 0.96, 0.96),
                ))

        table.setStyle(TableStyle(style_cmds))
        return table

    def _create_quarterly_table(self, tenants: List[str]) -> Table:
        """Skapa tabell för kvartalshyresgäster med dynamiska kolumner."""
        max_name_len  = max(len(name) for name in tenants) if tenants else 10
        name_width    = max(max_name_len * 6 + 15, 100)
        quarter_width = (190 * mm - name_width) / 4

        header = [
            "Hyresgäst",
            "Q1\nJan–Mar",
            "Q2\nApr–Jun",
            "Q3\nJul–Sep",
            "Q4\nOkt–Dec",
        ]
        data = [header]
        for name in tenants:
            data.append([name] + [""] * 4)

        col_widths = [name_width] + [quarter_width] * 4
        table      = Table(data, colWidths=col_widths)

        style_cmds = [
            ("BOX",           (0, 0), (-1, -1), 1, colors.Color(0.4, 0.4, 0.4)),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, colors.Color(0.7, 0.7, 0.7)),
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.Color(0.85, 0.85, 0.85)),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  10),
            ("ALIGN",         (0, 0), (0, -1),  "LEFT"),
            ("FONTNAME",      (0, 1), (0, -1),  "Helvetica"),
            ("FONTSIZE",      (0, 1), (0, -1),  10),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("FONTSIZE",      (1, 1), (-1, -1), 11),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_cmds.append((
                    "BACKGROUND",
                    (0, i), (-1, i),
                    colors.Color(0.96, 0.96, 0.96),
                ))

        table.setStyle(TableStyle(style_cmds))
        return table


# ══════════════════════════════════════════════════════════
# PLUGIN-KLASS
# ══════════════════════════════════════════════════════════

class Plugin(BasePlugin):
    """
    Hyresfakturering Plugin.

    v2.2.0: VERSION synkad, last_file sparas vid shutdown,
            subprocess check=False för plattformsöppning.
    """

    NAME:        str = PLUGIN_INFO["name"]
    VERSION:     str = "2.9.0"
    DESCRIPTION: str = PLUGIN_INFO["description"]
    AUTHOR:      str = PLUGIN_INFO["author"]

    #: Ordning bland flikarna i huvudfönstret (lägst = längst till vänster)
    TAB_ORDER:   int = 10

    def __init__(
        self,
        event_bus:        "EventBus",
        settings_manager: "SettingsManager",
    ):
        super().__init__(event_bus, settings_manager)
        self.tenant_manager: TenantManager          = TenantManager()
        self._main_view:     Optional[HyraMainView] = None

        # Lokal kopia av pluginets inställningar (v2.4.0 – logotyp m.m.)
        self.settings: Dict[str, Any] = dict(self.get_settings() or {})
        self.settings.setdefault("logo_svg", "")

        # Återställ sparat år
        saved = self.get_settings()
        if saved and "year" in saved:
            try:
                self.tenant_manager.set_year(int(saved["year"]))
            except (ValueError, TypeError):
                pass

    def get_name(self) -> str:
        """Returnera pluginens unika namn."""
        return self.NAME

    def _save_settings(self) -> None:
        """Spara pluginets inställningar till plugins.json (v2.4.0)."""
        try:
            self.save_settings(self.settings)
        except Exception as exc:  # pragma: no cover – defensivt
            logger.error(f"Kunde inte spara inställningar: {exc}")

    def get_version(self) -> str:
        """Returnera pluginens versionssträng."""
        return self.VERSION

    def get_tab_widget(self) -> QWidget:
        """Returnera widget för tabb-visning i MainApp."""
        if self._main_view is None:
            self._main_view = HyraMainView(
                tenant_manager=self.tenant_manager,
                plugin_ref=self,
            )
        return self._main_view

    def initialize(self) -> bool:
        """Initiera pluginet – prenumerera på events."""
        logger.info(f"Initierar {self.NAME} v{self.VERSION}")
        self.subscribe("app:shutting_down", self._on_app_shutdown)
        self.subscribe("settings:changed",  self._on_settings_changed)
        self._is_initialized = True
        self.emit("plugin:loaded", {
            "name":    self.get_name(),
            "version": self.get_version(),
        })
        return True

    def shutdown(self) -> None:
        """Städa upp pluginet vid avlastning."""
        logger.info(f"Stänger ner {self.NAME}")
        try:
            self.save_settings({
                "year":      self.tenant_manager.get_year(),
                "last_file": self.tenant_manager.tenant_file,
                "last_used": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error(f"Kunde inte spara inställningar: {e}")

        if self._main_view is not None:
            self._main_view.deleteLater()
            self._main_view = None

        super().shutdown()

    def _on_app_shutdown(self, data: Any = None) -> None:
        """Hantera app-nedstängning."""
        self.shutdown()

    def _on_settings_changed(self, data: Any = None) -> None:
        """Hantera ändrade inställningar."""
        if data and isinstance(data, dict):
            key = data.get("key", "")
            if key.startswith("hyresfakturering."):
                logger.info(f"Inställning ändrad: {key}")

    def _generate_pdf(self) -> None:
        """Generera PDF-rapport."""
        generator = PDFGenerator(self)
        success   = generator.generate()
        if success:
            self.emit("hyresfakturering:pdf_generated", {
                "timestamp": datetime.now().isoformat(),
            })

    def _manage_tenants(self) -> None:
        """
        Öppna listredigeraren för hyresgäster (v2.4.0).

        Användaren kan lägga till, ändra, ta bort och sortera hyresgäster
        direkt i programmet. Efter sparning laddas listan om automatiskt.
        """
        from core.list_editor_dialog import ListEditorDialog

        saved = ListEditorDialog.edit(
            self.tenant_manager.tenant_file,
            name="Hyresgäster",
            parent=self._main_view,
            section_titles=[
                i18n.t("hyra.tenants.monthly"),
                i18n.t("hyra.tenants.quarterly"),
            ],
        )

        if saved:
            self._reload_tenants(show_message=False)

    def _open_tenant_file(self) -> None:
        """Öppna hyresgästfilen i standard-redigeraren."""
        file_path = self.tenant_manager.tenant_file

        if not os.path.exists(file_path):
            self.tenant_manager._create_example_file()

        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                import subprocess
                subprocess.run(["open", file_path], check=False)
            else:
                import subprocess
                subprocess.run(["xdg-open", file_path], check=False)

            self.emit("hyresfakturering:file_opened", {
                "file": file_path,
            })

        except Exception as e:
            QMessageBox.critical(
                None,
                "Fel",
                f"Kunde inte öppna fil:\n{e}",
            )

    def _reload_tenants(self, show_message: bool = True) -> None:
        """
        Ladda om hyresgäster och uppdatera UI.

        Args:
            show_message: Visa en bekräftelseruta (False efter redigering
                          i listredigeraren, där dialogen redan stängts).
        """
        self.tenant_manager.reload()

        if self._main_view is not None:
            self._main_view._refresh_ui()

        monthly_count   = len(self.tenant_manager.get_monthly_tenants())
        quarterly_count = len(self.tenant_manager.get_quarterly_tenants())

        self.emit("hyresfakturering:data_reloaded", {
            "monthly_count":   monthly_count,
            "quarterly_count": quarterly_count,
        })

        if not show_message:
            return

        QMessageBox.information(
            None,
            "Klart",
            (
                f"Hyresgäster laddade om!\n\n"
                f"Månad: {monthly_count}\n"
                f"Kvartal: {quarterly_count}"
            ),
        )

    @property
    def main_view(self) -> Optional[HyraMainView]:
        """Returnera huvudvyn (kan vara None före get_tab_widget())."""
        return self._main_view