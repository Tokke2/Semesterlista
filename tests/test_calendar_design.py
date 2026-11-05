"""Calendar, seasonal image and compact UI regression coverage."""
import importlib.util
import unittest
from datetime import date
from unittest.mock import patch
from core.calendar_data import month_weeks, year_days, season
from test_pdf_layout import PdfLayoutTestBase, _media_box


def _calendar_grids(page):
    import fitz
    strokes = [d['rect'] for d in page.get_drawings() if d['type'] == 's']
    horizontal = [r for r in strokes if r.width > 500]
    left = min(r.x0 for r in horizontal)
    width = max(r.width for r in horizontal)
    return [fitz.Rect(r.x0, r.y0, r.x0 + width, r.y1) for r in strokes
            if r.height > 30 and r.width < 1 and abs(r.x0 - left) < 1]


class CalendarModelTests(unittest.TestCase):
    def test_monday_first_leap_year(self):
        weeks = month_weeks(2024, 2)
        self.assertEqual(len(year_days(2024)), 366)
        self.assertEqual([day for day in weeks[0][:3]], [None] * 3)
        for week in weeks:
            for column, day in enumerate(week):
                if day:
                    self.assertEqual(day.date.weekday(), column)
                    self.assertEqual(day.date.month, 2)

    def test_region_names_and_classification(self):
        swedish, american = year_days(2026, 'sv'), year_days(2026, 'us')
        self.assertEqual(swedish[date(2026, 6, 6)].kind, 'holiday')
        self.assertEqual(american[date(2026, 7, 3)].kind, 'holiday')
        self.assertTrue(american[date(2026, 7, 3)].holiday_key)
        self.assertEqual(swedish[date(2026, 7, 3)].kind, 'weekday')

    def test_season_boundaries(self):
        self.assertEqual([season(m) for m in (12, 1, 2, 3, 5, 6, 8, 9, 11)],
                         ['winter'] * 3 + ['spring'] * 2 + ['summer'] * 2 + ['autumn'] * 2)


class SeasonalExportTests(PdfLayoutTestBase):
    def _images(self):
        from PIL import Image
        path = self.outdir / 'local.png'
        Image.new('RGB', (160, 90), (210, 40, 30)).save(path)
        return {'seasonal_pdf': True, 'season_images': {s: str(path) for s in ('winter', 'spring', 'summer', 'autumn')}}

    def test_calendar_images_keep_all_months(self):
        from core.calendar_pdf import export_calendar
        for per_page in (1, 2, 3):
            path = self.outdir / f'calendar-{per_page}.pdf'
            self.assertTrue(export_calendar(path, 2026, range(1, 13), per_page, 'sv', self._images()))
            (width, height), count = _media_box(path)
            self.assertEqual(count, 12 // per_page)
            self.assertGreater(width, height)

    @unittest.skipUnless(importlib.util.find_spec('fitz'), 'PyMuPDF unavailable')
    def test_calendar_without_images_fills_landscape_print_area(self):
        import fitz
        from core.calendar_pdf import export_calendar
        for per_page in (1, 2, 3):
            path = self.outdir / f'full-{per_page}.pdf'
            export_calendar(path, 2026, range(1, 13), per_page, 'sv', {'seasonal_pdf': True})
            with fitz.open(path) as doc:
                self.assertEqual(len(doc), 12 // per_page)
                for page in doc:
                    self.assertGreater(page.rect.width, page.rect.height)
                    grids = _calendar_grids(page)
                    self.assertEqual(len(grids), per_page)
                    self.assertGreater(min(r.width for r in grids), page.rect.width * .88)
                    self.assertGreater(max(r.y1 for r in grids), page.rect.height - 65)

    @unittest.skipUnless(importlib.util.find_spec('fitz'), 'PyMuPDF unavailable')
    def test_calendar_only_actual_images_take_space_and_partial_page_expands(self):
        import fitz
        from core.calendar_pdf import export_calendar
        settings = self._images()
        heights = []
        for options in ({'seasonal_pdf': True}, settings):
            path = self.outdir / 'space.pdf'
            export_calendar(path, 2026, [1], 3, 'sv', options)
            with fitz.open(path) as doc:
                grids = _calendar_grids(doc[0])
                self.assertEqual(len(grids), 1)
                heights.append(grids[0].height)
        self.assertGreater(heights[0], 400)
        self.assertGreater(heights[0] - heights[1], 45)

    @unittest.skipUnless(importlib.util.find_spec('fitz'), 'PyMuPDF unavailable')
    def test_us_calendar_names_and_pagination_in_both_languages(self):
        import fitz
        from core import i18n
        from core.calendar_pdf import export_calendar
        from core.observances import get_us_observances
        original = i18n.current_language()
        try:
            for language in ('sv', 'en'):
                i18n.set_language(language)
                for per_page in (1, 2, 3):
                    path = self.outdir / 'us-observances.pdf'
                    self.assertTrue(export_calendar(path, 2027, range(1, 13), per_page, 'us', self._images()))
                    with fitz.open(path) as doc:
                        self.assertEqual(len(doc), 12 // per_page)
                        text = ' '.join(' '.join(page.get_text() for page in doc).split())
                        for keys in get_us_observances(2027).values():
                            for key in keys:
                                self.assertIn(' '.join(i18n.holiday_name(key).split()) + ' *', text)
                        self.assertIn(i18n.t('calendar.observed_label', name=i18n.holiday_name('us.christmas')), text)
                        self.assertIn(i18n.t('calendar.observance_note'), text)
                        self.assertTrue(all(page.rect.width > page.rect.height for page in doc))
        finally:
            i18n.set_language(original)

    def test_us_screen_labels_match_pdf_model(self):
        from PySide6.QtCore import QDate
        from plugins.kalender.plugin import Plugin
        from core.calendar_data import day_labels
        from core.event_bus import EventBus
        from core import i18n
        plugin = Plugin(EventBus(), self.settings_manager)
        with patch('plugins.kalender.plugin.get_region_from_settings', return_value='us'):
            view = plugin.get_tab_widget()
            view.calendar.setSelectedDate(QDate(2027, 3, 17))
            view.refresh()
            labels = day_labels(year_days(2027, 'us')[date(2027, 3, 17)])
            self.assertIn(labels[0], view.names.text())
            self.assertEqual(view.calendar.dateTextFormat(QDate(2027, 3, 17)).toolTip(), labels[0])
            self.assertEqual(view.observance_note.text(), i18n.t('calendar.observance_note'))
            # December 24 has two separate labels: observed Christmas and Christmas Eve.
            view.calendar.setSelectedDate(QDate(2027, 12, 24))
            view.refresh()
            for label in day_labels(year_days(2027, 'us')[date(2027, 12, 24)]):
                self.assertIn(label, view.names.text())
        view.deleteLater()

    def test_roster_vehicle_images_keep_all_months(self):
        self.plugin.settings.update(self._images())
        for mode in ('Semesterlista', 'Limokörning'):
            for per_page in (1, 2, 3):
                path = self._generate(mode=mode, months_per_page=per_page)
                self.assertEqual(_media_box(path)[1], 12 // per_page)

    def test_calendar_cancel_preserves_existing_pdf(self):
        from core.calendar_pdf import export_calendar
        path = self.outdir / 'existing.pdf'
        path.write_bytes(b'existing')
        with patch('core.calendar_pdf.confirm_readability', return_value=False):
            self.assertFalse(export_calendar(path, 2026, [1], 1, 'sv', {}))
        self.assertEqual(path.read_bytes(), b'existing')

    def test_calendar_render_failure_preserves_existing_pdf(self):
        from core.calendar_pdf import export_calendar
        path = self.outdir / 'existing.pdf'
        path.write_bytes(b'existing')
        with patch('core.calendar_pdf.SimpleDocTemplate.build', side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError):
                export_calendar(path, 2026, [1], 1, 'sv', {})
        self.assertEqual(path.read_bytes(), b'existing')
        self.assertFalse(list(self.outdir.glob('.calendar-*')))

    def test_invalid_month_selection(self):
        from core.calendar_pdf import export_calendar
        for months, per_page in (([], 1), ([13], 1), ([1], 4)):
            with self.assertRaises(ValueError):
                export_calendar(self.outdir / 'invalid.pdf', 2026, months, per_page, 'sv', {})

    def test_missing_image_fallback_and_supported_files(self):
        from core.seasonal_pdf import seasonal_header, image_files
        settings = self._images()
        self.assertEqual(len(image_files(str(self.outdir))), 1)
        self.assertEqual(image_files(''), [])
        settings['season_images']['winter'] = str(self.outdir / 'missing.png')
        with self.assertLogs('core.seasonal_pdf', level='WARNING'):
            self.assertTrue(seasonal_header(1, settings, 400))
        self.assertEqual(seasonal_header(1, {'seasonal_pdf': False}, 400), [])

    @unittest.skipUnless(importlib.util.find_spec('fitz'), 'PyMuPDF unavailable')
    def test_grayscale_pixels_and_named_holidays(self):
        import fitz
        from core.calendar_pdf import export_calendar
        from core import i18n
        settings = self._images()
        settings['pdf_monochrome'] = True
        path = self.outdir / 'gray.pdf'
        export_calendar(path, 2026, [1], 1, 'sv', settings)
        with fitz.open(path) as doc:
            self.assertIn(i18n.holiday_name(year_days(2026)[date(2026, 1, 1)].holiday_key), doc[0].get_text())
            image = doc[0].get_pixmap(colorspace=fitz.csRGB)
            pixels = image.samples
            self.assertTrue(all(max(pixels[i:i+3]) - min(pixels[i:i+3]) <= 1 for i in range(0, len(pixels), 3)))

    def test_flow_wraps_and_calendar_has_no_employee_model(self):
        from PySide6.QtWidgets import QWidget, QPushButton
        from core.ui_layout import FlowLayout
        from plugins.kalender.plugin import Plugin
        from core.event_bus import EventBus
        widget = QWidget()
        layout = FlowLayout(widget)
        for text in ('Action one', 'Action two', 'Action three'):
            layout.addWidget(QPushButton(text))
        self.assertGreater(layout.heightForWidth(120), layout.heightForWidth(800))
        plugin = Plugin(EventBus(), self.settings_manager)
        self.assertFalse(hasattr(plugin, 'leave_store'))
        self.assertFalse(hasattr(plugin, 'roster'))
        view = plugin.get_tab_widget()
        self.assertEqual(view.calendar.firstDayOfWeek().value, 1)
        self.assertEqual(len(view._selected_months()), 12)
        view.deleteLater()

    def test_contrast_theme_and_local_selection(self):
        from core.theme_manager import ThemeManager
        from core.seasonal_options import SeasonalOptions
        manager = ThemeManager(self.settings_manager)
        manager.set_theme('contrast')
        self.assertIn('#FFFF00', self.app.styleSheet())
        self.assertIn('check-black.svg', self.app.styleSheet())
        settings = self._images()
        options = SeasonalOptions(settings)
        self.assertEqual(options.values()['season_images'], settings['season_images'])
        options.monochrome.setChecked(True)
        self.assertTrue(options.values()['pdf_monochrome'])
        self.assertNotIn('pdf_monochrome', settings)  # Cancel can leave original untouched.
        manager.set_theme('system')
        options.deleteLater()


if __name__ == '__main__':
    unittest.main()
