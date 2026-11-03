#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för core/roster.py – hantering av anställda, fordon och hyresgäster.

Körs utan PySide6 och utan nätverk:

    python -m unittest discover -s tests -v
    python tests/test_roster.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.roster import (  # noqa: E402
    MAX_ENTRY_LENGTH,
    RosterError,
    RosterFile,
    decode_bytes,
    ensure_file,
    is_comment,
    is_separator,
    normalize_entry,
    read_entries,
    read_names,
    resolve_path,
    sort_key,
)


class RosterTestCase(unittest.TestCase):
    """Bastest med en temporär appmapp."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="semesterlista-roster-"))
        self.base = self.tmp

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── Hjälpare ─────────────────────────────────────────

    def write(self, name: str, text: str, encoding: str = "utf-8") -> Path:
        path = self.tmp / name
        path.write_bytes(text.encode(encoding))
        return path

    def load(self, path: str = "Anställda.txt", **kwargs) -> RosterFile:
        return RosterFile.load(path, base=self.base, **kwargs)


# ══════════════════════════════════════════════════════════
# INLÄSNING
# ══════════════════════════════════════════════════════════

class TestParsing(RosterTestCase):

    def test_kommentarer_och_tomma_rader(self):
        self.write("Anställda.txt", (
            "# Anställda\n"
            "; också en kommentar\n"
            "\n"
            "Anna Andersson\n"
            "   \n"
            "Bertil Bengtsson\n"
        ))
        roster = self.load(name="Anställda")

        self.assertEqual(roster.entries, ["Anna Andersson", "Bertil Bengtsson"])
        self.assertEqual(len(roster.comments), 2)
        self.assertTrue(roster.exists)

    def test_normaliserar_blanksteg(self):
        self.write("Anställda.txt", "Anna   Andersson \t\n")
        roster = self.load()
        self.assertEqual(roster.entries, ["Anna Andersson"])

    def test_dubbletter_tas_bort_och_rapporteras(self):
        self.write("Anställda.txt", "Anna Andersson\nanna andersson\nAnna Andersson\n")
        roster = self.load()

        self.assertEqual(roster.entries, ["Anna Andersson"])
        self.assertTrue(
            any("Dubbletten" in issue.message for issue in roster.load_issues)
        )

    def test_crlf_och_bom(self):
        path = self.tmp / "Anställda.txt"
        path.write_bytes("Anna Andersson\r\nBertil Bengtsson\r\n".encode("utf-8-sig"))
        roster = RosterFile.load(path)

        self.assertEqual(roster.entries, ["Anna Andersson", "Bertil Bengtsson"])
        self.assertEqual(roster.encoding, "utf-8")   # BOM tas bort vid inläsning

    def test_cp1252_fallback(self):
        self.write("Hyresgäster.txt", "Åsa Öberg\nLars Ölund\n", encoding="cp1252")
        roster = self.load("Hyresgäster.txt")

        self.assertEqual(roster.entries, ["Åsa Öberg", "Lars Ölund"])
        self.assertEqual(roster.encoding, "cp1252")
        self.assertTrue(
            any("cp1252" in issue.message for issue in roster.load_issues)
        )

    def test_sektioner(self):
        self.write("Hyresgäster.txt", (
            "# Månad\n"
            "Anna Andersson\n"
            "Bertil Bengtsson\n"
            "-------\n"
            "# Kvartal\n"
            "Företag AB\n"
            "Konsult & Co\n"
        ))
        roster = self.load("Hyresgäster.txt")

        self.assertEqual(roster.section_count, 2)
        self.assertEqual(roster.section(0), ["Anna Andersson", "Bertil Bengtsson"])
        self.assertEqual(roster.section(1), ["Företag AB", "Konsult & Co"])
        self.assertEqual(roster.entry_count(), 4)

    def test_tre_streck_ocksa_separator(self):
        self.write("Hyresgäster.txt", "A\n---\nB\n")
        roster = self.load("Hyresgäster.txt")
        self.assertEqual(roster.section_count, 2)

    def test_saknad_fil(self):
        roster = self.load("Saknas.txt")
        self.assertFalse(roster.exists)
        self.assertEqual(roster.entries, [])
        self.assertTrue(roster.is_empty())

    def test_skapa_fil_med_exempel(self):
        roster = self.load(
            "Hyresgäster.txt",
            name="Hyresgäster",
            create=True,
            default_sections=[["Anna"], ["Företag AB"]],
        )
        self.assertTrue(roster.path.exists())
        self.assertEqual(roster.section(0), ["Anna"])
        self.assertEqual(roster.section(1), ["Företag AB"])

        # Filen ska gå att läsa tillbaka
        self.assertEqual(RosterFile.load(roster.path).section(1), ["Företag AB"])

    def test_trasig_fil_ger_fel(self):
        path = self.tmp / "Anställda.txt"
        path.write_bytes(b"Anna\n")
        path.chmod(0o000)
        try:
            with self.assertRaises(RosterError):
                RosterFile.load(path)
        finally:
            path.chmod(0o644)


# ══════════════════════════════════════════════════════════
# REDIGERING
# ══════════════════════════════════════════════════════════

class TestEditing(RosterTestCase):

    def setUp(self):
        super().setUp()
        self.write("Anställda.txt", "Anna Andersson\nBertil Bengtsson\nCecilia Carlsson\n")
        self.roster = self.load(name="Anställda")

    def test_lagg_till(self):
        self.assertEqual(self.roster.add("David Dahl"), "David Dahl")
        self.assertIn("David Dahl", self.roster.entries)

    def test_lagg_till_pa_position(self):
        self.roster.add("David Dahl", position=0)
        self.assertEqual(self.roster.entries[0], "David Dahl")

    def test_tom_post_avvisas(self):
        with self.assertRaises(RosterError):
            self.roster.add("   ")

    def test_dubblett_avvisas(self):
        with self.assertRaises(RosterError):
            self.roster.add("anna andersson")

    def test_for_lang_post_avvisas(self):
        with self.assertRaises(RosterError):
            self.roster.add("A" * (MAX_ENTRY_LENGTH + 1))

    def test_byt_namn(self):
        self.roster.rename(0, "Anna A. Andersson")
        self.assertEqual(self.roster.entries[0], "Anna A. Andersson")

    def test_byt_till_dubblett_avvisas(self):
        with self.assertRaises(RosterError):
            self.roster.rename(0, "Bertil Bengtsson")

    def test_byt_till_samma_namn_gar_bra(self):
        self.roster.rename(0, "Anna Andersson")
        self.assertEqual(self.roster.entries[0], "Anna Andersson")

    def test_ogiltigt_index(self):
        with self.assertRaises(RosterError):
            self.roster.rename(99, "Någon")
        with self.assertRaises(RosterError):
            self.roster.remove(99)
        with self.assertRaises(RosterError):
            self.roster.move(99, -1)

    def test_ta_bort(self):
        removed = self.roster.remove(1)
        self.assertEqual(removed, "Bertil Bengtsson")
        self.assertEqual(self.roster.entries, ["Anna Andersson", "Cecilia Carlsson"])

    def test_flytta(self):
        self.assertEqual(self.roster.move(2, -1), 1)
        self.assertEqual(
            self.roster.entries,
            ["Anna Andersson", "Cecilia Carlsson", "Bertil Bengtsson"],
        )
        # Kan inte flyttas utanför listan
        self.assertEqual(self.roster.move(0, -1), 0)
        self.assertEqual(self.roster.move(2, 1), 2)

    def test_sortera_svenskt(self):
        self.roster.set_entries(["Örjan", "Zäta", "Åsa", "Anna", "Ärlig"])
        self.roster.sort()
        self.assertEqual(
            self.roster.entries,
            ["Anna", "Zäta", "Åsa", "Ärlig", "Örjan"],
        )

    def test_sortera_fallande(self):
        self.roster.sort(reverse=True)
        self.assertEqual(self.roster.entries[0], "Cecilia Carlsson")

    def test_set_entries_normaliserar(self):
        self.roster.set_entries(["  Anna   Andersson ", "", "  "])
        self.assertEqual(self.roster.entries, ["Anna Andersson"])

    def test_clear(self):
        self.roster.clear()
        self.assertTrue(self.roster.is_empty())


# ══════════════════════════════════════════════════════════
# VALIDERING
# ══════════════════════════════════════════════════════════

class TestValidation(RosterTestCase):

    def test_giltig_lista_har_inga_fel(self):
        self.write("Anställda.txt", "Anna Andersson\nBertil Bengtsson\n")
        roster = self.load()
        self.assertEqual(
            [issue for issue in roster.validate() if issue.is_error],
            [],
        )
        self.assertFalse(roster.has_errors())

    def test_dubbletter_ger_fel(self):
        roster = self.load("Tom.txt")
        roster.sections = [["Anna Andersson", "anna andersson"]]
        errors = [issue for issue in roster.validate() if issue.is_error]
        self.assertTrue(errors)
        self.assertTrue(roster.has_errors())

    def test_lang_post_ger_varning(self):
        self.write("Anställda.txt", "A" * 50 + "\n")
        roster = self.load()
        warnings = [issue for issue in roster.validate() if issue.is_warning]
        self.assertTrue(any("lång" in issue.message for issue in warnings))
        self.assertFalse(roster.has_errors())

    def test_tom_lista_ger_varning(self):
        roster = self.load("Tom.txt")
        self.assertTrue(any(issue.is_warning for issue in roster.validate()))

    def test_for_lang_post_ger_fel(self):
        roster = self.load("Tom.txt")
        roster.sections = [["B" * (MAX_ENTRY_LENGTH + 5)]]
        self.assertTrue(roster.has_errors())


# ══════════════════════════════════════════════════════════
# SKRIVNING
# ══════════════════════════════════════════════════════════

class TestSaving(RosterTestCase):

    def test_sparar_utf8_med_crlf(self):
        roster = self.load("Anställda.txt", name="Anställda")
        roster.set_entries(["Åsa Öberg", "Anna Andersson"])
        path = roster.save(backup=False)

        raw = path.read_bytes()
        self.assertTrue(raw.startswith(b"# Anst"))
        self.assertIn("Åsa Öberg".encode("utf-8"), raw)
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\n\n", raw)

        # Ska gå att läsa tillbaka
        self.assertEqual(RosterFile.load(path).entries, ["Åsa Öberg", "Anna Andersson"])

    def test_backup_skapas(self):
        self.write("Anställda.txt", "Anna Andersson\n")
        roster = self.load()
        roster.add("Bertil Bengtsson")
        roster.save()

        backup = roster.backup_path
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(encoding="utf-8"), "Anna Andersson\n")

    def test_tmp_fil_stadas(self):
        roster = self.load("Anställda.txt")
        roster.set_entries(["Anna Andersson"])
        roster.save(backup=False)

        leftovers = list(self.tmp.glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_sparar_sektioner(self):
        self.write("Hyresgäster.txt", "Anna\n-------\nFöretag AB\n")
        roster = self.load("Hyresgäster.txt")
        roster.section(1).append("Konsult & Co")
        roster.save(backup=False)

        again = RosterFile.load(roster.path)
        self.assertEqual(again.section(0), ["Anna"])
        self.assertEqual(again.section(1), ["Företag AB", "Konsult & Co"])

    def test_kommentarer_bevaras(self):
        self.write("Anställda.txt", "# Viktig kommentar\nAnna Andersson\n")
        roster = self.load()
        roster.save(backup=False)

        text = roster.path.read_text(encoding="utf-8")
        self.assertIn("# Viktig kommentar", text)

    def test_valideringsfel_hindrar_sparning(self):
        roster = self.load("Tom.txt")
        roster.sections = [["Anna", "anna"]]
        with self.assertRaises(RosterError):
            roster.save()
        self.assertFalse(roster.path.exists())

    def test_reload_laser_om_filen(self):
        self.write("Anställda.txt", "Anna Andersson\n")
        roster = self.load()
        self.write("Anställda.txt", "Anna Andersson\nBertil Bengtsson\n")
        roster.reload()
        self.assertEqual(len(roster.entries), 2)


# ══════════════════════════════════════════════════════════
# HJÄLPFUNKTIONER
# ══════════════════════════════════════════════════════════

class TestHelpers(RosterTestCase):

    def test_normalize_entry(self):
        self.assertEqual(normalize_entry("  Anna \t Andersson  "), "Anna Andersson")
        self.assertEqual(normalize_entry("Anna\u00a0Andersson"), "Anna Andersson")
        self.assertEqual(normalize_entry(None), "")

    def test_sort_key_svensk_ordning(self):
        names = ["Örjan", "Zäta", "Åsa", "Anna", "Ärlig"]
        self.assertEqual(
            sorted(names, key=sort_key),
            ["Anna", "Zäta", "Åsa", "Ärlig", "Örjan"],
        )
        self.assertEqual(sort_key("ÅSA"), sort_key("åsa"))

    def test_is_separator(self):
        self.assertTrue(is_separator("-------"))
        self.assertTrue(is_separator("---"))
        self.assertTrue(is_separator("  -----  "))
        self.assertFalse(is_separator("--"))
        self.assertFalse(is_separator("Anna"))
        self.assertFalse(is_separator("--- Anna"))

    def test_is_comment(self):
        self.assertTrue(is_comment("# hej"))
        self.assertTrue(is_comment("; hej"))
        self.assertFalse(is_comment("Anna # Andersson"))

    def test_resolve_path(self):
        absolute = resolve_path("/tmp/x/Anställda.txt")
        self.assertTrue(absolute.is_absolute())
        self.assertEqual(absolute, Path("/tmp/x/Anställda.txt"))

        relative = resolve_path("Anställda.txt", self.tmp)
        self.assertEqual(relative, self.tmp / "Anställda.txt")

    def test_read_names(self):
        self.write("Fordon.txt", "# Bilar\nABC 123\nXYZ 789\n")
        self.assertEqual(read_names("Fordon.txt", base=self.tmp), ["ABC 123", "XYZ 789"])

    def test_read_names_saknad_fil(self):
        self.assertEqual(read_names("Saknas.txt", base=self.tmp), [])

    def test_read_names_tar_bort_lediga_dagar(self):
        """Lediga dagar efter namnet ska inte hamna i namnlistan (v2.11.0)."""
        self.write(
            "Anställda.txt",
            "Anna Andersson ; 18/12 - 7/1\n"
            "Bertil Bengtsson\n"
            "Cecilia Carlsson | 6/7 - 20/7\n",
        )
        self.assertEqual(
            read_names("Anställda.txt", base=self.tmp),
            ["Anna Andersson", "Bertil Bengtsson", "Cecilia Carlsson"],
        )

    def test_read_entries_ger_namn_och_franvaro(self):
        self.write(
            "Anställda.txt",
            "Anna Andersson ; 18/12 - 7/1\n"
            "Bertil Bengtsson\n",
        )
        self.assertEqual(
            read_entries("Anställda.txt", base=self.tmp),
            [("Anna Andersson", "18/12 - 7/1"), ("Bertil Bengtsson", "")],
        )

    def test_read_entries_saknad_fil(self):
        self.assertEqual(read_entries("Saknas.txt", base=self.tmp), [])

    def test_read_entries_kolon_och_namn_med_kolon(self):
        """Kolon delar bara när det följs av ett datum (v2.11.0)."""
        self.write(
            "Anställda.txt",
            "Roland: 18/12-7/1\n"
            "Avdelning: Ekonomi\n",
        )
        self.assertEqual(
            read_entries("Anställda.txt", base=self.tmp),
            [("Roland", "18/12-7/1"), ("Avdelning: Ekonomi", "")],
        )

    def test_ensure_file_skapar(self):
        roster = ensure_file(
            "Fordon.txt", name="Fordon", base=self.tmp,
            default_sections=[["ABC 123"]],
        )
        self.assertTrue(roster.path.exists())
        self.assertEqual(roster.entries, ["ABC 123"])

    def test_decode_bytes(self):
        text, encoding = decode_bytes("Åsa".encode("cp1252"))
        self.assertEqual(text, "Åsa")
        self.assertEqual(encoding, "cp1252")

        text, encoding = decode_bytes("Åsa".encode("utf-8"))
        self.assertEqual(text, "Åsa")
        self.assertEqual(encoding, "utf-8")

        text, encoding = decode_bytes("Åsa".encode("utf-8-sig"))
        self.assertEqual(text, "Åsa")
        self.assertEqual(encoding, "utf-8-sig")


if __name__ == "__main__":
    unittest.main(verbosity=2)
