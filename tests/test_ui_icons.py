"""Shared brand assets, themed controls, translation and accessible labels."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from test_pdf_layout import PdfLayoutTestBase

ROOT = Path(__file__).resolve().parent.parent


class BrandAssetTests(unittest.TestCase):
    def test_brand_and_all_ui_assets_are_self_contained_svg(self):
        paths = list((ROOT / 'assets' / 'ui').glob('*.svg'))
        self.assertEqual(len(paths), 18)
        paths += list((ROOT / 'assets' / 'brand').glob('*.svg'))
        for path in paths:
            with self.subTest(path=path.name):
                source = path.read_text(encoding='utf-8')
                self.assertEqual(ET.fromstring(source).tag, '{http://www.w3.org/2000/svg}svg')
                self.assertNotIn('<script', source)
                self.assertNotIn('href=', source)

    def test_print_logos_are_outlined_vectors_with_physical_size(self):
        for name in ('logotyp-tryck.svg', 'logotyp-svart.svg'):
            root = ET.parse(ROOT / 'assets' / 'brand' / name).getroot()
            self.assertTrue(root.attrib['width'].endswith('mm'))
            tags = [node.tag.split('}')[-1] for node in root.iter()]
            for forbidden in ('text', 'image', 'foreignObject', 'use', 'style'):
                self.assertNotIn(forbidden, tags)
            self.assertGreater(tags.count('path'), 20)
        black = ET.parse(ROOT / 'assets/brand/logotyp-svart.svg').getroot()
        for node in black.iter():
            self.assertNotIn('Gradient', node.tag)
            self.assertNotIn('opacity', node.attrib)
            for attribute in ('fill', 'stroke'):
                if attribute in node.attrib:
                    self.assertIn(node.attrib[attribute], ('none', '#000000', '#ffffff'))
        from core.app_icon import ICON_SVG
        self.assertEqual(ICON_SVG, (ROOT / 'assets/ikon/appikon.svg').read_text(encoding='utf-8'))

    def test_release_archive_includes_print_material_and_app(self):
        import shutil
        import subprocess
        import tempfile
        import zipfile
        if not shutil.which('git'):
            self.skipTest('Git is needed to verify the release archive')
        status = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT,
                                capture_output=True, text=True)
        if status.returncode or Path(status.stdout.strip()).resolve() != ROOT.resolve():
            self.skipTest('Source ZIP has no Git checkout')
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'release.zip'
            subprocess.run(['git', 'archive', '--format=zip', 'HEAD', '-o', str(archive)],
                           cwd=ROOT, check=True, capture_output=True)
            with zipfile.ZipFile(archive) as bundle:
                for name in ('main.pyw', 'assets/brand/logotyp-tryck.svg',
                             'assets/brand/logotyp-svart.svg', 'assets/brand/FONT-LICENSE.txt',
                             'assets/ikon/appikon.svg', 'assets/ikon/appikon.ico'):
                    self.assertIn(name, bundle.namelist())
                    self.assertEqual(bundle.read(name), (ROOT / name).read_bytes())

    def test_readme_is_short_and_local_images_exist(self):
        import re
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertLess(len(readme.splitlines()), 120)
        for path in re.findall(r'src="([^"]+)"', readme):
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertTrue((ROOT / 'docs' / 'guide.md').is_file())

    def test_internal_icons_are_not_customer_pdf_logos(self):
        from core.pdf_assets import scan_assets
        assets = scan_assets(ROOT / 'assets')
        self.assertFalse(any(asset.relative.startswith(('ui/', 'brand/', 'ikon/')) for asset in assets))


class UiIconTests(PdfLayoutTestBase):
    def test_button_label_and_theme_changes_keep_icon(self):
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtGui import QPalette, QColor
        from core.ui_icons import IconController
        controller = IconController(self.app)
        button = QPushButton('📝 Redigera egen lista')
        self.addCleanup(button.deleteLater)
        controller.decorate(button)
        self.assertEqual(button.text(), 'Redigera egen lista')
        self.assertFalse(button.icon().isNull())
        for color in ('#ffffff', '#000000', '#ffff00'):
            palette = button.palette()
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(color))
            button.setPalette(palette)
            controller.decorate(button)
            signature = button.property('semesterlistaIconSignature')
            self.assertIn(color, signature)
            cache_key = button.icon().cacheKey()
            controller.decorate(button)
            self.assertEqual(button.icon().cacheKey(), cache_key)
        button.setText('Edit custom list')
        controller.decorate(button)
        self.assertEqual(button.text(), 'Edit custom list')
        self.assertFalse(button.icon().isNull())

    def test_application_filter_covers_late_dialog_buttons_actions_and_tabs(self):
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTabWidget, QMenu
        from core.ui_icons import install_ui_icons
        controller = install_ui_icons(self.app)
        self.addCleanup(lambda: delattr(self.app, '_semesterlista_icon_controller'))
        self.addCleanup(lambda: self.app.removeEventFilter(controller))
        self.addCleanup(controller.deleteLater)
        window = QWidget()
        layout = QVBoxLayout(window)
        button = QPushButton('🖨️ Generera PDF')
        layout.addWidget(button)
        tabs = QTabWidget()
        page = QWidget()
        page.setProperty('semesterlistaIcon', 'calendar')
        tabs.addTab(page, 'Kalender')
        layout.addWidget(tabs)
        menu = QMenu(window)
        action = menu.addAction('📝 Redigera')
        window.addAction(action)
        window.show()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        for _ in range(3):
            self.app.processEvents()
        self.assertFalse(button.icon().isNull())
        self.assertFalse(tabs.tabIcon(0).isNull())
        self.assertFalse(action.icon().isNull())
        self.assertEqual(button.text(), 'Generera PDF')
