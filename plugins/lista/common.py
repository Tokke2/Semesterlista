"""Semesterlista: common (v2.12.0)."""

from __future__ import annotations
from core.version import MODULE_VERSION
import os
import platform
import logging
from datetime import date
from pathlib import Path
from typing import List
from typing import Dict
from typing import Any
from typing import Optional
from typing import Set
from typing import Tuple
from reportlab.lib.pagesizes import landscape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from core import holidays
from core import i18n

logger = logging.getLogger(__name__)


TABLE_WIDTH_MM = 270.0


TABLE_WIDTH_PT = TABLE_WIDTH_MM * mm


NAME_COL_WIDTH = 70


LEAVE_COLOR = colors.Color(0.35, 0.38, 0.45)


LEAVE_MARK = "\u00d7"


MIN_DAY_COL_WIDTH = 8


FONT_SIZE = 7


LEAVE_FONT_SIZE = FONT_SIZE + 3


ROW_PADDING = 2


PAGE_SAFETY = 8.0


FRAME_PADDING = 6.0


LEGEND_ITEMS: Tuple[Tuple[colors.Color, str], ...] = (
    (colors.Color(0.94, 0.5, 0.5), "lista.pdf.legend.red"),
    (colors.Color(0.68, 0.85, 0.9), "lista.pdf.legend.blue"),
    (colors.Color(0.56, 0.93, 0.56), "lista.pdf.legend.green"),
    (colors.Color(1, 0.65, 0), "lista.pdf.legend.orange"),
    (LEAVE_COLOR, "lista.pdf.legend.leave"),
)


ORIENTATION_LANDSCAPE: str = "Liggande"


ORIENTATION_PORTRAIT: str = "Stående"


ORIENTATIONS: List[str] = [ORIENTATION_LANDSCAPE, ORIENTATION_PORTRAIT]


DEFAULT_ORIENTATION: str = ORIENTATION_LANDSCAPE


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


MONTHS_PER_PAGE_OPTIONS: List[int] = [1, 2, 3]


DEFAULT_MONTHS_PER_PAGE: int = 3


PLUGIN_INFO = {
    "id": "semesterlista",
    "name": "Semesterlista & Limokörning",
    "version": MODULE_VERSION,
    "author": "Din Organisation",
    "description": "Genererar semesterlistor och limokörningsscheman i PDF-format",
}


def month_options() -> List[str]:
    """
    Månadsval till dropdownen – översatta (v2.11.0).

    Index 0 = standardläge, index 1–12 = månad. Hämtas från ``core/i18n.py``
    så att listan följer valt språk.
    """
    return i18n.month_options(i18n.t("lista.start_month.standard"))


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
    """Påskdagen för ett år (delegerar till ``core.holidays``)."""
    return holidays.get_easter(year)


def get_swedish_holidays(year: int) -> Set[date]:
    """Svenska röda dagar (bakåtkompatibel genväg)."""
    return holidays.get_holidays(year, holidays.REGION_SWEDEN)


def get_half_days(year: int, region: Optional[str] = None) -> Set[date]:
    """Halvdagar för vald region (standard: Sverige)."""
    return holidays.get_half_days(year, region or holidays.DEFAULT_REGION)


def holidays_for(year: int, region: Optional[str] = None) -> Set[date]:
    """
    Röda dagar för valt år och vald region (v2.12.0).

    Regionen kommer från inställningen ``holiday_region`` (sv eller us) och
    styr vilka dagar som blir röda i PDF:en.
    """
    return holidays.get_holidays(year, region or holidays.DEFAULT_REGION)


def holiday_region_label(region: Optional[str]) -> str:
    """Läsbar namn på regionen ("Sverige" / "USA"), för logg och PDF."""
    return holidays.describe_region(region)


