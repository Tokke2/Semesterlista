"""Selected display/export controls, date boundaries and seasonal headings."""
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core.display_options import contrast_ratio, text_scale
from core.export_period import validate_period
from test_settings_dialog import HAVE_QT


class PureOptionsTests(unittest.TestCase):
    def test_contrast_and_zoom_bounds(self):
        self.assertAlmostEqual(contrast_ratio('#000000'), 21)
        self.assertAlmostEqual(contrast_ratio('#FFFFFF'), 1)
        self.assertGreaterEqual(contrast_ratio('#086F78'), 4.5)
        with self.assertRaises(ValueError):
            contrast_ratio('red')
        self.assertEqual(text_scale(250), 2)
        self.assertEqual(text_scale(None), 1)
        self.assertEqual(text_scale(150), 1.5)

    def test_year_boundary_and_leap_centuries(self):
        first, last, leap = validate_period([(2027, 12), (2028, 1), (2028, 2)])
        self.assertEqual(first, date(2027, 12, 1))
        self.assertEqual(last, date(2028, 2, 29))
        self.assertEqual(leap, [2028])
        self.assertEqual(validate_period([(2100, 2)])[1], date(2100, 2, 28))
        self.assertEqual(validate_period([(2000, 2)])[1], date(2000, 2, 29))
        for invalid in ([], [(2028, 13)], [(2028, 2), (2028, 1)], [(2028, 1)] * 2):
            with self.assertRaises(ValueError):
                validate_period(invalid)


@unittest.skipUnless(HAVE_QT, 'Qt unavailable')
class DisplayExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_adaptive_columns_switch_and_keep_widgets(self):
        from PySide6.QtWidgets import QWidget, QLabel
        from core.ui_layout import AdaptiveColumns
        widget = QWidget()
        self.addCleanup(widget.deleteLater)
        layout = AdaptiveColumns(widget)
        for _ in range(2):
            layout.addWidget(QLabel('Example'))
        self.assertEqual(layout.columns(500), 1)
        self.assertEqual(layout.columns(1000), 2)
        self.assertGreater(layout.heightForWidth(500), layout.heightForWidth(1000))

    def test_bilingual_labels_do_not_change_app_language(self):
        from core import i18n
        from core.pdf_labels import month_label
        language = i18n.current_language()
        self.assertIn('January', month_label(1, {'pdf_bilingual': True}))
        self.assertIn('Januari', month_label(1, {'pdf_bilingual': True}))
        self.assertEqual(i18n.current_language(), language)

    def test_season_options_roundtrip(self):
        from core.seasonal_options import SeasonalOptions
        options = SeasonalOptions({'pdf_bilingual': True, 'season_layouts': {'winter': 'frame'}})
        self.addCleanup(options.deleteLater)
        self.assertTrue(options.values()['pdf_bilingual'])
        self.assertEqual(options.values()['season_layouts']['winter'], 'frame')

    def test_three_month_bilingual_export_stays_one_landscape_page(self):
        try:
            import fitz
        except ImportError:
            self.skipTest('PDF parser unavailable')
        from core.calendar_pdf import export_calendar
        with tempfile.TemporaryDirectory() as temp, patch('core.calendar_pdf.confirm_readability', return_value=True):
            for style in ('band', 'line', 'frame', 'split'):
                path = Path(temp) / (style + '.pdf')
                settings = {'seasonal_pdf': True, 'pdf_bilingual': True,
                            'season_layouts': dict(winter=style, spring=style)}
                self.assertTrue(export_calendar(path, 2028, [1, 2, 3], 3, 'sv', settings))
                with fitz.open(path) as pdf:
                    self.assertEqual(len(pdf), 1)
                    self.assertGreater(pdf[0].rect.width, pdf[0].rect.height)
                    self.assertIn('February', pdf[0].get_text())
