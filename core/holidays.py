"""
Helgdagar – Sverige och USA (region-val).
=========================================

Central modul för helgdagsberäkning. Ersätter de tidigare funktionerna
get_swedish_holidays() / get_half_days() som låg i plugins/lista/plugin.py.

NYTT v2.3.0:
  - Region väljs i Inställningar: "sv" (Sverige) eller "us" (USA).
  - Regionen styr vilka dagar som blir RÖDA (helgdag) och GRÖNA
    (halvdag) i semesterlistor och limokörningsscheman.
  - Amerikanska federala helgdagar (11 st) med "observed"-regel:
    helgdag på lördag → firas fredagen före,
    helgdag på söndag  → firas måndagen efter.
  - Namn på alla helgdagar finns på svenska och engelska
    (via core/i18n.py).

Svenska helgdagar delas som tidigare i:
  - Röda dagar (officiella helgdagar)   → get_swedish_holidays()
  - Halvdagar/klämdagar                 → get_swedish_half_days()

Amerikanska helgdagar (11 federala helgdagar enligt 5 U.S.C. 6103):
  - Röda dagar = federala helgdagar, på det datum de firas (observed).
  - Observed-regeln (5 U.S.C. 6103(b) + Executive Order 11582 § 3(a)):
      lördag → fredagen före        söndag → måndagen efter
    Gäller federala anställda med mån–fre-vecka. Domstolar, Federal
    Reserve, banker och börser följer samma mönster, medan enskilda
    delstater och privata arbetsgivare inte är bundna av regeln.
  - ÖVER ÅRSSKIFTET: Nyårsdagen den 1 januari kan firas redan den
    31 december året innan (när 1 januari är en lördag). Den firade
    dagen ligger då i december ÅRET INNAN, t.ex. 31 dec 2021 för
    Nyårsdagen 2022. get_us_holidays(2021) innehåller därför 31 dec 2021,
    medan get_us_holidays(2022) inte innehåller den dagen.
    Antalet firade dagar per kalenderår är därför 10–12, inte alltid 11.
  - Halvdagar  = tomt i USA (finns ingen motsvarighet till
                 midsommarafton/julafton som halvdag i lagstiftningen).
                 Funktionen finns ändå så att API:et är symmetriskt.

  Historiska startår (så att äldre år inte får dagens helgdagslista):
      Martin Luther King-dagen      federal helgdag från 1986
      Juneteenth                    federal helgdag från 2021
      Presidents' Day               3:e måndagen i februari från 1971,
                                    dessförinnan 22 februari
                                    (Washington's Birthday)
      Memorial Day                  sista måndagen i maj från 1971,
                                    dessförinnan 30 maj
      Columbus Day                  2:a måndagen i oktober från 1971,
                                    dessförinnan 12 oktober
      Veterans Day                  11 november, Armistice Day före 1954

  MEDVETET UTELÄMNAD: Inauguration Day (20 januari vart fjärde år).
  Den är visserligen en "legal public holiday" i 5 U.S.C. 6103(c), men
  gäller bara federala anställda i Washington DC-området och har ingen
  lördags-flytt. Lägg till den i _us_federal_holidays_actual() om den
  behövs för en verksamhet i DC.

Användning:
    from core.holidays import get_holidays, get_half_days, get_holiday_names

    red  = get_holidays(2026, "sv")     # set[date]
    half = get_half_days(2026, "sv")    # set[date]
    red  = get_holidays(2026, "us")     # set[date] – inkl. observed-datum
    names = get_holiday_names(2026, "us")   # {date: "us.thanksgiving"}

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.3.0"

# ──────────────────────────────────────────────────────────
# Regioner
# ──────────────────────────────────────────────────────────
REGION_SWEDEN: str = "sv"
REGION_USA: str = "us"

DEFAULT_REGION: str = REGION_SWEDEN

VALID_REGIONS: Tuple[str, ...] = (REGION_SWEDEN, REGION_USA)

# Engelska namnen på regionerna (används i logg/PDF-texter)
REGION_NAMES_SV: Dict[str, str] = {
    REGION_SWEDEN: "Sverige",
    REGION_USA: "USA",
}

SATURDAY: int = 5
SUNDAY: int = 6


# ══════════════════════════════════════════════════════════
# GEMENSAMMA HJÄLPFUNKTIONER
# ══════════════════════════════════════════════════════════

def get_easter(year: int) -> date:
    """
    Beräkna påskdagen för ett givet år (Gauss algoritm).

    Args:
        year: Årtal (t.ex. 2026).

    Returns:
        date: Påskdagen (alltid en söndag).
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l_val = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_val) // 451
    month = (h + l_val - 7 * m + 114) // 31
    day = ((h + l_val - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """
    Hitta n:te <weekday> i en månad.

    Args:
        year:    Årtal.
        month:   Månad 1–12.
        weekday: 0 = måndag ... 6 = söndag.
        n:       1 = första, 2 = andra ... -1 = sista.

    Returns:
        date: Datumet.

    Exempel:
        nth_weekday_of_month(2026, 11, 3, 4)  → fjärde torsdagen i november
    """
    if n > 0:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (n - 1))

    # Sista <weekday> i månaden
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Sista <weekday> i månaden (t.ex. sista måndagen i maj = Memorial Day)."""
    return nth_weekday_of_month(year, month, weekday, -1)


def _saturday_closest_to(year: int, month: int, day: int) -> date:
    """
    Lördagen inom intervallet [day, day+6] – används för midsommardagen
    och Alla helgons dag (samma logik som tidigare version).
    """
    for day_num in range(day, day + 7):
        try:
            current = date(year, month, day_num)
        except ValueError:
            break
        if current.weekday() == SATURDAY:
            return current
    return date(year, month, day)


# ══════════════════════════════════════════════════════════
# SVERIGE
# ══════════════════════════════════════════════════════════

def get_swedish_holidays(year: int) -> Set[date]:
    """
    Officiella svenska helgdagar (röda dagar) för ett år.

    Nyårsdagen, Trettondedag jul, Långfredag, Påskdagen,
    Annandag påsk, Första maj, Kristi himmelsfärdsdag, Pingstdagen,
    Nationaldagen, Midsommardagen, Alla helgons dag, Juldagen,
    Annandag jul.

    OBS: Påskafton, Pingstafton, Midsommarafton, Julafton och
    Nyårsafton är INTE officiella helgdagar (se get_swedish_half_days).
    """
    holidays: Set[date] = set()
    easter = get_easter(year)

    # Fasta helgdagar
    holidays.add(date(year, 1, 1))
    holidays.add(date(year, 1, 6))
    holidays.add(date(year, 5, 1))
    holidays.add(date(year, 6, 6))
    holidays.add(date(year, 12, 25))
    holidays.add(date(year, 12, 26))

    # Påskberoende helgdagar
    holidays.add(easter - timedelta(days=2))   # Långfredag
    holidays.add(easter)                       # Påskdagen
    holidays.add(easter + timedelta(days=1))   # Annandag påsk
    holidays.add(easter + timedelta(days=39))  # Kristi himmelsfärds dag
    holidays.add(easter + timedelta(days=49))  # Pingstdagen

    # Midsommardagen – lördagen närmast 24 juni (20–26 juni)
    holidays.add(_saturday_closest_to(year, 6, 20))

    # Alla helgons dag – lördagen 31 okt–6 nov
    try:
        d_oct_31 = date(year, 10, 31)
    except ValueError:  # pragma: no cover – kan inte inträffa
        d_oct_31 = date(year, 10, 30)

    if d_oct_31.weekday() == SATURDAY:
        holidays.add(d_oct_31)
    else:
        holidays.add(_saturday_closest_to(year, 11, 1))

    return holidays


def get_swedish_half_days(year: int) -> Set[date]:
    """
    Svenska halvdagar/klämdagar (gröna dagar).

    Skärtorsdagen, Valborgsmässoafton, Midsommarafton,
    dagen före Alla helgons dag, Julafton, Nyårsafton.

    OBS: Midsommarafton är GRÖN (halvdag), inte röd.
    """
    half_days: Set[date] = set()
    easter = get_easter(year)

    # Skärtorsdagen
    half_days.add(easter - timedelta(days=3))

    # Valborgsmässoafton
    half_days.add(date(year, 4, 30))

    # Midsommarafton – fredagen närmast 24 juni (19–25 juni)
    for day_num in range(19, 26):
        current = date(year, 6, day_num)
        if current.weekday() == 4:
            half_days.add(current)
            break

    # Dagen före Alla helgons dag (fredagen före den lördagen)
    if date(year, 10, 31).weekday() == SATURDAY:
        all_saints = date(year, 10, 31)
    else:
        all_saints = _saturday_closest_to(year, 11, 1)
    half_days.add(all_saints - timedelta(days=1))

    # Julafton och Nyårsafton
    half_days.add(date(year, 12, 24))
    half_days.add(date(year, 12, 31))

    return half_days


def get_swedish_holiday_names(year: int) -> Dict[date, str]:
    """
    Namn (nycklar för i18n) på svenska helgdagar och halvdagar.

    Returns:
        {date: "sv.good_friday", ...} – se core/i18n.py för texterna.
    """
    easter = get_easter(year)
    names: Dict[date, str] = {}

    # Röda dagar
    names[date(year, 1, 1)] = "sv.new_year"
    names[date(year, 1, 6)] = "sv.epiphany"
    names[easter - timedelta(days=2)] = "sv.good_friday"
    names[easter] = "sv.easter_sunday"
    names[easter + timedelta(days=1)] = "sv.easter_monday"
    names[date(year, 5, 1)] = "sv.may_day"
    names[easter + timedelta(days=39)] = "sv.ascension"
    names[easter + timedelta(days=49)] = "sv.whit_sunday"
    names[date(year, 6, 6)] = "sv.national_day"

    for holiday in get_swedish_holidays(year):
        if holiday.month == 6 and holiday.weekday() == SATURDAY and holiday not in names:
            names[holiday] = "sv.midsummer_day"
        elif holiday.month in (10, 11) and holiday.weekday() == SATURDAY and holiday not in names:
            names[holiday] = "sv.all_saints"

    names[date(year, 12, 25)] = "sv.christmas_day"
    names[date(year, 12, 26)] = "sv.boxing_day"

    # Halvdagar
    names[easter - timedelta(days=3)] = "sv.maundy_thursday"
    names[date(year, 4, 30)] = "sv.walpurgis"
    names[date(year, 12, 24)] = "sv.christmas_eve"
    names[date(year, 12, 31)] = "sv.new_years_eve"

    for half_day in get_swedish_half_days(year):
        if half_day.month == 6 and half_day.weekday() == 4 and half_day not in names:
            names[half_day] = "sv.midsummer_eve"
        elif half_day.month in (10, 11) and half_day.weekday() == 4 and half_day not in names:
            names[half_day] = "sv.all_saints_eve"

    return names


# ══════════════════════════════════════════════════════════
# USA – federala helgdagar
# ══════════════════════════════════════════════════════════

def _us_federal_holidays_actual(year: int) -> Dict[date, str]:
    """
    Amerikanska federala helgdagar på sina FAKTISKA datum.

    Datumen är de som gäller i modern tid. För äldre år används de regler
    som faktiskt gällde då (se modulens dokumentation), så att t.ex. en
    lista för 1990 inte visar Juneteenth.

    Returns:
        {date: "us.thanksgiving", ...}
    """
    holidays: Dict[date, str] = {}

    # Nyårsdagen – 1 januari
    holidays[date(year, 1, 1)] = "us.new_year"

    # Martin Luther King-dagen – 3:e måndagen i januari, federal från 1986
    if year >= 1986:
        holidays[nth_weekday_of_month(year, 1, 0, 3)] = "us.mlk_day"

    # Presidents' Day – 3:e måndagen i februari (Uniform Monday Holiday Act,
    # 1971). Dessförinnan firades Washington's Birthday den 22 februari.
    if year >= 1971:
        holidays[nth_weekday_of_month(year, 2, 0, 3)] = "us.presidents_day"
    else:
        holidays[date(year, 2, 22)] = "us.washington_birthday"

    # Memorial Day – sista måndagen i maj från 1971, dessförinnan 30 maj
    if year >= 1971:
        holidays[last_weekday_of_month(year, 5, 0)] = "us.memorial_day"
    else:
        holidays[date(year, 5, 30)] = "us.memorial_day"

    # Juneteenth – federal helgdag sedan 2021 (5 U.S.C. 6103 infogat 2021)
    if year >= 2021:
        holidays[date(year, 6, 19)] = "us.juneteenth"

    # USA:s självständighetsdag – 4 juli
    holidays[date(year, 7, 4)] = "us.independence_day"

    # Labor Day – 1:a måndagen i september
    holidays[nth_weekday_of_month(year, 9, 0, 1)] = "us.labor_day"

    # Columbus Day – 2:a måndagen i oktober från 1971, dessförinnan 12 oktober
    if year >= 1971:
        holidays[nth_weekday_of_month(year, 10, 0, 2)] = "us.columbus_day"
    else:
        holidays[date(year, 10, 12)] = "us.columbus_day"

    # Veterans Day – 11 november (Armistice Day hette den till 1954)
    holidays[date(year, 11, 11)] = (
        "us.veterans_day" if year >= 1954 else "us.armistice_day"
    )

    # Thanksgiving – 4:e torsdagen i november (sedan 1942)
    holidays[nth_weekday_of_month(year, 11, 3, 4)] = "us.thanksgiving"

    # Juldagen – 25 december
    holidays[date(year, 12, 25)] = "us.christmas"

    return holidays


def _observed_date(value: date) -> date:
    """
    Datumet en amerikansk helgdag firas när den infaller på helg.

    Lördag → fredagen före.
    Söndag  → måndagen efter.
    Vardag  → oförändrat.
    """
    if value.weekday() == SATURDAY:
        return value - timedelta(days=1)
    if value.weekday() == SUNDAY:
        return value + timedelta(days=1)
    return value


def get_us_holidays(year: int, include_actual: bool = False) -> Set[date]:
    """
    Amerikanska federala helgdagar som FIRAS under ett kalenderår.

    Regler (5 U.S.C. 6103(b) och Executive Order 11582 § 3(a)):
        helgdag på lördag → firas fredagen före
        helgdag på söndag  → firas måndagen efter

    Mängden innehåller de datum som ligger INOM det angivna året:
        - Nyårsdagen den 1 januari firas 31 december året innan när den
          1 januari är en lördag. Därför läggs nästa års Nyårsdag till
          redan i december detta år (t.ex. 31 dec 2021 för Nyårsdagen 2022),
          och motsvarande datum tas bort från nästa års mängd.
        - Antalet firade dagar per kalenderår är därför 10–12.

    Args:
        year:           Årtal.
        include_actual: Även helgdagarnas FAKTISKA datum läggs till
                        (används av testvyn; PDF:en visar samma
                        uppsättning som de firade datumen).

    Returns:
        Set[date]: Röda dagar för USA inom det angivna året.
    """
    holidays: Set[date] = set()

    for actual in _us_federal_holidays_actual(year):
        observed = _observed_date(actual)
        if observed.year == year:
            holidays.add(observed)
        # Annars firas helgdagen i grannåret och ligger i den årgångens mängd

        if include_actual:
            holidays.add(actual)

    # Nyårsdagen nästa år kan firas redan i december i år (1 jan på lördag)
    next_new_year_observed = _observed_date(date(year + 1, 1, 1))
    if next_new_year_observed.year == year:
        holidays.add(next_new_year_observed)

    return holidays


def get_us_half_days(year: int) -> Set[date]:
    """
    Halvdagar i USA.

    Federal lagstiftning har inga halvdagar, så mängden är tom.
    Funktionen finns för att API:et ska vara symmetriskt mot Sverige
    (och för att enkelt kunna lägga till t.ex. julafton/nyårsafton
    som halvdagar om så önskas senare).
    """
    _ = year  # Ingen halvdagslista för USA
    return set()


def get_us_holiday_names(year: int, observed: bool = True) -> Dict[date, str]:
    """
    Namn (i18n-nycklar) på amerikanska helgdagar och deras firade datum.

    Nycklarna motsvarar exakt de datum som get_us_holidays() returnerar
    (observed=True → samma mängd som get_us_holidays(year)).

    Args:
        year:     Årtal.
        observed: True  → nycklar på de datum de firas (inom året).
                  False → nycklar på de faktiska datumen.

    Returns:
        {date: "us.thanksgiving", ...}
    """
    names: Dict[date, str] = {}

    for actual, key in _us_federal_holidays_actual(year).items():
        if observed:
            target = _observed_date(actual)
            if target.year != year:
                continue      # firas i grannåret i stället
        else:
            target = actual

        names[target] = key

    # Nyårsdagen nästa år kan firas redan i december i år
    if observed:
        next_new_year_observed = _observed_date(date(year + 1, 1, 1))
        if next_new_year_observed.year == year:
            names[next_new_year_observed] = "us.new_year_observed"

    return names


# ══════════════════════════════════════════════════════════
# GEMENSAMT API (region-styrt)
# ══════════════════════════════════════════════════════════

def normalize_region(region: Optional[str]) -> str:
    """
    Kontrollera att regionen är giltig.

    Ogiltig/None → DEFAULT_REGION ("sv") och en varning loggas.
    """
    if region in VALID_REGIONS:
        return region  # type: ignore[return-value]

    if region is not None:
        logger.warning(
            f"Ogiltig helgdagsregion {region!r} – använder {DEFAULT_REGION!r}"
        )
    return DEFAULT_REGION


def get_holidays(year: int, region: Optional[str] = DEFAULT_REGION) -> Set[date]:
    """
    Röda dagar (helgdagar) för valt år och vald region.

    Args:
        year:   Årtal.
        region: "sv" = Sverige (officiella helgdagar)
                "us" = USA (federala helgdagar, inkl. observed-datum)

    Returns:
        Set[date]
    """
    region = normalize_region(region)
    if region == REGION_USA:
        return get_us_holidays(year)
    return get_swedish_holidays(year)


def get_half_days(year: int, region: Optional[str] = DEFAULT_REGION) -> Set[date]:
    """
    Gröna dagar (halvdagar) för valt år och vald region.

    Sverige har halvdagar (midsommarafton, julafton m.fl.).
    USA har inga halvdagar → tom mängd.
    """
    region = normalize_region(region)
    if region == REGION_USA:
        return get_us_half_days(year)
    return get_swedish_half_days(year)


def get_holiday_names(
    year: int,
    region: Optional[str] = DEFAULT_REGION,
) -> Dict[date, str]:
    """
    Namn på helgdagar och halvdagar för valt år och region.

    Returns:
        {date: "sv.good_friday" | "us.thanksgiving" | ...}
        Texten hämtas med core.i18n.holiday_name(nyckel).
    """
    region = normalize_region(region)
    if region == REGION_USA:
        return get_us_holiday_names(year)
    return get_swedish_holiday_names(year)


def get_region_from_settings(settings_manager, default: str = DEFAULT_REGION) -> str:
    """
    Läs vald helgdagsregion från applikationens inställningar.

    Nyckeln är "holiday_region" i data/settings.json och sätts i
    Arkiv → Inställningar → Helgdagar.

    Args:
        settings_manager: SettingsManager (eller None).
        default:          Reservvärde om inget är sparat.

    Returns:
        "sv" eller "us".
    """
    if settings_manager is None:
        return normalize_region(default)

    try:
        value = settings_manager.get("holiday_region", default)
    except Exception as e:  # pragma: no cover – defensivt
        logger.warning(f"Kunde inte läsa holiday_region: {e}")
        value = default

    return normalize_region(value)


def describe_region(region: Optional[str]) -> str:
    """Kort beskrivning av regionen, t.ex. 'Sverige (svenska helgdagar)'."""
    region = normalize_region(region)
    if region == REGION_USA:
        return "USA"
    return "Sverige"


def region_info(year: int, region: Optional[str] = DEFAULT_REGION) -> Dict[str, int]:
    """
    Sammanfattning för logg/test: antal helgdagar och halvdagar.

    Returns:
        {"holidays": n, "half_days": n}
    """
    return {
        "holidays": len(get_holidays(year, region)),
        "half_days": len(get_half_days(year, region)),
    }


def list_holidays(
    year: int,
    region: Optional[str] = DEFAULT_REGION,
) -> List[Tuple[date, str]]:
    """
    Sorterad lista med (datum, i18n-nyckel) för alla markerade dagar.

    Används av testvyn för att visa vad som faktiskt markerats.
    """
    names = get_holiday_names(year, region)
    holidays = get_holidays(year, region)
    half_days = get_half_days(year, region)

    result: List[Tuple[date, str]] = []
    for day in sorted(holidays | half_days):
        key = names.get(day)
        if key is None:
            key = "public_holiday" if day in holidays else "half_day"
        result.append((day, key))
    return result


def get_version() -> str:
    """Returnera modulversionen."""
    return MODULE_VERSION
