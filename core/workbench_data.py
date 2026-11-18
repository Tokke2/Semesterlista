"""Read-only, Qt-free overview and search helpers. No inferred payment status."""
from dataclasses import dataclass
from datetime import date, timedelta
from core.roster import RosterFile
from core.leave import LeaveCalendar, split_entry


@dataclass(frozen=True)
class SearchEntry:
    module: str
    label: str
    detail: str = ""


def search_entries(entries, query):
    tokens = query.casefold().split()
    return [entry for entry in entries
            if all(token in (entry.module + " " + entry.label + " " + entry.detail).casefold()
                   for token in tokens)]


def read_overview(path, module, vacation=False, today=None):
    today = today or date.today()
    roster = RosterFile.load(path)
    lines = [line for section in roster.sections for line in section]
    entries = [SearchEntry(module, split_entry(line)[0], line) for line in lines]
    upcoming = []
    if vacation:
        calendar = LeaveCalendar.from_lines(lines, default_year=today.year)
        for entry in entries:
            for period in calendar.ranges_for(entry.label):
                if period.end >= today and period.start <= today + timedelta(days=30):
                    upcoming.append((entry.label, period.start, period.end))
        upcoming.sort(key=lambda row: (row[1], row[0].casefold()))
        return entries, upcoming, calendar.errors
    return entries, upcoming, []
