#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester för core/leave.py – lediga dagar i listfilen (v2.11.0).

Kontrollerar att datum snäpps till närmaste måndag, att frånvaro skrivs som
``Anna Andersson ; 18/12 - 7/1``, att flera perioder och olika datumformat
fungerar samt att PDF-generatorn kan slå upp lediga dagar per person.

    python -m unittest discover -s tests -v
    python tests/test_leave.py
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.leave import (  # noqa: E402
    LeaveCalendar,
    LeaveError,
    LeaveRange,
    format_leave,
    looks_like_leave,
    parse_leave,
    snap_to_monday,
    split_entry,
)


class SnapToMondayTests(unittest.TestCase):
    """Närmaste måndag – må–to bakåt, fre–sö framåt."""

    def test_monday_stays(self) -> None:
        self.assertEqual(snap_to_monday(date(2026, 12, 21)), date(2026, 12, 21))

    def test_tuesday_goes_back(self) -> None:
        self.assertEqual(snap_to_monday(date(2026, 12, 22)), date(2026, 12, 21))

    def test_thursday_goes_back(self) -> None:
        # torsdag 17/12 ligger 3 dagar efter måndagen
        self.assertEqual(snap_to_monday(date(2026, 12, 17)), date(2026, 12, 14))

    def test_friday_goes_forward(self) -> None:
        # fredag 18/12 2026 ligger 3 dagar före nästa måndag
        self.assertEqual(snap_to_monday(date(2026, 12, 18)), date(2026, 12, 21))

    def test_sunday_goes_forward(self) -> None:
        self.assertEqual(snap_to_monday(date(2026, 12, 20)), date(2026, 12, 21))

    def test_result_is_always_monday(self) -> None:
        day = date(2026, 1, 1)
        while day.year == 2026:
            self.assertEqual(snap_to_monday(day).weekday(), 0, day)
            day += timedelta(days=1)


class ParseLeaveTests(unittest.TestCase):
    """Tolkning av frånvarosträngar."""

    def test_user_example_crosses_new_year(self) -> None:
        ranges = parse_leave("18/12 - 7/1", 2026)
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0].start, date(2026, 12, 21))   # fredag → måndag
        self.assertEqual(ranges[0].end, date(2027, 1, 4))       # torsdag → måndag
        self.assertEqual(str(ranges[0]), "2026-12-21 – 2027-01-04")

    def test_end_before_start_means_next_year(self) -> None:
        start, end = parse_leave("18/12-7/1", 2026)[0].start, parse_leave("18/12-7/1", 2026)[0].end
        self.assertEqual(start.year, 2026)
        self.assertEqual(end.year, 2027)

    def test_default_year_is_current_year(self) -> None:
        ranges = parse_leave("18/12-7/1")
        self.assertEqual(ranges[0].start.year, date.today().year)

    def test_explicit_years_are_respected(self) -> None:
        # 18/12 2028 är en måndag, 8/1 2029 en måndag → oförändrat
        ranges = parse_leave("18/12/2028 - 8/1/2029", 2026)
        self.assertEqual(ranges[0].start, date(2028, 12, 18))
        self.assertEqual(ranges[0].end, date(2029, 1, 8))

    def test_iso_format(self) -> None:
        # fredag 18/12 → måndag 21/12, torsdag 7/1 → måndag 4/1
        ranges = parse_leave("2026-12-18 - 2027-01-07", 2026)
        self.assertEqual(ranges[0].start, date(2026, 12, 21))
        self.assertEqual(ranges[0].end, date(2027, 1, 4))

    def test_iso_format_without_snap(self) -> None:
        ranges = parse_leave("2026-12-18 - 2027-01-07", 2026, snap=False)
        self.assertEqual(ranges[0].start, date(2026, 12, 18))
        self.assertEqual(ranges[0].end, date(2027, 1, 7))

    def test_several_periods_with_comma(self) -> None:
        ranges = parse_leave("18/12-7/1, 6/7-20/7", 2026)
        self.assertEqual(len(ranges), 2)
        self.assertEqual((ranges[1].start.month, ranges[1].start.day), (7, 6))

    def test_several_periods_with_och(self) -> None:
        ranges = parse_leave("6/7-20/7 och 3/8-17/8", 2026)
        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[1].start, date(2026, 8, 3))

    def test_semicolon_separates_periods(self) -> None:
        ranges = parse_leave("6/7-20/7 ; 3/8-17/8", 2026)
        self.assertEqual(len(ranges), 2)

    def test_single_date_marks_that_day_only(self) -> None:
        ranges = parse_leave("18/12", 2026)
        self.assertEqual(ranges[0].start, date(2026, 12, 18))
        self.assertEqual(ranges[0].end, date(2026, 12, 18))
        self.assertEqual(ranges[0].days(), 1)

    def test_snap_can_be_disabled(self) -> None:
        ranges = parse_leave("18/12-7/1", 2026, snap=False)
        self.assertEqual(ranges[0].start, date(2026, 12, 18))
        self.assertEqual(ranges[0].end, date(2027, 1, 7))

    def test_empty_text(self) -> None:
        self.assertEqual(parse_leave("", 2026), [])
        self.assertEqual(parse_leave(None, 2026), [])

    def test_invalid_month_raises(self) -> None:
        with self.assertRaises(LeaveError):
            parse_leave("18/13-7/1", 2026)

    def test_garbage_raises(self) -> None:
        with self.assertRaises(LeaveError):
            parse_leave("semester", 2026)


class LeaveRangeTests(unittest.TestCase):
    """Periodens egenskaper."""

    def test_contains_inclusive(self) -> None:
        r = LeaveRange(date(2026, 12, 21), date(2027, 1, 4))
        self.assertTrue(r.contains(date(2026, 12, 21)))
        self.assertTrue(r.contains(date(2027, 1, 4)))
        self.assertFalse(r.contains(date(2026, 12, 20)))
        self.assertFalse(r.contains(date(2027, 1, 5)))

    def test_days(self) -> None:
        r = LeaveRange(date(2026, 12, 21), date(2027, 1, 4))
        self.assertEqual(r.days(), 15)

    def test_overlaps_month(self) -> None:
        r = LeaveRange(date(2026, 12, 21), date(2027, 1, 4))
        self.assertTrue(r.overlaps_month(2026, 12))
        self.assertTrue(r.overlaps_month(2027, 1))
        self.assertFalse(r.overlaps_month(2026, 11))

    def test_start_after_end_is_rejected(self) -> None:
        with self.assertRaises(LeaveError):
            LeaveRange(date(2027, 1, 4), date(2026, 12, 21))


class SplitEntryTests(unittest.TestCase):
    """Listfilens rad → (namn, frånvaro)."""

    def test_semicolon(self) -> None:
        self.assertEqual(
            split_entry("Anna Andersson ; 18/12 - 7/1"),
            ("Anna Andersson", "18/12 - 7/1"),
        )

    def test_pipe(self) -> None:
        self.assertEqual(
            split_entry("Anna Andersson | 18/12 - 7/1"),
            ("Anna Andersson", "18/12 - 7/1"),
        )

    def test_colon(self) -> None:
        """Vanligaste skrivsättet i befintliga listor: "Roland: 18/12-7/1"."""
        self.assertEqual(split_entry("Roland: 18/12-7/1"), ("Roland", "18/12-7/1"))

    def test_colon_with_space(self) -> None:
        self.assertEqual(
            split_entry("Roland : 18/12 - 7/1"),
            ("Roland", "18/12 - 7/1"),
        )

    def test_colon_without_date_is_kept(self) -> None:
        """Utan datum efter avskiljaren är hela raden namnet."""
        self.assertEqual(split_entry("Volvo: ABC 123"), ("Volvo: ABC 123", ""))
        self.assertEqual(
            split_entry("Avdelning: Ekonomi"), ("Avdelning: Ekonomi", "")
        )

    def test_name_only(self) -> None:
        self.assertEqual(split_entry("Anna Andersson"), ("Anna Andersson", ""))

    def test_extra_whitespace(self) -> None:
        self.assertEqual(
            split_entry("  Anna Andersson;18/12  "),
            ("Anna Andersson", "18/12"),
        )


class LooksLikeLeaveTests(unittest.TestCase):
    """Säkerhetsregeln som avgör om raden ska delas."""

    def test_dates_are_recognised(self) -> None:
        for text in ("18/12", "18/12 - 7/1", "2026-12-18", "6/7-20/7 och 3/8-17/8"):
            self.assertTrue(looks_like_leave(text), text)

    def test_non_dates_are_rejected(self) -> None:
        for text in ("", "ABC 123", "Ekonomi", "Roland"):
            self.assertFalse(looks_like_leave(text), text)


class LeaveCalendarTests(unittest.TestCase):
    """Uppslagning av lediga dagar."""

    def setUp(self) -> None:
        self.calendar = LeaveCalendar.from_lines(
            [
                "Anna Andersson ; 18/12 - 7/1",
                "Bertil Berg",
                "Cecilia Carlsson | 6/7 - 20/7",
                "David Dahl ; inte ett datum",
            ],
            default_year=2026,
        )

    def test_len_counts_people_with_leave(self) -> None:
        self.assertEqual(len(self.calendar), 2)

    def test_is_off_inside_range(self) -> None:
        self.assertTrue(self.calendar.is_off("Anna Andersson", date(2026, 12, 24)))
        self.assertTrue(self.calendar.is_off("Anna Andersson", date(2027, 1, 1)))

    def test_is_off_outside_range(self) -> None:
        self.assertFalse(self.calendar.is_off("Anna Andersson", date(2026, 12, 18)))
        self.assertFalse(self.calendar.is_off("Anna Andersson", date(2027, 1, 12)))

    def test_person_without_leave(self) -> None:
        self.assertFalse(self.calendar.is_off("Bertil Berg", date(2026, 12, 24)))

    def test_unknown_person_is_not_off(self) -> None:
        self.assertFalse(self.calendar.is_off("Nils Nilsson", date(2026, 12, 24)))

    def test_case_and_whitespace_insensitive(self) -> None:
        self.assertTrue(self.calendar.is_off("anna   andersson", date(2026, 12, 24)))
        self.assertTrue(self.calendar.is_off("ANNA ANDERSSON", date(2026, 12, 24)))

    def test_ranges_for(self) -> None:
        ranges = self.calendar.ranges_for("Cecilia Carlsson")
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0].start, date(2026, 7, 6))

    def test_off_dates(self) -> None:
        days = self.calendar.off_dates(
            "Cecilia Carlsson", date(2026, 7, 1), date(2026, 7, 31)
        )
        self.assertEqual(len(days), 15)
        self.assertEqual(days[0], date(2026, 7, 6))
        self.assertEqual(days[-1], date(2026, 7, 20))

    def test_colon_line_is_registered(self) -> None:
        calendar = LeaveCalendar.from_lines(["Roland: 18/12-7/1"], default_year=2026)
        self.assertEqual(len(calendar), 1)
        self.assertTrue(calendar.is_off("Roland", date(2026, 12, 24)))
        self.assertFalse(calendar.is_off("Roland", date(2026, 12, 18)))

    def test_invalid_leave_is_reported(self) -> None:
        self.assertEqual(len(self.calendar.errors), 1)
        self.assertIn("David Dahl", self.calendar.errors[0])

    def test_names_with_leave(self) -> None:
        self.assertEqual(
            self.calendar.names_with_leave(),
            ["anna andersson", "cecilia carlsson"],
        )

    def test_add_line_after_construction(self) -> None:
        calendar = LeaveCalendar()
        calendar.add_line("Erik Eriksson ; 3/8-17/8", default_year=2026)
        self.assertTrue(calendar.is_off("Erik Eriksson", date(2026, 8, 10)))

    def test_empty_calendar_is_falsy(self) -> None:
        self.assertFalse(LeaveCalendar())
        self.assertTrue(self.calendar)


class FormatLeaveTests(unittest.TestCase):
    """Perioder tillbaka till listfilens format."""

    def test_roundtrip(self) -> None:
        ranges = parse_leave("18/12-7/1", 2026)
        self.assertEqual(format_leave(ranges), "21/12-4/1")

    def test_multiple(self) -> None:
        ranges = parse_leave("6/7-20/7, 3/8-17/8", 2026)
        self.assertEqual(format_leave(ranges), "6/7-20/7, 3/8-17/8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
