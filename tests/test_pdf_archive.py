"""Archive regressions: no overwritten PDFs, no partial files, automatic opening."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core import pdf_export
from core.updater import _skip_file
from test_pdf_layout import PdfLayoutTestBase, HAVE_GUI


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'App åäö with spaces'
        self.root.mkdir()
        root_patch = patch.object(pdf_export, 'app_root', return_value=self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def target(self):
        return Path(pdf_export.get_export_folder('Kalender')) / 'kalender_2026.pdf'

    @staticmethod
    def render(path):
        Path(path).write_bytes(b'%PDF-complete')
        return True

    def test_type_folders_independent_of_working_directory(self):
        previous = Path.cwd()
        try:
            os.chdir(self.temp.name)
            for kind in pdf_export.EXPORT_TYPES:
                folder = Path(pdf_export.get_export_folder(kind))
                self.assertEqual(folder, self.root / 'export' / kind)
                self.assertTrue(folder.is_dir())
        finally:
            os.chdir(previous)
        with self.assertRaises(ValueError):
            pdf_export.get_export_folder('../outside')

    def test_repeated_exports_preserve_every_previous_pdf(self):
        target = self.target()
        target.write_bytes(b'old PDF')
        outputs = [pdf_export.render_to_archive(target, self.render) for _ in range(3)]
        self.assertEqual(len(set(outputs)), 3)
        self.assertEqual(target.read_bytes(), b'old PDF')
        for output in outputs:
            self.assertEqual(Path(output).read_bytes(), b'%PDF-complete')
        self.assertEqual(len(list(target.parent.iterdir())), 4)

    def test_cancel_and_render_failure_leave_no_partial_files(self):
        target = self.target()
        target.write_bytes(b'old PDF')
        self.assertIsNone(pdf_export.render_to_archive(target, lambda path: False))
        def broken(path):
            Path(path).write_bytes(b'partial')
            raise RuntimeError('render failed')
        with self.assertRaisesRegex(RuntimeError, 'render failed'):
            pdf_export.render_to_archive(target, broken)
        self.assertEqual(target.read_bytes(), b'old PDF')
        self.assertEqual(list(target.parent.iterdir()), [target])

    def test_publish_failure_removes_reserved_name_and_temporary(self):
        target = self.target()
        with patch.object(Path, 'replace', side_effect=PermissionError('read only')):
            with self.assertRaises(PermissionError):
                pdf_export.render_to_archive(target, self.render)
        self.assertEqual(list(target.parent.iterdir()), [])

    def test_identical_timestamps_still_have_unique_names(self):
        target = self.target()
        with patch.object(pdf_export, 'datetime') as clock:
            clock.now.return_value.strftime.return_value = 'fixed-time'
            outputs = [pdf_export.render_to_archive(target, self.render) for _ in range(4)]
        self.assertEqual(len(set(outputs)), 4)

    def test_updater_excludes_all_export_types(self):
        for kind in pdf_export.EXPORT_TYPES:
            self.assertTrue(_skip_file(Path('export') / kind / 'test.pdf'))
        self.assertFalse(_skip_file(Path('core') / 'pdf_export.py'))


class ListArchiveTests(PdfLayoutTestBase):
    def test_lists_archive_and_open_even_when_old_setting_is_false(self):
        self.plugin.settings['auto_open_pdf'] = False
        with patch.object(pdf_export, 'app_root', return_value=self.outdir), \
             patch.object(self.pdf_module, 'get_export_folder', pdf_export.get_export_folder), \
             patch.object(self.pdf_module, 'open_pdf') as opened:
            for mode, folder in [('Semesterlista', 'Semesterlista'), ('Limokörning', 'Fordon')]:
                for _ in range(2):
                    self.assertTrue(self.generator._generate_pdf(['Anna Andersson'], 2026, mode))
                outputs = list((self.outdir / 'export' / folder).glob('*.pdf'))
                self.assertEqual(len(outputs), 2)
                self.assertTrue(all(p.read_bytes().startswith(b'%PDF-') for p in outputs))
            self.assertEqual(opened.call_count, 4)
            self.assertEqual(len({c.args[0] for c in opened.call_args_list}), 4)


    def test_calendar_archives_opens_and_cancel_does_not_open(self):
        from plugins.kalender import plugin as calendar
        view = calendar.CalendarView(self.plugin)
        self.addCleanup(view.deleteLater)
        with patch.object(pdf_export, 'app_root', return_value=self.outdir), \
             patch.object(calendar, 'open_pdf') as opened:
            view._export()
            view._export()
            outputs = list((self.outdir / 'export' / 'Kalender').glob('*.pdf'))
            self.assertEqual(len(outputs), 2)
            self.assertTrue(all(p.read_bytes().startswith(b'%PDF-') for p in outputs))
            self.assertEqual(opened.call_count, 2)
            with patch.object(calendar, 'export_calendar', return_value=False):
                view._export()
            self.assertEqual(opened.call_count, 2)
            self.assertEqual(len(list(outputs[0].parent.iterdir())), 2)

    def test_rent_archives_and_reports_unwritable_folder(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from plugins.hyra import plugin as rent
        tenant_file = self.outdir / 'Hyresgäster.txt'
        tenant_file.write_text('Anna Andersson\n-------\nFirma AB\n', encoding='utf-8')
        tenants = rent.TenantManager(str(tenant_file))
        tenants.set_year(2026)
        generator = rent.PDFGenerator(SimpleNamespace(
            settings={}, tenant_manager=tenants, emit=Mock()))
        with patch.object(pdf_export, 'app_root', return_value=self.outdir), \
             patch.object(rent, 'open_pdf') as opened:
            self.assertTrue(generator.generate())
            self.assertTrue(generator.generate())
            outputs = list((self.outdir / 'export' / 'Hyra').glob('*.pdf'))
            self.assertEqual(len(outputs), 2)
            self.assertTrue(all(p.read_bytes().startswith(b'%PDF-') for p in outputs))
            self.assertEqual(opened.call_count, 2)
            with patch.object(rent, 'get_export_folder', side_effect=PermissionError('read only')), \
                 patch.object(rent.QMessageBox, 'critical') as error:
                self.assertFalse(generator.generate())
                error.assert_called_once()
                self.assertEqual(opened.call_count, 2)


@unittest.skipUnless(HAVE_GUI, 'PySide6/reportlab missing')
class ViewerTests(unittest.TestCase):
    def test_local_file_url_and_failed_viewer_warning(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QMessageBox
        path = Path(tempfile.gettempdir()) / 'åäö # % PDF.pdf'
        with patch.object(QDesktopServices, 'openUrl', return_value=True) as opened, \
             patch.object(QMessageBox, 'warning') as warning:
            self.assertTrue(pdf_export.open_pdf(path))
            url = opened.call_args.args[0]
            self.assertTrue(url.isLocalFile())
            self.assertEqual(Path(url.toLocalFile()), path.resolve())
            warning.assert_not_called()
            opened.return_value = False
            self.assertFalse(pdf_export.open_pdf(path))
            self.assertIn(str(path), warning.call_args.args[2])
