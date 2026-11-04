"""Regression tests for Swedish and US calendars."""
import unittest
from datetime import date
from core import holidays as h


class HolidayTests(unittest.TestCase):
    def test_easter_known_dates(self):
        for year, month, day in [(2024, 3, 31), (2025, 4, 20), (2026, 4, 5), (2000, 4, 23)]:
            self.assertEqual(h.get_easter(year), date(year, month, day))

    def test_swedish_easter(self):
        days = h.get_holidays(2026, "sv")
        for day in [3, 5, 6]:
            self.assertIn(date(2026, 4, day), days)
        self.assertNotIn(date(2026, 4, 2), days)
        self.assertIn(date(2026, 4, 2), h.get_half_days(2026, "sv"))

    def test_midsummer(self):
        self.assertIn(date(2026, 6, 20), h.get_holidays(2026, "sv"))
        self.assertNotIn(date(2026, 6, 19), h.get_holidays(2026, "sv"))
        self.assertIn(date(2026, 6, 19), h.get_half_days(2026, "sv"))

    def test_swedish_half_days(self):
        days = h.get_half_days(2026, "sv")
        for month, day in [(4, 30), (10, 30), (12, 24), (12, 31)]:
            self.assertIn(date(2026, month, day), days)

    def test_us_weekday_holidays(self):
        days = h.get_holidays(2026, "us")
        for month, day in [(1, 19), (2, 16), (5, 25), (6, 19), (9, 7), (10, 12), (11, 11), (11, 26)]:
            self.assertIn(date(2026, month, day), days)
        self.assertEqual(h.get_half_days(2026, "us"), set())

    def test_us_saturday_observed_friday(self):
        days = h.get_holidays(2026, "us")
        self.assertIn(date(2026, 7, 3), days)
        self.assertNotIn(date(2026, 7, 4), days)
        self.assertIn(date(2026, 7, 4), h.get_us_holidays(2026, include_actual=True))

    def test_us_sunday_observed_monday(self):
        self.assertIn(date(2027, 7, 5), h.get_holidays(2027, "us"))

    def test_observed_new_year_crosses_year(self):
        self.assertIn(date(2021, 12, 31), h.get_holidays(2021, "us"))
        self.assertNotIn(date(2021, 12, 31), h.get_holidays(2022, "us"))
        self.assertNotIn(date(2022, 1, 1), h.get_holidays(2022, "us"))

    def test_region_fallback(self):
        self.assertEqual(h.get_holidays(2026, "invalid"), h.get_holidays(2026, "sv"))
        self.assertEqual(h.get_region_from_settings(None), "sv")
        self.assertEqual(h.get_region_from_settings({"holiday_region": "us"}), "us")

    def test_dates_and_names_stay_in_requested_year(self):
        for year in range(2020, 2041):
            for region in ["sv", "us"]:
                days = h.get_holidays(year, region)
                self.assertTrue(all(day.year == year for day in days))
                self.assertEqual(days | h.get_half_days(year, region), set(h.get_holiday_names(year, region)))
