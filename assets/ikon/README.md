# Appikon – används överallt

Samma ikon används av fönstret, systemfältet (tray) och aktivitetsfältet
(Windows-taskbar). Aktivitetshanterarens processdetaljer kan fortfarande visa
Python-ikonen eftersom processen är pythonw.exe. Källan är **SVG-filen**;
PNG/ICO genereras från den.

| Fil | Används till |
|-----|--------------|
| `appikon.svg` | källfil (redigera denna) |
| `appikon-16/24/32/48/64/128/256.png` | Qt väljer rätt storlek per yta (tray, fönster, HiDPI) |
| `appikon.ico` | Windows: appfönster och genvägar |

## Bygg om efter ändring i SVG:n

```bash
python tools/make_icons.py
```

Skriptet kräver bara PySide6 (samma beroende som appen) och skriver om
PNG-filerna samt `.ico`-filen.

## Design

- Mörkblå platta `#16324f`, vit kalender, mintgrön rubrik och blå bock; mintgrön accent `#36d6be`.
- Inga tunna detaljer – ska vara läsbar i 16 × 16 px (systemfält).
- Färgerna finns som konstanter i `core/app_icon.py` (`ICON_BLUE`,
  `ICON_YELLOW`) och används även av reservikonen som ritas
  programmatiskt om bildfilerna skulle saknas.

## Bygga en .exe (valfritt)

Packar du appen med PyInstaller, peka på ICO-filen så får även
exe-filen/aktivitetsfältet rätt ikon:

```bash
pyinstaller --noconsole --icon assets/ikon/appikon.ico main.pyw
```

## Var används den i koden?

| Plats | Kod |
|-------|-----|
| Hela appen (alla fönster/dialoger) | `core.app_icon.apply_app_icon(app)` i `main.pyw` |
| Huvudfönstret | `self.setWindowIcon(app_icon())` i `MainWindow._init_ui()` |
| Systemfältet | `QSystemTrayIcon(app_icon(), app)` i `SystrayManager` |
| Aktivitetsfältet (Windows) | `set_windows_app_user_model_id()` före fönstret skapas |
| Listredigeraren, logotypväljaren, inställningsdialogen | `setWindowIcon(app_icon())` |

Startprogrammet skapar `Semesterlista.lnk` i programmappen, med denna ICO som
ikon och den dolda VBS-startfilen som mål. Använd den i stället för en gammal
genväg till python.exe/pythonw.exe. Windows kan behöva att en gammal fäst
Python-genväg lossas och den nya genvägen fästs igen.

Ett fullständigt byte av processens EXE-ikon kräver en egen programfil med
ikonresurs. AppUserModelID och Qt-ikoner ändrar inte Python-installationens
binärfil. Denna version paketerar inte en separat Python-miljö.

## Logotyp och gränssnittsikoner (2.20.0)

- `assets/brand/logotyp.svg`: ordmärke och kalender för GitHub README.
- `assets/ui/*.svg`: 18 egenritade linjeikoner, gemensamt 24 × 24-rutnät.
- `core/ui_icons.py`: färgar ikoner efter Qt-paletten och använder dem i
  knappar, menyer, flikar och systemfältsmeny. Textetiketter behålls.
- Huvudfönstret visar kalender och ordmärke; fönster/dialoger och systemfält
  använder samma appikon. Inga AI-genererade bilder eller externa ikontjänster.
- Appens `ikon`, `ui` och `brand`-mappar visas inte som kundlogotyper i PDF-väljaren.
- Gamla fästa genvägar kan behöva ersättas. På macOS behöver tidigare skapad
  Semesterlista.app skapas om för att få den nya ikonen. Pythonprocessens
  egen binärikon ändras fortfarande inte.

## Kalender med bockmarkering (2.21.0)

Ny kalenderform med tydliga datumrutor och gul bockmarkering (#ffcb77).
SVG, PNG, ICO och den inbyggda reservikonen visar samma symbol.
Trycklogotyperna finns i `../brand/logotyp-tryck.svg` och `../brand/logotyp-svart.svg`.
Bokstäverna är verkliga banor, inte SVG-text. Läs `../brand/README.md` för tryckinformation.

## Färgstark ikon (2.21.1)

Blå–lila vektorövertoning, turkos kant/bockmarkering, lutad kalender och gul
stjärna. Filerna appikon.svg, PNG i sju storlekar och appikon.ico är uppdaterade,
liksom den inbyggda SVG-reserven. Både appen och README använder den nya grafiken.
