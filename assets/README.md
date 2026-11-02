# assets – bilder till PDF-exporten

Här ligger bilder som kan väljas som logotyp i programmet. Mappen läses
**rekursivt**, så du kan skapa egna undermappar (t.ex. per företag eller
avdelning).

```
assets/
├── README.md
├── ikon/                 ← appens ikon (fönster, tray, aktivitetsfält)
│   ├── appikon.svg
│   ├── appikon-16…256.png
│   └── appikon.ico
└── logotyper/
    └── exempel-logotyp.svg
```

## Så används bilderna

1. Öppna fliken **Hyra**, **Semesterlista** eller **Fordon**.
2. Klicka på **🖼️ Välj logotyp…**.
3. Välj en fil i listan (förhandsgranskning visas) och klicka **Använd**.

Logotypen ritas i övre högra hörnet på **varje sida** i den PDF som
genereras och sparas i inställningarna per flik.

## Format

| Format | Kvalitet i PDF | Kommentar |
|--------|----------------|-----------|
| `.svg` | Vektorgrafik (bäst) | Kräver `svglib`; annars rasteriseras SVG i 300 dpi med Qt |
| `.png` | Bra | Transparent bakgrund stöds |
| `.jpg` | Bra | Ingen transparens |

Rekommenderad storlek: bred bild, max ca 35 × 16 mm i PDF:en.
Bilden skalas automatiskt och proportionerna behålls.

## Tips

- Filnamn med å/ä/ö fungerar, men undvik mellanslag om du delar mappen.
- Dolda filer och mappar (som börjar med `.`) ignoreras.
- Lägg gärna logotypen i en undermapp, t.ex. `assets/logotyper/`.
