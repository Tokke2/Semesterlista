#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logotyper och bilder till PDF – assets-mappen (v2.5.0)
=====================================================

Appen kan sätta en logotyp på alla PDF:er som genereras. Bilderna ligger
i en undermapp till appen (`assets/`) och kan väljas i gränssnittet – även
från undermappar, t.ex. `assets/logotyper/`.

    Semesterlista/
    ├── assets/
    │   ├── README.md
    │   └── logotyper/
    │       ├── foretag.svg
    │       └── avdelning.svg
    ├── main.pyw
    └── ...

Modulen är Qt-fri där det går:
    - scan_assets()      – hitta bilder (rekursivt) utan Qt/reportlab
    - PdfLogo.load()     – ladda SVG/PNG/JPG till något som kan ritas i PDF
    - PdfLogo.draw_on()  – rita på en reportlab-canvas
    - make_page_logo_drawer() – onPage-callback till SimpleDocTemplate

SVG hanteras på två sätt:
    1. svglib (om installerat) → vektorgrafik i PDF:en (bäst kvalitet)
    2. PySide6 (alltid installerat) → rasteriseras i 300 dpi till PNG

Saknas båda ges ett tydligt fel (AssetError) i stället för en krasch.

Användning:
    from core.pdf_assets import scan_assets, logo_for_settings, \\
        make_page_logo_drawer

    for asset in scan_assets():                 # assets/ + undermappar
        print(asset.relative)

    logo = logo_for_settings(plugin.settings)   # settings["logo_svg"]
    drawer = make_page_logo_drawer(logo)        # None om ingen logotyp
    doc = SimpleDocTemplate(..., onFirstPage=drawer, onLaterPages=drawer)

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional, Sequence, Tuple, Union

from core.roster import resolve_path

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.5.0"

#: Mapp (relativt appens rot) där bilder letas upp
ASSET_DIR_NAME: str = "assets"

#: Filändelser som kan väljas som logotyp
SVG_SUFFIXES: Tuple[str, ...] = (".svg",)
RASTER_SUFFIXES: Tuple[str, ...] = (".png", ".jpg", ".jpeg")
IMAGE_SUFFIXES: Tuple[str, ...] = SVG_SUFFIXES + RASTER_SUFFIXES

#: 1 mm i punkter (samma som reportlab.lib.units.mm)
MM: float = 72.0 / 25.4

#: Upplösning när SVG rasteriseras med Qt
RASTER_DPI: int = 300

#: Standardstorlek på logotypen i PDF (mm)
DEFAULT_MAX_WIDTH_MM: float = 35.0
DEFAULT_MAX_HEIGHT_MM: float = 16.0

#: Standardmarginal från sidkanten (mm)
DEFAULT_MARGIN_MM: float = 8.0


# ══════════════════════════════════════════════════════════
# FEL
# ══════════════════════════════════════════════════════════

class AssetError(Exception):
    """Fel vid läsning eller rendering av en bild till PDF."""


# ══════════════════════════════════════════════════════════
# HITTA BILDER
# ══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AssetFile:
    """En bild som hittats i assets-mappen."""

    path: Path
    root: Path

    @property
    def name(self) -> str:
        """Filnamn utan ändelse, t.ex. 'foretag'."""
        return self.path.stem

    @property
    def suffix(self) -> str:
        """Filändelse i gemener, t.ex. '.svg'."""
        return self.path.suffix.lower()

    @property
    def is_svg(self) -> bool:
        """True om filen är en SVG."""
        return self.suffix in SVG_SUFFIXES

    @property
    def relative(self) -> str:
        """Sökväg relativt assets-mappen (med / som avgränsare)."""
        try:
            return self.path.relative_to(self.root).as_posix()
        except ValueError:  # pragma: no cover – defensivt
            return self.path.name

    @property
    def folder(self) -> str:
        """Undermapp relativt assets-mappen ('' om filen ligger direkt i den)."""
        parent = self.relative.rsplit("/", 1)
        return parent[0] if len(parent) > 1 else ""

    def __str__(self) -> str:  # pragma: no cover – endast presentation
        return self.relative


def assets_root(base: Optional[Union[str, Path]] = None) -> Path:
    """
    Sökväg till assets-mappen (skapas inte).

    Utan argument används appens egen assets-mapp. Anges en sökväg som
    redan slutar på "assets" används den, annars läggs "assets" till.
    """
    if base is None:
        return resolve_path(ASSET_DIR_NAME)

    path = Path(base).expanduser()
    return path if path.name.casefold() == ASSET_DIR_NAME else path / ASSET_DIR_NAME


def ensure_assets_dir(base: Optional[Union[str, Path]] = None) -> Path:
    """Skapa assets-mappen om den inte finns och returnera sökvägen."""
    root = assets_root(base)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_hidden(path: Path, root: Path) -> bool:
    """True om filen eller någon mapp på vägen börjar med punkt."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:  # pragma: no cover – defensivt
        parts = (path.name,)
    return any(part.startswith(".") for part in parts)


def scan_assets(
    root: Optional[Union[str, Path]] = None,
    suffixes: Sequence[str] = IMAGE_SUFFIXES,
    recursive: bool = True,
) -> List[AssetFile]:
    """
    Hitta bildfiler i assets-mappen.

    Args:
        root:      Mapp att söka i (standard: appens assets-mapp).
        suffixes:  Tillåtna filändelser (standard: svg/png/jpg/jpeg).
        recursive: Sök även i undermappar (standard: True).

    Returns:
        Alfabetiskt sorterad lista med AssetFile (tom om mappen saknas).
    """
    asset_root = Path(root).expanduser() if root is not None else assets_root()
    if not asset_root.exists() or not asset_root.is_dir():
        return []

    wanted = {suffix.lower() for suffix in suffixes}
    pattern = "**/*" if recursive else "*"

    found: List[AssetFile] = []
    for path in asset_root.glob(pattern):
        if not path.is_file():
            continue
        if path.suffix.lower() not in wanted:
            continue
        if _is_hidden(path, asset_root):
            continue
        found.append(AssetFile(path=path, root=asset_root))

    return sorted(found, key=lambda asset: asset.relative.casefold())


def find_asset(
    name: str,
    root: Optional[Union[str, Path]] = None,
    recursive: bool = True,
) -> Optional[AssetFile]:
    """
    Hitta en bild på filnamn, relativ sökväg eller stam.

    Exempel: find_asset("foretag.svg"), find_asset("logotyper/foretag.svg").
    """
    wanted = str(name).replace("\\", "/").strip().lower()
    if not wanted:
        return None

    assets = scan_assets(root, recursive=recursive)
    for asset in assets:
        if asset.relative.lower() == wanted:
            return asset
    for asset in assets:
        if asset.path.name.lower() == wanted:
            return asset
    for asset in assets:
        if asset.name.lower() == wanted:
            return asset
    return None


# ══════════════════════════════════════════════════════════
# LOGOTYP
# ══════════════════════════════════════════════════════════

class PdfLogo:
    """
    En logotyp som kan ritas på en reportlab-canvas.

    Skapas med PdfLogo.load("assets/logotyper/foretag.svg").
    """

    def __init__(
        self,
        path: Path,
        width: float,
        height: float,
        drawing: Any = None,
        image_path: Optional[Path] = None,
        natural_size: Optional[Tuple[float, float]] = None,
        vector: bool = False,
    ):
        self.path = Path(path)
        self.width = float(width)          # punkter (1/72 tum)
        self.height = float(height)
        self._drawing = drawing            # reportlab Drawing (vektor)
        self._image_path = image_path      # rasteriserad PNG
        self._natural_size = natural_size or (self.width, self.height)
        self.vector = vector

    # ──────────────────────────────────────────────────────
    # Laddning
    # ──────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        path: Union[str, Path],
        max_width_mm: float = DEFAULT_MAX_WIDTH_MM,
        max_height_mm: float = DEFAULT_MAX_HEIGHT_MM,
    ) -> "PdfLogo":
        """
        Ladda en SVG/PNG/JPG och skala den till max-storleken.

        Args:
            path:          Sökväg (relativ tolkas mot appens rotmapp).
            max_width_mm:  Största bredd i mm.
            max_height_mm: Största höjd i mm.

        Raises:
            AssetError: om filen saknas eller inte kan läsas.
        """
        target = resolve_path(path)
        if not target.exists():
            raise AssetError(f"Filen finns inte: {target}")

        max_w = float(max_width_mm) * MM
        max_h = float(max_height_mm) * MM

        if target.suffix.lower() in SVG_SUFFIXES:
            return cls._load_svg(target, max_w, max_h)
        return cls._load_raster(target, max_w, max_h)

    @classmethod
    def _load_svg(cls, path: Path, max_w: float, max_h: float) -> "PdfLogo":
        """Ladda SVG – helst som vektor (svglib), annars rasteriserad (Qt)."""
        drawing = cls._try_svg2rlg(path)
        if drawing is not None:
            natural_w = float(getattr(drawing, "width", 0) or 1)
            natural_h = float(getattr(drawing, "height", 0) or 1)
            scale = min(max_w / natural_w, max_h / natural_h)

            drawing.scale(scale, scale)
            drawing.width = natural_w * scale
            drawing.height = natural_h * scale

            logger.debug(f"Logotyp laddad som vektor: {path.name}")
            return cls(
                path=path,
                width=drawing.width,
                height=drawing.height,
                drawing=drawing,
                natural_size=(natural_w, natural_h),
                vector=True,
            )

        image_path, width, height = _rasterize_svg(path, max_w, max_h)
        logger.debug(f"Logotyp laddad som bild: {path.name}")
        return cls(
            path=path,
            width=width,
            height=height,
            image_path=image_path,
            natural_size=(width, height),
        )

    @staticmethod
    def _try_svg2rlg(path: Path) -> Any:
        """Försök konvertera SVG till en reportlab-Drawing med svglib."""
        try:
            from svglib.svglib import svg2rlg  # type: ignore[import-not-found]
        except Exception:
            return None

        try:
            return svg2rlg(str(path))
        except Exception as exc:  # svglib kan kasta flera olika fel
            logger.warning(f"svglib kunde inte läsa {path.name}: {exc}")
            return None

    @classmethod
    def _load_raster(cls, path: Path, max_w: float, max_h: float) -> "PdfLogo":
        """Ladda PNG/JPG och skala till max-storleken."""
        try:
            from reportlab.lib.utils import ImageReader
        except Exception as exc:  # pragma: no cover – reportlab saknas
            raise AssetError("reportlab krävs för att bädda in bilder") from exc

        try:
            width_px, height_px = ImageReader(str(path)).getSize()
        except Exception as exc:
            raise AssetError(f"Kunde inte läsa bilden {path.name}: {exc}") from exc

        if not width_px or not height_px:
            raise AssetError(f"Bilden {path.name} har ingen storlek")

        scale = min(max_w / float(width_px), max_h / float(height_px))
        return cls(
            path=path,
            width=float(width_px) * scale,
            height=float(height_px) * scale,
            image_path=path,
            natural_size=(float(width_px), float(height_px)),
        )

    # ──────────────────────────────────────────────────────
    # Rita
    # ──────────────────────────────────────────────────────

    def draw_on(
        self,
        canvas: Any,
        x: float,
        y: float,
        width: Optional[float] = None,
        height: Optional[float] = None,
    ) -> None:
        """
        Rita logotypen på en reportlab-canvas.

        Args:
            canvas: reportlab.pdfgen.canvas.Canvas
            x, y:   Nedre vänstra hörnet i punkter.
            width:  Valfri bredd (annars den inladdade storleken).
            height: Valfri höjd (annars den inladdade storleken).
        """
        target_w = float(width or self.width)
        target_h = float(height or self.height)

        if self._drawing is not None:
            from reportlab.graphics import renderPDF  # lokal import

            if abs(target_w - self._drawing.width) > 0.01 or abs(target_h - self._drawing.height) > 0.01:
                # Rita i önskad storlek utan att ändra originalet
                canvas.saveState()
                canvas.translate(x, y)
                canvas.scale(target_w / self._drawing.width, target_h / self._drawing.height)
                renderPDF.draw(self._drawing, canvas, 0, 0)
                canvas.restoreState()
                return

            renderPDF.draw(self._drawing, canvas, x, y)
            return

        if self._image_path is None:  # pragma: no cover – defensivt
            raise AssetError("Logotypen har inget innehåll")

        canvas.drawImage(
            str(self._image_path),
            x,
            y,
            width=target_w,
            height=target_h,
            mask="auto",
        )

    def draw_corner(
        self,
        canvas: Any,
        doc: Any,
        margin_mm: float = DEFAULT_MARGIN_MM,
        corner: str = "right",
    ) -> None:
        """
        Rita logotypen i övre högra (eller vänstra) hörnet på sidan.

        Args:
            canvas:    reportlab-canvas (eller None vid onPage).
            doc:       SimpleDocTemplate/BaseDocTemplate (för sidstorlek).
            margin_mm: Marginal till sidkanten.
            corner:    "right" eller "left".
        """
        page_size = getattr(doc, "pagesize", None) or getattr(canvas, "_pagesize", None)
        if not page_size:
            return

        page_w, page_h = float(page_size[0]), float(page_size[1])
        margin = float(margin_mm) * MM

        if corner == "left":
            x = margin
        else:
            x = page_w - margin - self.width
        y = page_h - margin - self.height

        canvas.saveState()
        try:
            self.draw_on(canvas, x, y)
        finally:
            canvas.restoreState()

    def __repr__(self) -> str:  # pragma: no cover – endast felsökning
        kind = "vektor" if self.vector else "bild"
        return f"PdfLogo({self.path.name!r}, {kind}, {self.width:.1f}×{self.height:.1f} pt)"


def _rasterize_svg(path: Path, max_w: float, max_h: float) -> Tuple[Path, float, float]:
    """
    Rasterisera en SVG till PNG med Qt (300 dpi).

    Returns:
        (png-sökväg, bredd i punkter, höjd i punkter)

    Raises:
        AssetError: om Qt saknas eller SVG-filen inte kan renderas.
    """
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except Exception as exc:  # pragma: no cover – Qt saknas
        raise AssetError(
            "SVG kan inte bäddas in: installera svglib (pip install svglib) "
            "eller använd en PNG/JPG."
        ) from exc

    try:
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            raise AssetError(f"Ogiltig SVG: {path.name}")

        default_size = renderer.defaultSize()
        natural_w = float(default_size.width() or 0)
        natural_h = float(default_size.height() or 0)
        if natural_w <= 0 or natural_h <= 0:
            natural_w, natural_h = max_w, max_h

        scale = min(max_w / natural_w, max_h / natural_h)
        target_w = max(1.0, natural_w * scale)
        target_h = max(1.0, natural_h * scale)

        px_scale = RASTER_DPI / 72.0
        width_px = max(1, int(round(target_w * px_scale)))
        height_px = max(1, int(round(target_h * px_scale)))

        image = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        try:
            renderer.render(painter)
        finally:
            painter.end()

        # Cacha renderingen så att samma SVG bara rastreras en gång
        digest = hashlib.sha1(
            f"{path.resolve()}|{path.stat().st_mtime_ns}|{width_px}x{height_px}".encode()
        ).hexdigest()[:12]
        cache_dir = Path(tempfile.gettempdir()) / "Semesterlista" / "logotyper"
        cache_dir.mkdir(parents=True, exist_ok=True)
        image_path = cache_dir / f"{path.stem}-{digest}.png"

        if not image_path.exists():
            if not image.save(str(image_path), "PNG"):
                raise AssetError(f"Kunde inte spara bilden för {path.name}")

        return image_path, target_w, target_h

    except AssetError:
        raise
    except Exception as exc:
        raise AssetError(f"Kunde inte rendera {path.name}: {exc}") from exc


def make_page_logo_drawer(
    logo: Optional[PdfLogo],
    margin_mm: float = DEFAULT_MARGIN_MM,
    corner: str = "right",
) -> Optional[Callable[[Any, Any], None]]:
    """
    Skapa en onPage-callback som ritar logotypen på varje sida.

    Returns:
        Callable(canvas, doc) eller None om ingen logotyp valts.
    """
    if logo is None:
        return None

    def _draw(canvas: Any, doc: Any) -> None:
        try:
            logo.draw_corner(canvas, doc, margin_mm=margin_mm, corner=corner)
        except Exception as exc:  # pragma: no cover – PDF:en ska alltid bli klar
            logger.warning(f"Kunde inte rita logotypen: {exc}")

    return _draw


def make_logo_canvas(
    logo: Optional[PdfLogo],
    margin_mm: float = DEFAULT_MARGIN_MM,
    corner: str = "right",
) -> Optional[Any]:
    """
    Skapa en Canvas-klass som ritar logotypen på varje sida.

    Används som ``canvasmaker`` till ``doc.build(...)``. Det fungerar i
    alla reportlab-versioner (onFirstPage/onLaterPages är inte giltiga
    argument i alla versioner och ignoreras då tyst).

    Returns:
        Canvas-klass, eller None om ingen logotyp valts.

    Exempel:
        maker = make_logo_canvas(logo)
        doc.build(elements, **({"canvasmaker": maker} if maker else {}))
    """
    if logo is None:
        return None

    try:
        from reportlab.pdfgen.canvas import Canvas as _Canvas
    except Exception:  # pragma: no cover – reportlab saknas
        logger.warning("reportlab saknas – logotypen kan inte ritas")
        return None

    class _LogoCanvas(_Canvas):
        """Canvas som ritar logotypen innan varje sida avslutas."""

        def showPage(self) -> None:  # noqa: N802 – reportlab-API
            try:
                logo.draw_corner(self, self, margin_mm=margin_mm, corner=corner)
            except Exception as exc:  # pragma: no cover – PDF:en ska bli klar
                logger.warning(f"Kunde inte rita logotypen: {exc}")
            super().showPage()

    return _LogoCanvas


def logo_for_settings(
    settings: Optional[Mapping[str, Any]],
    key: str = "logo_svg",
    max_width_mm: float = DEFAULT_MAX_WIDTH_MM,
    max_height_mm: float = DEFAULT_MAX_HEIGHT_MM,
) -> Optional[PdfLogo]:
    """
    Hämta logotypen som angetts i inställningarna.

    Args:
        settings: Plugin-inställningar (dict).
        key:      Inställningsnyckel (standard: "logo_svg").
        max_width_mm / max_height_mm: Största storlek i PDF:en.

    Returns:
        PdfLogo, eller None om ingen logotyp är vald.

    Raises:
        AssetError: om den valda filen inte kan läsas.
    """
    if not settings:
        return None

    value = str(settings.get(key) or "").strip()
    if not value:
        return None

    return PdfLogo.load(value, max_width_mm=max_width_mm, max_height_mm=max_height_mm)
