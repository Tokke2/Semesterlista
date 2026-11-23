"""Desktop design must remain readable, scalable and theme aware."""
import unittest
from test_settings_dialog import HAVE_QT


@unittest.skipUnless(HAVE_QT, 'Qt unavailable')
class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_fonts_and_all_theme_palettes(self):
        from unittest.mock import Mock
        from core.theme_manager import ThemeManager
        old_font, old_palette, old_style = self.app.font(), self.app.palette(), self.app.styleSheet()
        self.addCleanup(self.app.setFont, old_font)
        self.addCleanup(self.app.setPalette, old_palette)
        self.addCleanup(self.app.setStyleSheet, old_style)
        settings = Mock()
        settings.get.side_effect = lambda key, default=None: default
        manager = ThemeManager(settings)
        for name in ('light', 'dark', 'contrast', 'system'):
            manager.set_theme(name)
            self.assertGreaterEqual(self.app.font().pointSizeF(), 11)
            stylesheet = manager.get_button_tab_stylesheet()
            self.assertIn('QMenu::item', stylesheet)
            self.assertIn('QPlainTextEdit', stylesheet)
            self.assertNotIn('QWidget { font-size: 13px;', stylesheet)
        manager.set_theme('contrast')
        self.assertEqual(manager.get_color('window_bg'), '#000000')
        self.assertEqual(manager.get_color('accent'), '#FFFF00')

    def test_new_vector_icons_render_in_light_and_dark_colors(self):
        from core.ui_icons import icon
        for name in ('search', 'heart', 'home', 'car'):
            for color in ('#172e43', '#ffffff'):
                self.assertFalse(icon(name, color).pixmap(24, 24).isNull())

    def test_vector_icons_render_at_fractional_and_high_dpi(self):
        from PySide6.QtCore import QSize
        from core.ui_icons import icon
        for ratio in (1.0, 1.25, 1.5, 2.0, 3.0):
            image = icon('search', '#172e43').pixmap(QSize(32, 32), ratio)
            self.assertFalse(image.isNull())
            self.assertGreaterEqual(image.width(), round(32 * ratio))
            self.assertAlmostEqual(image.devicePixelRatio(), ratio, places=2)
        # Beyond the previous maximum 64px raster bucket: still native rendering.
        image = icon('heart', '#ffffff').pixmap(192, 192)
        self.assertEqual(image.width(), 192)

    def test_app_marks_are_painted_from_vector_not_scaled_bitmaps(self):
        from core.vector_graphics import VectorMark
        from core.app_icon import ICON_SVG
        widget = VectorMark(ICON_SVG, 64)
        self.addCleanup(widget.deleteLater)
        self.assertTrue(widget.renderer.isValid())
        self.assertFalse(widget.grab().isNull())
