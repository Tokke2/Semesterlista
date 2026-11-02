#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för hyresvyns årbyte (v2.8.1).

Buggen som testas: när man bytte år i **Hyra**-fliken byggdes vyn om med
``QVBoxLayout(self)`` trots att widgeten redan hade en layout. Qt vägrar då
sätta den nya layouten (”QLayout: Attempting to add QLayout … which already
has a layout”), vilket gjorde att **hela sidan blev tom**.

Kräver PySide6 och körs offscreen. Saknas Qt hoppas filen över.

    python -m unittest discover -s tests -v
    python tests/test_hyra_view.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication, QGroupBox, QLabel

    HAVE_QT = True
except Exception:  # pragma: no cover – miljö utan PySide6
    HAVE_QT = False

PLUGIN_PATH = PROJECT_ROOT / "plugins" / "hyra" / "plugin.py"


def _load_plugin_module():
    """Ladda plugins/hyra/plugin.py utan att gå via PluginManager."""
    name = "plugins.hyra.plugin"
    if name in sys.modules:
        return sys.modules[name]

    spec = importlib.util.spec_from_file_location(name, PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakePlugin:
    """Minimal Plugin-stub som vyn behöver."""

    def __init__(self) -> None:
        self.settings: dict = {}

    def _save_settings(self) -> None:  # pragma: no cover – anropas ej
        pass

    def _manage_tenants(self) -> None:  # pragma: no cover
        pass

    def _generate_pdf(self) -> None:  # pragma: no cover
        pass


@unittest.skipUnless(HAVE_QT, "PySide6 saknas")
class HyraYearChangeTests(unittest.TestCase):
    """Årbytet ska uppdatera kvartalskorten – inte tömma sidan."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.app = QApplication.instance() or QApplication([])
        except Exception as exc:  # pragma: no cover – ingen skärm
            raise unittest.SkipTest(f"Qt kunde inte startas: {exc}")

        cls.module = _load_plugin_module()

        from core import i18n
        from core.settings_manager import SettingsManager

        cls.i18n = i18n
        cls._i18n_tmp = tempfile.TemporaryDirectory()
        i18n.init(SettingsManager(cls._i18n_tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._i18n_tmp.cleanup()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

        # Streckraden skiljer månads- från kvartalshyresgäster
        self.tenant_file = Path(self._tmp.name) / "Hyresgäster.txt"
        self.tenant_file.write_text(
            "Anna Andersson\nBertil Berg\n-------\nFirma AB\n",
            encoding="utf-8",
        )

        self.tenants = self.module.TenantManager(str(self.tenant_file))
        self.view = self.module.HyraMainView(self.tenants, FakePlugin())
        self.addCleanup(self.view.deleteLater)

    # ── Hjälpare ─────────────────────────────────────────

    def _group_titles(self) -> list[str]:
        return [g.title() for g in self.view.findChildren(QGroupBox)]

    def _labels_in_layout(self) -> int:
        """Antal synliga etiketter – 0 om sidan har blivit tom."""
        return len([w for w in self.view.findChildren(QLabel) if w.isVisible()])

    def _quarter_group_in_layout(self) -> bool:
        layout = self.view.layout()
        group = self.view._quarter_group
        if layout is None or group is None:
            return False
        return layout.indexOf(group) >= 0

    # ── Tester ───────────────────────────────────────────

    def test_view_builds(self) -> None:
        self.assertIsNotNone(self.view.layout())
        self.assertGreaterEqual(self.view.layout().count(), 4)
        self.assertIn(
            "📅 Kvartalsfakturor – Skicka senast", self._group_titles()
        )

    def test_layout_reused_after_refresh(self) -> None:
        """Rotlayouten ska vara samma objekt före och efter uppdateringen."""
        before = self.view.layout()
        self.view._refresh_ui()
        self.app.processEvents()
        self.assertIs(self.view.layout(), before)

    def test_year_change_keeps_page(self) -> None:
        """Hela sidan fick tidigare 0 layoutobjekt efter ett årbyte."""
        self.view.show()
        self.app.processEvents()
        labels_before = self._labels_in_layout()
        self.assertGreater(labels_before, 0)

        self.view.year_spin.setValue(self.tenants.get_year() + 1)
        self.app.processEvents()

        layout = self.view.layout()
        self.assertIsNotNone(layout)
        self.assertGreaterEqual(
            layout.count(), 4, "layouten tömdes när året ändrades"
        )
        self.assertTrue(
            self._quarter_group_in_layout(),
            "kvartalspanelen ligger inte kvar i layouten",
        )
        self.assertGreater(self._labels_in_layout(), 0, "sidan blev tom")

    def test_year_change_updates_cards(self) -> None:
        """Kvartalskorten ska visas för det nya året."""
        self.view.show()
        self.app.processEvents()

        self.view.year_spin.setValue(2030)
        self.app.processEvents()

        self.assertEqual(self.tenants.get_year(), 2030)
        self.assertEqual(self.view.year_spin.value(), 2030)

        texts = [lbl.text() for lbl in self.view._quarter_group.findChildren(QLabel)]
        self.assertTrue(any("Q1" == t for t in texts), texts)
        self.assertTrue(any("Skickas" in t for t in texts), texts)
        self.assertTrue(any("dagar" in t for t in texts), texts)

    def test_no_duplicate_quarter_group(self) -> None:
        """Den gamla kvartalspanelen ska tas bort, inte staplas."""
        self.view.show()
        self.app.processEvents()

        for year in (2029, 2030, 2031):
            self.view.year_spin.setValue(year)
            self.app.processEvents()

        groups = [g for g in self.view.findChildren(QGroupBox)
                  if g.title() == "📅 Kvartalsfakturor – Skicka senast"]
        self.assertEqual(len(groups), 1, "kvartalspanelen duplicerades")

    def test_no_qlayout_warning(self) -> None:
        """Qt ska inte varna om att widgeten redan har en layout."""
        messages: list[str] = []
        previous = qInstallMessageHandler(lambda mode, ctx, msg: messages.append(msg))
        try:
            self.view.year_spin.setValue(self.tenants.get_year() + 2)
            self.app.processEvents()
        finally:
            qInstallMessageHandler(previous)

        offending = [m for m in messages if "already has a layout" in m]
        self.assertEqual(offending, [], offending)

    def test_reload_still_works(self) -> None:
        """”Ladda om” bygger om hela vyn – utan att tömma den."""
        before = self.view.layout()
        self.view._reload()
        self.app.processEvents()

        self.assertIs(self.view.layout(), before)
        self.assertGreaterEqual(self.view.layout().count(), 4)
        self.assertTrue(self._quarter_group_in_layout())

    def test_logo_dropdown_is_present(self) -> None:
        """Logotypen väljs i en dropdown (v2.10.0) – utan förhandsgranskning."""
        picker = getattr(self.view, "logo_picker", None)
        self.assertIsNotNone(picker, "vyn ska ha en LogoPicker")
        self.assertFalse(picker.preview.isVisible())
        # Post 0 = ingen logotyp, resten kommer från assets/ (+ undermappar)
        self.assertEqual(picker.combo.itemData(0), "")
        self.assertEqual(
            picker.combo.count(), 1 + len(picker.assets()),
            "listan ska spegla bilderna i assets-mappen",
        )

    def test_tenants_are_listed(self) -> None:
        """Månads- respektive kvartalshyresgäster hamnar i rätt ruta."""
        self.assertEqual(self.tenants.get_monthly_tenants(), ["Anna Andersson", "Bertil Berg"])
        self.assertEqual(self.tenants.get_quarterly_tenants(), ["Firma AB"])

        texts = " ".join(lbl.text() for lbl in self.view.findChildren(QLabel))
        self.assertIn("Anna Andersson", texts)
        self.assertIn("Firma AB", texts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
