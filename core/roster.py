#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
List- och namnhantering (roster) – anställda, fordon och hyresgäster.
v2.4.0
=====================================================================

En gemensam, Qt-fri modul för de textlistor appen bygger på:

    Anställda.txt      – semesterlista (en anställd per rad)
    Fordon.txt         – limokörning (ett fordon per rad)
    Hyresgäster.txt    – hyresfakturering (månad + kvartal, separerade
                         med en rad med streck: -------)

Modulen ersätter de tidigare separata inläsarna i plugins (som saknade
kommentarer, teckenkodningsfallback, dubblettkontroll och atomär
skrivning) med EN implementation för alla tre listorna.

Format som stöds (bakåtkompatibelt med befintliga filer):
    # Kommentar – ignoreras
    ; Kommentar – ignoreras också
    Anna Andersson          ← en post per rad
    -------                 ← valfri sektionbrytare (minst 3 streck)
    Företag AB              ← sektion 2 (t.ex. kvartalshyresgäster)

Egenskaper:
- Läser UTF-8 (med/utan BOM) och faller tillbaka på cp1252/latin-1,
  så att filer skapade i Anteckningar/Excel på Windows också fungerar.
- Normaliserar blanksteg, tar bort tomma rader och dubbletter
  (skiftlägesokänsligt) samt rapporterar vad som ändrades.
- Sparar atomärt (tmp → rename) med backup (*.bak) och UTF-8 + CRLF.
- Validerar innan sparande: tomma poster, för långa rader, dubbletter.
- Svenska sorteringsregler (å, ä, ö efter z).

Användning:
    from core.roster import RosterFile, read_names, resolve_path

    lista = RosterFile.load(resolve_path("Anställda.txt"), name="Anställda")
    lista.add("Anna Andersson")
    lista.save()

    namn = read_names("Fordon.txt")          # enkel inläsning för PDF

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import codecs
import os
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.4.0"

# ──────────────────────────────────────────────────────────
# Format
# ──────────────────────────────────────────────────────────

SEPARATOR: str = "-------"
COMMENT_PREFIXES: Tuple[str, ...] = ("#", ";")
MIN_SEPARATOR_LEN: int = 3

#: Teckenkodningar som provas i ordning vid inläsning
ENCODINGS: Tuple[str, ...] = ("utf-8", "cp1252", "latin-1")

#: Standardteckenkodning när filen sparas
SAVE_ENCODING: str = "utf-8"
SAVE_NEWLINE: str = "\r\n"

#: Längsta tillåtna post (antal tecken)
MAX_ENTRY_LENGTH: int = 80

#: Längre än så här blir trångt i PDF-tabellerna (varning, inte fel)
WARN_ENTRY_LENGTH: int = 40

LEVEL_ERROR: str = "error"
LEVEL_WARNING: str = "warning"

#: Svenska sorteringsregler: å, ä, ö sorteras efter z
_SWEDISH_ORDER = str.maketrans({"å": "{", "ä": "|", "ö": "}"})


# ══════════════════════════════════════════════════════════
# FEL
# ══════════════════════════════════════════════════════════

class RosterError(Exception):
    """Fel vid läsning, redigering eller skrivning av en lista."""


# ══════════════════════════════════════════════════════════
# HJÄLPFUNKTIONER
# ══════════════════════════════════════════════════════════

def app_root() -> Path:
    """Appens rotmapp (där main.pyw och txt-filerna ligger)."""
    return Path(__file__).resolve().parent.parent


def resolve_path(path: Union[str, Path], base: Optional[Path] = None) -> Path:
    """
    Gör om ett filnamn till en absolut sökväg.

    Relativa namn (t.ex. "Anställda.txt") tolkas mot appens rotmapp,
    inte mot aktuell arbetskatalog – det gör att PDF-generering fungerar
    även om programmet startats från en genväg med annan arbetskatalog.
    """
    candidate = Path(os.path.expanduser(str(path)))
    if candidate.is_absolute():
        return candidate
    return (Path(base) if base is not None else app_root()) / candidate


def normalize_entry(value: Any) -> str:
    """
    Normalisera en post: trimma, slå ihop blanksteg och ta bort
    osynliga styrtecken (t.ex. från kopiering av webbtext).
    """
    text = str(value if value is not None else "")
    text = text.replace("\u00a0", " ")                 # hårt mellanslag
    text = "".join(
        " " if unicodedata.category(char) == "Cc" else char
        for char in text
    )
    return " ".join(text.split())


def sort_key(value: str) -> str:
    """Sorteringsnyckel med svenska regler (å, ä, ö efter z)."""
    return normalize_entry(value).casefold().translate(_SWEDISH_ORDER)


def is_separator(line: str) -> bool:
    """True om raden är en sektionsbrytare (minst tre streck)."""
    stripped = line.strip()
    return (
        len(stripped) >= MIN_SEPARATOR_LEN
        and set(stripped) == {"-"}
    )


def is_comment(line: str) -> bool:
    """True om raden är en kommentar (# eller ;)."""
    stripped = line.strip()
    return stripped.startswith(COMMENT_PREFIXES)


def decode_bytes(raw: bytes) -> Tuple[str, str]:
    """
    Avkoda filinnehåll med fallback mellan vanliga teckenkodningar.

    Returns:
        (text, använd_teckenkodning)
    """
    has_bom = raw.startswith(codecs.BOM_UTF8)

    for encoding in ENCODINGS:
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        text = text.lstrip("\ufeff")      # ta bort eventuell BOM
        return text, ("utf-8-sig" if encoding == "utf-8" and has_bom else encoding)

    return raw.decode("latin-1", errors="replace").lstrip("\ufeff"), "latin-1"


@dataclass
class RosterIssue:
    """Ett problem som hittats i en lista."""

    level: str
    message: str
    section: int = 0
    entry: str = ""

    @property
    def is_error(self) -> bool:
        """True om problemet hindrar sparning."""
        return self.level == LEVEL_ERROR

    @property
    def is_warning(self) -> bool:
        """True om problemet bara är en varning."""
        return self.level == LEVEL_WARNING

    def __str__(self) -> str:  # pragma: no cover – endast presentation
        return self.message


# ══════════════════════════════════════════════════════════
# LISTAN
# ══════════════════════════════════════════════════════════

@dataclass
class RosterFile:
    """
    En textlista med en eller flera sektioner (t.ex. hyresgäster).

    Sektion 0 är huvudlistan (anställda/fordon/månadshyresgäster).
    Sektion 1+ används av Hyresgäster.txt för kvartalshyresgäster.
    """

    path: Path
    name: str = ""
    sections: List[List[str]] = field(default_factory=lambda: [[]])
    comments: List[str] = field(default_factory=list)
    encoding: str = SAVE_ENCODING
    exists: bool = False
    load_issues: List[RosterIssue] = field(default_factory=list)

    # ──────────────────────────────────────────────────────
    # Inläsning
    # ──────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        path: Union[str, Path],
        name: str = "",
        base: Optional[Path] = None,
        create: bool = False,
        default_sections: Optional[Sequence[Sequence[str]]] = None,
    ) -> "RosterFile":
        """
        Läs en lista från disk.

        Args:
            path:             Sökväg (relativ tolkas mot appens rotmapp).
            name:             Visningsnamn, t.ex. "Anställda".
            base:             Basmapp för relativa sökvägar.
            create:           Skapa filen (med default_sections) om den saknas.
            default_sections: Innehåll till en nyskapad fil.

        Raises:
            RosterError: om filen finns men inte kan läsas.
        """
        roster = cls(path=resolve_path(path, base), name=name or Path(path).stem)

        if not roster.path.exists():
            if default_sections:
                roster.sections = [list(section) for section in default_sections]
            if create:
                roster.save(backup=False)
            return roster

        try:
            raw = roster.path.read_bytes()
        except OSError as exc:
            raise RosterError(f"Kunde inte läsa {roster.path.name}: {exc}") from exc

        text, roster.encoding = decode_bytes(raw)
        roster.encoding = "utf-8" if roster.encoding == "utf-8-sig" else roster.encoding
        roster.exists = True
        roster._parse(text)
        return roster

    def _parse(self, text: str) -> None:
        """Tolka filinnehåll till sektioner."""
        self.sections = [[]]
        self.comments = []
        self.load_issues = []

        seen: Dict[str, int] = {}

        raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        for raw_line in raw_lines:
            line = raw_line.strip()
            if not line:
                continue

            if is_separator(line):
                self.sections.append([])
                continue

            if is_comment(line):
                self.comments.append(line)
                continue

            entry = normalize_entry(line)
            if not entry:
                continue

            key = entry.casefold()
            if key in seen:
                self.load_issues.append(RosterIssue(
                    level=LEVEL_WARNING,
                    message=f"Dubbletten '{entry}' togs bort (fanns redan)",
                    section=len(self.sections) - 1,
                    entry=entry,
                ))
                continue

            seen[key] = len(self.sections) - 1
            self.sections[-1].append(entry)

        if self.encoding not in ("utf-8", "utf-8-sig"):
            self.load_issues.append(RosterIssue(
                level=LEVEL_WARNING,
                message=(
                    f"Filen lästes som {self.encoding}. "
                    "Den sparas som UTF-8 nästa gång."
                ),
            ))

    def reload(self) -> "RosterFile":
        """Läs om filen från disk (behåller namn och sökväg)."""
        fresh = type(self).load(self.path, self.name)
        self.sections = fresh.sections
        self.comments = fresh.comments
        self.encoding = fresh.encoding
        self.exists = fresh.exists
        self.load_issues = fresh.load_issues
        return self

    # ──────────────────────────────────────────────────────
    # Egenskaper
    # ──────────────────────────────────────────────────────

    @property
    def entries(self) -> List[str]:
        """Huvudlistan (sektion 0)."""
        return self.sections[0]

    @property
    def section_count(self) -> int:
        """Antal sektioner (minst 1)."""
        return len(self.sections)

    def section(self, index: int = 0) -> List[str]:
        """Returnera en sektion (tom lista om index saknas)."""
        if 0 <= index < len(self.sections):
            return self.sections[index]
        return []

    def entry_count(self) -> int:
        """Totalt antal poster i alla sektioner."""
        return sum(len(section) for section in self.sections)

    def is_empty(self) -> bool:
        """True om alla sektioner är tomma."""
        return self.entry_count() == 0

    def all_entries(self) -> List[str]:
        """Alla poster i alla sektioner (i ordning)."""
        return [entry for section in self.sections for entry in section]

    def duplicates(self, index: Optional[int] = None) -> List[str]:
        """Poster som förekommer fler än en gång (skiftlägesokänsligt)."""
        sections = (
            [self.section(index)] if index is not None else self.sections
        )
        seen: set = set()
        found: List[str] = []
        for section in sections:
            for entry in section:
                key = entry.casefold()
                if key in seen and entry not in found:
                    found.append(entry)
                seen.add(key)
        return found

    # ──────────────────────────────────────────────────────
    # Redigering
    # ──────────────────────────────────────────────────────

    def set_entries(self, entries: Iterable[str], index: int = 0) -> None:
        """Ersätt innehållet i en sektion (normaliserat, utan tomma rader)."""
        while len(self.sections) <= index:
            self.sections.append([])
        self.sections[index] = [
            entry for entry in (normalize_entry(value) for value in entries) if entry
        ]

    def add(
        self,
        value: str,
        index: int = 0,
        position: Optional[int] = None,
    ) -> str:
        """
        Lägg till en post.

        Returns:
            Den normaliserade posten.

        Raises:
            RosterError: om posten är tom, för lång eller redan finns.
        """
        entry = normalize_entry(value)
        if not entry:
            raise RosterError("Posten får inte vara tom.")
        if len(entry) > MAX_ENTRY_LENGTH:
            raise RosterError(
                f"Posten är för lång ({len(entry)} tecken, max {MAX_ENTRY_LENGTH})."
            )

        section = self.section(index)
        if any(existing.casefold() == entry.casefold() for existing in section):
            raise RosterError(f"'{entry}' finns redan i listan.")

        if position is None or position < 0 or position > len(section):
            section.append(entry)
        else:
            section.insert(position, entry)
        return entry

    def rename(self, position: int, value: str, index: int = 0) -> str:
        """
        Byt namn på en post.

        Raises:
            RosterError: vid ogiltigt index eller dubblett.
        """
        section = self.section(index)
        if not 0 <= position < len(section):
            raise RosterError("Posten finns inte i listan.")

        entry = normalize_entry(value)
        if not entry:
            raise RosterError("Namnet får inte vara tomt.")
        if len(entry) > MAX_ENTRY_LENGTH:
            raise RosterError(
                f"Namnet är för långt ({len(entry)} tecken, max {MAX_ENTRY_LENGTH})."
            )
        if any(
            other.casefold() == entry.casefold() and offset != position
            for offset, other in enumerate(section)
        ):
            raise RosterError(f"'{entry}' finns redan i listan.")

        section[position] = entry
        return entry

    def remove(self, position: int, index: int = 0) -> str:
        """
        Ta bort en post.

        Raises:
            RosterError: vid ogiltigt index.
        """
        section = self.section(index)
        if not 0 <= position < len(section):
            raise RosterError("Posten finns inte i listan.")
        return section.pop(position)

    def move(self, position: int, delta: int, index: int = 0) -> int:
        """
        Flytta en post uppåt (delta = -1) eller nedåt (delta = +1).

        Returns:
            Postens nya position.

        Raises:
            RosterError: vid ogiltigt index.
        """
        section = self.section(index)
        if not 0 <= position < len(section):
            raise RosterError("Posten finns inte i listan.")

        new_position = max(0, min(len(section) - 1, position + delta))
        if new_position != position:
            section.insert(new_position, section.pop(position))
        return new_position

    def sort(self, index: int = 0, reverse: bool = False) -> None:
        """Sortera en sektion alfabetiskt (svenska regler)."""
        if 0 <= index < len(self.sections):
            self.sections[index].sort(key=sort_key, reverse=reverse)

    def clear(self, index: int = 0) -> None:
        """Töm en sektion."""
        if 0 <= index < len(self.sections):
            self.sections[index] = []

    # ──────────────────────────────────────────────────────
    # Validering
    # ──────────────────────────────────────────────────────

    def validate(self) -> List[RosterIssue]:
        """
        Kontrollera listan inför sparning.

        Returns:
            Lista med problem. Nivån "error" hindrar sparning,
            "warning" visas men tillåts.
        """
        issues: List[RosterIssue] = []

        if self.is_empty():
            issues.append(RosterIssue(
                level=LEVEL_WARNING,
                message="Listan är tom.",
            ))

        for index, section in enumerate(self.sections):
            seen: set = set()
            for entry in section:
                if not entry:
                    issues.append(RosterIssue(
                        level=LEVEL_ERROR,
                        message="Tom post förekommer.",
                        section=index,
                    ))
                    continue

                if len(entry) > MAX_ENTRY_LENGTH:
                    issues.append(RosterIssue(
                        level=LEVEL_ERROR,
                        message=(
                            f"'{entry[:25]}…' är för lång "
                            f"({len(entry)} tecken, max {MAX_ENTRY_LENGTH})."
                        ),
                        section=index,
                        entry=entry,
                    ))

                if WARN_ENTRY_LENGTH < len(entry) <= MAX_ENTRY_LENGTH:
                    issues.append(RosterIssue(
                        level=LEVEL_WARNING,
                        message=(
                            f"'{entry[:30]}…' är lång ({len(entry)} tecken) "
                            "och kan bli trång i PDF:en."
                        ),
                        section=index,
                        entry=entry,
                    ))

                key = entry.casefold()
                if key in seen:
                    issues.append(RosterIssue(
                        level=LEVEL_ERROR,
                        message=f"'{entry}' förekommer flera gånger.",
                        section=index,
                        entry=entry,
                    ))
                seen.add(key)

        return issues

    def has_errors(self) -> bool:
        """True om validate() hittar något som hindrar sparning."""
        return any(issue.is_error for issue in self.validate())

    # ──────────────────────────────────────────────────────
    # Skrivning
    # ──────────────────────────────────────────────────────

    @property
    def backup_path(self) -> Path:
        """Sökväg till säkerhetskopian (*.bak)."""
        return self.path.with_suffix(self.path.suffix + ".bak")

    def as_text(self) -> str:
        """Listans innehåll som text (kommentarer + sektioner)."""
        comments = list(self.comments)
        if not comments:
            comments = [
                f"# {self.name} – en post per rad",
                "# Rader som börjar med # eller ; ignoreras",
            ]
            if self.section_count > 1:
                comments.append(
                    f"# Sektioner separeras med en rad med streck: {SEPARATOR}"
                )

        lines: List[str] = list(comments)
        for number, section in enumerate(self.sections):
            if number > 0:
                lines.append("")
                lines.append(SEPARATOR)
            for entry in section:
                lines.append(entry)

        text = SAVE_NEWLINE.join(lines)
        return text + SAVE_NEWLINE

    def save(self, backup: bool = True) -> Path:
        """
        Spara listan atomärt.

        Skapar en säkerhetskopia (*.bak) av föregående version och skriver
        UTF-8 (utan BOM) med CRLF – samma format som Anteckningar på Windows.

        Raises:
            RosterError: om valideringen hittar fel eller filen inte kan skrivas.
        """
        issues = self.validate()
        errors = [issue for issue in issues if issue.is_error]
        if errors:
            raise RosterError("\n".join(issue.message for issue in errors))

        self.path.parent.mkdir(parents=True, exist_ok=True)

        if backup and self.path.exists():
            try:
                shutil.copy2(self.path, self.backup_path)
            except OSError:
                pass  # backup är "nice to have" – hindrar inte sparningen

        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            tmp_path.write_bytes(self.as_text().encode(SAVE_ENCODING))
            tmp_path.replace(self.path)
        except OSError as exc:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise RosterError(f"Kunde inte spara {self.path.name}: {exc}") from exc

        self.exists = True
        self.encoding = SAVE_ENCODING
        return self.path

    def __repr__(self) -> str:  # pragma: no cover – endast felsökning
        return (
            f"RosterFile({self.path.name!r}, sections={self.entry_count()} poster)"
        )


# ══════════════════════════════════════════════════════════
# GENVÄGAR FÖR PLUGINS
# ══════════════════════════════════════════════════════════

def read_names(path: Union[str, Path], base: Optional[Path] = None) -> List[str]:
    """
    Läs en namnlista (huvudsektionen) från en txt-fil.

    Används av PDF-generatorn i Semesterlista & Limokörning.

    Raises:
        RosterError: om filen inte kan läsas.
    """
    return RosterFile.load(path, base=base).entries


def ensure_file(
    path: Union[str, Path],
    name: str = "",
    default_sections: Optional[Sequence[Sequence[str]]] = None,
    base: Optional[Path] = None,
) -> RosterFile:
    """
    Öppna en lista och skapa filen om den saknas.

    Args:
        path:             Sökväg till txt-filen.
        name:             Visningsnamn (används i filens rubrik).
        default_sections: Innehåll till en ny fil.
        base:             Basmapp för relativa sökvägar.
    """
    return RosterFile.load(
        path,
        name=name,
        base=base,
        create=True,
        default_sections=default_sections,
    )


def open_in_editor(path: Union[str, Path]) -> bool:
    """
    Öppna filen i operativsystemets standardredigerare.

    Returns:
        True om kommandot kunde startas.
    """
    import platform
    import subprocess

    target = str(resolve_path(path))
    try:
        if platform.system() == "Windows":
            os.startfile(target)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.run(["open", target], check=False)
        else:
            subprocess.run(["xdg-open", target], check=False)
        return True
    except OSError:
        return False
