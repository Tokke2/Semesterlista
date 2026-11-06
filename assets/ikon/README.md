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

- Mörkblå platta `#14507d`, vit kalender, gul rubrik och blå bock `#f2b705`.
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
