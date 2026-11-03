#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för hjälptexten om lediga dagar i listredigeraren (v2.11.0).

Hela filen hoppas över om PySide6 saknas.

    python -m unittest discover -s tests -v
    python tests/test_list_editor.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAVE_QT = True
except Exception:  # pragma: no cover – miljö utan Qt
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 saknas")
class LeaveHintTests(unittest.TestCase):
    """Redigeraren ska visa hur lediga dagar skrivs – och behålla dem."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.app = QApplication.instance() or QApplication([])
        except Exception as exc:  # pragma: no cover – ingen skärm
            raise unittest.SkipTest(f"Qt kunde inte startas: {exc}")

        from core import i18n

        cls.i18n = i18n
        cls.old_language = i18n.current_language()
        i18n.set_language("sv")

        from core.list_editor_dialog import SectionEditor

        cls.Editor = SectionEditor

    @classmethod
    def tearDownClass(cls) -> None:
        cls.i18n.set_language(cls.old_language)

    def test_hint_is_shown(self) -> None:
        editor = self.Editor([])
        self.assertEqual(editor.leave_hint.text(), self.i18n.t("roster.leave.hint"))
        self.assertIn("18/12", editor.leave_hint.text())
        self.assertIn("måndag", editor.leave_hint.text())

    def test_hint_has_english_text(self) -> None:
        self.i18n.set_language("en")
        try:
            editor = self.Editor([])
            self.assertIn("Monday", editor.leave_hint.text())
        finally:
            self.i18n.set_language("sv")

    def test_entries_keep_leave_text(self) -> None:
        editor = self.Editor(["Anna Andersson ; 18/12 - 7/1", "Bertil Bengtsson"])
        self.assertEqual(
            editor.entries(),
            ["Anna Andersson ; 18/12 - 7/1", "Bertil Bengtsson"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
