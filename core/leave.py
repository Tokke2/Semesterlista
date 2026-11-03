#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lediga dagar per anställd (v2.11.0)
===================================

Semesterlistan blir mycket mer användbar om man ser **när varje person är
ledig** – då syns det direkt vem som är kvar på jobbet.

I ``Anställda.txt`` skrivs frånvaron efter namnet, avskilt med ``;`` eller
``|``::

    Anna Andersson ; 18/12 - 7/1
    Bertil Berg
    Cecilia Carlsson ; 2026-12-21 - 2027-01-04
    David Dahl ; 18/12-7/1, 6/7-20/7

Datumen tolkas som **veckor**: varje datum flyttas till *närmaste måndag*
(torsdag och tidigare → måndagen före, fredag och senare → måndagen efter).
Det gör att man kan skriva ungefärliga datum som ``18/12`` och ändå få en
period som börjar och slutar på en vecka.

Stöds också:

* ``18/12/2026 - 7/1/2027`` – utskrivet år
* ``2026-12-18 - 2027-01-07`` – ISO-format
* ``18/12`` – en enskild dag (utan veckosnäppning)
* flera perioder separerade med komma eller ``och``

Användning:

    from core.leave import parse_leave, split_entry

    name, rest = split_entry("Anna Andersson ; 18/12 - 7/1")
    ranges = parse_leave(rest, default_year=2026)
    any(r.contains(date(2026, 12, 24)) for r in ranges)   # True

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

MODULE_VERSION: str = "2.11.0"

#: Tecken som skiljer namnet från frånvaron i listfilen
ENTRY_SEPARATORS: Tuple[str, ...] = (";", "|")

#: 18/12, 18/12/2026 eller 2026-12-18
DATE_PATTERN = r"(?:\d{1,2}/\d{1,2}(?:/\d{4})?|\d{4}-\d{1,2}-\d{1,2})"

RANGE_RE = re.compile(
    rf"(?P<start>{DATE_PATTERN})\s*(?:-|–|—|till|to)\s*(?P<end>{DATE_PATTERN})",
    re.IGNORECASE,
)
SINGLE_RE = re.compile(DATE_PATTERN)

#: Separerar flera perioder: ", " / " och " / ";"
PERIOD_SPLIT_RE = re.compile(r"\s*(?:,|;|\boch\b|\band\b)\s*", re.IGNORECASE)


class LeaveError(ValueError):
    """Fel i en frånvaroperiod (t.ex. okänt datum)."""


@dataclass(frozen=True, order=True)
class LeaveRange:
    """En sammanhängande ledig period (båda dagarna inräknade)."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise LeaveError(f"Slutdatum {self.end} ligger före start {self.start}")

    def contains(self, day: date) -> bool:
        """True om dagen ligger inom perioden."""
        return self.start <= day <= self.end

    def days(self) -> int:
        """Antal dagar i perioden (båda dagarna inräknade)."""
        return (self.end - self.start).days + 1

    def overlaps_month(self, year: int, month: int) -> bool:
        """True om perioden har någon dag i angiven månad."""
        first = date(year, month, 1)
        last = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
        return self.start <= last and self.end >= first

    def __str__(self) -> str:
        return f"{self.start.isoformat()} – {self.end.isoformat()}"


# ══════════════════════════════════════════════════════════
# Datumtolkning
# ══════════════════════════════════════════════════════════

def snap_to_monday(day: date) -> date:
    """
    Flytta ett datum till *närmaste måndag*.

    Måndag–torsdag → måndagen i samma vecka, fredag–söndag → måndagen
    därpå. (Torsdag ligger 3 dagar från måndagen och 4 från nästa, alltså
    närmast den föregående.)

    Exempel:
        >>> snap_to_monday(date(2026, 12, 18))   # fredag
        datetime.date(2026, 12, 21)
        >>> snap_to_monday(date(2027, 1, 4))     # måndag
        datetime.date(2027, 1, 4)
    """
    offset = day.weekday()  # 0 = måndag
    if offset <= 3:
        return day - timedelta(days=offset)
    return day + timedelta(days=7 - offset)


def _parse_date(text: str, default_year: int) -> date:
    """Tolka ``18/12``, ``18/12/2026`` eller ``2026-12-18``."""
    text = text.strip()
    try:
        if "-" in text:  # ISO
            year, month, day = (int(part) for part in text.split("-"))
            return date(year, month, day)

        parts = text.split("/")
        if len(parts) == 3:
            day, month, year = (int(part) for part in parts)
            return date(year, month, day)

        day, month = (int(part) for part in parts)
        return date(default_year, month, day)
    except ValueError as exc:
        raise LeaveError(f"Ogiltigt datum {text!r}") from exc


def _end_year(start: date, end: date, explicit: bool) -> date:
    """Om slutet ligger före starten menar man nästa år (t.ex. 18/12–7/1)."""
    if explicit:
        return end
    if end < start:
        try:
            return end.replace(year=end.year + 1)
        except ValueError:  # 29 februari
            return end.replace(year=end.year + 1, day=28)
    return end


def parse_leave(
    text: str,
    default_year: Optional[int] = None,
    snap: bool = True,
) -> List[LeaveRange]:
    """
    Tolka en frånvarosträng till perioder.

    Args:
        text:         t.ex. ``"18/12 - 7/1"``, ``"18/12-7/1, 6/7-20/7"``.
        default_year: år för datum utan år (standard: i år).
        snap:         flytta datumen till närmaste måndag (standard: True).

    Enstaka datum (``"18/12"``) markerar **bara den dagen** och snäpps inte
    till måndag – snäppningen gäller periodernas start- och slutdatum.

    Returns:
        Lista med ``LeaveRange`` i den ordning de skrevs.

    Raises:
        LeaveError: om ett datum inte går att tolka eller slutet ligger före
                    starten.

    Exempel:
        >>> [str(r) for r in parse_leave("18/12 - 7/1", 2026)]
        ['2026-12-21 – 2027-01-04']
    """
    text = (text or "").strip()
    if not text:
        return []

    year = int(default_year or date.today().year)
    ranges: List[LeaveRange] = []

    for chunk in PERIOD_SPLIT_RE.split(text):
        chunk = chunk.strip()
        if not chunk:
            continue

        match = RANGE_RE.search(chunk)
        if match:
            start = _parse_date(match.group("start"), year)
            end = _parse_date(match.group("end"), start.year)
            end_has_year = _has_year(match.group("end"))
            end = _end_year(start, end, end_has_year)
            start = snap_to_monday(start) if snap else start
            end = snap_to_monday(end) if snap else end
            ranges.append(LeaveRange(start, end))
            continue

        single = SINGLE_RE.fullmatch(chunk)
        if single:
            ranges.append(LeaveRange(_parse_date(chunk, year), _parse_date(chunk, year)))
            continue

        raise LeaveError(f"Kunde inte tolka frånvaron {chunk!r}")

    return ranges


def _has_year(text: str) -> bool:
    """True om datumsträngen innehåller ett årtal."""
    text = text.strip()
    return text.count("-") >= 2 or text.count("/") == 2


# ══════════════════════════════════════════════════════════
# Listfilen
# ══════════════════════════════════════════════════════════

def split_entry(line: str) -> Tuple[str, str]:
    """
    Dela en rad i ``(namn, frånvaro)``.

    ``"Anna Andersson ; 18/12 - 7/1"`` → ``("Anna Andersson", "18/12 - 7/1")``.
    Saknas avskiljare blir frånvaron en tom sträng.
    """
    text = (line or "").strip()
    for separator in ENTRY_SEPARATORS:
        if separator in text:
            name, _, rest = text.partition(separator)
            return name.strip(), rest.strip()
    return text, ""


def format_leave(ranges: Sequence[LeaveRange]) -> str:
    """Skriv tillbaka perioder i listfilens format (``18/12-7/1``)."""
    return ", ".join(
        f"{r.start.day}/{r.start.month}-{r.end.day}/{r.end.month}" for r in ranges
    )


class LeaveCalendar:
    """
    Uppslagning av lediga dagar per namn.

    Byggs från listfilens rader och används av PDF-generatorn::

        kalender = LeaveCalendar.from_lines(lines, default_year=2026)
        kalender.is_off("Anna Andersson", date(2026, 12, 24))   # True
    """

    def __init__(self) -> None:
        self._ranges: dict[str, List[LeaveRange]] = {}
        self._errors: List[str] = []

    @classmethod
    def from_lines(
        cls,
        lines: Iterable[str],
        default_year: Optional[int] = None,
    ) -> "LeaveCalendar":
        """Bygg kalendern från listans rader (okända perioder loggas)."""
        calendar = cls()
        for line in lines:
            calendar.add_line(str(line), default_year=default_year)
        return calendar

    def add_line(self, line: str, default_year: Optional[int] = None) -> None:
        """Läs en rad och registrera eventuell frånvaro."""
        name, rest = split_entry(line)
        if not rest:
            return
        try:
            ranges = parse_leave(rest, default_year=default_year)
        except LeaveError as exc:
            self._errors.append(f"{name}: {exc}")
            logger.warning(f"Kunde inte tolka frånvaron för {name}: {exc}")
            return
        if ranges:
            self._ranges[self._key(name)] = ranges

    @staticmethod
    def _key(name: str) -> str:
        return " ".join((name or "").split()).casefold()

    def ranges_for(self, name: str) -> List[LeaveRange]:
        """Alla perioder för en person."""
        return list(self._ranges.get(self._key(name), []))

    def is_off(self, name: str, day: date) -> bool:
        """True om personen är ledig den dagen."""
        return any(r.contains(day) for r in self._ranges.get(self._key(name), []))

    def off_dates(self, name: str, first: date, last: date) -> List[date]:
        """Alla lediga dagar mellan två datum (för tester och sammanställningar)."""
        days = []
        current = first
        while current <= last:
            if self.is_off(name, current):
                days.append(current)
            current += timedelta(days=1)
        return days

    def names_with_leave(self) -> List[str]:
        """Namn (normaliserade, gemener) som har minst en period."""
        return sorted(self._ranges)

    @property
    def errors(self) -> List[str]:
        """Rader som inte kunde tolkas (namn: orsak)."""
        return list(self._errors)

    def __len__(self) -> int:
        return len(self._ranges)


__all__ = [
    "ENTRY_SEPARATORS",
    "LeaveCalendar",
    "LeaveError",
    "LeaveRange",
    "MODULE_VERSION",
    "format_leave",
    "parse_leave",
    "snap_to_monday",
    "split_entry",
]
