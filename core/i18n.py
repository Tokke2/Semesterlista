"""
Internationalisering (i18n) – svenska och engelska.
=================================================

Detta modul tillhandahåller ALLA användarsynliga texter i applikationen
på svenska och engelska, inklusive:

  - Menyer, dialoger, knappar, statusrad och systemfält
  - Månads- och veckodagsnamn (långa och korta)
  - Namn på helgdagar (svenska och amerikanska)
  - Texter i genererade PDF-filer

NYTT v2.3.0:
  - Ny modul. Ersätter hårdkodade svenska strängar i main.pyw,
    plugins/lista/plugin.py och plugins/hyra/plugin.py.
  - Språk väljs i Inställningar (Arkiv → Inställningar → Språk).
  - Språkbyte slår igenom direkt utan omstart (signal language_changed).

Användning:
    from core import i18n

    i18n.init(settings_manager)        # en gång vid start
    text = i18n.t("menu.file")          # "&Arkiv" eller "&File"
    text = i18n.t("app.autostart.tooltip", app="Semesterlista")
    i18n.set_language("en")             # byter språk + emitterar signal

    i18n.month_name(3)                  # "Mars" / "March"
    i18n.weekday_short()                # ["Mån", ...] / ["Mon", ...]

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from core.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.17.0"

# Standard- och reservspråk
DEFAULT_LANGUAGE: str = "sv"
FALLBACK_LANGUAGE: str = "sv"

# ──────────────────────────────────────────────────────────
# Tillgängliga språk (visas i Inställningar)
# ──────────────────────────────────────────────────────────
LANGUAGES: Dict[str, str] = {
    "sv": "Svenska",
    "en": "English",
}


# ══════════════════════════════════════════════════════════
# MÅNADS- OCH VECKODAGSNAMN
# ══════════════════════════════════════════════════════════

MONTH_NAMES: Dict[str, Dict[str, List[str]]] = {
    "sv": {
        "long": [
            "Januari", "Februari", "Mars", "April", "Maj", "Juni",
            "Juli", "Augusti", "September", "Oktober", "November",
            "December",
        ],
        "short": [
            "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
            "Jul", "Aug", "Sep", "Okt", "Nov", "Dec",
        ],
        # Gemener används i löpande text: "1 december"
        "lower": [
            "januari", "februari", "mars", "april", "maj", "juni",
            "juli", "augusti", "september", "oktober", "november",
            "december",
        ],
    },
    "en": {
        "long": [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November",
            "December",
        ],
        "short": [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ],
        "lower": [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November",
            "December",
        ],
    },
}

# Index 0 = Måndag ... 6 = Söndag (matchar date.weekday())
WEEKDAY_NAMES: Dict[str, Dict[str, List[str]]] = {
    "sv": {
        "short": ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"],
        "long": [
            "Måndag", "Tisdag", "Onsdag", "Torsdag",
            "Fredag", "Lördag", "Söndag",
        ],
    },
    "en": {
        "short": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "long": [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ],
    },
}


# ══════════════════════════════════════════════════════════
# ÖVERSÄTTNINGAR
# ══════════════════════════════════════════════════════════
#
# Konvention för nycklar:
#   menu.*        menyraden
#   theme.*       teman
#   status.*      statusraden
#   tray.*        systemfältet
#   about.*       Om-dialogen
#   settings.*    Inställningsdialogen (huvudfönstret)
#   common.*      återanvändbara ord (OK, Avbryt, Fel ...)
#   autostart.*   autostart-meddelanden
#   lista.*       Semesterlista & Limokörning
#   hyra.*        Hyresfakturering
#   holiday.*     namn på helgdagar
#   legend.*      färgförklaring i PDF (delas av plugins)
#
# ══════════════════════════════════════════════════════════

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ══════════════════════════════════════════════════════
    # SVENSKA
    # ══════════════════════════════════════════════════════
    "sv": {
        # ── Menyrad ───────────────────────────────────────
        "menu.file":                       "&Arkiv",
        "menu.file.settings":              "&Inställningar...",
        "menu.file.autostart":             "&Autostart vid inloggning",
        "menu.file.autostart_tooltip":     "Starta {app} automatiskt vid inloggning.",
        "menu.file.quit":                  "&Avsluta",
        "menu.view":                       "&Visa",
        "menu.view.hide_tab":              'Dölj "{name}"',
        "menu.view.show_all":              "Visa alla dolda tabbar",
        "menu.appearance":                 "&Utseende",
        "menu.help":                       "&Hjälp",
        "menu.help.about":                 "&Om {app}...",
        "menu.unknown_tab":                "Okänd",

        # ── Teman ─────────────────────────────────────────
        "theme.dark":                      "&Mörkt tema",
        "theme.light":                     "&Ljust tema",
        "theme.system":                    "&System-tema",
        "theme.dark.name":                 "Mörkt",
        "theme.contrast": "&Hög kontrast",
        "theme.contrast.name": "Hög kontrast",
        "calendar.tab": "Kalender",
        "calendar.title": "Kalender",
        "calendar.description": "Fristående kalender med helgdagar och lokala bilder. Inga anställda eller semesterperioder. Veckan börjar alltid på måndag. PDF: liggande A4.",
        "calendar.year": "År:",
        "calendar.per_page": "Månader per PDF-blad:",
        "calendar.region": "Helgdagsregion:",
        "calendar.months": "Månader som ska exporteras:",
        "calendar.export": "Generera PDF",
        "calendar.all_months": "Markera alla månader",
        "calendar.select_months": "Välj minst en månad och 1, 2 eller 3 månader per blad.",
        "calendar.no_holidays": "Inga namngivna helgdagar denna månad.",
        "calendar.saved": "Kalendern har sparats:\n{path}",
        "calendar.page": "Sida {page} av {total}",
        "calendar.week": "Vecka",
        "season.settings": "PDF-utseende…",
        "season.enable": "Säsongsfärger och bilder i PDF",
        "season.monochrome": "Svartvit PDF (gråskala)",
        "season.folder": "Välj bildmapp…",
        "season.no_folder": "Ingen bildmapp vald",
        "season.no_image": "Ingen bild",
        "season.missing": "Bilden kunde inte läsas – PDF skapas utan den.",
        "season.winter": "Vinter",
        "season.spring": "Vår",
        "season.summer": "Sommar",
        "season.autumn": "Höst",

        "theme.light.name":                "Ljust",
        "theme.system.name":               "System",

        # ── Statusrad ─────────────────────────────────────
        "status.ready":                    "Redo",
        "status.tab_shown":                "Visade: {name}",
        "status.tab_hidden":               "Dolde: {name}",
        "status.active_tab":               "Aktiv: {name}",
        "status.theme":                    "Tema: {name}",
        "status.language":                 "Språk: {name}",

        # ── Systemfält ────────────────────────────────────
        "tray.show":                       "Visa {app}",
        "tray.hide":                       "Dölj",
        "tray.quit":                       "Avsluta",
        "tray.started_message":            "v{version} – Körs i systemfältet",

        # ── Om-dialogen ───────────────────────────────────
        "about.title":                     "Om {app}",
        "about.body": (
            "<b>{app}</b> v{version}<br><br>"
            "Plugin-baserad desktopapplikation<br>"
            "för semesterlistor, limokörning &amp; hyresfakturering.<br><br>"
            "Byggd med Python {py_major}.{py_minor} och PySide6.<br><br>"
            "&copy; {year} Rickard Längkvist"
        ),

        # ── Autostart ─────────────────────────────────────
        "autostart.title":                 "Autostart",
        "autostart.enable":                "aktivera",
        "autostart.disable":               "avaktivera",
        "autostart.error":                 "Kunde inte {action} autostart.",
        "autostart.location":              "Plats: {path}",
        "autostart.status_on":             "Aktiverad",
        "autostart.status_off":            "Avaktiverad",

        # ── Gemensamma ord ────────────────────────────────
        "common.ok":                       "OK",
        "common.cancel":                   "Avbryt",
        "common.save":                     "Spara",
        "common.close":                    "Stäng",
        "common.error":                    "Fel",
        "common.warning":                  "Varning",
        "common.info":                     "Information",
        "common.done":                     "Klart",

        # ── Listor: anställda, fordon, hyresgäster (v2.4.0) ─
        "lista.manage_list":               "Hantera lista…",
        "lista.manage_list.tooltip":       "Lägg till, ändra eller ta bort poster i listan",
        "lista.list_count":                "{count} poster i filen",
        "lista.list_missing":              "{file} finns inte än – skapas när du sparar",
        "lista.error.read":                "Kunde inte läsa listan: {error}",
        "hyra.manage_tenants":             "Hantera hyresgäster…",
        "hyra.manage_tenants.tooltip":     "Lägg till, ändra eller ta bort hyresgäster",
        "roster.dialog.title":             "Hantera {name}",
        "roster.header":                   "Fil: {path}",
        "roster.count":                    "{count} poster",
        "roster.section.number":           "Sektion {number}",
        "roster.button.add":               "Lägg till",
        "roster.button.edit":              "Ändra",
        "roster.button.remove":            "Ta bort",
        "roster.leave.hint":               "Lediga dagar skrivs efter namnet: Roland: 18/12 - 7/1 (även ; eller |) – starten snäpps till närmaste måndag, slutet till närmaste söndag, och syns bara som kryss i listan",
        "roster.button.up":                "Upp",
        "roster.button.down":              "Ner",
        "roster.button.up.tooltip":        "Flytta posten ett steg upp",
        "roster.button.down.tooltip":      "Flytta posten ett steg ned",
        "roster.button.sort":              "Sortera A–Ö",
        "roster.button.sort.tooltip":      "Sortera listan alfabetiskt (Å, Ä, Ö efter Z)",
        "roster.button.paste":             "Klistra in flera…",
        "roster.button.paste.tooltip":     "Lägg till många poster samtidigt (en per rad)",
        "roster.button.open_text":         "Öppna i textredigerare",
        "roster.button.open_text.tooltip": "Redigera filen i Anteckningar/TextEdit",
        "roster.button.save":              "Spara",
        "roster.button.cancel":            "Avbryt",
        "roster.add.title":                "Lägg till post",
        "roster.add.prompt":               "Namn (max {max} tecken):",
        "roster.edit.title":               "Ändra post",
        "roster.edit.prompt":              "Namn (max {max} tecken):",
        "roster.remove.question":          "Ta bort {count} poster?",
        "roster.paste.title":              "Klistra in flera",
        "roster.paste.prompt":             "En post per rad:",
        "roster.paste.result":             "{added} poster tillagda, {skipped} överhoppade (dubbletter, tomma eller för långa).",
        "roster.info.created":             "Filen skapades: {path}",
        "roster.confirm.title":            "Osparade ändringar",
        "roster.confirm.discard":          "Det finns osparade ändringar. Vill du spara dem?",
        "roster.warning.title":            "Kontrollera listan",
        "roster.warning.body":             "Följande bör ses över:\n\n• {issues}\n\nVill du spara ändå?",
        "roster.error.title":              "Listan kunde inte hanteras",
        "roster.error.read":               "Kunde inte läsa listan: {error}",
        "roster.error.too_long":           "Posten är för lång (max {max} tecken).",
        "roster.error.duplicate":          "\"{entry}\" finns redan i listan.",
        "roster.open_failed":              "Kunde inte öppna {path} i textredigeraren.",

        # ── Inställningsdialog (huvudfönster) ─────────────
        "settings.title":                  "Inställningar",
        "settings.group.appearance":       "Språk och utseende",
        "settings.language":               "Språk:",
        "settings.language.tooltip": (
            "Språket gäller hela applikationen, inklusive de PDF-filer "
            "som genereras.\nÄndringen slår igenom direkt."
        ),
        "settings.theme":                  "Tema:",
        "settings.group.holidays":         "Helgdagar",
        "settings.holiday_region":         "Helgdagar:",
        "settings.holiday_region.sv":      "Sverige (svenska helgdagar)",
        "settings.holiday_region.us":      "USA (amerikanska helgdagar)",
        "settings.holiday_region.tooltip": (
            "Styr vilka dagar som markeras som röda (helgdag) och gröna "
            "(halvdag) i semesterlistor och limokörningsscheman."
        ),
        "settings.holiday_region.help": (
            "Röda dagar och halvdagar i PDF-listorna följer valt land."
        ),
        "settings.group.window":           "Fönster och systemfält",
        "settings.autostart":              "Starta automatiskt vid inloggning",
        "settings.start_minimized":        "Starta minimerad i systemfältet",
        "settings.minimize_to_tray":       "Minimera till systemfältet",
        "settings.close_to_tray":          "Stäng (X) minimerar till systemfältet",
        "settings.notifications":          "Visa aviseringar",
        "settings.group.plugins":          "Plugins",
        "settings.group.advanced":         "Avancerat",
        "settings.debug_mode":             "Felsökningsläge",
        "settings.log_to_file":            "Logga till fil",
        "settings.check_updates":          "Sök efter uppdatering vid start",
        "settings.clear_cache_on_exit":    "Rensa cache vid avslut",
        "settings.clear_cache_on_exit.tooltip": (
            "Logotyper som renderats till bildfiler ligger i temp-mappen under "
            "körningen. Med den här inställningen tas de bort när appen avslutas "
            "– inget blir kvar och skräpar, men nästa start renderar logotyperna "
            "igen (några tiondels sekunder per logotyp)."
        ),
        "settings.cache_size":             "Cache: {size}",
        "log.cache_cleared":               "Cache rensad: {summary}",
        "settings.group.data":             "Data",
        "settings.data_path":              "Inställningarna sparas i:",
        "settings.plugin_restart_hint":    "Ändring av plugins kräver omstart.",
        "settings.saved":                  "Inställningar sparade.",
        "settings.no_plugins":             "Inga plugins hittades.",
        "settings.tab.general":            "Allmänt",
        "settings.tab.window":             "Fönster",
        "settings.tab.plugins":            "Plugins",
        "settings.tab.advanced":           "Avancerat",
        "settings.save":                   "Spara",
        "settings.cancel":                 "Avbryt",
        "settings.notification_duration":  "Aviseringens längd:",
        "settings.debug_mode.tooltip":     (
            "Skriver mer detaljerad information till loggen "
            "(data/app.log). Används vid felsökning."
        ),
        "settings.log_file":               "Loggfil:",
        "settings.open_log_folder":        "Öppna loggmapp",
        "settings.copy_log":               "Kopiera senaste loggen",
        "settings.log_empty":              "Loggen är tom ännu.",
        "settings.open_log_error":         "Kunde inte öppna mappen:\n{error}",
        "settings.error_log_file":         "Fellogg ({count} rader): {path}",
        "settings.open_error_log":         "Öppna felloggen",
        "settings.clear_error_log":        "Rensa felloggen",
        "settings.clear_error_log.tooltip": "När felen är åtgärdade kan felloggen rensas – den arkiveras aldrig automatiskt.",
        "settings.clear_error_log_confirm": "Rensa felloggen?\n\nFelen som ligger där försvinner från filen.",
        "settings.clear_error_log_failed":  "Kunde inte rensa felloggen – filen kan vara låst av ett annat program.",
        "settings.error_log_empty":         "Felloggen är tom – inga fel loggade.",
        "settings.save_error":             "Kunde inte spara inställningarna:\n{error}",
        "settings.autostart.unavailable":  "Autostart kunde inte läsas i den här miljön.",
        # ── Uppdatering från GitHub (v2.9.0) ──────────────
        "update.group":                    "Uppdatering",
        "update.current":                  "Nuvarande version: {version}",
        "update.check":                    "Sök efter uppdatering",
        "update.checking":                 "Söker efter uppdatering…",
        "update.available":                "Ny version {version} finns ({date}).",
        "update.latest":                   "Du har senaste versionen ({version}).",
        "update.error":                    "Kunde inte söka: {error}",
        "update.install":                  "Uppdatera nu",
        "update.downloading":              "Laddar ner… {percent} %",
        "update.installing":               "Installerar…",
        "update.confirm_title":            "Uppdatera",
        "update.confirm":                  (
            "Uppdatera från {old} till {new}?\n\n"
            "Dina listor, inställningar och loggar rörs inte. Nuvarande "
            "programfiler säkerhetskopieras i data/backup/."
        ),
        "update.done":                     (
            "Uppdaterat till {version} ({files} filer).\n"
            "Säkerhetskopia: {backup}"
        ),
        "update.install_error":            "Kunde inte uppdatera: {error}",
        "update.restart_title":            "Starta om",
        "update.restart_question":         (
            "Uppdateringen är klar. Starta om Semesterlista nu för att "
            "använda version {version}?"
        ),
        "update.restart_manual":           (
            "Starta om appen manuellt för att använda den nya versionen."
        ),
        "update.release_page":             "Öppna release-sidan",
        "update.notes":                    "Ändringar i releasen:",
        "update.no_zip":                   "Releasen saknar nedladdningsbar fil.",
        "update.tray_title":               "Uppdatering finns",
        "update.tray_body":                (
            "Semesterlista {version} finns på GitHub (du har {current})."
        ),
        "menu.help.check_updates":         "Sök efter &uppdatering…",

        # ── Loggning & fel (v2.8.0) ───────────────────────
        "log.started":                     "Loggning startad: {path}",
        "log.file_missing":                "Filen {module} saknas – {feature} är avstängt.",
        "log.import_failed":               "Kunde inte importera {module}: {error}",
        "log.crash_title":                 "Ett fel inträffade",
        "log.crash_body":                  (
            "Applikationen stötte på ett fel.\n\n"
            "{error}\n\nLoggfil: {log}"
        ),

        # ── Sidlayout (v2.6.0) ────────────────────────────
        "lista.orientation":               "Sidlayout:",
        "lista.company_name": "Företagsnamn i PDF",
        "vacation.title": "Semesterkalender…",
        "vacation.year": "År för summering:",
        "vacation.person": "Anställd",
        "vacation.total": "Semesterdagar detta år",
        "vacation.start": "Första semesterdag",
        "vacation.end": "Sista semesterdag",
        "vacation.add": "Lägg till vald period",
        "vacation.remove": "Ta bort markerad period",
        "vacation.invalid_dates": "Slutdatum får inte vara före startdatum.",
        "vacation.changed": "Listfilen har ändrats. Stäng och öppna kalendern igen innan du sparar.",
        "vacation.note": "Summering: måndag–fredag, exklusive officiella helgdagar i vald region. Halvdagar räknas som en dag. Överlapp räknas bara en gång. Kalenderdatum sparas exakt, utan veckosnäppning. Detta är planering, inte beräkning av semesterlön.",
        "hyra.quarter.send_by": "Skickas senast:\n{date}",
        "hyra.quarter.paid_by": "Betald senast:\n{date}",

        "lista.pdf.small_text.title": "Liten text i PDF",
        "lista.pdf.small_text.message": "Texten blir som minst cirka {size} punkter på sida/sidor {pages} (under 6 punkter) och kan bli svår att läsa.\n\nDu har valt {months} månader per blad. Välj färre månader eller en kortare lista om du vill ha större text.\n\nVill du ändå skapa PDF:en med ditt nuvarande val?",
        "lista.orientation.auto": "Automatiskt: 1 månad = stående A4, 2–3 = liggande A4",
        "lista.orientation.landscape":     "Liggande (A4)",
        "lista.orientation.portrait":      "Stående (A4)",

        # ── Flikar: Hyra, Semesterlista, Fordon ───────────
        "fordon.tab_name":                 "Fordon",
        "fordon.plugin_description":       "Limokörningsscheman per fordon som PDF",
        "fordon.title":                    "\U0001F697 Fordonsschema",
        "fordon.description":              "Generera limokörningsscheman per fordon som PDF",

        # ── Logotyp i PDF ─────────────────────────────────
        "logo.label":                      "Logotyp:",
        "logo.no_logo":                    "Ingen logotyp",
        "logo.choose":                     "Välj logotyp…",
        "logo.clear":                      "Ta bort",
        "logo.browse":                     "Bläddra till fil…",
        "logo.rescan":                     "Uppdatera lista",
        "logo.dialog_title":               "Välj logotyp",
        "logo.dialog_hint":                "Bilder från mappen assets och dess undermappar. Endast SVG listas – EPS, PDF och PNG/JPG infogas med knappen.",
        "logo.preview":                    "Förhandsgranskning",
        "logo.folder":                     "Mapp: {path}",
        "logo.assets":                     "Bilder i assets:",
        "logo.empty":                      "Inga bilder hittades i assets-mappen.",
        "logo.outside_assets":             "utanför assets",
        "logo.missing":                    "Filen finns inte: {path}",
        "logo.error":                      "Kunde inte läsa logotypen: {error}",
        "logo.ok":                         "Använd",
        "logo.cancel":                     "Avbryt",
        "logo.selected":                   "Logotyp: {name}",
        "logo.missing_file":               "Saknas: {path}",
        "logo.insert":                     "Infoga logotyp…",
        "logo.insert_tooltip":             "Infoga en logotyp: SVG, EPS eller PDF (PNG/JPG fungerar också). EPS kräver Ghostscript.",
        "logo.rescan_tooltip":             "Sök igenom assets-mappen och dess undermappar igen.",
        "logo.auto_size":                  "Storleken anpassas automatiskt – både i förhandsgranskningen och i PDF:en.",
        "logo.size_label":                 "Storlek:",
        "logo.size_hint":                  "Proportionerna behålls alltid.",
        "logo.size_tooltip":               "Logotypens storlek i PDF:en och i förhandsgranskningen. 100 % = automatisk storlek.",
        "logo.filter_all":                 "Logotyper",
        "logo.filter_images":              "Bilder",
        "logo.filter_any":                 "Alla filer",
        "tray.settings":                   "Inställningar…",
        "tray.check_updates":              "Sök efter uppdatering…",
        "tray.about":                      "Om {app} v{version}…",

        # ── Semesterlista & Limokörning ───────────────────
        "lista.tab_name":                  "Semesterlista",
        "lista.plugin_description":        "Semesterlistor och limokörningsscheman som PDF",
        "lista.window_title":              "Inställningar – Semesterlista",
        "lista.title":                     "📅 Semesterlista",
        "lista.description":               "Generera semesterlistor som PDF",
        "lista.group.settings":            "Inställningar",
        "lista.group.legend":              "Färgförklaring i PDF",
        "lista.mode":                      "Läge:",
        "lista.mode.semesterlista":        "Semesterlista",
        "lista.mode.limo":                 "Limokörning",
        "lista.year":                      "År:",
        "lista.start_month":               "Startmånad:",
        "lista.months_per_page":           "Månader/blad:",
        "lista.file.employees":            "Fil med anställda:",
        "lista.file.vehicles":             "Fil med fordon:",
        "lista.file.browse_tooltip":       "Välj textfil med namn eller fordon",
        "lista.button.generate":           "🖨️ Generera PDF",
        "lista.button.tests":              "🧪 Kör tester",
        "lista.button.open_documents":     "📁 Öppna Dokument",
        "lista.button.browse":             "Bläddra...",
        "lista.settings.auto_open":        "Öppna PDF automatiskt:",
        "lista.settings.default_mode":     "Standardläge:",
        "lista.settings.months_per_page":  "Månader per blad:",
        "lista.settings.start_month":      "Standardstartmånad:",
        "lista.settings.saved":            "Inställningar sparade!",
        "lista.start_month.standard":      "Standard (Januari)",
        "lista.start_month.tooltip": (
            "Standard (Januari) = jan–dec valt år.\n"
            "Väljer du en månad manuellt genereras 12 månader från den\n"
            "månaden och perioden kan gå över årsskifte,\n"
            "t.ex. dec 2026 → jan 2027."
        ),
        "lista.file_dialog.title":         "Välj fil",
        "lista.file_dialog.filter":        "Textfiler (*.txt);;Alla filer (*.*)",
        "lista.pdf.title_prefix.semesterlista": "Semesterlista",
        "lista.pdf.title_prefix.limo":     "Limokörningsschema",
        "lista.pdf.header.employees":      "Anställd",
        "lista.pdf.header.vehicles":       "Fordon",
        "lista.pdf.period_standard":       "Standard (Januari)",
        "lista.pdf.done_title":            "Klart",
        "lista.pdf.done_body": (
            "{title} har genererats!\n\n"
            "Period: {range}\n"
            "Fil: {filename}\n"
            "Startval: {start}\n"
            "Månader per blad: {months}"
        ),
        "lista.pdf.error_title":           "Fel",
        "lista.pdf.error_body":            "Fel vid PDF-generering: {error}",
        "lista.pdf.legend.red":            "Röd = Helgdag eller söndag",
        "lista.pdf.legend.blue":           "Blå = Lördag",
        "lista.pdf.legend.green":          "Grön = Halvdag (midsommarafton, julafton m.fl.)",
        "lista.pdf.legend.orange":         "Orange = Ny vecka",
        "lista.pdf.legend.leave":          "Grå = Ledig",
        "lista.pdf.legend.red_us":         "Röd = Amerikansk helgdag (inkl. fridag) eller söndag",
        "lista.pdf.legend.green_us":       "Grön = Halvdag (används inte för USA)",
        "lista.legend.red":                "Röd = Helgdagar och söndagar (Nyår, Påsk, Midsommardagen, Jul, etc.)",
        "lista.legend.blue":               "Blå = Lördagar",
        "lista.legend.green":              "Grön = Halvdagar (Midsommarafton, Julafton, Nyårsafton, Skärtorsdag, Valborg, dag före Alla helgons dag)",
        "lista.legend.orange":             "Orange linje = Ny vecka",
        "lista.legend.leave":              "Grå med × = Ledig (anges i listan efter namnet, t.ex. 18/12 – 7/1)",
        "lista.legend.red_us":             "Röd = Amerikanska helgdagar och söndagar (Thanksgiving, Independence Day, Christmas, etc.)",
        "lista.legend.green_us":           "Grön = Halvdagar (används inte för USA – amerikanska helgdagar som infaller på helg blir i stället röda på fridagen)",
        "lista.msg.year_invalid":          "Ogiltigt år. Ange ett giltigt heltal",
        "lista.msg.year_range":            "År måste vara mellan 1900 och 2100",
        "lista.msg.file_empty":            "Filnamn får inte vara tomt",
        "lista.msg.file_missing":          "Filen '{path}' finns inte",
        "lista.msg.mode_invalid":          "Ogiltigt läge",
        "lista.msg.no_data":               "Ingen data hittades i {path}",
        "lista.msg.read_error":            "Fel vid läsning av fil: {error}",
        "lista.week_prefix":               "v",
        "lista.tests.title":               "Testresultat",
        "lista.tests.heading":             "Testresultat – Semesterlista & Limokörning v{version} ({language})",
        "lista.tests.ok":                  "✅ OK",
        "lista.tests.fail":                "❌ Fel",
        "lista.tests.1":                   "1. Ogiltigt år",
        "lista.tests.2":                   "2. År utanför intervall",
        "lista.tests.3":                   "3. Ogiltigt läge",
        "lista.tests.4":                   "4. Skottårshantering",
        "lista.tests.5":                   "5. Svenska helgdagar",
        "lista.tests.6":                   "6. Midsommarafton = grön (ej röd)",
        "lista.tests.7":                   "7. Julafton = grön",
        "lista.tests.8":                   "8. Påskberäkning 2024",
        "lista.tests.9":                   "9. Standardläge = jan–dec samma år",
        "lista.tests.10":                  "10. December → januari över årsskifte",
        "lista.tests.11":                  "11. Amerikanska helgdagar (Thanksgiving m.fl.)",
        "lista.tests.12":                  "12. Helgdagsval följer Inställningar",

        # ── Hyresfakturering ──────────────────────────────
        "hyra.tab_name":                   "Hyra",
        "hyra.plugin_description":         "Hyreslistor med tomma kryssrutor som PDF",
        "hyra.title":                      "🏠 Hyresfakturering",
        "hyra.year":                       "År:",
        "hyra.file":                       "📁 Fil: {file}",
        "hyra.button.edit":                "📝 Redigera",
        "hyra.button.reload":              "🔄 Ladda om",
        "hyra.button.generate":            "🖨️ Generera PDF",
        "hyra.button.edit_file":           "📝 Redigera {file}",
        "hyra.tooltip.edit_file":          "Öppna {file} i textredigerare",
        "hyra.tooltip.edit_std":           "Öppna textfilen i standard-redigeraren",
        "hyra.tooltip.reload":             "Ladda om hyresgäster från fil",
        "hyra.tooltip.generate":           "Generera hyreslista som PDF",
        "hyra.quarter.panel":              "📅 Kvartalsfakturor – Skicka senast",
        "hyra.quarter.send":               "Skickas: {date}",
        "hyra.status.passed":              "Passerad",
        "hyra.status.today":               "IDAG!",
        "hyra.status.days":                "{days} dagar",
        "hyra.invoice_date":               "1 {month}",
        "hyra.tenants.monthly":            "Månadshyresgäster",
        "hyra.tenants.quarterly":          "Kvartalshyresgäster",
        "hyra.tenants.empty":              "Inga hyresgäster\n\nRedigera {file}",
        "hyra.tenants.total":              "Totalt: {count} st",
        "hyra.pdf.title":                  "Hyreslista {year}",
        "hyra.pdf.quarter_header":         "Kvartalsfakturor – Skicka senast:",
        "hyra.pdf.quarter_cell":           "Q{quarter}: 1 {month}\n({period})",
        "hyra.pdf.tenant_header":          "Hyresgäst",
        "hyra.pdf.monthly_section":        "Månadshyresgäster",
        "hyra.pdf.quarterly_section":      "Kvartalshyresgäster",
        "hyra.pdf.footer":                 "Genererad: {timestamp}",
        "hyra.pdf.done_title":             "Klart",
        "hyra.pdf.done_body":              "PDF genererad!\n\n{filename}",
        "hyra.pdf.no_tenants":             "Inga hyresgäster!\n\nRedigera {file} först.",
        "hyra.pdf.error_title":            "Fel",
        "hyra.pdf.error_body":             "Kunde inte generera PDF:\n{error}",
        "hyra.reload.done_title":          "Klart",
        "hyra.reload.done_body":           "Hyresgäster laddade om!\n\nMånad: {monthly}\nKvartal: {quarterly}",
        "hyra.file_open_error":            "Kunde inte öppna fil:\n{error}",

        # ── Helgdagsnamn – Sverige ────────────────────────
        "holiday.sv.new_year":             "Nyårsdagen",
        "holiday.sv.epiphany":             "Trettondedag jul",
        "holiday.sv.maundy_thursday":      "Skärtorsdagen",
        "holiday.sv.good_friday":          "Långfredagen",
        "holiday.sv.easter_sunday":        "Påskdagen",
        "holiday.sv.easter_monday":        "Annandag påsk",
        "holiday.sv.may_day":              "Första maj",
        "holiday.sv.ascension":            "Kristi himmelsfärdsdag",
        "holiday.sv.whit_sunday":          "Pingstdagen",
        "holiday.sv.national_day":         "Nationaldagen",
        "holiday.sv.midsummer_eve":        "Midsommarafton",
        "holiday.sv.midsummer_day":        "Midsommardagen",
        "holiday.sv.all_saints_eve":       "Dagen före Alla helgons dag",
        "holiday.sv.all_saints":           "Alla helgons dag",
        "holiday.sv.christmas_eve":        "Julafton",
        "holiday.sv.christmas_day":        "Juldagen",
        "holiday.sv.boxing_day":           "Annandag jul",
        "holiday.sv.new_years_eve":        "Nyårsafton",
        "holiday.sv.walpurgis":            "Valborgsmässoafton",

        # ── Helgdagsnamn – USA ────────────────────────────
        "holiday.us.new_year":             "Nyårsdagen",
        "holiday.us.mlk_day":              "Martin Luther King-dagen",
        "holiday.us.presidents_day":       "Presidents' Day",
        "holiday.us.memorial_day":         "Memorial Day",
        "holiday.us.juneteenth":           "Juneteenth",
        "holiday.us.independence_day":     "USA:s självständighetsdag",
        "holiday.us.labor_day":            "Labor Day",
        "holiday.us.columbus_day":         "Columbus Day",
        "holiday.us.veterans_day":         "Veterans Day",
        "holiday.us.thanksgiving":         "Thanksgiving",
        "holiday.us.national_freedom": "National Freedom Day",
        "holiday.us.groundhog": "Groundhog Day",
        "holiday.us.valentines": "Alla hjärtans dag",
        "holiday.us.st_patricks": "St. Patrick's Day",
        "holiday.us.april_fools": "Första april",
        "holiday.us.earth_day": "Jordens dag",
        "holiday.us.cinco_de_mayo": "Cinco de Mayo",
        "holiday.us.flag_day": "Flaggans dag (USA)",
        "holiday.us.patriot_day": "Patriot Day (11 september)",
        "holiday.us.constitution_day": "Konstitutionsdagen",
        "holiday.us.halloween": "Halloween",
        "holiday.us.pearl_harbor": "Minnesdagen för Pearl Harbor",
        "holiday.us.christmas_eve": "Julafton",
        "holiday.us.new_years_eve": "Nyårsafton",
        "holiday.us.mothers_day": "Mors dag (USA)",
        "holiday.us.armed_forces_day": "Armed Forces Day",
        "holiday.us.fathers_day": "Fars dag (USA)",
        "holiday.us.parents_day": "Föräldrarnas dag",
        "holiday.us.indigenous_peoples_day": "Urfolkens dag",
        "holiday.us.grandparents_day": "Mor- och farföräldrarnas dag",
        "holiday.us.black_friday": "Black Friday",
        "holiday.us.small_business_saturday": "Small Business Saturday",
        "holiday.us.cyber_monday": "Cyber Monday",
        "holiday.us.giving_tuesday": "Giving Tuesday",
        "holiday.us.election_day": "Valdagen (ordinarie federala val)",
        "holiday.us.mardi_gras": "Mardi Gras",
        "holiday.us.ash_wednesday": "Askonsdagen",
        "holiday.us.palm_sunday": "Palmsöndagen",
        "holiday.us.good_friday": "Långfredagen",
        "holiday.us.easter_sunday": "Påskdagen",
        "holiday.us.easter_monday": "Annandag påsk",
        "holiday.us.ascension": "Kristi himmelsfärds dag",
        "holiday.us.pentecost": "Pingstdagen",
        "holiday.sv.twentieth_day": "Tjugondag Knut",
        "holiday.sv.sami_day": "Samernas nationaldag",
        "holiday.sv.valentines": "Alla hjärtans dag",
        "holiday.sv.womens_day": "Internationella kvinnodagen",
        "holiday.sv.waffle_day": "Våffeldagen",
        "holiday.sv.april_fools": "Första april",
        "holiday.sv.earth_day": "Jordens dag",
        "holiday.sv.europe_day": "Europadagen",
        "holiday.sv.families_day": "Internationella familjedagen",
        "holiday.sv.cinnamon_bun_day": "Kanelbullens dag",
        "holiday.sv.un_day": "FN-dagen",
        "holiday.sv.halloween": "Halloween",
        "holiday.sv.gustav_adolf": "Gustav Adolfsdagen",
        "holiday.sv.nobel_day": "Nobeldagen",
        "holiday.sv.lucia": "Lucia",
        "holiday.sv.mothers_day": "Mors dag",
        "holiday.sv.fathers_day": "Fars dag",
        "holiday.sv.shrove_tuesday": "Fettisdagen",
        "holiday.sv.ash_wednesday": "Askonsdagen",
        "holiday.sv.palm_sunday": "Palmsöndagen",
        "holiday.sv.easter_eve": "Påskafton",
        "holiday.sv.whit_eve": "Pingstafton",
        "holiday.sv.whit_monday": "Annandag pingst",
        "holiday.sv.advent_1": "Första advent",
        "holiday.sv.advent_2": "Andra advent",
        "holiday.sv.advent_3": "Tredje advent",
        "holiday.sv.advent_4": "Fjärde advent",
        "calendar.observance_note_sv": "* Högtid/temadag eller afton, inte egen allmän helgdag. Rött visar allmän helgdag, inklusive söndag. Semestersummor ändras inte.",
        "calendar.observed_label": "{name} – ersättningsdag",
        "calendar.observance_note": "* Högtid/temadag, inte federal helgdag. Markeringen ändrar inte arbetsdagar. Ersättningsdagar anges separat.",
        "holiday.us.christmas":            "Juldagen",
        "holiday.us.new_year_observed":    "Nyårsdagen – ersättningsdag för nästa år",
        "holiday.us.washington_birthday":  "Washingtons födelsedag",
        "holiday.us.armistice_day":        "Stilleståndsdagen (Armistice Day)",
    },

    # ══════════════════════════════════════════════════════
    # ENGLISH
    # ══════════════════════════════════════════════════════
    "en": {
        # ── Menu bar ──────────────────────────────────────
        "menu.file":                       "&File",
        "menu.file.settings":              "&Settings...",
        "menu.file.autostart":             "&Start at login",
        "menu.file.autostart_tooltip":     "Start {app} automatically when you log in.",
        "menu.file.quit":                  "&Quit",
        "menu.view":                       "&View",
        "menu.view.hide_tab":              'Hide "{name}"',
        "menu.view.show_all":              "Show all hidden tabs",
        "menu.appearance":                 "&Appearance",
        "menu.help":                       "&Help",
        "menu.help.about":                 "&About {app}...",
        "menu.unknown_tab":                "Unknown",

        # ── Themes ────────────────────────────────────────
        "theme.dark":                      "&Dark theme",
        "theme.light":                     "&Light theme",
        "theme.system":                    "&System theme",
        "theme.dark.name":                 "Dark",
        "theme.contrast": "&High contrast",
        "theme.contrast.name": "High contrast",
        "calendar.tab": "Calendar",
        "calendar.title": "Calendar",
        "calendar.description": "Standalone calendar with holidays and local images. No employees or vacation periods. Weeks always start on Monday. PDF: landscape A4.",
        "calendar.year": "Year:",
        "calendar.per_page": "Months per PDF sheet:",
        "calendar.region": "Holiday region:",
        "calendar.months": "Months to export:",
        "calendar.export": "Generate PDF",
        "calendar.all_months": "Select all months",
        "calendar.select_months": "Select at least one month and 1, 2 or 3 months per sheet.",
        "calendar.no_holidays": "No named holidays this month.",
        "calendar.saved": "Calendar saved:\n{path}",
        "calendar.page": "Page {page} of {total}",
        "calendar.week": "Week",
        "season.settings": "PDF appearance…",
        "season.enable": "Seasonal colours and images in PDF",
        "season.monochrome": "Black-and-white PDF (grayscale)",
        "season.folder": "Choose image folder…",
        "season.no_folder": "No image folder selected",
        "season.no_image": "No image",
        "season.missing": "Image could not be read – PDF created without it.",
        "season.winter": "Winter",
        "season.spring": "Spring",
        "season.summer": "Summer",
        "season.autumn": "Autumn",

        "theme.light.name":                "Light",
        "theme.system.name":               "System",

        # ── Status bar ────────────────────────────────────
        "status.ready":                    "Ready",
        "status.tab_shown":                "Shown: {name}",
        "status.tab_hidden":               "Hidden: {name}",
        "status.active_tab":               "Active: {name}",
        "status.theme":                    "Theme: {name}",
        "status.language":                 "Language: {name}",

        # ── System tray ───────────────────────────────────
        "tray.show":                       "Show {app}",
        "tray.hide":                       "Hide",
        "tray.quit":                       "Quit",
        "tray.started_message":            "v{version} – running in the system tray",

        # ── About dialog ──────────────────────────────────
        "about.title":                     "About {app}",
        "about.body": (
            "<b>{app}</b> v{version}<br><br>"
            "Plugin-based desktop application<br>"
            "for vacation schedules, limo runs &amp; rent invoicing.<br><br>"
            "Built with Python {py_major}.{py_minor} and PySide6.<br><br>"
            "&copy; {year} Rickard Längkvist"
        ),

        # ── Autostart ─────────────────────────────────────
        "autostart.title":                 "Autostart",
        "autostart.enable":                "enable",
        "autostart.disable":               "disable",
        "autostart.error":                 "Could not {action} autostart.",
        "autostart.location":              "Location: {path}",
        "autostart.status_on":             "Enabled",
        "autostart.status_off":            "Disabled",

        # ── Common words ──────────────────────────────────
        "common.ok":                       "OK",
        "common.cancel":                   "Cancel",
        "common.save":                     "Save",
        "common.close":                    "Close",
        "common.error":                    "Error",
        "common.warning":                  "Warning",
        "common.info":                     "Information",
        "common.done":                     "Done",

        # ── Lists: employees, vehicles, tenants (v2.4.0) ───
        "lista.manage_list":               "Manage list…",
        "lista.manage_list.tooltip":       "Add, edit or remove entries in the list",
        "lista.list_count":                "{count} entries in the file",
        "lista.list_missing":              "{file} does not exist yet – it is created when you save",
        "lista.error.read":                "Could not read the list: {error}",
        "hyra.manage_tenants":             "Manage tenants…",
        "hyra.manage_tenants.tooltip":     "Add, edit or remove tenants",
        "roster.dialog.title":             "Manage {name}",
        "roster.header":                   "File: {path}",
        "roster.count":                    "{count} entries",
        "roster.section.number":           "Section {number}",
        "roster.button.add":               "Add",
        "roster.button.edit":              "Edit",
        "roster.button.remove":            "Remove",
        "roster.leave.hint":               "Days off are written after the name: Roland: 18/12 - 7/1 (or ; and |) – the start snaps to the nearest Monday and the end to the nearest Sunday; only crosses are shown in the table",
        "roster.button.up":                "Up",
        "roster.button.down":              "Down",
        "roster.button.up.tooltip":        "Move the entry one step up",
        "roster.button.down.tooltip":      "Move the entry one step down",
        "roster.button.sort":              "Sort A–Z",
        "roster.button.sort.tooltip":      "Sort the list alphabetically (Å, Ä, Ö after Z)",
        "roster.button.paste":             "Paste several…",
        "roster.button.paste.tooltip":     "Add many entries at once (one per line)",
        "roster.button.open_text":         "Open in text editor",
        "roster.button.open_text.tooltip": "Edit the file in Notepad/TextEdit",
        "roster.button.save":              "Save",
        "roster.button.cancel":            "Cancel",
        "roster.add.title":                "Add entry",
        "roster.add.prompt":               "Name (max {max} characters):",
        "roster.edit.title":               "Edit entry",
        "roster.edit.prompt":              "Name (max {max} characters):",
        "roster.remove.question":          "Remove {count} entries?",
        "roster.paste.title":              "Paste several",
        "roster.paste.prompt":             "One entry per line:",
        "roster.paste.result":             "{added} entries added, {skipped} skipped (duplicates, empty or too long).",
        "roster.info.created":             "The file was created: {path}",
        "roster.confirm.title":            "Unsaved changes",
        "roster.confirm.discard":          "There are unsaved changes. Do you want to save them?",
        "roster.warning.title":            "Check the list",
        "roster.warning.body":             "Please review the following:\n\n• {issues}\n\nSave anyway?",
        "roster.error.title":              "Could not handle the list",
        "roster.error.read":               "Could not read the list: {error}",
        "roster.error.too_long":           "The entry is too long (max {max} characters).",
        "roster.error.duplicate":          "\"{entry}\" already exists in the list.",
        "roster.open_failed":              "Could not open {path} in the text editor.",

        # ── Settings dialog (main window) ─────────────────
        "settings.title":                  "Settings",
        "settings.group.appearance":       "Language and appearance",
        "settings.language":               "Language:",
        "settings.language.tooltip": (
            "The language applies to the whole application, including the "
            "generated PDF files.\nThe change takes effect immediately."
        ),
        "settings.theme":                  "Theme:",
        "settings.group.holidays":         "Holidays",
        "settings.holiday_region":         "Holidays:",
        "settings.holiday_region.sv":      "Sweden (Swedish holidays)",
        "settings.holiday_region.us":      "United States (US holidays)",
        "settings.holiday_region.tooltip": (
            "Controls which days are marked red (public holiday) and green "
            "(half-day) in vacation schedules and limo run schedules."
        ),
        "settings.holiday_region.help": (
            "Red-letter days and half-days in the generated PDFs follow the selected country."
        ),
        "settings.group.window":           "Window and system tray",
        "settings.autostart":              "Start automatically at login",
        "settings.start_minimized":        "Start minimized in the system tray",
        "settings.minimize_to_tray":       "Minimize to the system tray",
        "settings.close_to_tray":          "Closing (X) minimizes to the system tray",
        "settings.notifications":          "Show notifications",
        "settings.group.plugins":          "Plugins",
        "settings.group.advanced":         "Advanced",
        "settings.debug_mode":             "Debug mode",
        "settings.log_to_file":            "Log to file",
        "settings.check_updates":          "Check for updates at startup",
        "settings.clear_cache_on_exit":    "Clear cache on exit",
        "settings.clear_cache_on_exit.tooltip": (
            "Logos rendered to image files are kept in the temp folder while "
            "the app runs. With this setting they are removed when the app "
            "closes – nothing is left behind, but the next start renders the "
            "logos again (a few tenths of a second per logo)."
        ),
        "settings.cache_size":             "Cache: {size}",
        "log.cache_cleared":               "Cache cleared: {summary}",
        "settings.group.data":             "Data",
        "settings.data_path":              "Settings are stored in:",
        "settings.plugin_restart_hint":    "Changing plugins requires a restart.",
        "settings.saved":                  "Settings saved.",
        "settings.no_plugins":             "No plugins found.",
        "settings.tab.general":            "General",
        "settings.tab.window":             "Window",
        "settings.tab.plugins":            "Plugins",
        "settings.tab.advanced":           "Advanced",
        "settings.save":                   "Save",
        "settings.cancel":                 "Cancel",
        "settings.notification_duration":  "Notification duration:",
        "settings.debug_mode.tooltip":     (
            "Writes more detailed information to the log "
            "(data/app.log). Used for troubleshooting."
        ),
        "settings.log_file":               "Log file:",
        "settings.open_log_folder":        "Open log folder",
        "settings.copy_log":               "Copy latest log",
        "settings.log_empty":              "The log is empty so far.",
        "settings.open_log_error":         "Could not open the folder:\n{error}",
        "settings.error_log_file":         "Error log ({count} lines): {path}",
        "settings.open_error_log":         "Open the error log",
        "settings.clear_error_log":        "Clear the error log",
        "settings.clear_error_log.tooltip": "Once the errors are fixed you can clear the error log – it is never archived automatically.",
        "settings.clear_error_log_confirm": "Clear the error log?\n\nThe errors in it will be removed from the file.",
        "settings.clear_error_log_failed":  "Could not clear the error log – the file may be locked by another program.",
        "settings.error_log_empty":         "The error log is empty – no errors logged.",
        "settings.save_error":             "Could not save the settings:\n{error}",
        "settings.autostart.unavailable":  "Autostart could not be read in this environment.",
        # ── Update from GitHub (v2.9.0) ───────────────────
        "update.group":                    "Update",
        "update.current":                  "Current version: {version}",
        "update.check":                    "Check for updates",
        "update.checking":                 "Checking for updates…",
        "update.available":                "New version {version} is available ({date}).",
        "update.latest":                   "You have the latest version ({version}).",
        "update.error":                    "Could not check: {error}",
        "update.install":                  "Update now",
        "update.downloading":              "Downloading… {percent} %",
        "update.installing":               "Installing…",
        "update.confirm_title":            "Update",
        "update.confirm":                  (
            "Update from {old} to {new}?\n\n"
            "Your lists, settings and logs are left untouched. The current "
            "program files are backed up in data/backup/."
        ),
        "update.done":                     (
            "Updated to {version} ({files} files).\n"
            "Backup: {backup}"
        ),
        "update.install_error":            "Could not update: {error}",
        "update.restart_title":            "Restart",
        "update.restart_question":         (
            "The update is complete. Restart Semesterlista now to use "
            "version {version}?"
        ),
        "update.restart_manual":           (
            "Restart the app manually to use the new version."
        ),
        "update.release_page":             "Open the release page",
        "update.notes":                    "Changes in the release:",
        "update.no_zip":                   "The release has no downloadable file.",
        "update.tray_title":               "Update available",
        "update.tray_body":                (
            "Semesterlista {version} is available on GitHub (you have {current})."
        ),
        "menu.help.check_updates":         "Check for &updates…",

        # ── Logging & errors (v2.8.0) ─────────────────────
        "log.started":                     "Logging started: {path}",
        "log.file_missing":                "{module} is missing – {feature} is disabled.",
        "log.import_failed":               "Could not import {module}: {error}",
        "log.crash_title":                 "An error occurred",
        "log.crash_body":                  (
            "The application encountered an error.\n\n"
            "{error}\n\nLog file: {log}"
        ),

        # ── Page layout (v2.6.0) ──────────────────────────
        "lista.orientation":               "Page layout:",
        "lista.company_name": "Company name in PDF",
        "vacation.title": "Vacation calendar…",
        "vacation.year": "Summary year:",
        "vacation.person": "Employee",
        "vacation.total": "Vacation days this year",
        "vacation.start": "First vacation day",
        "vacation.end": "Last vacation day",
        "vacation.add": "Add selected period",
        "vacation.remove": "Remove selected period",
        "vacation.invalid_dates": "End date cannot precede start date.",
        "vacation.changed": "The list file has changed. Reopen the calendar before saving.",
        "vacation.note": "Summary: Monday–Friday, excluding official holidays in the selected region. Half-days count as one day. Overlaps count once. Calendar dates are saved exactly without week rounding. This is planning, not payroll accounting.",
        "hyra.quarter.send_by": "Send by:\n{date}",
        "hyra.quarter.paid_by": "Paid by:\n{date}",

        "lista.pdf.small_text.title": "Small text in PDF",
        "lista.pdf.small_text.message": "The smallest text will be approximately {size} points on page(s) {pages} (below 6 points) and may be difficult to read.\n\nYou selected {months} months per sheet. Choose fewer months or a shorter list for larger text.\n\nCreate the PDF with your current selection anyway?",
        "lista.orientation.auto": "Automatic: 1 month = portrait A4, 2–3 = landscape A4",
        "lista.orientation.landscape":     "Landscape (A4)",
        "lista.orientation.portrait":      "Portrait (A4)",

        # ── Tabs: Rent, Vacation, Vehicles ────────────────
        "fordon.tab_name":                 "Vehicles",
        "fordon.plugin_description":       "Limo run schedules per vehicle as PDF",
        "fordon.title":                    "\U0001F697 Vehicle Schedule",
        "fordon.description":              "Generate limo run schedules per vehicle as PDF",

        # ── Logo in PDF ───────────────────────────────────
        "logo.label":                      "Logo:",
        "logo.no_logo":                    "No logo",
        "logo.choose":                     "Choose logo…",
        "logo.clear":                      "Remove",
        "logo.browse":                     "Browse…",
        "logo.rescan":                     "Refresh",
        "logo.dialog_title":               "Choose logo",
        "logo.dialog_hint":                "Images from the assets folder and its subfolders. Only SVG is listed – use the button for EPS, PDF and PNG/JPG.",
        "logo.preview":                    "Preview",
        "logo.folder":                     "Folder: {path}",
        "logo.assets":                     "Images in assets:",
        "logo.empty":                      "No images found in the assets folder.",
        "logo.outside_assets":             "outside assets",
        "logo.missing":                    "File not found: {path}",
        "logo.error":                      "Could not read the logo: {error}",
        "logo.ok":                         "Use",
        "logo.cancel":                     "Cancel",
        "logo.selected":                   "Logo: {name}",
        "logo.missing_file":               "Missing: {path}",
        "logo.insert":                     "Insert logo…",
        "logo.insert_tooltip":             "Insert a logo: SVG, EPS or PDF (PNG/JPG also work). EPS requires Ghostscript.",
        "logo.rescan_tooltip":             "Scan the assets folder and its subfolders again.",
        "logo.auto_size":                  "The size adapts automatically – in the preview and in the PDF.",
        "logo.size_label":                 "Size:",
        "logo.size_hint":                  "Proportions are always kept.",
        "logo.size_tooltip":               "Logo size in the PDF and in the preview. 100 % = automatic size.",
        "logo.filter_all":                 "Logos",
        "logo.filter_images":              "Images",
        "logo.filter_any":                 "All files",
        "tray.settings":                   "Settings…",
        "tray.check_updates":              "Check for updates…",
        "tray.about":                      "About {app} v{version}…",

        # ── Vacation schedule & Limo runs ─────────────────
        "lista.tab_name":                  "Vacation Schedule",
        "lista.plugin_description":        "Vacation schedules and limo run schedules as PDF",
        "lista.window_title":              "Settings – Vacation Schedule",
        "lista.title":                     "📅 Vacation Schedule",
        "lista.description":               "Generate PDF vacation schedule lists",
        "lista.group.settings":            "Settings",
        "lista.group.legend":              "Colour key in the PDF",
        "lista.mode":                      "Mode:",
        "lista.mode.semesterlista":        "Vacation schedule",
        "lista.mode.limo":                 "Limo runs",
        "lista.year":                      "Year:",
        "lista.start_month":               "Start month:",
        "lista.months_per_page":           "Months per page:",
        "lista.file.employees":            "Employee file:",
        "lista.file.vehicles":             "Vehicle file:",
        "lista.file.browse_tooltip":       "Select a text file with names or vehicles",
        "lista.button.generate":           "🖨️ Generate PDF",
        "lista.button.tests":              "🧪 Run tests",
        "lista.button.open_documents":     "📁 Open Documents folder",
        "lista.button.browse":             "Browse...",
        "lista.settings.auto_open":        "Open PDF automatically:",
        "lista.settings.default_mode":     "Default mode:",
        "lista.settings.months_per_page":  "Months per page:",
        "lista.settings.start_month":      "Default start month:",
        "lista.settings.saved":            "Settings saved!",
        "lista.start_month.standard":      "Default (January)",
        "lista.start_month.tooltip": (
            "Default (January) = Jan–Dec of the selected year.\n"
            "If you pick a month manually, 12 months are generated from\n"
            "that month and the period may span the turn of the year,\n"
            "e.g. Dec 2026 → Jan 2027."
        ),
        "lista.file_dialog.title":         "Select file",
        "lista.file_dialog.filter":        "Text files (*.txt);;All files (*.*)",
        "lista.pdf.title_prefix.semesterlista": "Vacation schedule",
        "lista.pdf.title_prefix.limo":     "Limo run schedule",
        "lista.pdf.header.employees":      "Employee",
        "lista.pdf.header.vehicles":       "Vehicle",
        "lista.pdf.period_standard":       "Default (January)",
        "lista.pdf.done_title":            "Done",
        "lista.pdf.done_body": (
            "{title} has been generated!\n\n"
            "Period: {range}\n"
            "File: {filename}\n"
            "Start: {start}\n"
            "Months per page: {months}"
        ),
        "lista.pdf.error_title":           "Error",
        "lista.pdf.error_body":            "Error generating PDF: {error}",
        "lista.pdf.legend.red":            "Red = public holiday or Sunday",
        "lista.pdf.legend.blue":           "Blue = Saturday",
        "lista.pdf.legend.green":          "Green = half-day (Midsummer Eve, Christmas Eve etc.)",
        "lista.pdf.legend.orange":         "Orange = new week",
        "lista.pdf.legend.leave":          "Grey = on leave",
        "lista.pdf.legend.red_us":         "Red = US public holiday (incl. observed date) or Sunday",
        "lista.pdf.legend.green_us":       "Green = half-day (not used for the US)",
        "lista.legend.red":                "Red = public holidays and Sundays (New Year, Easter, Midsummer Day, Christmas, etc.)",
        "lista.legend.blue":               "Blue = Saturdays",
        "lista.legend.green":              "Green = half-days (Midsummer Eve, Christmas Eve, New Year's Eve, Maundy Thursday, Walpurgis Night, day before All Saints' Day)",
        "lista.legend.orange":             "Orange line = new week",
        "lista.legend.leave":              "Grey with × = on leave (set in the list after the name, e.g. 18/12 – 7/1)",
        "lista.legend.red_us":             "Red = US public holidays and Sundays (Thanksgiving, Independence Day, Christmas, etc.)",
        "lista.legend.green_us":           "Green = half-days (not used for the US – US holidays falling on a weekend become red on the observed date instead)",
        "lista.msg.year_invalid":          "Invalid year. Enter a valid whole number",
        "lista.msg.year_range":            "Year must be between 1900 and 2100",
        "lista.msg.file_empty":            "File name cannot be empty",
        "lista.msg.file_missing":          "The file '{path}' does not exist",
        "lista.msg.mode_invalid":          "Invalid mode",
        "lista.msg.no_data":               "No data found in {path}",
        "lista.msg.read_error":            "Error reading file: {error}",
        "lista.week_prefix":               "W",
        "lista.tests.title":               "Test results",
        "lista.tests.heading":             "Test results – Vacation Schedule & Limo Runs v{version} ({language})",
        "lista.tests.ok":                  "✅ OK",
        "lista.tests.fail":                "❌ Failed",
        "lista.tests.1":                   "1. Invalid year",
        "lista.tests.2":                   "2. Year out of range",
        "lista.tests.3":                   "3. Invalid mode",
        "lista.tests.4":                   "4. Leap year handling",
        "lista.tests.5":                   "5. Swedish holidays",
        "lista.tests.6":                   "6. Midsummer Eve = green (not red)",
        "lista.tests.7":                   "7. Christmas Eve = green",
        "lista.tests.8":                   "8. Easter calculation 2024",
        "lista.tests.9":                   "9. Default mode = Jan–Dec same year",
        "lista.tests.10":                  "10. December → January across the new year",
        "lista.tests.11":                  "11. US holidays (Thanksgiving etc.)",
        "lista.tests.12":                  "12. Holiday region follows Settings",

        # ── Rent invoicing ────────────────────────────────
        "hyra.tab_name":                   "Rent",
        "hyra.plugin_description":         "Rent lists with empty check boxes as PDF",
        "hyra.title":                      "🏠 Rent Invoicing",
        "hyra.year":                       "Year:",
        "hyra.file":                       "📁 File: {file}",
        "hyra.button.edit":                "📝 Edit",
        "hyra.button.reload":              "🔄 Reload",
        "hyra.button.generate":            "🖨️ Generate PDF",
        "hyra.button.edit_file":           "📝 Edit {file}",
        "hyra.tooltip.edit_file":          "Open {file} in your text editor",
        "hyra.tooltip.edit_std":           "Open the text file in the default editor",
        "hyra.tooltip.reload":             "Reload tenants from file",
        "hyra.tooltip.generate":           "Generate the rent list as a PDF",
        "hyra.quarter.panel":              "📅 Quarterly invoices – send by",
        "hyra.quarter.send":               "Send by: {date}",
        "hyra.status.passed":              "Passed",
        "hyra.status.today":               "TODAY!",
        "hyra.status.days":                "{days} days",
        "hyra.invoice_date":               "{month} 1",
        "hyra.tenants.monthly":            "Monthly tenants",
        "hyra.tenants.quarterly":          "Quarterly tenants",
        "hyra.tenants.empty":              "No tenants\n\nEdit {file}",
        "hyra.tenants.total":              "Total: {count}",
        "hyra.pdf.title":                  "Rent list {year}",
        "hyra.pdf.quarter_header":         "Quarterly invoices – send by:",
        "hyra.pdf.quarter_cell":           "Q{quarter}: {month} 1\n({period})",
        "hyra.pdf.tenant_header":          "Tenant",
        "hyra.pdf.monthly_section":        "Monthly tenants",
        "hyra.pdf.quarterly_section":      "Quarterly tenants",
        "hyra.pdf.footer":                 "Generated: {timestamp}",
        "hyra.pdf.done_title":             "Done",
        "hyra.pdf.done_body":              "PDF generated!\n\n{filename}",
        "hyra.pdf.no_tenants":             "No tenants!\n\nEdit {file} first.",
        "hyra.pdf.error_title":            "Error",
        "hyra.pdf.error_body":             "Could not generate PDF:\n{error}",
        "hyra.reload.done_title":          "Done",
        "hyra.reload.done_body":           "Tenants reloaded!\n\nMonthly: {monthly}\nQuarterly: {quarterly}",
        "hyra.file_open_error":            "Could not open file:\n{error}",

        # ── Holiday names – Sweden ────────────────────────
        "holiday.sv.new_year":             "New Year's Day",
        "holiday.sv.epiphany":             "Epiphany",
        "holiday.sv.maundy_thursday":      "Maundy Thursday",
        "holiday.sv.good_friday":          "Good Friday",
        "holiday.sv.easter_sunday":        "Easter Sunday",
        "holiday.sv.easter_monday":        "Easter Monday",
        "holiday.sv.may_day":              "May Day",
        "holiday.sv.ascension":            "Ascension Day",
        "holiday.sv.whit_sunday":          "Whit Sunday",
        "holiday.sv.national_day":         "National Day of Sweden",
        "holiday.sv.midsummer_eve":        "Midsummer Eve",
        "holiday.sv.midsummer_day":        "Midsummer Day",
        "holiday.sv.all_saints_eve":       "Day before All Saints' Day",
        "holiday.sv.all_saints":           "All Saints' Day",
        "holiday.sv.christmas_eve":        "Christmas Eve",
        "holiday.sv.christmas_day":        "Christmas Day",
        "holiday.sv.boxing_day":           "Boxing Day",
        "holiday.sv.new_years_eve":        "New Year's Eve",
        "holiday.sv.walpurgis":            "Walpurgis Night",

        # ── Holiday names – USA ───────────────────────────
        "holiday.us.new_year":             "New Year's Day",
        "holiday.us.mlk_day":              "Martin Luther King Jr. Day",
        "holiday.us.presidents_day":       "Presidents' Day",
        "holiday.us.memorial_day":         "Memorial Day",
        "holiday.us.juneteenth":           "Juneteenth",
        "holiday.us.independence_day":     "Independence Day",
        "holiday.us.labor_day":            "Labor Day",
        "holiday.us.columbus_day":         "Columbus Day",
        "holiday.us.veterans_day":         "Veterans Day",
        "holiday.us.thanksgiving":         "Thanksgiving Day",
        "holiday.us.national_freedom": "National Freedom Day",
        "holiday.us.groundhog": "Groundhog Day",
        "holiday.us.valentines": "Valentine's Day",
        "holiday.us.st_patricks": "St. Patrick's Day",
        "holiday.us.april_fools": "April Fools' Day",
        "holiday.us.earth_day": "Earth Day",
        "holiday.us.cinco_de_mayo": "Cinco de Mayo",
        "holiday.us.flag_day": "Flag Day",
        "holiday.us.patriot_day": "Patriot Day",
        "holiday.us.constitution_day": "Constitution Day",
        "holiday.us.halloween": "Halloween",
        "holiday.us.pearl_harbor": "Pearl Harbor Remembrance Day",
        "holiday.us.christmas_eve": "Christmas Eve",
        "holiday.us.new_years_eve": "New Year's Eve",
        "holiday.us.mothers_day": "Mother's Day",
        "holiday.us.armed_forces_day": "Armed Forces Day",
        "holiday.us.fathers_day": "Father's Day",
        "holiday.us.parents_day": "Parents' Day",
        "holiday.us.indigenous_peoples_day": "Indigenous Peoples' Day",
        "holiday.us.grandparents_day": "Grandparents Day",
        "holiday.us.black_friday": "Black Friday",
        "holiday.us.small_business_saturday": "Small Business Saturday",
        "holiday.us.cyber_monday": "Cyber Monday",
        "holiday.us.giving_tuesday": "Giving Tuesday",
        "holiday.us.election_day": "Election Day (regular federal elections)",
        "holiday.us.mardi_gras": "Mardi Gras",
        "holiday.us.ash_wednesday": "Ash Wednesday",
        "holiday.us.palm_sunday": "Palm Sunday",
        "holiday.us.good_friday": "Good Friday",
        "holiday.us.easter_sunday": "Easter Sunday",
        "holiday.us.easter_monday": "Easter Monday",
        "holiday.us.ascension": "Ascension Day",
        "holiday.us.pentecost": "Pentecost",
        "holiday.sv.twentieth_day": "St. Knut’s Day",
        "holiday.sv.sami_day": "Sámi National Day",
        "holiday.sv.valentines": "Valentine’s Day",
        "holiday.sv.womens_day": "International Women’s Day",
        "holiday.sv.waffle_day": "Waffle Day",
        "holiday.sv.april_fools": "April Fools’ Day",
        "holiday.sv.earth_day": "Earth Day",
        "holiday.sv.europe_day": "Europe Day",
        "holiday.sv.families_day": "International Day of Families",
        "holiday.sv.cinnamon_bun_day": "Cinnamon Bun Day",
        "holiday.sv.un_day": "United Nations Day",
        "holiday.sv.halloween": "Halloween",
        "holiday.sv.gustav_adolf": "Gustav Adolf Day",
        "holiday.sv.nobel_day": "Nobel Day",
        "holiday.sv.lucia": "Saint Lucia’s Day",
        "holiday.sv.mothers_day": "Mother’s Day (Sweden)",
        "holiday.sv.fathers_day": "Father’s Day (Sweden)",
        "holiday.sv.shrove_tuesday": "Shrove Tuesday",
        "holiday.sv.ash_wednesday": "Ash Wednesday",
        "holiday.sv.palm_sunday": "Palm Sunday",
        "holiday.sv.easter_eve": "Holy Saturday",
        "holiday.sv.whit_eve": "Pentecost Eve",
        "holiday.sv.whit_monday": "Whit Monday",
        "holiday.sv.advent_1": "First Sunday of Advent",
        "holiday.sv.advent_2": "Second Sunday of Advent",
        "holiday.sv.advent_3": "Third Sunday of Advent",
        "holiday.sv.advent_4": "Fourth Sunday of Advent",
        "calendar.observance_note_sv": "* Observance or holiday eve, not a public holiday in its own right. Red marks public holidays, including Sundays. Vacation totals are unchanged.",
        "calendar.observed_label": "{name} – observed day",
        "calendar.observance_note": "* Observance, not a federal holiday. This marker does not change working days. Observed holidays are labelled separately.",
        "holiday.us.christmas":            "Christmas Day",
        "holiday.us.new_year_observed":    "New Year's Day – observed for next year",
        "holiday.us.washington_birthday":  "Washington's Birthday",
        "holiday.us.armistice_day":        "Armistice Day",
    },
}


# ══════════════════════════════════════════════════════════
# PLUGIN-NAMN
# ══════════════════════════════════════════════════════════
#
# Pluginens interna namn (från plugins.json) är på svenska och används
# som nyckel i inställningarna. Den TEXT som visas i tabbar, menyer och
# inställningsdialogen översätts via nedanstående tabell.
#
PLUGIN_NAME_KEYS: Dict[str, str] = {
    "Semesterlista & Limokörning": "lista.tab_name",
    "Hyresfakturering":            "hyra.tab_name",
    "Semesterlista":               "lista.tab_name",
    "Hyra":                        "hyra.tab_name",
    "Fordon":                      "fordon.tab_name",
    "Kalender":                    "calendar.tab",
}

# Mappnamn i plugins/ → internt plugin-namn
PLUGIN_FOLDER_NAMES: Dict[str, str] = {
    "lista":   "Semesterlista",
    "hyra":    "Hyra",
    "fordon":  "Fordon",
    "kalender": "Kalender",
}


def plugin_display_name(plugin_name: str) -> str:
    """
    Översatt visningsnamn för en plugin.

    Saknas en översättning returneras pluginens namn oförändrat,
    så att nya plugins fungerar utan ändringar i i18n-modulen.
    """
    key = PLUGIN_NAME_KEYS.get(plugin_name)
    if key is None:
        return plugin_name
    return t(key)


def escape_mnemonics(text: str) -> str:
    """
    Gör text säker för Qt-widgets som tolkar & som snabbvalsnyckel.

    QTabBar, QAction, QCheckBox, QPushButton och QGroupBox tolkar "&"
    som snabbvalsnyckel: "Semesterlista & Limokörning" visas som
    "Semesterlista _Limokörning" (ampersanden göms och nästa bokstav
    stryks under). Dubblar man tecknet ("&&") visas ett vanligt &.

    Använd på text som skickas till QTabWidget.setTabText(),
    QAction(...), QCheckBox(...) m.fl. – t.ex. plugin-namn.

    Args:
        text: Text som ska visas.

    Returns:
        str: Texten med & dubblerade.

    Exempel:
        escape_mnemonics("Semesterlista & Limokörning")
        → "Semesterlista && Limokörning"
    """
    return text.replace("&", "&&")


def plugin_display_name_qt(plugin_name: str) -> str:
    """
    Som plugin_display_name(), men säker att lägga direkt i en
    Qt-widget som tolkar snabbvalsnycklar (t.ex. flikar och kryssrutor).
    """
    return escape_mnemonics(plugin_display_name(plugin_name))


# ══════════════════════════════════════════════════════════
# TRANSLATOR
# ══════════════════════════════════════════════════════════

class Translator(QObject):
    """
    Håller aktuellt språk och slår upp texter.

    Signal:
        language_changed(str): emitteras när språket byts.

    Exempel:
        tr = Translator("sv")
        tr.t("menu.file")            # "&Arkiv"
        tr.set_language("en")
        tr.t("menu.file")            # "&File"
    """

    language_changed = Signal(str)

    def __init__(self, language: str = DEFAULT_LANGUAGE):
        super().__init__()
        if language not in TRANSLATIONS:
            language = FALLBACK_LANGUAGE
        self._language: str = language

    # ──────────────────────────────────────────────────────
    # Språk
    # ──────────────────────────────────────────────────────

    @property
    def language(self) -> str:
        """Aktuell språkkod: 'sv' eller 'en'."""
        return self._language

    def set_language(self, language: str) -> None:
        """
        Byt språk och emittera language_changed.

        Ogiltig kod ignoreras (språket behålls oförändrat).
        """
        if language not in TRANSLATIONS:
            logger.warning(f"Okänt språk: {language!r} – behåller {self._language}")
            return

        if language == self._language:
            return

        self._language = language
        logger.info(f"Språk ändrat till: {language}")
        self.language_changed.emit(language)

    def language_name(self, code: Optional[str] = None) -> str:
        """Visningsnamn för ett språk, t.ex. 'Svenska'."""
        return LANGUAGES.get(code or self._language, code or self._language)

    # ──────────────────────────────────────────────────────
    # Uppslag
    # ──────────────────────────────────────────────────────

    def t(self, key: str, **kwargs: Any) -> str:
        """
        Slå upp en text på aktuellt språk.

        Args:
            key:    Nyckel, t.ex. "menu.file".
            kwargs: Värden för platshållare i texten.

        Returns:
            Översatt text. Saknas nyckeln returneras nyckeln själv
            och en varning loggas (så att inget kraschar).
        """
        text = TRANSLATIONS.get(self._language, {}).get(key)

        if text is None:
            # Reservspråket först, sedan nyckeln själv
            text = TRANSLATIONS.get(FALLBACK_LANGUAGE, {}).get(key)
            if text is None:
                logger.warning(f"Saknad översättning: {key!r}")
                return key

        if not kwargs:
            return text

        try:
            return text.format(**kwargs)
        except (KeyError, IndexError) as e:
            logger.warning(f"Kunde inte formatera {key!r}: {e}")
            return text

    # ──────────────────────────────────────────────────────
    # Datumnamn
    # ──────────────────────────────────────────────────────

    def month_name(self, month: int, short: bool = False, lower: bool = False) -> str:
        """Månadsnamn 1–12. lower=True ger gemener ('december')."""
        names = MONTH_NAMES[self._language]
        if lower:
            key = "lower"
        elif short:
            key = "short"
        else:
            key = "long"
        try:
            return names[key][month - 1]
        except IndexError:
            return str(month)

    def month_names(self, short: bool = False, lower: bool = False) -> List[str]:
        """Alla 12 månadsnamn i ordning."""
        return [self.month_name(m, short=short, lower=lower) for m in range(1, 13)]

    def month_options(self, standard_label: Optional[str] = None) -> List[str]:
        """
        Lista för startmånads-dropdown.

        Index 0 = standardläge, index 1–12 = månad.
        """
        head = standard_label if standard_label is not None else self.t("lista.start_month.standard")
        return [head] + self.month_names()

    def weekday_short(self, weekday: int) -> str:
        """Kort veckodagsnamn, 0 = måndag ... 6 = söndag."""
        try:
            return WEEKDAY_NAMES[self._language]["short"][weekday]
        except IndexError:
            return ""

    def weekday_short_names(self) -> List[str]:
        """Alla korta veckodagsnamn, måndag först."""
        return list(WEEKDAY_NAMES[self._language]["short"])

    def weekday_long(self, weekday: int) -> str:
        """Långt veckodagsnamn, 0 = måndag ... 6 = söndag."""
        try:
            return WEEKDAY_NAMES[self._language]["long"][weekday]
        except IndexError:
            return ""

    def format_date(self, value: date) -> str:
        """'5 april 2026' (sv) eller 'April 5, 2026' (en)."""
        if self._language == "en":
            return f"{self.month_name(value.month)} {value.day}, {value.year}"
        return f"{value.day} {self.month_name(value.month, lower=True)} {value.year}"

    def holiday_name(self, holiday_key: str) -> str:
        """
        Namn på en helgdag.

        Args:
            holiday_key: T.ex. "sv.thanksgiving" eller "us.mlk_day"
                         (se core/holidays.py).
        """
        return self.t(f"holiday.{holiday_key}")


# ══════════════════════════════════════════════════════════
# MODUL-SINGLETON
# ══════════════════════════════════════════════════════════

_translator: Optional[Translator] = None


def init(settings_manager: Optional["SettingsManager"] = None) -> Translator:
    """
    Initiera i18n-modulen (anropas en gång vid appstart).

    Läser språket från SettingsManager om en sådan anges,
    annars används standardspråket (svenska).

    Args:
        settings_manager: Applikationens SettingsManager (valfritt).

    Returns:
        Translator-instansen.
    """
    global _translator

    language = DEFAULT_LANGUAGE
    if settings_manager is not None:
        try:
            language = settings_manager.get("language", DEFAULT_LANGUAGE)
        except Exception as e:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte läsa språk: {e}")

    _translator = Translator(language or DEFAULT_LANGUAGE)
    return _translator


def get_translator() -> Translator:
    """
    Hämta Translator-instansen (skapar en svensk om ingen finns).

    Anropas av t()/set_language() och av plugin-koden.
    """
    global _translator
    if _translator is None:
        _translator = Translator(DEFAULT_LANGUAGE)
    return _translator


def t(key: str, **kwargs: Any) -> str:
    """Genväg till aktuell översättning: t("menu.file")."""
    return get_translator().t(key, **kwargs)


def set_language(language: str) -> None:
    """Genväg: byt språk (emitterar language_changed)."""
    get_translator().set_language(language)


def current_language() -> str:
    """Aktuell språkkod ('sv' eller 'en')."""
    return get_translator().language


def month_name(month: int, short: bool = False, lower: bool = False) -> str:
    """Genväg: månadsnamn på aktuellt språk."""
    return get_translator().month_name(month, short=short, lower=lower)


def month_names(short: bool = False, lower: bool = False) -> List[str]:
    """Genväg: alla månadsnamn på aktuellt språk."""
    return get_translator().month_names(short=short, lower=lower)


def month_options(standard_label: Optional[str] = None) -> List[str]:
    """Lista för startmånads-dropdown (index 0 = standard, 1–12 = månad)."""
    return get_translator().month_options(standard_label)

def weekday_short_names() -> List[str]:
    """Genväg: korta veckodagsnamn på aktuellt språk."""
    return get_translator().weekday_short_names()


def holiday_name(holiday_key: str) -> str:
    """Genväg: helgdagsnamn på aktuellt språk."""
    return get_translator().holiday_name(holiday_key)


def get_version() -> str:
    """Returnera modulversionen."""
    return MODULE_VERSION
