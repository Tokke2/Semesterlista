# Sida till PDF

Webbläsartillägg för **Chrome** och **Brave** som sparar sidor från de webbplatser du själv väljer som PDF – med ett enda klick.

Inget skickas till någon server: PDF:en skapas lokalt av webbläsarens egen utskriftsmotor.

---

## Funktioner

| Funktion | Beskrivning |
| --- | --- |
| **Valda webbplatser** | PDF-funktionen är bara aktiv på de sajter du lägger till i listan. Övriga sajter lämnas ifred. |
| **Knapp på sidan** | En liten flytande PDF-knapp längst ner på valda sidor. Ett klick = en PDF. Placering och synlighet går att ställa in. |
| **Knapp i verktygsfältet** | Visar status för aktuell flik och sparar sidan. Om sajten inte är vald läggs den till direkt. |
| **Snabbtangent** | `Alt+Shift+P` sparar aktuell sida utan att du behöver klicka. |
| **Högerklicksmeny** | ”Spara sidan som PDF” på valda sidor. |
| **Ren utskrift** | Vit bakgrund, A4, inga sidhuvuden/sidofot och anpassade marginaler. Allt går att ändra. |
| **Filnamn och mappar** | Filerna sparas som `Sidor/<sajt>/<datum>_<titel>.pdf` med valfri mall och egen underkatalog. |
| **Svenska / engelska** | Välj språk i inställningarna, eller låt webbläsarens språk styra. |
| **Import/export** | Hela inställningsfilen kan exporteras och importeras som JSON. |

---

## Installation

### Chrome

1. Ladda ner eller kopiera mappen `browser-extension` till datorn.
2. Öppna `chrome://extensions`.
3. Slå på **Utvecklarläge** uppe till höger.
4. Klicka på **Läs in opackat** och välj mappen `browser-extension` (mappen som innehåller `manifest.json`).
5. Tillägget dyker upp i verktygsfältet – gärna fäst det med nål-ikonen.

### Brave

Samma sak, men öppna `brave://extensions` i steg 2. Brave använder samma tilläggsmotor som Chrome.

Efter installationen öppnas inställningssidan automatiskt. Där lägger du till de webbplatser som ska få sparas.

> Tillägget laddas som ”opackat” och uppdateras inte automatiskt. Uppdatera genom att klicka på uppdateringsikonen för tillägget på `chrome://extensions`.

---

## Använda tillägget

1. **Lägg till en webbplats** – klicka på tilläggets ikon när du står på sidan och välj **Lägg till … och spara**. Du kan också skriva adressen direkt i inställningarna, t.ex. `aftonbladet.se`, `*.example.com` eller `example.com/nyheter`.
2. **Bevilja åtkomst** när webbläsaren frågar. Det behövs för att den flytande knappen ska kunna visas på just den sajten. Utan åtkomst fungerar fortfarande verktygsfältets knapp och snabbtangenten.
3. **Klicka på PDF-knappen** som dyker upp längst ner på sidan. Klart – filen ligger i Hämtade filer.

### Mönster

| Mönster | Matchar |
| --- | --- |
| `example.com` | Endast `example.com` |
| `*.example.com` | `example.com` och alla subdomäner, t.ex. `www.example.com` |
| `example.com/nyheter` | Bara sidor under `/nyheter` |
| `localhost:3000` | Lokal utveckling |

Protokoll (`https://`) och avslutande snedstreck spelar ingen roll.

---

## Inställningar

Inställningssidan öppnas via kugghjulet i panelen eller via `chrome://extensions` → **Information** → **Tilläggsalternativ**.

- **Valda webbplatser** – lista, på/av, åtkomst och borttagning.
- **Knapp på sidan** – visa/dölj och placering (fyra hörn).
- **PDF** – pappersformat (A4/Letter/Legal/A3), marginal, skala, bakgrundsfärger, sidhuvud med sidnummer, CSS `@page` och väntetid före utskrift.
- **Filnamn** – underkatalog, mall med taggarna `{site} {title} {date} {time} {year} {month} {day}`, egen mapp per sajt och ”fråga var filen ska sparas”.
- **Allmänt** – språk, tillåt alla webbplatser, snabbtangent, import/export och återställning.

Inställningarna sparas lokalt i webbläsaren. Använd **Exportera** om du vill säkerhetskopiera eller flytta dem till en annan dator.

---

## Behörigheter – och varför

| Behörighet | Används till |
| --- | --- |
| `debugger` | Anrop till webbläsarens DevTools-protokoll (`Page.printToPDF`) för att skapa PDF:en. Krävs för att kunna spara utan utskriftsdialog. |
| `downloads` | Sparar den färdiga PDF-filen i Hämtade filer. |
| `storage` | Inställningar och webbplatslista, sparas lokalt i webbläsaren. |
| `scripting` + valfri värdåtkomst | Registrerar den flytande knappen – bara på sajter du uttryckligen beviljat. |
| `activeTab` | Läser aktuell fliks adress när du klickar på tillägget. |
| `contextMenus` | Högerklicksvalet ”Spara sidan som PDF”. |
| `offscreen` | Gör om PDF:en till en blob så att filer över 2 MB sparas hela (data-URL:er klipps annars av). |

Ingen kod körs på sajter du inte har valt, och inga data lämnar datorn.

---

## Så skapas PDF:en

1. Bakgrundstjänsten kopplar upp sig mot fliken via DevTools-protokollet.
2. Den väntar på att teckensnitt och bilder ska bli klara (och på den väntetid du ställt in).
3. `Page.printToPDF` renderar sidan med dina inställningar – samma motor som Ctrl+P, men helt utan dialogruta.
4. PDF:en skickas till nedladdningshanteraren med automatiskt filnamn.

Medan tillägget skapar PDF:en visas en liten informationsrad i webbläsaren: *”Sida till PDF började felsöka den här webbläsaren”*. Den försvinner när utskriften är klar.

---

## Felsökning

| Problem | Lösning |
| --- | --- |
| ”Stäng DevTools för fliken och försök igen.” | DevTools får bara ha en felsökare per flik. Stäng DevTools-panelen och klicka igen. |
| Interna sidor kan inte sparas | `chrome://`, `brave://`, webbutiken och nya flikar kan inte skrivas ut. |
| Ingen PDF-knapp på sidan | Kontrollera att sajten är **aktiv** i listan och att **Åtkomst beviljad** står vid den. Ladda om sidan efteråt. |
| Filen sparas inte | Slå av ”Fråga var filen ska sparas” om du inte vill bekräfta varje gång, och kontrollera webbläsarens nedladdningsinställningar. |
| Ingenting händer vid klick | Ladda om tillägget på `chrome://extensions` efter en uppdatering av filerna. |

---

## Utveckling

```
browser-extension/
├── manifest.json
├── icons/                  # ikoner (SVG-källa + PNG i 16/32/48/128)
├── src/
│   ├── background.js       # service worker: PDF, behörigheter, meny, badge
│   ├── content.js          # flytande knapp + toast (klassiskt skript)
│   ├── popup.html/.css/.js # panelen i verktygsfältet
│   ├── options.html/.css/.js
│   ├── ui.css              # delad design
│   └── lib/
│       ├── sites.js        # mönstermatchning (ren modul)
│       ├── filename.js     # filnamn (ren modul)
│       ├── i18n.js         # svenska/engelska
│       └── settings.js     # storage + standardvärden
├── tests/                  # node:test
└── package.json
```

```bash
cd browser-extension
npm test        # 21 tester för mönster, filnamn och översättningar
npm run check   # syntaxkontroll av alla skript
```

Ändringar slår igenom efter **Ladda om** på `chrome://extensions`. Innehållsskriptet på redan öppna flikar uppdateras när du laddar om sidan.

### Kända begränsningar

- Endast `http`/`https` kan sparas.
- DevTools får inte vara öppet i fliken som sparas.
- Mycket stora sidor kan ta några sekunder extra; höj **Väntetid före utskrift** om lazy-laddat innehåll saknas.
- Tillägget är inte signerat – det installeras som opackat och kräver utvecklarläge.
