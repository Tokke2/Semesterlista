"""Shared Monday-first calendar model. No employee/vacation data."""
import calendar
from dataclasses import dataclass
from datetime import date
from core.holidays import get_holidays, get_half_days, get_holiday_names


@dataclass(frozen=True)
class CalendarDay:
    date: date
    holiday_key: str
    kind: str


def year_days(year, region="sv", official=None, half=None):
    holidays = get_holidays(year, region) if official is None else official
    half_days = get_half_days(year, region) if half is None else half
    names = get_holiday_names(year, region)
    result = {}
    for month in range(1, 13):
        for number in range(1, calendar.monthrange(year, month)[1] + 1):
            day = date(year, month, number)
            kind = ("holiday" if day in holidays else "sunday" if day.weekday() == 6
                    else "halfday" if day in half_days else "saturday" if day.weekday() == 5 else "weekday")
            result[day] = CalendarDay(day, names.get(day, ""), kind)
    return result


def month_weeks(year, month, region="sv"):
    days = year_days(year, region)
    return [[days.get(day) if day.month == month else None for day in week]
            for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)]


def season(month):
    return ("winter" if month in (12, 1, 2) else "spring" if month <= 5
            else "summer" if month <= 8 else "autumn")
