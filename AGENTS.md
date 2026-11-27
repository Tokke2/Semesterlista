# Semesterlista – bestående arbetsregler

Läs denna fil vid början av varje chatt. Regler är krav, inte intyg om att funktioner är implementerade. Följ även plattformens överordnade instruktioner. Lägg till nya uttryckliga användarregler här och publicera dem på arbetsbranchen.

## Git och leverans – hårda regler
- Arbeta endast på sessionens arbetsbranch, nu `arena/320ac526-semesterlista`. Aldrig utveckling eller appuppdateringar mot main. Ingen PR och ingen merge. Byt/skapa/byt namn på branch inte i denna session.
- Önskat slutläge: endast arbetsbranchen kvar och den som GitHub-standardbranch, även för kommande chattar. Inte uppnått: GitHub nekade standardbyte med 403; andra brancher har inte raderats. Ny chatt måste kontrollera sin tilldelade branch. Radera aldrig historik utan kontroll av unika commits och gällande behörigheter.
- Fast appversion **2.26.0**. Releasebyggtaggar får öka. Uppdateraren jämför filer, även vid samma appversion, inte enbart versionsnummer.
- Vid kodändring: tester, commit/push endast arbetsbranch, ny GitHubrelease, ett gemensamt ZIP för alla OS. Markera Latest först efter lyckad uppladdning och verifiera med API.
- Inga tysta beroende- eller gränssnittsbrott. Redovisa tester, överhoppade tester, kvarstående risker och begränsningar innan arbetet kallas klart.
- CRLF i textfiler utom README. PowerShell UTF-8 med exakt en BOM.

## Dialog och förslag – hårda regler
- Förslag ska alltid skrivas direkt i chatten, inte bara i en fil.
- Efter tio användarmeddelanden: skriv tio nya, inte återanvända förslag i chatten. För beständig räknare och idéhistorik i docs/conversation-state.md; uppdatera vid varje behandlat användarmeddelande. Startpunkt är användarmeddelandet som införde regeln, räknat som 1.
- Vid begäran om 25 nya förslag: ge 25. Konkurrentluckor och efterfrågan får inte påstås vara verifierade utan källor. Jämför med tidigare listor.
- Skriv in framtida krav uttryckligen märkta ”regel” eller ”hård regel” här. Anpassa till Semesterlista; inför inte funktioner från andra appar utan relevans.
- REQ-K4 nämndes utan definition. Hitta inte på betydelsen; be om definition när den behövs.

## Gränssnitt och resurser
- Anpassa vyer, text, bilder, ikoner och kolumner efter skärm och DPI; tydlig text utan uppskalade små rasterikoner. Minimera scroll men behåll åtkomst till allt; ingen garanti att allt ryms samtidigt vid 200% zoom.
- Start alltid minimerad/terminalfri, även skanning och omstart. Vid öppning: använd skärmens tillgängliga höjd och anpassad bredd, utan att täcka systemfält. Minimerad start har företräde framför synligt maximerat fönster.
- En instans; nytt manuellt startförsök visar befintlig. Minimera och X till systemfältet; öppna appmapp via systemfältets meny.
- Gemensam skarp logotyp överallt, redigerbar SVG för tryck och tydliga vektorikoner. Ingen AI-bildgenerering; lokala bilder, eventuellt senare valfri Pixabay.
- Förbättra minne, hastighet och energiförbrukning; mät innan procenttal eller garantier anges. Undvik kontinuerlig polling för sällanhändelser.
- Sorterbara/flyttbara kolumner där semantiken tillåter det; sortera aldrig datum så kalenderlogiken förstörs.
- Egen inställningsunderflik för profilskapande endast om appen har profiler. Återställ äldre ”ruta”-val i projektskapare endast i appar som hade det; sådan funktion är inte identifierad i Semesterlista.

## Uppdatering och loggar
- Krav: säker filbaserad uppdatering, automatisk kontroll dagligen 00:00 lokal tid, installera endast vid skillnad, därefter automatisk omstart/start utan terminal. Hantera osparat arbete och missad midnatt säkert; genomförandet återstår att verifiera.
- Behåll uppdateringsbackup vid fel; ta bort den först efter verifierat lyckad uppdatering/start. Detta är inte samma sak som att all filkopiering lyckades. Befintlig implementation uppfyller ännu inte hela kravet.
- Gårdagens applogg arkiveras. Arkiverade apploggar rensas efter sju dagar. Separat beständig fellogg för aktiva fel; åldersrensning får inte ta bort aktiva fel.
- Åtgärdade fel ska kunna tas bort; automatisk borttagning kräver faktiskt verifierad återhämtning, inte att felet slutat loggas. Nuvarande manuella rensning är inte ett per-fel-ärendesystem.

## Befintliga produktregler
- Kalender separat från anställda/semester. Anställda avser semester, fordon körning. Hyra månads-/kvartalsvis utan fakturor; kvartalsutskick och betalning vid kvartalsbörjan.
- PDF arkiveras under app/export efter sort och öppnas automatiskt. Kalender alltid liggande A4. Semesterlista/Fordon en månad stående, två–tre liggande. Tre månader ska rymmas på ett blad. Ingen tom bildplats utan bild. Säsongsfärger och lokala bilder för alla tre exporttyper.
- Veckostart alltid måndag. Svenska/amerikanska helgdagar efter region; endast officiella helgdagar röda, temadagar inte ledighet.
- Samma gemensamma installerade Python, ingen venv. Prioritera Python 3.15, annars 3.14/annan stödd system-Python. Erbjud Pythoninstallation endast om Python helt saknas; aldrig uppgradering av befintlig Python. Ingen separat Pythoninstallerare i paketet och inget Pythonunderhåll vid start/veckoschema.
- Appberoenden installeras/uppdateras med samtycke, inte tyst.
- Licens: gratis privat/kommersiellt bruk och gratis oförändrad vidareförmedling med licens. Ingen ändring/försäljning utan tillstånd. Inte MIT; tidigare GPL-rättigheter påverkas inte retroaktivt.
- Donation låst i menyn: Swish 0721817177, standard-Swish-QR. Ingen användarredigering av betalningsmottagare.
