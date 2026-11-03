# Semesterlista

En liten Windows-app (PySide6) som skriver ut **semesterlistor**, **limokörningsscheman** och **hyresfakturor** som PDF – körs i systemfältet och kommer ihåg allt mellan gångerna.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Licens](https://img.shields.io/badge/licens-MIT-green)

---

## Vad appen gör

| Flik | Innehåll |
|------|----------|
| **Hyra** | Månads- och kvartalshyresgäster, kvartalsöversikt, PDF med tomma kryssrutor |
| **Semesterlista** | Semester- och limokörningsschema, 1–3 månader per blad, liggande eller stående A4 |
| **Fordon** | Samma schema som Semesterlista men låst till limokörning |

Alla tre flikarna kan ha **egen logotyp** (SVG) som ritas automatiskt skalenligt
i PDF:ens hörn – väljs i en dropdown med bilderna i `assets/` och dess undermappar.

## Funktioner

- **PDF-export** med färgkodning (helgdagar, lördagar, halvdagar, veckonummer),
  valbar startmånad (även över årsskifte) och 1, 2 eller 3 månader per blad.
- **Egna listor** (`Anställda.txt`, `Fordon.txt`, `Hyresgäster.txt`) som redigeras
  direkt i appen – kommentarer, blandade teckenkodningar och dubbletter hanteras.
- **Logotyp** per flik: dropdown med SVG:er från `assets/` + undermappar,
  förhandsgranskning och automatiskt anpassad storlek i PDF:en
  (15 % av sidbredden / 8 % av sidhöjden, proportionerna bevaras).
- **Systray**: startar minimerat, vänsterklick visar/döljer, högerklick ger
  *Visa*, *Dölj*, *Inställningar…*, *Sök efter uppdatering…*, *Om…* och *Avsluta*.
- **Uppdatering från GitHub Releases** med knapp i appen, säkerhetskopia i
  `data/backup/` och automatisk omstart – dina listor och inställningar rörs aldrig.
- **Smart cache**: rastrerade logotyper cachas under körningen i `%TEMP%/Semesterlista`
  och **städas automatiskt när appen avslutas** (kan stängas av i
  *Inställningar → Avancerat*). Vid start rensas bara gammalt skräp, så en
  omstart inte tvingar fram nya renderingar.
- **Loggning** till `data/app.log` (roterande, 2 MB × 5) och `data/crash.log`.
- **Teman**: ljust, mörkt eller följ systemet. Svenska och engelska.

## Installation

```bash
git clone https://github.com/Tokke2/Semesterlista.git
cd Semesterlista
python -m pip install -r requirements.txt
python main.pyw
```

Kräver **Python 3.10+** och beroendena i [`requirements.txt`](requirements.txt)
(PySide6, reportlab). På Windows startas appen enklast med `pythonw main.pyw`
(eller en genväg till `main.pyw`) så slipper du terminalfönstret.

### Uppdatera

Appen kan uppdatera sig själv: **Hjälp → Sök efter uppdatering…** (eller
*Sök efter uppdatering…* i systemfältets meny). Den hämtar senaste releasen från
GitHub, säkerhetskopierar de filer som ersätts och startar om.

## Utveckling

```bash
python -m unittest discover -s tests -v     # hela testsviten (utan Qt hoppas Qt-testerna över)
python tools/bump_version.py --check        # kontrollera att versionen är synkad
python tools/bump_version.py 2.12.0         # höj versionen på alla ställen
python tools/make_icons.py                  # rita om ikonerna i assets/ikon
```

### Struktur

```
main.pyw              startfönster, meny, systemfält
core/                 i18n, inställningar, PDF-tillgångar, uppdatering, loggning, cache …
plugins/hyra          hyresfakturering
plugins/lista         semesterlista + limokörning (Fordon ärver denna)
plugins/fordon        låst läge för limokörning
assets/               ikoner och logotyper (logotyper väljs i appen)
tests/                unittest-svit som körs utan nätverk
tools/                bump_version.py, make_icons.py
spec.md               fullständig teknisk specifikation
FORSLAG.md            förslag på kommande funktioner
```

## Felsökning

| Symptom | Åtgärd |
|---------|--------|
| Ingenting händer vid start | Starta från terminal: `python main.pyw` och läs felmeddelandet |
| Appen syns inte | Den startar i systemfältet – klicka på ikonen |
| PDF:en blir tom/fel | Kontrollera listfilen i fliken, se `data/app.log` |
| Uppdateringen hittar inget | Kolla nätet och att det finns en publik release |

Loggfilens sökväg visas i **Inställningar → Avancerat**.

## Licens

MIT – se [LICENSE](LICENSE).
