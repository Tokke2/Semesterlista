"""Semesterlista: plugin (v2.12.0)."""

from __future__ import annotations
import os
import json
import platform
from datetime import datetime
from typing import Dict
from typing import Any
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QMessageBox
from plugins.base_plugin import BasePlugin
from .common import logger
from .common import DEFAULT_ORIENTATION
from .common import DEFAULT_MONTHS_PER_PAGE
from .common import PLUGIN_INFO
from .common import get_documents_folder
from .common import get_plugin_data_folder
from .view import SettingsDialog
from .view import SemesterlistaView
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.settings_manager import SettingsManager
from .common import TABLE_WIDTH_MM as TABLE_WIDTH_MM
from .common import TABLE_WIDTH_PT as TABLE_WIDTH_PT
from .common import NAME_COL_WIDTH as NAME_COL_WIDTH
from .common import LEAVE_COLOR as LEAVE_COLOR
from .common import LEAVE_MARK as LEAVE_MARK
from .common import MIN_DAY_COL_WIDTH as MIN_DAY_COL_WIDTH
from .common import FONT_SIZE as FONT_SIZE
from .common import LEAVE_FONT_SIZE as LEAVE_FONT_SIZE
from .common import ROW_PADDING as ROW_PADDING
from .common import PAGE_SAFETY as PAGE_SAFETY
from .common import FRAME_PADDING as FRAME_PADDING
from .common import LEGEND_ITEMS as LEGEND_ITEMS
from .common import ORIENTATION_LANDSCAPE as ORIENTATION_LANDSCAPE
from .common import ORIENTATION_PORTRAIT as ORIENTATION_PORTRAIT
from .common import ORIENTATIONS as ORIENTATIONS
from .common import LAYOUT_SETTINGS as LAYOUT_SETTINGS
from .common import MONTHS_PER_PAGE_OPTIONS as MONTHS_PER_PAGE_OPTIONS
from .common import month_options as month_options
from .common import normalize_orientation as normalize_orientation
from .common import page_geometry as page_geometry
from .common import orientation_label as orientation_label
from .common import get_easter as get_easter
from .common import get_swedish_holidays as get_swedish_holidays
from .common import get_half_days as get_half_days
from .common import holidays_for as holidays_for
from .common import holiday_region_label as holiday_region_label
from .pdf import PDFGenerator as PDFGenerator
from .view import TestRunner as TestRunner
import calendar as calendar
import webbrowser as webbrowser
import logging as logging
from datetime import date as date
from pathlib import Path as Path
from typing import List as List
from typing import Set as Set
from typing import Tuple as Tuple
from PySide6.QtWidgets import QVBoxLayout as QVBoxLayout
from PySide6.QtWidgets import QHBoxLayout as QHBoxLayout
from PySide6.QtWidgets import QGridLayout as QGridLayout
from PySide6.QtWidgets import QLabel as QLabel
from PySide6.QtWidgets import QPushButton as QPushButton
from PySide6.QtWidgets import QGroupBox as QGroupBox
from PySide6.QtWidgets import QSpinBox as QSpinBox
from PySide6.QtWidgets import QComboBox as QComboBox
from PySide6.QtWidgets import QLineEdit as QLineEdit
from PySide6.QtWidgets import QCheckBox as QCheckBox
from PySide6.QtWidgets import QFileDialog as QFileDialog
from PySide6.QtWidgets import QDialog as QDialog
from PySide6.QtWidgets import QDialogButtonBox as QDialogButtonBox
from PySide6.QtWidgets import QSizePolicy as QSizePolicy
from PySide6.QtCore import Qt as Qt
from PySide6.QtCore import Signal as Signal
from PySide6.QtCore import Slot as Slot
from PySide6.QtGui import QFont as QFont
from reportlab.platypus import SimpleDocTemplate as SimpleDocTemplate
from reportlab.platypus import Table as Table
from reportlab.platypus import TableStyle as TableStyle
from reportlab.platypus import Paragraph as Paragraph
from reportlab.platypus import Spacer as Spacer
from reportlab.platypus import PageBreak as PageBreak
from reportlab.platypus import KeepInFrame as KeepInFrame
from reportlab.lib.pagesizes import landscape as landscape
from reportlab.lib.pagesizes import A4 as A4
from reportlab.lib import colors as colors
from reportlab.lib.styles import ParagraphStyle as ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet as getSampleStyleSheet
from reportlab.lib.units import mm as mm
from core import holidays as holidays
from core import i18n as i18n
from core.pdf_assets import AssetError as AssetError
from core.pdf_assets import PdfLogo as PdfLogo
from core.pdf_assets import logo_for_settings as logo_for_settings
from core.pdf_assets import make_logo_canvas as make_logo_canvas
from core.roster import RosterError as RosterError
from core.roster import read_entries as read_entries
from core.roster import read_names as read_names
from core.roster import resolve_path as resolve_path
from core.leave import LeaveCalendar as LeaveCalendar

class Plugin(BasePlugin):
    """
    Semesterlista & Limokörning Plugin.

    v2.2.0:
      - Standardläge om ingen månad väljs
      - Manuellt val av startmånad över årsskifte
      - Exempel: Dec 2026 → Jan 2027
    """

    NAME: str = PLUGIN_INFO["name"]
    VERSION: str = "2.18.2"
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
            "logo_scale": 100,
            "seasonal_pdf": True,
            "pdf_monochrome": False,
            "season_images": {},
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
        from core.pdf_export import get_export_folder
        try:
            path = get_export_folder("Fordon" if self.FIXED_MODE != "Semesterlista" else "Semesterlista")
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


# Compatibility exports for Fordon and existing integrations.
__all__ = ['A4', 'Any', 'AssetError', 'BasePlugin', 'DEFAULT_MONTHS_PER_PAGE', 'DEFAULT_ORIENTATION', 'Dict', 'FONT_SIZE', 'FRAME_PADDING', 'KeepInFrame', 'LAYOUT_SETTINGS', 'LEAVE_COLOR', 'LEAVE_FONT_SIZE', 'LEAVE_MARK', 'LEGEND_ITEMS', 'LeaveCalendar', 'List', 'MIN_DAY_COL_WIDTH', 'MONTHS_PER_PAGE_OPTIONS', 'NAME_COL_WIDTH', 'ORIENTATIONS', 'ORIENTATION_LANDSCAPE', 'ORIENTATION_PORTRAIT', 'Optional', 'PAGE_SAFETY', 'PDFGenerator', 'PLUGIN_INFO', 'PageBreak', 'Paragraph', 'ParagraphStyle', 'Path', 'PdfLogo', 'Plugin', 'QCheckBox', 'QComboBox', 'QDialog', 'QDialogButtonBox', 'QFileDialog', 'QFont', 'QGridLayout', 'QGroupBox', 'QHBoxLayout', 'QLabel', 'QLineEdit', 'QMessageBox', 'QPushButton', 'QSizePolicy', 'QSpinBox', 'QVBoxLayout', 'QWidget', 'Qt', 'ROW_PADDING', 'RosterError', 'SemesterlistaView', 'Set', 'SettingsDialog', 'Signal', 'SimpleDocTemplate', 'Slot', 'Spacer', 'TABLE_WIDTH_MM', 'TABLE_WIDTH_PT', 'TYPE_CHECKING', 'Table', 'TableStyle', 'TestRunner', 'Tuple', 'calendar', 'colors', 'date', 'datetime', 'getSampleStyleSheet', 'get_documents_folder', 'get_easter', 'get_half_days', 'get_plugin_data_folder', 'get_swedish_holidays', 'holiday_region_label', 'holidays', 'holidays_for', 'i18n', 'json', 'landscape', 'logger', 'logging', 'logo_for_settings', 'make_logo_canvas', 'mm', 'month_options', 'normalize_orientation', 'orientation_label', 'os', 'page_geometry', 'platform', 'read_entries', 'read_names', 'resolve_path', 'webbrowser']
