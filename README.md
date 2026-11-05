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

## Svenska högtider från 2.17.0

Kalenderfliken har nu också **27 svenska högtider och temadagar**, utöver
befintliga helgdagar och aftnar: bland annat fettisdagen, våffeldagen,
alla hjärtans dag, mors dag, fars dag, kanelbullens dag, Lucia och fyra advent.
Datumen visas på skärmen och i PDF, på både svenska och engelska.

**Endast helgdagar markeras rött i den fristående kalendern.** Svenska söndagar
är allmänna helgdagar och förblir röda. En temadag på en söndag är alltså röd
på grund av söndagen, inte på grund av temadagen. Vanliga amerikanska söndagar
är inte federala helgdagar och färgas inte röda enbart för att det är söndag.
Faktiska federala helgdagar och deras ersättningsdagar markeras fortsatt rött.

Temadagar och aftnar markeras med **\*** och ändrar inte ledighet eller
semestersummor. Exempelvis är Lucia och julafton 2027 inte röda, men juldagen
är röd. En fullständig svensk namnsdagskalender ingår inte i denna utökning.
Semesterlista och Fordon behåller sina tidigare färg-/ledighetsregler.

## Amerikanska högtider från 2.16.0

Kalenderfliken visar nu även **33 typer av vanliga amerikanska högtider och
märkesdagar**, utöver federala helgdagar. Välj USA som helgdagsregion.

- Bland annat St. Patrick’s Day, alla hjärtans dag, Halloween, mors dag,
  fars dag, mor-/farföräldrarnas dag, Earth Day, Flag Day och Cinco de Mayo.
- Västerländska påskdagar, Mardi Gras, askonsdagen, Kristi himmelsfärds dag
  och pingst; dessutom Black Friday, Cyber Monday, Giving Tuesday med flera.
- Ordinarie federala valdagen visas under jämna år.
- **\*** betyder högtid/temadag, **inte federal helgdag**. Den ändrar inte
  arbetsdagsklassificeringen eller semestersummeringen. Delstater och
  arbetsgivare kan ha egna ledighetsregler.
- Faktiskt datum och ersättningsdag visas separat. Julen 2027 visar
  exempelvis ”Juldagen – ersättningsdag” den 24:e och ”Juldagen” den 25:e.
  Julafton visas som en separat högtid den 24:e.
- Listan är inte en fullständig delstats-/religionskalender och innehåller
  inte svenska namnsdagar. Sammanfallande dagar behåller alla namn.
- Högtiderna visas på skärmen och i kalender-PDF. Semesterlista/Fordon behåller
  sina ledighetsregler och får bara förtydligade officiella helgdagsnamn.

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

### Saknade tillägg: erbjud reparation (från 2.17.1)

Om PySide6/reportlab saknas eller inte kan importeras erbjuder startprogrammet
**Installera/reparera tillägg och försök igen** i en vanlig Windows-dialog.
Dialogen kräver inte Qt. Standardval är **Nej**.

- Ja installerar om/uppdaterar kraven i **samma Python** med dess egen pip.
  Saknas pip används `ensurepip` i den befintliga installationen.
- Ingen ny Python, separat miljö eller automatisk installationsloop skapas.
- Tilläggen verifieras före ett enda nytt startförsök. Misslyckande visas som
  meddelande med sökväg till `data/loggar/fel.log` och loggas beständigt.
- Normal start gör inga extra pip-/uppdateringskontroller. Det ordinarie
  veckounderhållet är oförändrat; interaktiv reparation är ett separat undantag.
- Reparation tillåts inte medan en annan start/app äger underhållslåset.
  Schemalagt underhåll visar ingen reparationsfråga.
- Paket delas med andra program som använder samma Python. Stäng sådana
  program innan du godkänner reparationen.

### Veckokontroll av Python och tillägg på Windows

Dubbelklicka på **`Starta Semesterlista.vbs`** för att starta **utan terminalfönster**.
Skapa gärna en skrivbordsgenväg till den filen. Även veckounderhållet körs dolt.
Den äldre `.cmd`-filen vidarebefordrar starten, men själva CMD-fönstret kan
blinka till; använd därför `.vbs` direkt. Windows Script Host/VBScript måste
vara tillgängligt för denna startfil. Direktstart av `main.pyw` fungerar också
när Python finns och `.pyw` är kopplad till `pythonw.exe`. Appen använder **befintlig Python och dess vanliga
paketmiljö** – ingen egen `.venv` skapas eller används. En gammal `.venv`
från tidigare version lämnas orörd men används inte längre.

- Kontroll och uppdatering sker **en gång per vecka, måndag kl. 08.00 lokal tid**.
  Ett schema registreras för inloggad användare i Windows Schemaläggaren.
- **Från 2.17.2 uppdateras befintlig Python aldrig som del av appstarten.**
  Inget missat veckounderhåll tas igen i startflödet, inte heller första gången.
  Starten kör inga automatiska pip-/winget-uppdateringar. Erbjudandet att
  installera/reparera saknade tillägg finns kvar och kräver ditt godkännande.
- Schemaläggaren kan köra ett missat veckotillfälle separat. Om appen redan
  körs avstår underhållet för att skydda dess paket; nästa möjlighet blir ett
  senare underhållstillfälle, inte nästa appstart. Om schemat inte kan
  registreras startar appen ändå utan uppdatering.
- Försöket sparas i `data/runtime-weekly.json`, även vid nätfel, så upprepade
  starter inte orsakar nya uppdateringsförsök samma vecka.
- Bara det separata underhållet får uppgradera befintlig Python med winget
  inom samma versionsserie. Vid appstart får en första Python-installation
  fortfarande göras om Python helt saknas (Python 3.14), aldrig som en extra kopia.
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
