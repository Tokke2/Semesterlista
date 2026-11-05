# Semesterlista

En liten Windows-app (PySide6) som skriver ut **semesterlistor**, **limokörningsscheman** och **hyresfakturor** som PDF – körs i systemfältet och kommer ihåg allt mellan gångerna.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Licens](https://img.shields.io/badge/licens-MIT-green)

---

## Vad appen gör

| Flik | Innehåll |
|------|----------|
| **Hyra** | Månads- och kvartalshyresgäster, kvartalsöversikt, PDF med tomma kryssrutor |
| **Semesterlista** | Semester- och limokörningsschema, 1–3 månader per blad, automatisk A4-orientering |
| **Fordon** | Samma schema som Semesterlista men låst till limokörning |

Alla tre flikarna kan ha **egen logotyp** (SVG, EPS eller PDF) som ritas
automatiskt skalenligt i PDF:ens hörn – väljs i en dropdown med bilderna i
`assets/` och dess undermappar, eller infogas med *Infoga logotyp…*.

## Funktioner

- **Anpassade inställningar:** fönstret anpassar startstorleken till skärmens arbetsyta.
  Flikarna kan rullas på mindre skärmar; Spara och Avbryt ligger utanför rullningen.

- **PDF-export** med färgkodning (helgdagar, lördagar, halvdagar, veckonummer),
  valbar startmånad (även över årsskifte) och 1, 2 eller 3 månader per blad.
  **1 månad = stående A4; 2–3 = liggande A4.** Valda månader hålls på samma
  blad och skalas ned vid behov; mycket långa listor får mindre text.
- **Helgdagsregion** i appens inställningar styr Sverige/USA i semester- och
  fordonsscheman (USA använder federala observed-datum, inga halvdagar).
- **Sidhuvud/sidfot i scheman:** företagsnamn (anges i flikens inställningar),
  utskriftsdatum och ”Sida X av Y”.
- **Egna listor** (`Anställda.txt`, `Fordon.txt`, `Hyresgäster.txt`) som redigeras
  direkt i appen – kommentarer, blandade teckenkodningar och dubbletter hanteras.
- **Logotyp** per flik: dropdown med SVG:er från `assets/` + undermappar och
  *Infoga logotyp…* för **SVG, EPS, PDF, PNG och JPG**. Förhandsgranskning,
  automatiskt anpassad storlek i PDF:en (15 % av sidbredden / 8 % av
  sidhöjden) och ett **storleksreglage 25–300 %** – proportionerna bevaras
  alltid. EPS kräver Ghostscript och PDF kräver PyMuPDF (frivilliga paket).
- **Systray**: startar minimerat, vänsterklick visar/döljer, högerklick ger
  *Visa*, *Dölj*, *Inställningar…*, *Sök efter uppdatering…*, *Om…* och *Avsluta*.
- **Uppdatering från GitHub Releases**: en manuell sökning som hittar en ny version
  öppnar en Ja/Nej-dialog direkt. Nej är förvalt; ingen installation sker utan Ja.
  Uppdateringen har säkerhetskopia i
  `data/backup/` och automatisk omstart – dina listor och inställningar rörs aldrig.
- **Lediga dagar**: skriv `Roland: 18/12 - 7/1` (eller `;` / `|`) i `Anställda.txt`
  så markeras frånvaron med ett **fett kryss i gråblå cell** i PDF:en – namnet
  står kvar rent i namnkolumnen. Starten snäpps till **närmaste måndag** och
  slutet till **närmaste söndag**, så `18/12 - 7/1` blir 21/12 – 10/1 (hela veckor)
- **Smart cache**: rastrerade logotyper cachas under körningen i `%TEMP%/Semesterlista`
  och **städas automatiskt när appen avslutas** (kan stängas av i
  *Inställningar → Avancerat*). Vid start rensas bara gammalt skräp, så en
  omstart inte tvingar fram nya renderingar.
- **Loggning** i egna mappen `data/loggar/`: `app.log` (roterande, 2 MB × 5),
  **`fel.log`** för ERROR/CRITICAL (arkiveras aldrig – ligger kvar tills felen
  är åtgärdade) och `arkiv/app-<dag>.log` för tidigare dagar, samt `data/crash.log`.
- **Teman**: ljust, mörkt eller följ systemet. Svenska och engelska.

## Installation

```bash
git clone https://github.com/Tokke2/Semesterlista.git
cd Semesterlista
python -m pip install -r requirements.txt
python main.pyw
```

Kräver **Python 3.10+** och beroendena i [`requirements.txt`](requirements.txt)
(PySide6, reportlab).

### Automatisk startkontroll på Windows

Starta med **`Starta Semesterlista.cmd`** (fungerar även när Python saknas).
Direktstart av `main.pyw` går också genom kontrollen när Python redan finns.

- Python hittas via Python Launcher, PATH eller Windows-registret.
- Befintlig Python uppgraderas med winget **inom samma versionsserie**.
  Ingen extra Python-installation görs när en befintlig hittas. Övergång
  exempelvis 3.12 → 3.14 görs inte automatiskt, eftersom den normalt skapar
  en separat installation. Saknas Python installeras stabila Python 3.14.
- PySide6 och reportlab kontrolleras/uppdateras vid varje ny appstart i
  appens **`.venv`**, som återanvänds. PyMuPDF och svglib uppdateras också
  om de redan finns. Andra programs Python-tillägg ändras inte.
- winget (Windows App Installer) krävs för automatisk Python-installation
  och uppgradering. Saknas winget används befintlig Python med varning.
- Utan nät försöker appen använda befintliga fungerande tillägg. Trasig
  miljö stoppar starten med felmeddelande; den skrivs inte över automatiskt.
- Startkontrollen kan ta tid och visar ett konsolfönster. Paketkontrollen
  loggas i `data/loggar/app.log`, fel även i `fel.log`.
- Om appen redan körs ändras inte dess laddade tillägg; befintligt fönster
  visas i stället. Linux/macOS behåller manuell beroendehantering.


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

### Releaser (obligatoriskt vid varje kodändring)

Appens uppdateringsknapp läser **GitHub → Releases → latest**, så varje
kodändring ska sluta med en ny release – annars ser användarna den inte.

```bash
python -m unittest discover -s tests            # 1. alla tester gröna
python tools/bump_version.py 2.11.1             # 2. höj versionen (alla ställen)
python tools/bump_version.py --check            # 3. kontrollera synken
git commit -am "..." && git push                # 4. pusha koden
git tag v0.0.4 -m "Semesterlista 2.11.1"        # 5. tagga (v0.0.x ökar)
git push origin v0.0.4
gh release create v0.0.4 --title "v0.0.4 – Semesterlista 2.11.1" --notes-file anteckningar.md
```

Taggen avgör vilken `config.json` uppdateraren läser, så **versionen i
`config.json` måste vara höjd** innan taggen skapas. Release-anteckningarna
visas i appens uppdateringsruta och i *Öppna release-sidan*.

### Struktur

```
main.pyw              startfönster, meny, systemfält
core/                 i18n, inställningar, PDF-tillgångar, uppdatering, loggning, cache, frånvaro …
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
| PDF:en blir tom/fel | Kontrollera listfilen i fliken, se `data/loggar/app.log` |
| Uppdateringen hittar inget | Kolla nätet och att det finns en publik release |

Loggfilens sökväg visas i **Inställningar → Avancerat**.

## Licens

MIT – se [LICENSE](LICENSE).
