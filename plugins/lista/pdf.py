"""Semesterlista: pdf (v2.12.0)."""

from __future__ import annotations
import os
from io import BytesIO
from xml.sax.saxutils import escape
import calendar
import webbrowser
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import List
from typing import Dict
from typing import Any
from typing import Optional
from typing import Set
from typing import Tuple
from PySide6.QtWidgets import QMessageBox
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Table
from reportlab.platypus import TableStyle
from reportlab.platypus import Paragraph
from reportlab.platypus import Spacer
from reportlab.platypus import PageBreak
from reportlab.platypus import KeepInFrame
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from core.calendar_data import year_days
from core.seasonal_pdf import seasonal_header, print_canvas
from core.pdf_readability import confirm_readability
from core import holidays
from core import i18n
from core.pdf_assets import AssetError
from core.pdf_assets import PdfLogo
from core.pdf_assets import logo_for_settings
from core.pdf_assets import make_logo_canvas
from core.roster import resolve_path
from core.leave import LeaveCalendar
from .common import logger
from .common import TABLE_WIDTH_PT
from .common import NAME_COL_WIDTH
from .common import LEAVE_COLOR
from .common import LEAVE_MARK
from .common import FONT_SIZE
from .common import LEAVE_FONT_SIZE
from .common import ROW_PADDING
from .common import PAGE_SAFETY
from .common import FRAME_PADDING
from .common import LEGEND_ITEMS
from .common import ORIENTATION_LANDSCAPE
from .common import ORIENTATION_PORTRAIT
from .common import ORIENTATIONS
from .common import DEFAULT_ORIENTATION
from .common import LAYOUT_SETTINGS
from .common import MONTHS_PER_PAGE_OPTIONS
from .common import DEFAULT_MONTHS_PER_PAGE
from .common import normalize_orientation
from .common import page_geometry
from .common import get_documents_folder
from .common import get_half_days
from .common import holidays_for
from .list_io import ListReader
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .plugin import Plugin

class PDFGenerator(ListReader):
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
        #: Lediga dagar per anställd, inlästa från listfilen (v2.11.0)
        self._leave_calendar: LeaveCalendar = LeaveCalendar()

    def _holiday_region(self) -> str:
        """
        Helgdagsregion från inställningarna (v2.12.0).

        ``holiday_region`` sätts i Inställningar → Allmänt och är ``sv``
        (svenska helgdagar) eller ``us`` (amerikanska). Okänt värde faller
        tillbaka på svenska.
        """
        return holidays.get_region_from_settings(self.plugin._settings_manager)


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
                leave=self._leave_calendar,
            )
        except Exception as e:
            logger.error(f"Fel vid PDF-generering: {e}")
            QMessageBox.critical(None, "Fel", f"Fel vid PDF-generering: {e}")
            return False

    @staticmethod
    def _confirm_readability(font_sizes: List[float], months_per_page: int) -> bool:
        return confirm_readability(font_sizes, months_per_page)

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

    def _create_legend_with_colors(
        self,
        table_width_pt: float = TABLE_WIDTH_PT,
    ) -> Table:
        """
        Färgförklaring för PDF:en (skalas till sidbredden).

        Etiketterna är stycken som radbryts inom sin kolumn och kolumn­
        bredderna följer textens längd. Då kan ingen text hamna ovanpå
        nästa färgruta, oavsett vilket språk som är valt (v2.11.0).
        """
        swatch_width = 14.0
        label_style = ParagraphStyle(
            "LegendLabel",
            fontName="Helvetica",
            fontSize=7,
            leading=8.5,
            textColor=colors.black,
        )

        keys = [key for _, key in LEGEND_ITEMS]
        if self._holiday_region() == "us":
            keys[0] += "_us"
            keys[2] += "_us"
        labels = [i18n.t(key) for key in keys]
        if self.plugin.settings.get("pdf_monochrome", False):
            labels = [text.split("=", 1)[-1].strip() for text in labels]
        total_label_width = table_width_pt - swatch_width * len(LEGEND_ITEMS)
        weights = [max(len(text), 1) for text in labels]
        label_widths = [
            total_label_width * weight / sum(weights) for weight in weights
        ]

        data: List[Any] = [[]]
        col_widths: List[float] = []
        commands: List[Any] = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]

        for index, ((color, _key), label, label_w) in enumerate(
            zip(LEGEND_ITEMS, labels, label_widths)
        ):
            column = index * 2
            data[0].extend(["", Paragraph(label, label_style)])
            col_widths.extend([swatch_width, label_w])
            commands.append(("BACKGROUND", (column, 0), (column, 0), color))
            commands.append(("BOX", (column, 0), (column, 0), 0.5, colors.black))

        legend_table = Table(data, colWidths=col_widths, hAlign="LEFT")
        legend_table.setStyle(TableStyle(commands))
        self._apply_table_scaling(legend_table, table_width_pt)
        return legend_table

    def _fit_layout(
        self,
        months_per_page: int,
        rows: int,
        title_prefix: str,
        months: List[tuple[int, int]],
        styles: Any,
        table_width_pt: float,
        available_height: float,
    ) -> Tuple[int, int, int]:
        """
        Anpassa layouten till listans längd (v2.11.0).

        Behåller användarens val av månader per blad och minskar radluften.
        Om det inte räcker skalas hela sidgruppen i _generate_pdf.

        Returns:
            (månader per blad, radluft, mellanrum mellan tabellerna)
        """
        header_height = self._estimate_header_height(
            title_prefix, months, styles, table_width_pt
        )
        budget = available_height - PAGE_SAFETY
        candidates = (
            (3, 16),
            (3, 12),
            (ROW_PADDING, 12),
            (ROW_PADDING, 8),
            (1, 8),
            (1, 4),
            (0, 4),
            (0, 2),
        )

        count = max(1, int(months_per_page))
        for pad, gap in candidates:
            month_height = self._estimate_month_height(rows, 31, pad, table_width_pt)
            needed = header_height + count * month_height + (count - 1) * gap
            if needed <= budget:
                return count, pad, gap

        return months_per_page, 0, 2

    def _estimate_header_height(
        self,
        title_prefix: str,
        months: List[tuple[int, int]],
        styles: Any,
        table_width_pt: float,
    ) -> float:
        """Höjd för rubrik + färgförklaring (samma mått som på sidan)."""
        header = [
            Paragraph(self._format_page_title(title_prefix, months), styles["Title"]),
            Spacer(1, 3),
            self._create_legend_with_colors(table_width_pt),
            Spacer(1, 6),
        ]
        return sum(self._flowable_height(flow, table_width_pt) for flow in header)

    def _estimate_month_height(
        self,
        rows: int,
        days: int,
        row_padding: int,
        table_width_pt: float,
    ) -> float:
        """
        Uppskatta höjden för en månadstabell med ``rows`` rader.

        Bygger en tabell med samma kolumnbredder, typsnitt och luft som den
        riktiga – då stämmer höjden utan att behöva gissa.
        """
        name_w, day_w = self._calc_column_widths(days, table_width_pt)
        data = [["1"] * (days + 1) for _ in range(rows)]
        sample = Table(data, colWidths=[name_w] + [day_w] * days)
        sample.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), FONT_SIZE),
            ("TOPPADDING", (0, 0), (-1, -1), row_padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), row_padding),
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ]))
        self._apply_table_scaling(sample, table_width_pt)
        return self._flowable_height(sample, table_width_pt)

    @staticmethod
    def _flowable_height(flowable: Any, width: float) -> float:
        """
        Höjd i punkter för en flowable vid given bredd.

        Används för att avgöra om nästa månad får plats på sidan. Går
        höjden inte att mäta returneras 0, så att en tabell aldrig tappas.
        """
        try:
            return float(flowable.wrap(width, 10 ** 6)[1])
        except (AttributeError, TypeError, ValueError):
            return 0.0

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
            return f"{i18n.month_name(start_month)}–{i18n.month_name(end_month)} {start_year}"

        return f"{i18n.month_name(start_month)} {start_year} – {i18n.month_name(end_month)} {end_year}"

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
            return f"{title_prefix} {i18n.month_name(start_month)} {start_year}"

        if start_year == end_year:
            return f"{title_prefix} {i18n.month_name(start_month)}–{i18n.month_name(end_month)} {start_year}"

        return (
            f"{title_prefix} "
            f"{i18n.month_name(start_month)} {start_year} – "
            f"{i18n.month_name(end_month)} {end_year}"
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
        leave: Optional[LeaveCalendar] = None,
    ) -> bool:
        """
        Generera PDF med färgkodade kalendertabeller.

        leave (v2.11.0):
            Lediga dagar per anställd. None → använd den kalender som
            lästes in från listfilen (``self._leave_calendar``).

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
        leave_calendar = leave if leave is not None else self._leave_calendar
        documents_path = get_documents_folder()
        month_sequence = self._build_month_sequence(year, start_month)
        range_label = self._format_range_label(month_sequence)
        filename = self._build_output_filename(documents_path, mode, month_sequence)

        if mode == "Semesterlista":
            title_prefix = "Semesterlista"
            header = "Anställd"
        else:
            title_prefix = "Limokörningsschema"
            header = "Fordon"

        # Automatisk A4-orientering, oberoende av gamla sparade layoutval.
        orientation = ORIENTATION_PORTRAIT if months_per_page == 1 else ORIENTATION_LANDSCAPE
        layout = LAYOUT_SETTINGS[orientation]
        pagesize, table_width_pt = page_geometry(orientation)
        side_margin = layout["side_margin_mm"]
        top_margin = max(16.0, layout["top_margin_mm"])
        styles = getSampleStyleSheet()

        # Anpassa layouten till listans längd innan månaderna fördelas
        # Behåll antalet månader; sidgruppen skalas vid behov.
        frame_width = pagesize[0] - 2 * side_margin * mm
        available_height = (
            pagesize[1] - 2 * top_margin * mm - 2 * FRAME_PADDING
        )
        months_per_page, row_padding, month_gap = self._fit_layout(
            months_per_page=months_per_page,
            rows=3 + len(data_list),
            title_prefix=title_prefix,
            months=month_sequence[:months_per_page],
            styles=styles,
            table_width_pt=table_width_pt,
            available_height=available_height,
        )

        pages = self._chunk_months(month_sequence, months_per_page)

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

        # Logotyp (v2.4.0) – ritas i övre högra hörnet på varje sida.
        # Används som canvasmaker eftersom onFirstPage/onLaterPages inte
        # stöds av alla reportlab-versioner.
        logo_canvas = make_logo_canvas(self._page_logo(), margin_mm=6.0)
        build_kwargs: Dict[str, Any] = {}
        build_kwargs["canvasmaker"] = print_canvas(logo_canvas, self.plugin.settings.get("pdf_monochrome", False))

        doc = SimpleDocTemplate(
            filename,
            pagesize=pagesize,
            rightMargin=side_margin * mm,
            leftMargin=side_margin * mm,
            topMargin=top_margin * mm,
            bottomMargin=top_margin * mm,
        )

        elements: List[Any] = []
        readable_sizes: List[float] = []
        measuring_canvas = Canvas(BytesIO(), pagesize=pagesize)

        # Samla alla år som förekommer i sekvensen
        years_in_sequence = sorted({month_year for month_year, _ in month_sequence})
        # Regionen (svenska eller amerikanska helgdagar) kommer från
        # inställningen holiday_region (v2.12.0).
        region = self._holiday_region()
        official_holidays_by_year: Dict[int, Set[date]] = {
            month_year: holidays_for(month_year, region)
            for month_year in years_in_sequence
        }
        half_days_by_year: Dict[int, Set[date]] = {
            month_year: get_half_days(month_year, region)
            for month_year in years_in_sequence
        }

        calendar_years = {year: year_days(year, region, official_holidays_by_year[year], half_days_by_year[year])
                          for year in years_in_sequence}

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

        def build_header(months: List[tuple[int, int]]) -> List[Any]:
            """Rubrik + färgförklaring – upprepas på varje fysisk sida."""
            return [
                Paragraph(self._format_page_title(title_prefix, months), styles["Title"]),
                Spacer(1, 3),
                self._create_legend_with_colors(table_width_pt),
                Spacer(1, 6),
            ]


        for page_index, page_months in enumerate(pages):
            page_header = build_header(page_months)
            page_elements = list(page_header)
            smallest_font = float(FONT_SIZE)

            for month_year, month_num in page_months:
                days_in_month = calendar.monthrange(month_year, month_num)[1]
                name_w, day_w = self._calc_column_widths(
                    days_in_month, table_width_pt
                )
                day_label_size = FONT_SIZE if day_w >= 18 else FONT_SIZE - 1
                smallest_font = min(smallest_font, day_label_size)

                month_days = calendar_years[month_year]
                page_elements.extend(seasonal_header(month_num, self.plugin.settings, table_width_pt))

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

                header_row1 = [f"{i18n.month_name(month_num)} {month_year}"] + week_numbers
                header_row2 = [header] + list(map(str, range(1, days_in_month + 1)))
                header_row3 = [""] + day_texts
                table_data = [header_row1, header_row2, header_row3]

                for item in data_list:
                    row = [item]
                    for day_num in range(1, days_in_month + 1):
                        if leave_calendar.is_off(
                            item, date(month_year, month_num, day_num)
                        ):
                            row.append(LEAVE_MARK)
                        else:
                            row.append("")
                    table_data.append(row)

                col_widths = [name_w] + [day_w] * days_in_month
                # repeatRows: om en månad med väldigt många anställda ändå
                # måste delas upprepas de tre rubrikraderna på nästa sida.
                table = Table(table_data, colWidths=col_widths, repeatRows=3)

                style = TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ("BACKGROUND", (0, 0), (0, 0), colors.lightgrey),
                    ("BACKGROUND", (0, 1), (0, 1), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (-1, 2), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), FONT_SIZE),
                    # Trånga dagkolumner (stående A4) får en mindre etikett,
                    # så att "Sön" och "Mån" inte går i varandra (v2.11.0).
                    ("FONTSIZE", (1, 2), (-1, 2), day_label_size),
                    ("TOPPADDING", (0, 0), (-1, -1), row_padding),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), row_padding),
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
                    kind = month_days[current_date].kind

                    if kind in ("holiday", "sunday"):
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
                    elif kind == "halfday":
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
                    elif kind == "saturday":
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

                # 5. Grå med ×: personlig frånvaro (vinner över veckofärgerna)
                if leave_calendar:
                    for row_idx, item in enumerate(data_list, start=3):
                        if not leave_calendar.ranges_for(item):
                            continue
                        for day_num in range(1, days_in_month + 1):
                            if table_data[row_idx][day_num] != LEAVE_MARK:
                                continue
                            style.add(
                                "BACKGROUND",
                                (day_num, row_idx), (day_num, row_idx),
                                LEAVE_COLOR,
                            )
                            style.add(
                                "TEXTCOLOR",
                                (day_num, row_idx), (day_num, row_idx),
                                colors.white,
                            )
                            style.add(
                                "FONTNAME",
                                (day_num, row_idx), (day_num, row_idx),
                                "Helvetica-Bold",
                            )
                            style.add(
                                "FONTSIZE",
                                (day_num, row_idx), (day_num, row_idx),
                                LEAVE_FONT_SIZE,
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

                page_elements.append(table)
                # Text names make holiday information independent of colour.
                notes = [f"{day.day}: {i18n.holiday_name(info.holiday_key)}"
                         for day, info in month_days.items()
                         if day.month == month_num and info.holiday_key]
                if notes:
                    page_elements.append(Paragraph(escape(" / ".join(notes)),
                        ParagraphStyle("holiday-notes", fontSize=7, leading=8.5, spaceBefore=3)))
                if (month_year, month_num) != page_months[-1]:
                    page_elements.append(Spacer(1, month_gap))

            # One indivisible group per sheet. Shrink, never drop months or rows.
            group = KeepInFrame(
                frame_width - 2 * FRAME_PADDING,
                available_height - PAGE_SAFETY,
                page_elements, mode="shrink",
            )
            # Measure the actual ReportLab shrink factor before opening the
            # output file. Cancel must leave even an existing PDF untouched.
            group.wrapOn(measuring_canvas, group.maxWidth, group.maxHeight)
            scale = max(1.0, float(getattr(group, "_scale", 1.0)))
            readable_sizes.append(smallest_font / scale)
            elements.append(group)

            if page_index < len(pages) - 1:
                elements.append(PageBreak())

        if not self._confirm_readability(readable_sizes, months_per_page):
            logger.info("PDF-export avbruten efter varning om liten text")
            return False

        company = str(self.plugin.settings.get("company_name", "")).strip()
        printed = datetime.now().strftime("%Y-%m-%d")

        def page_details(canvas, document):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            # Limit the header to the left half, clear of the logo.
            from reportlab.pdfbase.pdfmetrics import stringWidth
            label = company
            while label and stringWidth(label, "Helvetica", 8) > pagesize[0] / 2:
                label = label[:-1]
            canvas.drawString(side_margin * mm, pagesize[1] - 9 * mm, label)
            canvas.drawString(side_margin * mm, 7 * mm, f"Utskriftsdatum: {printed}")
            canvas.drawRightString(
                pagesize[0] - side_margin * mm, 7 * mm,
                f"Sida {document.page} av {len(pages)}",
            )
            canvas.restoreState()

        doc.build(elements, onFirstPage=page_details, onLaterPages=page_details, **build_kwargs)

        selected_start_value = 0 if start_month is None else start_month
        start_text = (
            "Standard (Januari)"
            if start_month is None
            else f"{i18n.month_name(start_month)} {year}"
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
            f"{doc.page} sidor, {size_kb:.0f} kB, "
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


