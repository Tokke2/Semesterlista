# Semesterlista

En liten Windows-app (PySide6) som skriver ut **kalendrar**, **semesterlistor**, **körscheman** och **hyreslistor** som PDF – körs i systemfältet och kommer ihåg allt mellan gångerna.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Licens](https://img.shields.io/badge/licens-MIT-green)

---

## Vad appen gör

| Flik | Innehåll |
|------|----------|
| **Kalender** | Fristående kalender med veckonummer och namngivna regionala helgdagar, inga anställda/semesterperioder |
| **Semesterlista** | Anställda och semester, 1–3 månader per blad, automatisk A4-orientering |
| **Fordon** | Fordon och körning, inga semesteruppgifter |
| **Hyra** | Månads- och kvartalshyresgäster, kvartalsöversikt, PDF med tomma kryssrutor |

Semesterlista, Fordon och Hyra kan ha **egen logotyp** (SVG, EPS eller PDF) som ritas
automatiskt skalenligt i PDF:ens hörn – väljs i en dropdown med bilderna i
`assets/` och dess undermappar, eller infogas med *Infoga logotyp…*.

## Nytt i 2.15.0

- Fyra flikar i ordningen **Kalender, Semesterlista, Fordon, Hyra**.
- Gemensamma färger och avstånd, mörkt tema och **Hög kontrast** under
  Utseende. Knapprader bryts och flikar får rullning i små fönster.
- **PDF-utseende…** i Kalender, Semesterlista och Fordon: slå på/av
  säsongsfärger, välj en lokal bildmapp och en bild för varje årstid.
  JPEG/PNG används i en separat, storleksbegränsad bildyta – aldrig bakom data.
  Inställningarna sparas separat per flik. Inga AI-bilder eller bildnedladdningar.
- PDF har ljus bakgrund oberoende av skärmtemat. **Svartvit/gråskala**
  omfattar även bilder och logotyper. Hyra har också ett gråskaleval.
- Den fristående kalendern börjar alltid på måndag och visar ISO-veckonummer
  samt svenska eller amerikanska helgdagsnamn enligt vald region.
  Markera vilka månader som ska exporteras. Ett helår blir 12, 6 eller 4 sidor
  med 1, 2 respektive 3 månader per blad. Kalendern använder alltid liggande A4
  (från 2.15.1) och fyller utskriftsytan. Ingen yta reserveras för bilder som
  inte visas; utan vald bild får kalendern hela den tillgängliga ytan.
  Varningen för text mindre än 6 punkter finns kvar även med säsongsbilder.

## Funktioner

- **Semesterkalender:** välj anställd, klicka på första och sista semesterdag
  och lägg till perioden. Veckan börjar alltid på måndag. Valda datum sparas
  exakt och visas också i semester-PDF:en.
- **Årssummering:** antal semesterdagar per anställd och valt år, räknat
  måndag–fredag utan officiella helgdagar i vald region. Överlapp räknas en
  gång; halvdagar räknas som en dag. Planeringsunderlag, inte löneberäkning.
- **Hyra skapar inga fakturor:** appen visar listor och utskicksplanering.
  Kvartalsutskick: 1 december, 1 mars, 1 juni och 1 september. Betalningen
  ska vara klar vid kvartalets början: 1 januari, 1 april, 1 juli, 1 oktober.

- **Anpassade inställningar:** fönstret anpassar startstorleken till skärmens arbetsyta.
  Flikarna kan rullas på mindre skärmar; Spara och Avbryt ligger utanför rullningen.

- **PDF-export för Semesterlista och Fordon** med färgkodning (helgdagar, lördagar, halvdagar, veckonummer),
  valbar startmånad (även över årsskifte) och 1, 2 eller 3 månader per blad.
  **1 månad = stående A4; 2–3 = liggande A4.** Valda månader hålls på samma
  blad och skalas ned vid behov; mycket långa listor får mindre text.
  Om kalendertext blir mindre än 6 punkter visas en varning före export.
  Du kan fortsätta med samma layout eller avbryta utan att ändra befintlig PDF.
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

### Veckokontroll av Python och tillägg på Windows

Starta med **`Starta Semesterlista.cmd`**. Direktstart av `main.pyw` fungerar
också när Python finns. Appen använder **befintlig Python och dess vanliga
paketmiljö** – ingen egen `.venv` skapas eller används. En gammal `.venv`
från tidigare version lämnas orörd men används inte längre.

- Kontroll och uppdatering sker **en gång per vecka, måndag kl. 08.00 lokal tid**.
  Ett schema registreras för inloggad användare i Windows Schemaläggaren.
- Om tiden missas, eller schemat inte kan registreras, görs veckans försök
  vid nästa appstart. Vanliga starter samma vecka gör inga pip-/winget-kontroller.
  Första användningen räknas som en missad veckokontroll och körs direkt.
- Om appen körs vid schematiden skjuts kontrollen upp till nästa start,
  så att tillägg inte byts medan appen använder dem.
- Försöket sparas i `data/runtime-weekly.json`, även vid nätfel, så upprepade
  starter inte orsakar nya uppdateringsförsök samma vecka.
- Befintlig Python uppgraderas med winget inom samma versionsserie. En ny
  Python-installation görs bara om Python saknas (Python 3.14).
- PySide6 och reportlab uppdateras via den befintliga Python-installationens
  pip. PyMuPDF och svglib uppdateras om de redan finns. **Det kan påverka
  andra program som använder samma Python och tillägg.**
- winget krävs för Python-uppdatering. Behörighets-/nätfel rapporteras;
  befintlig Python behålls. Paketunderhåll loggas i `data/loggar/app.log`
  och fel i `fel.log`. Linux/macOS behåller manuell beroendehantering.

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
