"""US observances must never expand the official non-working-day set."""
from datetime import date
import unittest
from core.calendar_data import year_days, calendar_background
from core.holidays import get_holidays
from core.leave import LeaveRange, vacation_workdays
from core.observances import get_us_observances, get_swedish_observances


class ObservanceTests(unittest.TestCase):
    def test_requested_dates_2027(self):
        days = get_us_observances(2027)
        for month, day, key in ((2, 14, 'valentines'), (3, 17, 'st_patricks'),
                                (3, 28, 'easter_sunday'), (5, 9, 'mothers_day'),
                                (6, 20, 'fathers_day'), (10, 31, 'halloween')):
            self.assertIn('us.' + key, days[date(2027, month, day)])

    def test_collisions_keep_both_names(self):
        self.assertEqual(set(get_us_observances(2024)[date(2024, 2, 14)]),
                         {'us.valentines', 'us.ash_wednesday'})
        christmas_eve = year_days(2027, 'us')[date(2027, 12, 24)]
        self.assertEqual(christmas_eve.holiday_key, 'us.christmas')
        self.assertEqual(christmas_eve.observance_keys, ('us.christmas_eve',))
        self.assertTrue(christmas_eve.observed)

    def test_actual_and_observed_across_year_boundary(self):
        days = year_days(2027, 'us')
        self.assertEqual(days[date(2027, 12, 25)].actual_holiday_key, 'us.christmas')
        self.assertFalse(days[date(2027, 12, 25)].observed)
        self.assertTrue(days[date(2027, 12, 31)].observed)
        self.assertEqual(days[date(2027, 12, 31)].observance_keys, ('us.new_years_eve',))
        self.assertEqual(year_days(2028, 'us')[date(2028, 1, 1)].actual_holiday_key, 'us.new_year')

    def test_non_federal_days_remain_workdays(self):
        for day in (date(2027, 3, 17), date(2027, 3, 26), date(2027, 11, 26)):
            info = year_days(day.year, 'us')[day]
            self.assertTrue(info.observance_keys)
            self.assertEqual(info.kind, 'weekday')
            self.assertNotIn(day, get_holidays(day.year, 'us'))
            self.assertEqual(vacation_workdays([LeaveRange(day, day)], day.year, 'us'), 1)

    def test_official_classification_unchanged_for_full_years(self):
        for year in range(2020, 2036):
            days = year_days(year, 'us')
            self.assertEqual({d for d, info in days.items() if info.kind == 'holiday'},
                             get_holidays(year, 'us'))
            self.assertTrue(all(d.year == year for d in get_us_observances(year)))

    def test_floating_dates_and_election_rule(self):
        days = get_us_observances(2026)
        for month, day, key in ((9, 13, 'grandparents_day'), (11, 3, 'election_day'),
                                (11, 27, 'black_friday'), (11, 30, 'cyber_monday'),
                                (12, 1, 'giving_tuesday')):
            self.assertIn('us.' + key, days[date(2026, month, day)])
        self.assertFalse(any('us.election_day' in names for names in get_us_observances(2027).values()))

    def test_us_observances_do_not_leak_into_sweden(self):
        self.assertTrue(all(all(key.startswith("sv.") for key in info.observance_keys) and not info.actual_holiday_key
                            and not info.observed for info in year_days(2027, 'sv').values()))


class SwedishObservanceTests(unittest.TestCase):
    def test_swedish_dates_2027(self):
        days = get_swedish_observances(2027)
        for month, day, key in ((2, 9, 'shrove_tuesday'), (3, 25, 'waffle_day'),
                                (5, 30, 'mothers_day'), (11, 14, 'fathers_day'),
                                (10, 4, 'cinnamon_bun_day'), (12, 13, 'lucia'),
                                (11, 28, 'advent_1'), (12, 19, 'advent_4')):
            self.assertIn('sv.' + key, days[date(2027, month, day)])

    def test_only_public_holidays_are_red(self):
        for year in range(2020, 2036):
            official = get_holidays(year, 'sv')
            for day, info in year_days(year, 'sv').items():
                self.assertEqual(calendar_background(info) == '#FFE1E1',
                                 day in official or day.weekday() == 6)
                self.assertEqual(info.kind == 'holiday', day in official)

    def test_weekday_observances_are_not_red_and_count_as_workdays(self):
        for day in (date(2027, 2, 9), date(2027, 10, 4), date(2027, 12, 13), date(2027, 12, 24)):
            self.assertNotEqual(calendar_background(year_days(2027, 'sv')[day]), '#FFE1E1')
            self.assertEqual(vacation_workdays([LeaveRange(day, day)], day.year, 'sv'), 1)

    def test_sunday_observance_does_not_change_holiday_reason(self):
        day = year_days(2027, 'sv')[date(2027, 5, 30)]
        self.assertEqual(day.observance_keys, ('sv.mothers_day',))
        self.assertEqual(day.kind, 'sunday')
        self.assertEqual(calendar_background(day), '#FFE1E1')

    def test_us_sundays_are_not_federal_holidays(self):
        days = year_days(2027, 'us')
        self.assertIsNone(calendar_background(days[date(2027, 10, 31)]))
        self.assertEqual(calendar_background(days[date(2027, 12, 24)]), '#FFE1E1')
        self.assertEqual(calendar_background(days[date(2027, 12, 25)]), '#FFE1E1')

    def test_advent_sundays_stay_before_christmas(self):
        for year in range(2020, 2036):
            dates = [day for day, names in get_swedish_observances(year).items()
                     if any(key.startswith('sv.advent_') for key in names)]
            self.assertEqual(len(dates), 4)
            self.assertTrue(all(day.weekday() == 6 and day < date(year, 12, 25) for day in dates))
            self.assertEqual((max(dates) - min(dates)).days, 21)
