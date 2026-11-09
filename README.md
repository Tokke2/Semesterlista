<p align="center">
  <img src="assets/brand/logotyp.svg" alt="Semesterlista – Planera. Samla. Skriv ut." width="640">
</p>

<p align="center"><strong>Kalendrar, semester, körlistor och hyra – i en app.</strong><br>Windows · macOS · Linux · Svenska och engelska</p>

<p align="center">
  <a href="https://github.com/Tokke2/Semesterlista/releases/latest">Hämta senaste versionen</a> ·
  <a href="docs/guide.md">Utförlig guide</a> ·
  <a href="https://github.com/Tokke2/Semesterlista/issues">Rapportera ett problem</a>
</p>

## Vad kan jag göra?

| Flik | Funktion |
|---|---|
| <img src="assets/brand/calendar.svg" width="24" alt=""> **Kalender** | Skriv ut kalendrar med svenska eller amerikanska helgdagar. |
| <img src="assets/brand/leave.svg" width="24" alt=""> **Semesterlista** | Planera anställdas semester och se semestersummor. |
| <img src="assets/brand/car.svg" width="24" alt=""> **Fordon** | Gör körlistor för dina fordon. |
| <img src="assets/brand/home.svg" width="24" alt=""> **Hyra** | Håll ordning på månads- och kvartalshyresgäster, utskick och betalstatus. Inga fakturor skapas. |

Välj egna bilder och logotyper för PDF:erna. Kalendern kan visa **1–3 månader per blad**.
Appen har ljust, mörkt och högkontrasttema.

## Kom igång

**Python-val:** först en fungerande installerad **3.15**, sedan **3.14**, därefter
en annan installerad **3.10+**. Startprogrammet kontrollerar att Qt/reportlab kan
laddas. Ingen extra Python installeras för att lösa kompatibilitetsproblem.

**1. Hämta och packa upp** senaste versionens **Source code (zip)** från
[Releases](https://github.com/Tokke2/Semesterlista/releases/latest).
Lägg mappen där du har skrivrättigheter, till exempel i din hemkatalog.
Behåll filerna tillsammans.

**2. Starta för ditt system:**

### Windows

Dubbelklicka på **`Starta Semesterlista.vbs`**.
Startprogrammet skapar även genvägen **`Semesterlista.lnk`** med appens ikon.

Befintlig Python återanvänds. Om Python helt saknas kan startprogrammet installera den.
Saknade tillägg ger ett erbjudande om reparation – inget installeras utan ditt godkännande.
Windows Script Host behövs för VBS-starten.

### macOS och Linux

Du behöver en befintlig **Python 3.10+** och en grafisk skrivbordsmiljö.
Öppna en terminal i appmappen och kör **en gång**:

```sh
python3 tools/install_launcher.py
```

Starta sedan utan terminal:
- **macOS:** dubbelklicka på `Semesterlista.app` i appmappen.
- **Linux:** välj **Semesterlista** i programmenyn.

Startikonen installerar inte Python och skapar ingen separat Pythonmiljö.
Saknade tillägg kan repareras efter ditt godkännande. Linux behöver Zenity,
KDialog eller Tkinter för reparationsdialogen; systembibliotek och skyddad
system-Python kan kräva manuell hantering. [Läs plattformskraven](docs/guide.md#windows-macos-och-linux-2190).
macOS-startappen är lokalt skapad, inte en signerad installationsfil med inbyggd Python.

> **Appen startar alltid minimerad.** Klicka på kalenderikonen i systemfältet
> för att öppna fönstret. Saknas systemfält finns appen minimerad i aktivitetsfältet/Dock.
> Startar du appen igen öppnas den redan körande instansen.

**Hitta appens filer:** högerklicka på kalenderikonen i systemfältet och välj
**Öppna appmappen**. Då öppnas appens huvudmapp i datorns filhanterare.

## Var hamnar mina PDF:er?

Klicka på **Generera PDF**. Filen sparas i appmappen och öppnas med datorns standardprogram:

```text
export/
├── Kalender/
├── Semesterlista/
├── Fordon/
└── Hyra/
```

**Äldre PDF:er skrivs inte över.** Nya filer får ett datum-/tidstillägg när namnet redan finns.
Knappen **Öppna exportmapp** tar dig till listans arkiv. Egna PDF-logotyper ändras inte av appens nya ikonstil.

## Uppdatera

Välj **Hjälp → Sök efter uppdatering…**. Exportarkivet och användardata skyddas vid uppdatering.
Python uppdateras inte automatiskt. Om du flyttar appmappen behöver startgenvägen skapas om.
På macOS: ta först bort den gamla `Semesterlista.app` och kör startikonskommandot igen.

## Om något inte fungerar

| Problem | Prova detta |
|---|---|
| Inget fönster syns | Klicka på kalenderikonen i systemfältet eller aktivitetsfältet/Dock. |
| Tillägg saknas | Starta igen och godkänn reparationen. På Linux, se plattformskraven ovan. |
| PDF sparas men öppnas inte | Välj ett standardprogram för PDF i operativsystemet. Filen finns kvar i `export`. |
| En gammal ikon visas | Skapa om startgenvägen och ersätt gamla fästa genvägar. |
| Ett annat fel uppstår | Öppna **Inställningar → Avancerat**. Felloggen finns i `data/loggar/fel.log`. |

## För utvecklare

[Utförlig guide](docs/guide.md) · [Teknisk specifikation](spec.md) · [Ikoner och logotyp](assets/ikon/README.md)

```sh
python -m unittest discover -s tests -v
python tools/bump_version.py --check
```

CI testar på Linux, macOS och Windows. Programmet kräver PySide6 och reportlab;
se [requirements.txt](requirements.txt). Licens: [MIT](LICENSE).
