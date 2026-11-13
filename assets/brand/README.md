# Semesterlista – vektorlogotyp för tryck

- `logotyp-tryck.svg`: färglogotyp, transparent bakgrund.
- `logotyp-svart.svg`: svart/vit variant, transparent bakgrund och vita urtag.
- `logotyp.svg`: webbvariant med ljus bakgrund, används i GitHub README.

Alla bokstäver är omvandlade till vektorbanor. Inga typsnitt behöver installeras
hos mottagaren. Filerna innehåller inga rasterbilder, länkade resurser eller
inbäddade typsnitt och kan skalas utan pixelförlust. Grundbredd: 180 mm;
behåll proportionerna vid storleksändring. Ikonen finns separat i `../ikon`.

Färgversionen använder SVG/RGB med lila, korallrosa och turkosa vektorövertoningar,
mörkblå #16324f, mint #36d6be, gul #ffcb77 och vitt.
Den är inte en CMYK/PDF-X-fil. Låt tryckeriet konvertera färgerna enligt sin
ICC-profil och lägga till eventuella skärmärken/utfall efter placering i layouten.
Den svarta varianten innehåller endast svart och vita urtag, utan övertoningar
eller genomskinliga färglager. Använd denna för enfärgstryck.

Designen är egenritad, utan AI-genererade bilder. Bokstavsformerna kommer från
DejaVu Sans/DejaVu Sans Bold; licensen finns i `FONT-LICENSE.txt`.

## Bygg om

Byggverktyget kräver fontTools (inte ett runtime-beroende för appen):

    python tools/make_brand.py --font /sökväg/DejaVuSans-Bold.ttf --regular-font /sökväg/DejaVuSans.ttf

Kör från repositoryts rot. Efter ändring av appikonens SVG körs även
`python tools/make_icons.py` för PNG/ICO. Vid ikonändring ska den inbyggda
ICON_SVG-reserven i core/app_icon.py uppdateras; ett test kontrollerar överensstämmelsen.

## Flashigare identitet (2.21.1)

Lutad kalender, blå–lila platta med ljus kant, turkos bockmarkering och gul
stjärndetalj. Ordmärket har två färger och en luftig versal underrad.
Övertoningarna är standard-SVG, inte rastereffekter. Använd en SVG-renderare
med stöd för linearGradient (t.ex. en modern webbläsare) för förhandsvisning.

## Ny identitet och samlat releasepaket (2.22.0)

Ny kalender med tydlig stor bock, varm solskiva, lila djup och turkos/rosa kant.
Ordmärket har en sammanhängande färgövergång från lila till korallorange.
Webblogotypen har ljus bakgrund; tryckversionerna är transparenta.

**Alla dessa filer följer med i samma Source code (zip) som appen i releasen.**
Ingen separat grafiknedladdning behövs. Efter uppackning finns färg- och
svartvit tryck-SVG samt licens här i `assets/brand/`. Bokstäverna är banor;
övertoningarna är vektorer. Ingen AI-generering eller inbäddad rastergrafik.
