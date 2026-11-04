"""Verify real PDFs, not only layout estimates."""
import importlib.util
from datetime import date
from unittest.mock import patch
from test_pdf_layout import PdfLayoutTestBase
from core import i18n


class ExportRegressionTests(PdfLayoutTestBase):
    def test_global_region_is_used_in_pdf(self):
        from plugins.lista import pdf
        from core import holidays
        for region in ["sv", "us"]:
            self.plugin._settings_manager.set("holiday_region", region)
            # A stale plugin-local setting must never override the app setting.
            self.plugin.settings["holiday_region"] = "us" if region == "sv" else "sv"
            self.assertEqual(self.generator._holiday_region(), region)
            with patch.object(pdf, "holidays_for", wraps=pdf.holidays_for) as called:
                self._generate(months_per_page=3, start_month=12)
                self.assertEqual([call.args for call in called.call_args_list], [(2026, region), (2027, region)])
                self.assertEqual(called(2026, region), holidays.get_holidays(2026, region))
        self.plugin._settings_manager.set("holiday_region", "sv")

    def test_real_exports_keep_every_month_and_name(self):
        if importlib.util.find_spec("fitz") is None:
            self.skipTest("PyMuPDF missing")
        import fitz
        old_language = i18n.current_language()
        i18n.set_language("sv")
        try:
            self.plugin.settings["company_name"] = "Exempelföretaget AB"
            for mode in ["Semesterlista", "Limokörning"]:
                for count in [1, 2, 3]:
                    for size in [6, 80]:
                        with self.subTest(mode=mode, months=count, names=size):
                            names = [f"Person{i:03}" for i in range(size)]
                            path = self._generate(names=names, mode=mode, months_per_page=count, start_month=12)
                            with fitz.open(path) as doc:
                                self.assertEqual(len(doc), 12 // count)
                                for index, page in enumerate(doc):
                                    self.assertEqual(page.rect.width < page.rect.height, count == 1)
                                    text = page.get_text()
                                    self.assertIn(f"Sida {index + 1} av {len(doc)}", text)
                                    self.assertIn(date.today().isoformat(), text)
                                    self.assertIn("Exempelföretaget AB", text)
                                    for name in names:
                                        self.assertEqual(text.count(name), count)
                                    sequence = self.generator._build_month_sequence(2026, 12)
                                    for year, month in sequence[index * count:(index + 1) * count]:
                                        self.assertIn(f"{i18n.month_name(month)} {year}", text)
                                    for x0, y0, x1, y1, *_ in page.get_text("words"):
                                        self.assertGreaterEqual(x0, 0)
                                        self.assertGreaterEqual(y0, 0)
                                        self.assertLessEqual(x1, page.rect.width)
                                        self.assertLessEqual(y1, page.rect.height)
        finally:
            i18n.set_language(old_language)

    def test_fordon_inherits_split_plugin(self):
        from plugins.fordon.plugin import Plugin
        from plugins.lista.view import SemesterlistaView
        plugin = Plugin(self.plugin._event_bus, self.plugin._settings_manager)
        self.assertIsInstance(plugin.get_tab_widget(), SemesterlistaView)
        self.assertEqual(plugin.FIXED_MODE, "Limokörning")
