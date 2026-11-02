# Förslag – 25 st (2026-11-02, v2.5.0)

Status per 2026-11-02 (v2.8.1). **[KLART]** = finns i koden nu, **[FÖRSLAG]** = inte gjort.

## Flikar & logotyp (från senaste önskemålen)

1. **[KLART] Tre flikar** – Hyra, Semesterlista och Fordon, i fast ordning
   (TAB_ORDER 10/20/30) och med låst läge per flik så fel lista inte kan skrivas ut.
2. **[KLART] SVG-logotyp från undermapp** – bilder läses rekursivt från
   `assets/` (t.ex. `assets/logotyper/`), väljs i appen och bäddas in i PDF:en
   på varje sida (vektor via `svglib`, annars 300 dpi via Qt).
3. **[FÖRSLAG] Logotypens placering och storlek** – välj hörn (vänster/höger,
   uppe/nere) och maxstorlek per flik i stället för dagens fasta värden.
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

## Rekommenderad ordning härnäst

1. **4 + 13** (sidhuvud/sidfot och samlings-PDF) – störst nytta för utskrifter.
2. **7 + 6** (kopiera in bilder, dra-och-släpp) – gör logotypflödet stabilt.
3. **25** (CI + GUI-tester) – billigt att införa nu när testfilerna redan finns.
