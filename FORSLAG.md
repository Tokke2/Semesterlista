# Förslag – 25 st (2026-11-02, v2.5.0)

Status per 2026-11-03 (v2.11.0). **[KLART]** = finns i koden nu, **[FÖRSLAG]** = inte gjort.
Den ursprungliga listan står kvar nedan; **25 helt nya förslag** finns i
avsnittet ”25 nya förslag” längst ner.

## Flikar & logotyp (från senaste önskemålen)

1. **[KLART] Tre flikar** – Hyra, Semesterlista och Fordon, i fast ordning
   (TAB_ORDER 10/20/30) och med låst läge per flik så fel lista inte kan skrivas ut.
2. **[KLART] SVG-logotyp från undermapp** – bilder läses rekursivt från
   `assets/` (t.ex. `assets/logotyper/`), väljs i appen och bäddas in i PDF:en
   på varje sida (vektor via `svglib`, annars 300 dpi via Qt).
3. **[KLART] Logotypens placering och storlek** – storleken anpassas
   automatiskt efter sidan (`PdfLogo.auto_size`, v2.10.0): 15 % av bredden /
   8 % av höjden, tak 60 × 25 mm och alltid bevarade proportioner. Valbar
   storlek per flik återstår som förslag.
4. **[FÖRSLAG] Sidhuvud/sidfot i PDF:en** – företagsnamn, utskriftsdatum,
   "Sida 2 av 5" och logotyp tillsammans. Höjer intrycket på utskrifter.
5. **[FÖRSLAG] Två logotyper samtidigt** – t.ex. företag uppe till vänster och
   avdelning uppe till höger (vanligt i koncerner).
6. **[FÖRSLAG] Dra-och-släpp av SVG/PNG på fliken** – släpp filen så kopieras
   den till `assets/logotyper/` och väljs direkt. Snabbare än filväljaren.
7. **[FÖRSLAG] Automatisk kopiering till assets** – om man väljer en bild
   utanför `assets/` kopieras den in, så logotypen aldrig "försvinner".
8. **[FÖRSLAG] Vattenstämpel** – logotypen som ljus bakgrundsbild (t.ex. 8 %
   opacitet) bakom tabellen, som tillval per flik.
9. **[FÖRSLAG] Logotyp som fönsterikon** – samma SVG blir appens ikon och
   systemfältsikon (`QIcon`), så appen känns företagsanpassad.
10. **[FÖRSLAG] Sökfält i logotypdialogen** – filtrera på namn/mapp när det
    finns många bilder i `assets/`.

## Logotypväljaren (v2.10.0)

- **[KLART] Dropdown i stället för dialog** – `core/logo_picker.py` listar
  alla bilder i `assets/` + undermappar direkt i vyn (Semesterlista och Hyra).
- **[KLART] Förhandsgranskning som skalar sig själv** – bilden anpassas till
  ytan i både höjd och bredd, utan att proportionerna ändras.
- **[KLART] Uppdatera lista** – nya bilder i `assets/` syns direkt.
- **[KLART] Inställningar… och Sök efter uppdatering… i systemfältets meny.**
- **[FÖRSLAG] Sökfält i dropdownen** – filtrera på namn/mapp när `assets/`
  innehåller många bilder (punkt 10 nedan).
- **[FÖRSLAG] Automatisk kopiering till `assets/logotyper/`** när man väljer
  en bild utanför mappen (punkt 7 nedan).

## PDF & utskrift

11. **[FÖRSLAG] Skriv ut direkt** – `QPrinter` + "Skriv ut"-knapp, inte bara PDF.
12. **[FÖRSLAG] Förhandsgranska PDF i appen** – `QPdfDocument` i en panel, så
    man ser resultatet innan filen öppnas i extern läsare.
13. **[FÖRSLAG] Samlings-PDF** – en fil med Hyra + Semesterlista + Fordon,
    praktiskt när hela paketet ska skickas till ekonomiavdelningen.
14. **[FÖRSLAG] Automatisk arkivering** – spara som
    `Dokument/Semesterlista/<år>/<flik>_<datum>.pdf` i stället för bara Dokument.
15. **[FÖRSLAG] E-post direkt** – knapp som öppnar standardklienten med PDF:en
    som bilaga (sparar många manuella steg vid utskick).
16. **[FÖRSLAG] Färgtema per flik** – Hyra röd, Semesterlista grön, Fordon blå i
    flikikon och rubrik, så flikarna känns igen direkt.

## Listor & data

17. **[FÖRSLAG] Listväljare per flik** – combobox med "senast använda listor"
    (t.ex. `Fordon.txt`, `Fordon-2027.txt`) i stället för fritextfält.
18. **[FÖRSLAG] Varna vid tom lista** – bekräftelse innan PDF skapas om listan
    har 0 poster (idag skapas en tom tabell).
19. **[FÖRSLAG] Minnesfunktion per flik** – år, startmånad och månader/blad
    sparas separat för Hyra/Semester/Fordon (idag delvis delat).
20. **[FÖRSLAG] Import från CSV/Excel** – klistra in eller importera
    `namn;avdelning;startdatum` i listredigeraren.
21. **[FÖRSLAG] Historik/ångra i listredigeraren** – Ctrl+Z för senaste
    ändringen innan filen sparas.

## Teknik & kvalitet

22. **[FÖRSLAG] Användarens flikordning** – spara `tabs.order` och tillämpa den
    vid start (idag sparas den men ordningen styrs av TAB_ORDER).
23. **[FÖRSLAG] Inställningsdialog per flik** – flytta år/färger/logotyp till
    en dialog så huvudvyn blir renare.
24. **[FÖRSLAG] Kommandorads-läge** – `python main.pyw --pdf hyra --year 2026`
    för schemaläggning (Windows Task Scheduler) utan att öppna fönstret.
25. **[FÖRSLAG] CI + GUI-tester** – GitHub Actions som kör de 62 testerna vid
    varje push, plus `pytest-qt` för flikar, logotypdialog och PDF-knappar.

## Klart efter listan skrevs

**v2.11.0 – Lediga dagar i listan + smart cache**

- **Lediga dagar per anställd** (`core/leave.py`): skriv
  `Anna Andersson ; 18/12 - 7/1` (eller `|`) i `Anställda.txt`. Datumen
  snäpps till **närmaste måndag** (må–to bakåt, fre–sö framåt), så raden
  blir 21/12–4/1. Fler perioder med `,` eller `och`, datumformat
  `18/12`, `18/12/2026` och `2026-12-18`; saknat år → listans år och slut
  före start → nästa år.
- **I PDF:en** markeras dagarna **grått med ×** (vinner över helgdags-,
  halvdags- och lördagsfärgerna) med en egen ruta i färgförklaringen
  (”Grå = Ledig”). Vyns förklaring och listredigerarens hjälptext visar
  samma sak.
- **`read_entries()`** i `core/roster.py` ger `(namn, frånvaro)`; befintlig
  `read_names()` lämnar bara namnen, så Fordon och Hyra påverkas inte.
- **Smart cache** (`core/cache.py`): `%TEMP%/Semesterlista` städas vid start
  (filer äldre än 1 h) och vid avslut (inställning *Avancerat → Rensa cache
  vid avslut*, med cachestorlek i dialogen).
- **Tester:** 56 nya (`test_leave.py` 42, `test_pdf_leave.py` 8,
  `test_list_editor.py` 3, `test_roster.py` +3) = **298 totalt**.

**v2.9.0 – Uppdatering från GitHub Releases**

- **Knapp:** *Hjälp → Sök efter uppdatering…* och **Inställningar →
  Avancerat → Uppdatering** (*Sök efter uppdatering*, *Uppdatera nu*,
  *Öppna release-sidan*).
- **`core/updater.py`:** läser `releases/latest` + `config.json` vid taggen,
  jämför versioner, laddar ner zipball, packar upp säkert och skriver
  programfilerna. Bara standardbiblioteket används.
- **Användardata rörs aldrig:** `data/`, `*.txt`-listorna, `.git/`,
  `__pycache__` och byggmappar hoppas över.
- **Säkerhetskopia** av ersatta filer i `data/backup/` innan något skrivs.
- **Automatisk kontroll vid start** (valfri) som visar en avisering i
  systemfältet när en nyare version finns – inget installeras automatiskt.
- **Tester:** `tests/test_updater.py` (24, offline) + 7 i dialogtestet =
  165 tester totalt. Verifierat skarpt mot GitHub: nedladdning och
  installation i en kopia av appen.

**v2.8.1 – Årbytet i Hyra-fliken tömde sidan**

- **Fixat:** när man bytte år i Hyra-fliken byggdes vyn om med en ny
  `QVBoxLayout(self)` trots att widgeten redan hade en layout. Qt vägrar
  sätta den nya layouten, och kvar blev en tom sida. Nu återanvänds
  rotlayouten och bara kvartalskorten byts ut på plats – fokus ligger kvar
  i årväljaren.
- **Regressionstester:** `tests/test_hyra_view.py` (8 tester) fångar bland
  annat Qt-varningen ”already has a layout”.

**v2.8.0 – Detaljerad loggning & inställningsdialog**

- **Loggning** (`core/logging_setup.py`): `data/app.log` med rotering
  (2 MB × 5), tidsstämplar och modul:rad, `data/crash.log` via faulthandler,
  Qt:s egna meddelanden i loggen och `SEMESTERLISTA_DEBUG=1` för DEBUG.
- **Stegloggning** i `main.pyw`: varje uppstartssteg loggas med ms, plugins
  med version, flikantal, tray-status, exit-kod och total körtid.
- **Felruta** vid ohanterat fel med loggfilens sökväg; `core/settings_dialog.py`
  saknas inte längre – och om den gör det startar appen ändå (menyvalet
  inaktiveras och felet loggas).
- **Inställningsdialog** (`core/settings_dialog.py`): flikarna Allmänt,
  Fönster, Plugins och Avancerat – språk, tema, helgdagsregion, autostart,
  systemfält, plugin-status, felsökningsläge samt knappar för att öppna
  loggmappen och kopiera senaste loggen.
- **PDF-loggning**: läge, år, startmånad, månader per blad, layout, antal
  poster/sidor, filstorlek och tidsåtgång.
- **Tester**: 126 (24 för loggningen, 15 för dialogen).


**v2.7.0**

- **Egen appikon överallt** (`assets/ikon` + `core/app_icon.py`): fönster,
  systemfält, aktivitetsfält och aktivitetshanterare (Windows
  AppUserModelID), dialoger och meddelanderutor.

**v2.6.0**

- **Valbar sidlayout** för semester-/fordons-PDF: liggande A4 (270 mm tabell)
  eller stående A4 (190 mm tabell).
- **1, 2 eller 3 månader per blad** (tidigare bara 2 och 3) samt vald
  startmånad – allt sparas per flik.

## 25 nya förslag (2026-11-03, v2.11.0)

Nya idéer som bygger vidare på det som finns i koden i dag (298 tester,
frånvarostöd, smart cache). N-numren krockar inte med listan ovan.

### Listor & frånvaro

**N1. Bemanningsvarning** – appen vet redan vem som är ledig. Varna i vyn när
fler än *N* personer (inställning, t.ex. 3) är lediga samma vecka, och visa
veckan med en notis i PDF:en. Fångar den vanligaste missen: att halva laget är
borta v. 52. *Insats: liten.*

**N2. Ledighetsöversikt i PDF:en** – en valfri extra sida som listar alla
perioder: namn, från–till, antal dagar, vecka. Ekonomi och HR slipper läsa tolv
tabeller för att hitta frånvaron. *Insats: liten–medel.*

**N3. Sökfält i listredigeraren** – filtrera listan medan du skriver
(`QLineEdit` + filtrerande modell). Oumbärligt vid 50+ namn. *Insats: liten.*

**N4. Direktvalidering när man skriver** – röd rad om posten är längre än 80
tecken eller frånvaron inte går att tolka, med orsaken i verktygstipset. I dag
upptäcks felet först när filen läses in. *Insats: liten.*

**N5. Visa tolkad frånvaro i listan** – verktygstips eller kolumn med
”21/12 2026 – 4/1 2027 (15 dagar)”, så man ser att veckosnäppningen blev rätt
innan man skriver ut. *Insats: liten.*

**N6. Dra och släpp en txt-fil på fönstret** – byt lista genom att släppa filen
på fliken (`dragEnterEvent`/`dropEvent`) med bekräftelse. *Insats: liten.*

**N7. Automatisk säkerhetskopia av listfilerna** – kopiera till
`data/backup/listor/<datum>_Anställda.txt` (behåll 10) före varje sparning,
plus *Återställ från kopia*. I dag säkerhetskopieras bara vid uppdatering.
*Insats: liten.*

**N8. Statusrad + automatisk omläsning** – under listan: ”12 anställda ·
3 med frånvaro · filen ändrad 14:12”. `QFileSystemWatcher` läser om filen om
någon redigerar den i Notepad samtidigt. *Insats: medel.*

### PDF & utskrift

**N9. Sidfot med sidnummer och datum** – ”Sida 2 av 4 · 2026-11-03”. PDF:en har
ingen sidfot alls i dag, vilket märks när bladen tappas bort. *Insats: liten.*

**N10. PDF-metadata** – titel, författare, ämne och nyckelord via
`doc.setTitle(...)`, så filen går att söka upp i Utforskaren och i
dokumenthanteringssystem. *Insats: liten.*

**N11. Egen rubrik överst** – valfri text (företag/avdelning) ovanför tabellen,
sparas per flik och kan användas i filnamnet. *Insats: liten.*

**N12. Utskrift som fungerar i svartvitt** – mönster eller symboler i cellerna
(helg, halvdag, lördag, ledig) som komplement till färgerna. Fungerar på
kontorets svartvita skrivare och för färgblinda. *Insats: medel.*

**N13. Årsöversikt på ett blad** – 12 miniatyrmånader på A3 för anslagstavlan:
samma data som i dag, men överskådligt på en enda sida. *Insats: medel.*

**N14. Filnamnsmall + ”öppna mappen efter export”** – inställning som ger t.ex.
`Semesterlista_2026_v44.pdf`, och en kryssruta som öppnar mappen i Utforskaren
när filen är klar. *Insats: liten.*

**N15. Tidsstämpel i sidfoten** – ”underlag 2026-11-03 14:12”, så att ingen
skriver ut en gammal version utan att märka det. *Insats: liten.*

### Vyn & arbetsflödet

**N16. Klicka på ett datum → vilka är lediga?** – klick i tabellen visar en
lista för dagen (och veckan). Bra vid akuta bemanningsfrågor. *Insats: medel.*

**N17. Påminnelse i systemfältet** – ”dags att uppdatera listan” på valt
intervall (t.ex. första måndagen i månaden), med en länk som öppnar fliken.
*Insats: liten–medel.*

**N18. Hjälpmenyn: ”Visa senaste felen” och ”Kopiera systeminfo”** – sista
raderna ur `data/app.log`/`crash.log` i en dialog, plus en knapp som kopierar
version, Python, Qt, pluginversioner och sökvägar. Halverar
felsökningsfrågorna. *Insats: liten.*

**N19. Snabbvägar i Arkiv-menyn** – *Öppna data-mappen*, *Öppna
Dokument-mappen* och *Öppna senaste PDF*. I dag nås mapparna bara via
Inställningar och loggknappen. *Insats: liten.*

**N20. Exportera/importera inställningar** – hela `settings.json` som en fil,
så ett kontor kan dela uppsättning eller man kan flytta till ny dator.
*Insats: liten–medel.*

### Teknisk kvalitet & drift

**N21. Schemaversion, migrering och backup av `settings.json`** – filen har
ingen version i dag; en trasig eller äldre JSON kan tyst nollställa
inställningarna. Inför `schema_version`, migreringssteg och en kopia före varje
skrivning. *Insats: medel.*

**N22. PDF-innehållstester i CI** – verifiera cellfärger och markeringar i den
färdiga PDF:en (t.ex. med `pymupdf`) i stället för bara sidantal och MediaBox
som i dag. Fångar regressionsfel i färglogiken. *Insats: medel.*

**N23. `core/pdf_style.py`** – samla färger, fonter och mått på ett ställe
(i dag 19 ställen med `Helvetica` och 17 hårdkodade färger). Gör teman och N12
möjliga utan att röra layoutkoden. *Insats: medel.*

**N24. Kvalitetsgrindar i CI** – `ruff`/pyflakes som gate, kodtäckning som
kommentar på varje push och `.editorconfig` + `pre-commit` som håller
CRLF/LF-regeln (den finns bara i dokumentationen i dag). *Insats: liten–medel.*

**N25. Release-workflow** – vid tagg: kör testerna, `bump_version.py --check`,
bygg zip och skapa releasen automatiskt. I dag görs releasen för hand och kan
hamna ur synk med `config.json`. *Insats: medel.*

### Rekommenderad ordning (första fem)

1. **N21** (settings-säkerhet) – billigast skydd mot datatapp, rör ingen UI.
2. **N9 + N10 + N15** (sidfot, metadata, tidsstämpel) – samma kod, stor nytta
   vid varje utskrift.
3. **N1** (bemanningsvarning) – bygger direkt på frånvarostödet i v2.11.0.
4. **N3 + N4 + N5** (sök, validering, tolkad frånvaro) – gör listredigeraren
   färdig när listorna växer.
5. **N22 + N24** (PDF-innehållstester och kvalitetsgrindar) – billigt nu när
   sviten redan har 298 tester.

## Rekommenderad ordning härnäst (ursprungliga listan)

1. **4 + 13** (sidhuvud/sidfot och samlings-PDF) – störst nytta för utskrifter.
2. **7 + 6** (kopiera in bilder, dra-och-släpp) – gör logotypflödet stabilt.
3. **25** (CI + GUI-tester) – billigt att införa nu när testfilerna redan finns.
