"""Semesterlista: list_io (v2.12.0)."""

from __future__ import annotations
from typing import List
from PySide6.QtWidgets import QMessageBox
from core import i18n
from core.roster import RosterError
from core.roster import read_entries
from core.roster import resolve_path
from core.leave import LeaveCalendar
from .common import logger

class ListReader:
    def _read_list_from_file(self, file_path: str) -> List[str]:
        """
        Läs lista med namn/fordon från txt-fil (via core.roster).

        Kommentarer (# eller ;), tomma rader, dubbletter och blandade
        teckenkodningar hanteras automatiskt av core/roster.py.

        v2.11.0: även lediga dagar läses. De skrivs efter namnet i listan
        (``Anna Andersson ; 18/12 - 7/1``) och sparas i
        ``self._leave_calendar`` så att PDF:en kan markera dem.
        """
        self._leave_calendar = LeaveCalendar()
        try:
            entries = read_entries(resolve_path(file_path))
        except RosterError as exc:
            logger.error(f"Fel vid läsning av fil: {exc}")
            QMessageBox.critical(
                None,
                i18n.t("roster.error.title"),
                i18n.t("lista.error.read", error=exc),
            )
            return []

        for name, leave_text in entries:
            if leave_text:
                self._leave_calendar.add_line(f"{name} ; {leave_text}")

        if self._leave_calendar.errors:
            logger.warning(f"Frånvaro som inte kunde tolkas: {self._leave_calendar.errors}")

        logger.info(
            f"Läste {len(entries)} poster, "
            f"{len(self._leave_calendar)} med lediga dagar"
        )
        return [name for name, _ in entries]

