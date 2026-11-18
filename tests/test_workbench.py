"""Overview/search must use real data; driver PDFs must not lose long text."""
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core.workbench_data import SearchEntry, read_overview, search_entries
from test_settings_dialog import HAVE_QT


class OverviewTests(unittest.TestCase):
    def test_search_all_tokens_case_insensitive_and_literal(self):
        entries = [SearchEntry('Fordon', 'ABC 123', 'Stor bil'),
                   SearchEntry('Hyra', 'Åsa & Co', 'kvartal')]
        self.assertEqual(search_entries(entries, 'BIL abc'), entries[:1])
        self.assertEqual(search_entries(entries, 'åSA'), entries[1:])
        self.assertEqual(search_entries(entries, '.*'), [])
        self.assertEqual(search_entries(entries, ''), entries)

    def test_upcoming_vacation_and_all_tenant_sections(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'list.txt'
            path.write_text('Anna; 2026-07-01 - 2026-07-12\nBo; 2026-09-01 - 2026-09-10\n-------\nÅsa\n', encoding='utf-8')
            entries, periods, errors = read_overview(path, 'Semesterlista', True, date(2026, 7, 5))
            self.assertEqual(len(entries), 3)
            self.assertEqual(periods, [('Anna', date(2026, 6, 29), date(2026, 7, 12))])
            self.assertEqual(errors, [])
            self.assertEqual(read_overview(path, 'Hyra')[1], [])


@unittest.skipUnless(HAVE_QT, 'Qt unavailable')
class WorkbenchUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_search_empty_and_enter_command(self):
        from PySide6.QtWidgets import QWidget
        from unittest.mock import Mock
        from core.workbench import SearchDialog
        window = QWidget()
        for method in ('_open_settings', '_show_donation', '_show_start'):
            setattr(window, method, Mock())
        with patch('core.workbench.snapshot', return_value=([], [])):
            dialog = SearchDialog(window)
            dialog.query.setText('does-not-exist-12345')
            dialog.activate()
            window._show_start.assert_not_called()
            from core import i18n
            dialog.query.setText(i18n.t('work.home'))
            dialog.activate()
            window._show_start.assert_called_once()
            dialog.deleteLater()
        window.deleteLater()

    def test_driver_pdf_archival_and_long_text(self):
        try:
            import fitz
        except ImportError:
            self.skipTest('PDF parser unavailable')
        from core.driver_sheet import export_driver_sheet
        with tempfile.TemporaryDirectory() as temp, patch('core.driver_sheet.get_export_folder', return_value=temp):
            values = {'vehicle': 'ABC 123', 'pickup': 'Åvägen 4 & Torget <5>',
                      'notes': ('Long note for driver. ' * 150) + ' END_OF_NOTES'}
            first = export_driver_sheet(date(2026, 7, 5), values)
            second = export_driver_sheet(date(2026, 7, 5), values)
            self.assertNotEqual(first, second)
            with fitz.open(first) as pdf:
                text = ''.join(page.get_text() for page in pdf)
                self.assertIn('ABC 123', text)
                self.assertIn('END_OF_NOTES', text)
                self.assertIn('Torget <5>', text)
                self.assertGreater(len(pdf), 1)
                for page in pdf:
                    self.assertAlmostEqual(page.rect.width, 595.28, delta=1)
                    self.assertAlmostEqual(page.rect.height, 841.89, delta=1)
