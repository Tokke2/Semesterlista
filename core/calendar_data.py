"""Shared Monday-first calendar model. No employee/vacation data."""
import calendar
from dataclasses import dataclass
from datetime import date
from core.holidays import get_holidays, get_half_days, get_holiday_names, get_us_holiday_names
from core.observances import get_us_observances


@dataclass(frozen=True)
class CalendarDay:
    date: date
    holiday_key: str
    kind: str
    actual_holiday_key: str = ""
    observance_keys: tuple[str, ...] = ()
    observed: bool = False


def year_days(year, region="sv", official=None, half=None):
    holidays = get_holidays(year, region) if official is None else official
    half_days = get_half_days(year, region) if half is None else half
    names = get_holiday_names(year, region)
    actual = get_us_holiday_names(year, observed=False) if region == "us" else {}
    observances = get_us_observances(year) if region == "us" else {}
    result = {}
    for month in range(1, 13):
        for number in range(1, calendar.monthrange(year, month)[1] + 1):
            day = date(year, month, number)
            kind = ("holiday" if day in holidays else "sunday" if day.weekday() == 6
                    else "halfday" if day in half_days else "saturday" if day.weekday() == 5 else "weekday")
            result[day] = CalendarDay(day, names.get(day, ""), kind,
                                      actual.get(day, ""), observances.get(day, ()),
                                      region == "us" and day in names and day not in actual)
    return result


def month_weeks(year, month, region="sv"):
    days = year_days(year, region)
    return [[days.get(day) if day.month == month else None for day in week]
            for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)]


def season(month):
    return ("winter" if month in (12, 1, 2) else "spring" if month <= 5
            else "summer" if month <= 8 else "autumn")


def day_labels(day, include_observances=True):
    """Translated display labels; markers never affect working-day classification."""
    from core import i18n
    labels = []
    if day.holiday_key:
        label = i18n.holiday_name(day.holiday_key)
        if day.observed and day.holiday_key != "us.new_year_observed":
            label = i18n.t("calendar.observed_label", name=label)
        labels.append(label)
    if day.actual_holiday_key and day.actual_holiday_key != day.holiday_key:
        labels.append(i18n.holiday_name(day.actual_holiday_key))
    if include_observances:
        labels.extend(i18n.holiday_name(key) + " *" for key in day.observance_keys)
    return labels
