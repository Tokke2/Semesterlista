#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för att källkoden är varningsfri.

Bakgrund: loggen 2026-11-03 visade ``SyntaxWarning: "\S" is an invalid escape
sequence`` från ``core/single_instance.py``. Python 3.12+ varnar för ogiltiga
escape-sekvenser i vanliga strängar och i framtiden blir det ett fel – därför
kompileras alla moduler här med ``SyntaxWarning`` som fel.

Körs utan Qt och utan nätverk.

    python -m unittest discover -s tests -v
    python tests/test_no_warnings.py
"""

from __future__ import annotations

import sys
import unittest
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def source_files() -> list:
    """Alla Python-filer som ingår i appen (inte testerna)."""
    files = sorted(PROJECT_ROOT.glob("core/*.py"))
    files += sorted(PROJECT_ROOT.glob("plugins/*/*.py"))
    files += sorted(PROJECT_ROOT.glob("tools/*.py"))
    for extra in ("main.pyw",):
        path = PROJECT_ROOT / extra
        if path.exists():
            files.append(path)
    return files


class SyntaxWarningTests(unittest.TestCase):
    """Källkoden ska kompilera utan SyntaxWarning."""

    def test_all_sources_compile_without_warnings(self) -> None:
        files = source_files()
        self.assertGreater(len(files), 10, "hittade inga källfiler")

        problems = []
        for path in files:
            source = path.read_text(encoding="utf-8")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    compile(source, str(path), "exec")
                except SyntaxError as exc:  # pragma: no cover – trasig fil
                    problems.append(f"{path.name}: SyntaxError {exc}")
                    continue
            for warning in caught:
                if issubclass(warning.category, SyntaxWarning):
                    problems.append(
                        f"{path.name}:{warning.lineno}: {warning.message}"
                    )

        self.assertEqual(problems, [], "SyntaxWarning i källkoden:\n" + "\n".join(problems))

    def test_single_instance_has_raw_docstrings(self) -> None:
        """Windows-sökvägarna i single_instance.py ska ligga i råa strängar."""
        source = (PROJECT_ROOT / "core" / "single_instance.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('r"""', source, "modulens docstring ska vara rå")


if __name__ == "__main__":
    unittest.main(verbosity=2)
