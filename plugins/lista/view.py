"""Semesterlista: view (v2.12.0)."""

from __future__ import annotations
from core.ui_layout import FlowLayout
import calendar
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import List
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QGroupBox
from PySide6.QtWidgets import QSpinBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot
from PySide6.QtGui import QFont
from core import i18n
from core.roster import RosterError
from core.roster import read_names
from core.roster import resolve_path
from .common import logger
from .common import ORIENTATION_LANDSCAPE
from .common import ORIENTATION_PORTRAIT
from .common import ORIENTATIONS
from .common import MONTHS_PER_PAGE_OPTIONS
from .common import DEFAULT_MONTHS_PER_PAGE
from .common import PLUGIN_INFO
from .common import month_options
from .common import normalize_orientation
from .common import orientation_label
from .common import get_easter
from .common import get_swedish_holidays
from .common import get_half_days
from .pdf import PDFGenerator
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .plugin import Plugin

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
        self.setWindowTitle(i18n.t("lista.window_title"))
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
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        company_row = QHBoxLayout()
        company_row.addWidget(QLabel(i18n.t("lista.company_name")))
        self.company_edit = QLineEdit(str(self.plugin.settings.get("company_name", "")))
        company_row.addWidget(self.company_edit)
        main_layout.addLayout(company_row)

        auto_row = QHBoxLayout()
        auto_row.addWidget(QLabel(i18n.t("lista.settings.auto_open")))
        auto_row.addStretch()
        self.auto_open_check = QCheckBox()
        auto_row.addWidget(self.auto_open_check)
        main_layout.addLayout(auto_row)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(i18n.t("lista.settings.default_mode")))
        mode_row.addStretch()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Semesterlista", "Limokörning"])
        self.mode_combo.setMinimumWidth(220)
        mode_row.addWidget(self.mode_combo)
        main_layout.addLayout(mode_row)

        months_row = QHBoxLayout()
        months_row.addWidget(QLabel(i18n.t("lista.settings.months_per_page")))
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
        orientation_row.addWidget(QLabel(i18n.t("lista.orientation")))
        orientation_row.addStretch()
        self.orientation_combo = QComboBox()
        self.orientation_combo.setEnabled(False)
        for value in ORIENTATIONS:
            self.orientation_combo.addItem(orientation_label(value), value)
        self.orientation_combo.setMinimumWidth(220)
        self.orientation_combo.setToolTip(
            "Liggande = breda tabeller (standard).\n"
            "Stående = vanlig A4 för pärm/utskrift."
        )
        orientation_row.addWidget(self.orientation_combo)
        main_layout.addLayout(orientation_row)
        def sync_orientation():
            value = ORIENTATION_PORTRAIT if self.months_per_page_combo.currentText() == "1" else ORIENTATION_LANDSCAPE
            self.orientation_combo.setCurrentIndex(self.orientation_combo.findData(value))
        self.months_per_page_combo.currentIndexChanged.connect(sync_orientation)
        sync_orientation()
        self.orientation_combo.setToolTip(i18n.t("lista.orientation.auto"))


        start_row = QHBoxLayout()
        start_label = QLabel(i18n.t("lista.settings.start_month"))
        start_label.setToolTip(
            "Standard (Januari) = jan–dec valt år.\n"
            "Väljer du en månad manuellt genereras 12 månader från den månaden\n"
            "och perioder kan gå över årsskifte, t.ex. dec 2026 → jan 2027."
        )
        start_row.addWidget(start_label)
        start_row.addStretch()
        self.start_month_combo = QComboBox()
        self.start_month_combo.addItems(month_options())
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
            ORIENTATION_PORTRAIT if self.months_per_page_combo.currentText() == "1" else ORIENTATION_LANDSCAPE
        )
        if orientation_idx >= 0:
            self.orientation_combo.setCurrentIndex(orientation_idx)

        saved_start = self.plugin.settings.get("start_month", 0)
        if isinstance(saved_start, int) and 0 <= saved_start <= 12:
            self.start_month_combo.setCurrentIndex(saved_start)
        else:
            self.start_month_combo.setCurrentIndex(0)

    def _save(self) -> None:
        self.plugin.settings["company_name"] = self.company_edit.text().strip()
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
        dialog.setWindowTitle(i18n.t("lista.tests.title"))
        dialog.setMinimumSize(560, 420)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(4)

        title = QLabel(
            i18n.t(
                "lista.tests.heading",
                version=PLUGIN_INFO["version"],
                language=i18n.current_language().upper(),
            )
        )
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

        close_btn = QPushButton(i18n.t("common.close"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        dialog.exec()


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
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        is_vehicle = (self._fixed_mode or "Semesterlista") != "Semesterlista"
        title = QLabel(i18n.t("fordon.title") if is_vehicle else i18n.t("lista.title"))
        title.setProperty("role", "title")
        main_layout.addWidget(title)

        desc = QLabel(
            i18n.t("fordon.description") if is_vehicle else i18n.t("lista.description")
        )
        desc.setWordWrap(True)
        desc.setFont(QFont("Helvetica", 10))
        desc.setProperty("role", "muted")
        main_layout.addWidget(desc)
        main_layout.addSpacing(8)

        main_layout.addWidget(self._create_form_group())
        main_layout.addWidget(self._create_legend_group())
        main_layout.addStretch()
        main_layout.addLayout(self._create_button_bar())

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
        group = QGroupBox(i18n.t("lista.group.settings"))
        form_layout = QGridLayout(group)
        form_layout.setContentsMargins(15, 20, 15, 15)
        form_layout.setSpacing(10)

        self.mode_label = QLabel(i18n.t("lista.mode"))
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

        year_label = QLabel(i18n.t("lista.year"))
        year_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(year_label, 1, 0)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setMinimumWidth(120)
        form_layout.addWidget(self.year_spin, 1, 1)

        start_label = QLabel(i18n.t("lista.start_month"))
        start_label.setFont(QFont("Helvetica", 10))
        start_label.setToolTip(
            "Om inget väljs används standard:\n"
            "jan–dec för valt år.\n\n"
            "Väljer du en månad manuellt genereras 12 månader från den månaden.\n"
            "Exempel: December 2026 → Dec 2026, Jan 2027, ... Nov 2027."
        )
        form_layout.addWidget(start_label, 2, 0)

        self.start_month_combo = QComboBox()
        self.start_month_combo.addItems(month_options())
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

        months_label = QLabel(i18n.t("lista.months_per_page"))
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
        layout_label = QLabel(i18n.t("lista.orientation"))
        layout_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(layout_label, 4, 0)

        self.orientation_combo = QComboBox()
        self.orientation_combo.setEnabled(False)
        for value in ORIENTATIONS:
            self.orientation_combo.addItem(orientation_label(value), value)
        self.orientation_combo.setToolTip(
            "Liggande (A4) = breda tabeller, 270 mm (standard)\n"
            "Stående (A4) = vanlig A4 för pärm/utskrift, 190 mm tabell"
        )
        orientation_idx = self.orientation_combo.findData(
            ORIENTATION_PORTRAIT if self.months_per_page_combo.currentText() == "1" else ORIENTATION_LANDSCAPE
        )
        if orientation_idx >= 0:
            self.orientation_combo.setCurrentIndex(orientation_idx)
        form_layout.addWidget(self.orientation_combo, 4, 1)
        def sync_orientation():
            value = ORIENTATION_PORTRAIT if self.months_per_page_combo.currentText() == "1" else ORIENTATION_LANDSCAPE
            self.orientation_combo.setCurrentIndex(self.orientation_combo.findData(value))
        self.months_per_page_combo.currentIndexChanged.connect(sync_orientation)
        sync_orientation()
        self.orientation_combo.setToolTip(i18n.t("lista.orientation.auto"))


        self.file_label = QLabel(i18n.t("lista.file.employees"))
        self.file_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(self.file_label, 5, 0)

        file_row = FlowLayout()
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

        # Logotyp i PDF:en (v2.10.0) – dropdown med bilderna i assets/ + undermappar
        logo_label = QLabel(i18n.t("logo.label"))
        logo_label.setFont(QFont("Helvetica", 10))
        form_layout.addWidget(logo_label, 7, 0)

        from core.logo_picker import LogoPicker

        self.logo_picker = LogoPicker(
            current=self._logo_path(),
            parent=self,
            scale=self._logo_scale(),
        )
        self.logo_picker.changed.connect(self._on_logo_changed)
        self.logo_picker.scale_changed.connect(self._on_logo_scale_changed)
        form_layout.addWidget(self.logo_picker, 7, 1)
        self._on_mode_change(self.mode_combo.currentText())
        self._update_list_count()
        return group

    def _create_button_bar(self) -> QHBoxLayout:
        """Skapa knappraden."""
        layout = FlowLayout()
        layout.setSpacing(10)

        generate_btn = QPushButton(i18n.t("lista.button.generate"))
        generate_btn.setMinimumHeight(30)
        generate_btn.setProperty("primary", True)
        generate_btn.clicked.connect(self._generate_pdf)
        layout.addWidget(generate_btn)
        appearance = QPushButton(i18n.t("season.settings"))
        appearance.clicked.connect(self._pdf_appearance)
        layout.addWidget(appearance)


        if self._fixed_mode == "Semesterlista":
            self.vacation_button = QPushButton(i18n.t("vacation.title"))
            self.vacation_button.clicked.connect(self._manage_vacation)
            layout.addWidget(self.vacation_button)



        test_btn = QPushButton(i18n.t("lista.button.tests"))
        test_btn.setMinimumHeight(36)
        test_btn.clicked.connect(self._run_tests)
        layout.addWidget(test_btn)

        folder_btn = QPushButton(i18n.t("lista.button.open_documents"))
        folder_btn.setMinimumHeight(36)
        folder_btn.clicked.connect(self._open_documents)
        layout.addWidget(folder_btn)

        layout.addStretch()
        return layout

    def _create_legend_group(self) -> QGroupBox:
        """Skapa färgförklaringsruta."""
        group = QGroupBox(i18n.t("lista.group.legend"))
        legend_layout = QVBoxLayout(group)
        legend_layout.setContentsMargins(15, 20, 15, 15)
        legend_layout.setSpacing(6)

        for color_hex, text in [
            ("#F08080", i18n.t("lista.legend.red")),
            ("#ADD8E6", i18n.t("lista.legend.blue")),
            ("#90EE90", i18n.t("lista.legend.green")),
            ("#FFA500", i18n.t("lista.legend.orange")),
            ("#595F73", i18n.t("lista.legend.leave")),
        ]:
            row = QHBoxLayout()
            box = QLabel("    ")
            box.setFixedSize(24, 18)
            box.setStyleSheet(
                f"background-color: {color_hex}; border: 1px solid #999;"
            )
            row.addWidget(box)
            label = QLabel(text)
            label.setWordWrap(True)
            row.addWidget(label)
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

    def _logo_scale(self) -> int:
        """Logotypens storlek i procent (100 = automatisk, v2.11.0)."""
        try:
            return int(self.plugin.settings.get("logo_scale", 100) or 100)
        except (TypeError, ValueError):
            return 100

    def _on_logo_changed(self, path: str) -> None:
        """
        Spara logotypen direkt när den väljs i dropdown-listan (v2.10.0).

        SVG, EPS och PDF fungerar; storleken anpassas automatiskt men kan
        också ställas med reglaget (v2.11.0).
        """
        self.plugin.settings["logo_svg"] = str(path or "")
        self.plugin._save_settings()
        logger.info(f"Logotyp för PDF: {path or 'ingen'}")

    def _on_logo_scale_changed(self, scale: int) -> None:
        """Spara storleksreglaget (v2.11.0)."""
        self.plugin.settings["logo_scale"] = int(scale)
        self.plugin._save_settings()
        logger.info(f"Logotypens storlek: {scale} %")

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

    def _pdf_appearance(self):
        from core.seasonal_options import edit_seasonal_options
        if edit_seasonal_options(self.plugin.settings, self):
            self.plugin._save_settings()

    def _manage_vacation(self):
        from core.vacation_dialog import VacationDialog
        from core.holidays import get_region_from_settings
        from core.roster import RosterError
        try:
            dialog = VacationDialog(self._current_list_path(), self.year_spin.value(),
                                    get_region_from_settings(self.plugin._settings_manager), self)
            dialog.exec()
            self._update_list_count()
        except (OSError, RosterError) as exc:
            QMessageBox.warning(self, i18n.t("vacation.title"), str(exc))

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


