"""US observances must never expand the official non-working-day set."""
from datetime import date
import unittest
from core.calendar_data import year_days
from core.holidays import get_holidays
from core.leave import LeaveRange, vacation_workdays
from core.observances import get_us_observances


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
        self.assertTrue(all(not info.observance_keys and not info.actual_holiday_key
                            and not info.observed for info in year_days(2027, 'sv').values()))
