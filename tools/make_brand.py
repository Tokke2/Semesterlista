"""Build print SVGs with outlined lettering; fontTools is a build-only dependency.

python tools/make_brand.py --font /path/DejaVuSans-Bold.ttf --regular-font /path/DejaVuSans.ttf
The output contains no text, embedded fonts, raster images or external references.
"""
import argparse
import re
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

ROOT = Path(__file__).resolve().parent.parent


def outlined(text, font_path, size, x, baseline, spacing=0):
    with TTFont(font_path) as font:
        glyphs = font.getGlyphSet()
        cmap = font.getBestCmap()
        scale = size / font['head'].unitsPerEm
        paths = []
        for char in text:
            name = cmap[ord(char)]
            pen = SVGPathPen(glyphs)
            glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
            commands = pen.getCommands()
            if commands:
                paths.append(f'<path d="{commands}"/>')
            x += glyphs[name].width * scale + spacing
        return '\n'.join(paths), x


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', required=True, type=Path)
    parser.add_argument('--regular-font', required=True, type=Path)
    args = parser.parse_args()
    mark = (ROOT / 'assets/ikon/appikon.svg').read_text(encoding='utf-8')
    mark = mark[mark.index('>') + 1:mark.rindex('</svg>')]
    first, join = outlined('Semester', args.font, 48, 130, 66)
    last, end = outlined('lista', args.font, 48, join, 66)
    tagline, _ = outlined('PLANERA. SAMLA. SKRIV UT.', args.regular_font, 12, 133, 98, spacing=1.9)
    width = round(end + 24)
    content = (f'<g transform="translate(12 16) scale(1.5)">{mark}</g>'
               f'<defs><linearGradient id="wordmark" gradientUnits="userSpaceOnUse" x1="{join}" y1="0" x2="{end}" y2="0">'
               '<stop stop-color="#a13ed7"/><stop offset="0.5" stop-color="#ec438e"/><stop offset="1" stop-color="#f28045"/>'
               '</linearGradient></defs>'
               f'<g fill="#261653">{first}</g><g fill="url(#wordmark)">{last}</g>'
               f'<g fill="#665776">{tagline}</g>'
               '<rect x="133" y="78" width="52" height="3" rx="1.5" fill="#ec438e"/>'
               '<rect x="190" y="78" width="14" height="3" rx="1.5" fill="#36d6be"/>')
    folder = ROOT / 'assets/brand'
    for name, background, black in [('logotyp.svg', True, False),
                                     ('logotyp-tryck.svg', False, False),
                                     ('logotyp-svart.svg', False, True)]:
        body = content
        if black:
            # One-ink artwork: no gradients, translucency or gray values.
            body = re.sub(r'<defs>.*?</defs>', '', body, flags=re.S)
            body = re.sub(r'<(?:path|rect)\b[^>]*\bopacity="[^"]+"[^>]*/>', '', body)
            body = re.sub(r' opacity="[^"]+"', '', body)
            def monochrome(match):
                attr, value = match.groups()
                if value == 'none':
                    return match.group(0)
                white = value in ('#ffffff', 'url(#icon-page)', 'url(#icon-badge)')
                return f'{attr}="{"#ffffff" if white else "#000000"}"'
            body = re.sub(r'(fill|stroke)="([^"]+)"', monochrome, body)
        if background:
            body = f'<rect width="{width}" height="128" rx="20" fill="#fbf8ff"/>' + body
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="{180*128/width:.3f}mm" '
               f'viewBox="0 0 {width} 128" role="img" aria-label="Semesterlista – Planera. Samla. Skriv ut.">\n'
               '<title>Semesterlista</title>\n' + body + '\n</svg>\n')
        svg = '\n'.join(line.rstrip() for line in svg.splitlines()) + '\n'
        (folder / name).write_text(svg, encoding='utf-8', newline='\r\n')


if __name__ == '__main__':
    main()
