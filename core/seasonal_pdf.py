"""Local seasonal images and independent PDF colour / grayscale output."""
from io import BytesIO
import logging
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image as PillowImage, ImageOps
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle
from core import i18n
from core.calendar_data import season

logger = logging.getLogger(__name__)
SEASON_COLORS = {"winter": "#DDECF6", "spring": "#E5EFCF", "summer": "#FFF0C2", "autumn": "#F5DCCD"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def image_files(folder):
    root = Path(folder)
    if not folder or not root.is_dir():
        return []
    try:
        return sorted((p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES), key=lambda p: p.name.casefold())
    except OSError as exc:
        logger.warning("Cannot read seasonal image folder %s: %s", folder, exc)
        return []


def seasonal_header(month, settings, width):
    if not settings.get("seasonal_pdf", False):
        return []
    key = season(month)
    band = Table([[i18n.t(f"season.{key}")]], colWidths=[width])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SEASON_COLORS[key])),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]))
    result = [band, Spacer(1, 3)]
    path = str(settings.get("season_images", {}).get(key, ""))
    if path:
        try:
            with PillowImage.open(path) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1800, 900))
                if settings.get("pdf_monochrome", False):
                    image = ImageOps.grayscale(image)
                else:
                    image = image.convert("RGB")
                stream = BytesIO()
                image.save(stream, "PNG")
                stream.seek(0)
                factor = min(width / image.width, 48 / image.height)
                result.append(Image(stream, width=image.width * factor, height=image.height * factor))
                result.append(Spacer(1, 4))
        except (OSError, ValueError, PillowImage.DecompressionBombError) as exc:
            logger.warning("Season image unavailable: %s: %s", path, exc)
            result.append(Paragraph(escape(i18n.t("season.missing")), ParagraphStyle("missing", fontSize=7, leading=9)))
    return result


def print_canvas(base=None, monochrome=False):
    base = base or Canvas
    if not monochrome:
        return base

    def gray(color):
        c = colors.toColor(color)
        value = 0.299 * c.red + 0.587 * c.green + 0.114 * c.blue
        return colors.Color(value, value, value, alpha=c.alpha)

    class GrayscaleCanvas(base):
        def setFillColor(self, color, alpha=None):
            return super().setFillColor(gray(color), alpha=alpha)

        def setStrokeColor(self, color, alpha=None):
            return super().setStrokeColor(gray(color), alpha=alpha)

        def setFillColorRGB(self, r, g, b, alpha=None):
            self.setFillColor(colors.Color(r, g, b), alpha=alpha)

        def setStrokeColorRGB(self, r, g, b, alpha=None):
            self.setStrokeColor(colors.Color(r, g, b), alpha=alpha)

        def drawImage(self, image, *args, **kwargs):
            reader = image if isinstance(image, ImageReader) else ImageReader(image)
            pixels = reader.getRGBData()
            source = PillowImage.frombytes(reader.mode, reader.getSize(), pixels)
            source = ImageOps.grayscale(source)
            alpha = getattr(reader, "_dataA", None)
            if alpha is not None:
                source.putalpha(PillowImage.frombytes("L", reader.getSize(), alpha.getRGBData()))
            return super().drawImage(ImageReader(source), *args, **kwargs)

    return GrayscaleCanvas
