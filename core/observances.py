"""Common US observances for display only; never used as non-working days.

Not an exhaustive state, religious or name-day calendar. Christian dates
use the Western/Gregorian Easter calculation. Federal dates stay in holidays.py.
"""
from datetime import date, timedelta
from core.holidays import get_easter, nth_weekday_of_month


def get_us_observances(year):
    result = {}

    def add(day, key):
        result.setdefault(day, []).append(f"us.{key}")

    for month, day, key in (
        (2, 1, "national_freedom"), (2, 2, "groundhog"), (2, 14, "valentines"),
        (3, 17, "st_patricks"), (4, 1, "april_fools"), (4, 22, "earth_day"),
        (5, 5, "cinco_de_mayo"), (6, 14, "flag_day"), (9, 11, "patriot_day"),
        (9, 17, "constitution_day"), (10, 31, "halloween"), (12, 7, "pearl_harbor"),
        (12, 24, "christmas_eve"), (12, 31, "new_years_eve"),
    ):
        add(date(year, month, day), key)
    for month, weekday, occurrence, key in (
        (5, 6, 2, "mothers_day"), (5, 5, 3, "armed_forces_day"),
        (6, 6, 3, "fathers_day"), (7, 6, 4, "parents_day"),
        (10, 0, 2, "indigenous_peoples_day"),
    ):
        add(nth_weekday_of_month(year, month, weekday, occurrence), key)
    add(nth_weekday_of_month(year, 9, 0, 1) + timedelta(days=6), "grandparents_day")
    thanksgiving = nth_weekday_of_month(year, 11, 3, 4)
    for offset, key in ((1, "black_friday"), (2, "small_business_saturday"),
                        (4, "cyber_monday"), (5, "giving_tuesday")):
        add(thanksgiving + timedelta(days=offset), key)
    # Regular federal general elections occur in even-numbered years.
    if year % 2 == 0:
        add(nth_weekday_of_month(year, 11, 0, 1) + timedelta(days=1), "election_day")
    easter = get_easter(year)
    for offset, key in ((-47, "mardi_gras"), (-46, "ash_wednesday"),
                        (-7, "palm_sunday"), (-2, "good_friday"),
                        (0, "easter_sunday"), (1, "easter_monday"),
                        (39, "ascension"), (49, "pentecost")):
        add(easter + timedelta(days=offset), key)
    return {day: tuple(keys) for day, keys in result.items()}
