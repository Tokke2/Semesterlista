# Semesterlista – vektorlogotyp för tryck

- `logotyp-tryck.svg`: färglogotyp, transparent bakgrund.
- `logotyp-svart.svg`: svart/vit variant, transparent bakgrund och vita urtag.
- `logotyp.svg`: webbvariant med ljus bakgrund, används i GitHub README.

Alla bokstäver är omvandlade till vektorbanor. Inga typsnitt behöver installeras
hos mottagaren. Filerna innehåller inga rasterbilder, länkade resurser eller
inbäddade typsnitt och kan skalas utan pixelförlust. Grundbredd: 180 mm;
behåll proportionerna vid storleksändring. Ikonen finns separat i `../ikon`.

Färgversionen använder SVG/RGB: mörkblå #16324f, mint #36d6be, gul #ffcb77 och vitt.
Den är inte en CMYK/PDF-X-fil. Låt tryckeriet konvertera färgerna enligt sin
ICC-profil och lägga till eventuella skärmärken/utfall efter placering i layouten.
Den svarta varianten innehåller endast svart och vita urtag.

Designen är egenritad, utan AI-genererade bilder. Bokstavsformerna kommer från
DejaVu Sans/DejaVu Sans Bold; licensen finns i `FONT-LICENSE.txt`.

## Bygg om

Byggverktyget kräver fontTools (inte ett runtime-beroende för appen):

    python tools/make_brand.py --font /sökväg/DejaVuSans-Bold.ttf --regular-font /sökväg/DejaVuSans.ttf

Kör från repositoryts rot. Efter ändring av appikonens SVG körs även
`python tools/make_icons.py` för PNG/ICO. Vid ikonändring ska den inbyggda
ICON_SVG-reserven i core/app_icon.py uppdateras; ett test kontrollerar överensstämmelsen.
