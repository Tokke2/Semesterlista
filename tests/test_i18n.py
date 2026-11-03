#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för översättningarna (v2.11.0).

Tre saker kontrolleras:

1. Svenska och engelska har **exakt samma nycklar**.
2. Alla ``i18n.t("...")`` som används i koden finns i båda språken
   (annars visas nyckelnamnet för användaren).
3. Inga **hårdkodade texter** i gränssnittet – texter ska gå via ``i18n.t``
   så att engelskan fungerar. Emoji, tomma strängar och standardfilnamn
   (``Anställda.txt``) är undantagna.

    python -m unittest discover -s tests -v
    python tests/test_i18n.py
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

I18N_PATH = PROJECT_ROOT / "core" / "i18n.py"

#: Widget-texter som inte får vara hårdkodade
WIDGET_PATTERN = re.compile(
    r'(?:QLabel|QPushButton|QCheckBox|QGroupBox|QRadioButton)\(\s*"((?:[^"\\]|\\.)*)"'
    r'|setWindowTitle\(\s*"((?:[^"\\]|\\.)*)"'
    r'|setToolTip\(\s*"((?:[^"\\]|\\.)*)"'
)

KEY_PATTERN = re.compile(r'i18n\.t\(\s*"([^"]+)"')

SOURCES = [
    PROJECT_ROOT / "main.pyw",
    *sorted((PROJECT_ROOT / "core").glob("*.py")),
    *sorted((PROJECT_ROOT / "plugins").glob("*/*.py")),
]


def load_translations() -> dict:
    """Läs TRANSLATIONS-dicten utan att importera PySide6."""
    tree = ast.parse(I18N_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        name = getattr(getattr(node, "targets", [None])[0], "id", None) or getattr(
            getattr(node, "target", None), "id", None
        )
        if name == "TRANSLATIONS":
            return ast.literal_eval(node.value)
    raise AssertionError("TRANSLATIONS hittades inte i core/i18n.py")


def _is_allowed_literal(text: str) -> bool:
    """Emoji, tomt och standardfilnamn får stå som de är."""
    stripped = text.strip()
    if not stripped:
        return True
    if not re.search(r"[A-Za-zÅÄÖåäö]", stripped):
        return True  # bara emoji/symboler
    if stripped.lower().endswith((".txt", ".svg", ".png", ".jpg")):
        return True
    return False


class TranslationContentTests(unittest.TestCase):
    """Innehållet i core/i18n.py."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_translations()

    def test_both_languages_exist(self) -> None:
        self.assertIn("sv", self.data)
        self.assertIn("en", self.data)

    def test_same_keys_in_both_languages(self) -> None:
        sv = set(self.data["sv"])
        en = set(self.data["en"])
        self.assertEqual(sv - en, set(), "nycklar som bara finns på svenska")
        self.assertEqual(en - sv, set(), "nycklar som bara finns på engelska")

    def test_no_empty_translations(self) -> None:
        for language, table in self.data.items():
            empty = [key for key, value in table.items() if not str(value).strip()]
            self.assertEqual(empty, [], f"tomma texter på {language}")

    def test_placeholders_match_between_languages(self) -> None:
        placeholder = re.compile(r"\{(\w+)\}")
        problems = []
        for key, sv_text in self.data["sv"].items():
            en_text = self.data["en"].get(key, "")
            if set(placeholder.findall(sv_text)) != set(placeholder.findall(en_text)):
                problems.append(key)
        self.assertEqual(problems, [], "olika platshållare i sv och en")


class UsageTests(unittest.TestCase):
    """Att koden använder nycklar som finns och inga hårdkodade texter."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_translations()

    def test_all_used_keys_exist(self) -> None:
        missing = []
        for path in SOURCES:
            if not path.is_file() or path.name == "i18n.py":
                continue
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for key in KEY_PATTERN.findall(line):
                    if key not in self.data["sv"]:
                        missing.append(f"{path.relative_to(PROJECT_ROOT)}:{line_no} {key}")
        self.assertEqual(missing, [], "nycklar som saknas i core/i18n.py")

    def test_no_hardcoded_widget_texts(self) -> None:
        offenders = []
        for path in SOURCES:
            if not path.is_file():
                continue
            # core/i18n.py innehåller texterna själva – hoppa över
            if path.name == "i18n.py":
                continue
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "i18n.t(" in line:
                    continue
                match = WIDGET_PATTERN.search(line)
                if not match:
                    continue
                text = next((g for g in match.groups() if g is not None), "")
                if _is_allowed_literal(text):
                    continue
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{line_no} {text!r}")
        self.assertEqual(
            offenders,
            [],
            "texter ska gå via i18n.t(...) så att engelskan fungerar:\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
