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
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional, Sequence, Tuple, Union

from core.roster import resolve_path

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.17.3"

#: Mapp (relativt appens rot) där bilder letas upp
ASSET_DIR_NAME: str = "assets"

#: Filändelser som kan väljas som logotyp
SVG_SUFFIXES: Tuple[str, ...] = (".svg",)
RASTER_SUFFIXES: Tuple[str, ...] = (".png", ".jpg", ".jpeg")
IMAGE_SUFFIXES: Tuple[str, ...] = SVG_SUFFIXES + RASTER_SUFFIXES

#: EPS (v2.11.0) – konverteras till PNG med Ghostscript
EPS_SUFFIXES: Tuple[str, ...] = (".eps",)

#: PDF (v2.11.0) – första sidan rastreras med PyMuPDF
PDF_SUFFIXES: Tuple[str, ...] = (".pdf",)

#: Allt som går att infoga som logotyp (dropdown-listan visar bara SVG)
IMPORT_SUFFIXES: Tuple[str, ...] = (
    IMAGE_SUFFIXES + EPS_SUFFIXES + PDF_SUFFIXES
)

#: Miljövariabel som pekar ut Ghostscript (behövs för EPS)
GHOSTSCRIPT_ENV: str = "SEMESTERLISTA_GHOSTSCRIPT"

#: Upplösning när EPS/PDF rastreras
CONVERT_DPI: int = 600

#: Gränser för storleksreglaget (procent av den automatiska storleken)
LOGO_SCALE_MIN: int = 25
LOGO_SCALE_MAX: int = 300
LOGO_SCALE_DEFAULT: int = 100

#: Undermappar som aldrig ska dyka upp i logotypväljaren (v2.7.0).
#: "ikon" innehåller appens egen ikon – den är ingen logotyp.
EXCLUDED_DIR_NAMES: Tuple[str, ...] = ("ikon",)

#: 1 mm i punkter (samma som reportlab.lib.units.mm)
MM: float = 72.0 / 25.4

#: Upplösning när SVG rasteriseras med Qt
RASTER_DPI: int = 300

#: Standardstorlek på logotypen i PDF (mm) när den laddas
DEFAULT_MAX_WIDTH_MM: float = 35.0
DEFAULT_MAX_HEIGHT_MM: float = 16.0

#: Automatisk storlek i PDF:en (v2.10.0) – andel av sidans bredd/höjd
AUTO_WIDTH_RATIO: float = 0.15
AUTO_HEIGHT_RATIO: float = 0.08

#: Tak för den automatiska storleken (mm) – gäller även stora sidor
AUTO_MAX_WIDTH_MM: float = 60.0
AUTO_MAX_HEIGHT_MM: float = 25.0

#: Minsta ruta som logotypen får ritas i (punkter) – gäller även små sidor
AUTO_MIN_WIDTH_PT: float = 36.0
AUTO_MIN_HEIGHT_PT: float = 12.0

#: Tak när användaren förstorar logotypen (v2.11.0). Höjden får aldrig bli
#: större än den automatiska (8 % av sidan) – då skulle logotypen hamna över
#: färgförklaringen. Bredden får växa till 25 % av sidan.
SCALE_MAX_WIDTH_RATIO: float = 0.25
SCALE_MAX_HEIGHT_RATIO: float = 0.08

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


def _in_excluded_dir(
    path: Path,
    root: Path,
    excluded: Sequence[str],
) -> bool:
    """True om filen ligger i en undantagen undermapp (t.ex. assets/ikon)."""
    if not excluded:
        return False

    try:
        folders = path.relative_to(root).parts[:-1]
    except ValueError:  # pragma: no cover – defensivt
        return False

    unwanted = {name.casefold() for name in excluded}
    return any(folder.casefold() in unwanted for folder in folders)


def scan_assets(
    root: Optional[Union[str, Path]] = None,
    suffixes: Sequence[str] = IMAGE_SUFFIXES,
    recursive: bool = True,
    exclude_dirs: Sequence[str] = EXCLUDED_DIR_NAMES,
) -> List[AssetFile]:
    """
    Hitta bildfiler i assets-mappen.

    Args:
        root:         Mapp att söka i (standard: appens assets-mapp).
        suffixes:     Tillåtna filändelser (standard: svg/png/jpg/jpeg).
        recursive:    Sök även i undermappar (standard: True).
        exclude_dirs: Undermappar att hoppa över (standard: "ikon",
                      där appens egen ikon ligger).

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
        if _in_excluded_dir(path, asset_root, exclude_dirs):
            continue
        found.append(AssetFile(path=path, root=asset_root))

    return sorted(found, key=lambda asset: asset.relative.casefold())


def find_asset(
    name: str,
    root: Optional[Union[str, Path]] = None,
    recursive: bool = True,
    exclude_dirs: Sequence[str] = EXCLUDED_DIR_NAMES,
) -> Optional[AssetFile]:
    """
    Hitta en bild på filnamn, relativ sökväg eller stam.

    Exempel: find_asset("foretag.svg"), find_asset("logotyper/foretag.svg").
    """
    wanted = str(name).replace("\\", "/").strip().lower()
    if not wanted:
        return None

    assets = scan_assets(root, recursive=recursive, exclude_dirs=exclude_dirs)
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
# KONVERTERING AV EPS OCH PDF (v2.11.0)
# ══════════════════════════════════════════════════════════

def find_ghostscript() -> Optional[str]:
    """
    Hitta Ghostscript (behövs för EPS).

    Ordningen är: miljövariabeln ``SEMESTERLISTA_GHOSTSCRIPT``, sedan
    ``gswin64c``/``gswin32c``/``gs`` i PATH och sist vanliga
    installationsmappar.

    Returns:
        Sökväg till programmet, eller None om det saknas.
    """
    override = os.environ.get(GHOSTSCRIPT_ENV, "").strip()
    if override:
        if Path(override).exists() or shutil.which(override):
            return override
        logger.warning(f"{GHOSTSCRIPT_ENV} pekar på en fil som inte finns: {override}")
        return None

    for name in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(name)
        if found:
            return found

    candidates: List[Path] = []
    if os.name == "nt":
        for base in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ):
            if base:
                candidates.extend(
                    sorted(Path(base).glob("gs/gs*/bin/gswin64c.exe"), reverse=True)
                )
    else:
        candidates.extend(
            Path(path)
            for path in ("/usr/local/bin/gs", "/opt/homebrew/bin/gs", "/usr/bin/gs")
        )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def ghostscript_hint() -> str:
    """Kort förklaring som visas när EPS saknar Ghostscript."""
    return (
        "EPS kräver Ghostscript, som inte hittades på datorn. Installera "
        "Ghostscript (gratis) och starta om appen – eller spara logotypen "
        "som SVG eller PDF i stället."
    )


def _logo_cache_path(path: Path, kind: str, dpi: int, suffix: str) -> Path:
    """Sökväg i logotypcachen (samma mapp som de rastrerade SVG-filerna)."""
    from core.cache import logo_cache_dir

    digest = hashlib.sha1(
        f"{path.resolve()}|{path.stat().st_mtime_ns}|{kind}|{dpi}".encode()
    ).hexdigest()[:12]
    return logo_cache_dir() / f"{path.stem}-{kind}-{digest}{suffix}"


def convert_eps_to_png(path: Union[str, Path], dpi: int = CONVERT_DPI) -> Path:
    """
    Konvertera en EPS-fil till PNG med Ghostscript.

    Args:
        path: EPS-filen.
        dpi:  Upplösning (600 räcker gott för en logotyp).

    Returns:
        Sökväg till den cachade PNG-filen.

    Raises:
        AssetError: om filen saknas, Ghostscript saknas eller körningen
                    misslyckas.
    """
    target = resolve_path(path)
    if not target.exists():
        raise AssetError(f"Filen finns inte: {target}")
    if not target.is_file():
        raise AssetError(f"Inte en fil: {target}")

    cached = _logo_cache_path(target, "eps", int(dpi), ".png")
    if cached.exists():
        return cached

    gs = find_ghostscript()
    if not gs:
        raise AssetError(ghostscript_hint())

    command = [
        gs,
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-dEPSCrop",
        "-dGraphicsAlphaBits=4",
        "-dTextAlphaBits=4",
        "-sDEVICE=pngalpha",
        f"-r{int(dpi)}",
        f"-sOutputFile={cached}",
        str(target),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AssetError(f"Kunde inte köra Ghostscript: {exc}") from exc

    if result.returncode != 0 or not cached.exists():
        message = (result.stderr or result.stdout or "").strip().splitlines()
        detail = message[-1] if message else f"felkod {result.returncode}"
        raise AssetError(f"Ghostscript kunde inte läsa {target.name}: {detail}")

    logger.info(f"EPS konverterad till PNG: {target.name}")
    return cached


def convert_pdf_to_png(path: Union[str, Path], dpi: int = CONVERT_DPI) -> Path:
    """
    Rastrera första sidan av en PDF till PNG med PyMuPDF.

    Args:
        path: PDF-filen.
        dpi:  Upplösning.

    Returns:
        Sökväg till den cachade PNG-filen.

    Raises:
        AssetError: om filen saknas, PyMuPDF saknas eller sidan inte kan
                    rastreras.
    """
    target = resolve_path(path)
    if not target.exists():
        raise AssetError(f"Filen finns inte: {target}")

    cached = _logo_cache_path(target, "pdf", int(dpi), ".png")
    if cached.exists():
        return cached

    try:
        import pymupdf  # type: ignore[import-not-found]
    except Exception:
        try:
            import fitz as pymupdf  # type: ignore[import-not-found,no-redef]
        except Exception as exc:  # pragma: no cover – PyMuPDF saknas
            raise AssetError(
                "PDF-logotyper kräver PyMuPDF (pip install pymupdf)."
            ) from exc

    try:
        document = pymupdf.open(str(target))
    except Exception as exc:
        raise AssetError(f"Kunde inte läsa PDF:en {target.name}: {exc}") from exc

    try:
        if document.page_count < 1:  # pragma: no cover – tom PDF
            raise AssetError(f"PDF:en {target.name} har inga sidor")
        page = document[0]
        pixmap = page.get_pixmap(dpi=int(dpi), alpha=True)
        if not pixmap.width or not pixmap.height:
            raise AssetError(f"PDF:en {target.name} gav en tom bild")
        pixmap.save(str(cached))
    except AssetError:
        raise
    except Exception as exc:
        raise AssetError(f"Kunde inte rastrera {target.name}: {exc}") from exc
    finally:
        document.close()

    logger.info(f"PDF konverterad till PNG: {target.name}")
    return cached


# ══════════════════════════════════════════════════════════
# LOGOTYP
# ══════════════════════════════════════════════════════════

class PdfLogo:
    """
    En logotyp som kan ritas på en reportlab-canvas.

    Skapas med PdfLogo.load("assets/logotyper/foretag.svg").
    """

    #: Standardvärde för storleksreglaget (1.0 = automatisk storlek)
    scale: float = 1.0

    def __init__(
        self,
        path: Path,
        width: float,
        height: float,
        drawing: Any = None,
        image_path: Optional[Path] = None,
        natural_size: Optional[Tuple[float, float]] = None,
        vector: bool = False,
        scale: float = 1.0,
    ):
        self.path = Path(path)
        self.width = float(width)          # punkter (1/72 tum)
        self.height = float(height)
        self._drawing = drawing            # reportlab Drawing (vektor)
        self._image_path = image_path      # rasteriserad PNG
        self._natural_size = natural_size or (self.width, self.height)
        self.vector = vector
        # Användarens storleksreglage (1.0 = automatisk storlek, v2.11.0)
        self.scale = max(0.1, min(float(scale or 1.0), 5.0))

    # ──────────────────────────────────────────────────────
    # Laddning
    # ──────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        path: Union[str, Path],
        max_width_mm: float = DEFAULT_MAX_WIDTH_MM,
        max_height_mm: float = DEFAULT_MAX_HEIGHT_MM,
        scale: float = 1.0,
    ) -> "PdfLogo":
        """
        Ladda en SVG/EPS/PDF/PNG/JPG och skala den till max-storleken.

        Args:
            path:          Sökväg (relativ tolkas mot appens rotmapp).
            max_width_mm:  Största bredd i mm.
            max_height_mm: Största höjd i mm.
            scale:         Storleksreglage (1.0 = automatisk storlek).

        Raises:
            AssetError: om filen saknas, EPS saknar Ghostscript eller
                        filen inte kan läsas.
        """
        target = resolve_path(path)
        if not target.exists():
            raise AssetError(f"Filen finns inte: {target}")

        factor = max(0.1, min(float(scale or 1.0), 5.0))
        max_w = float(max_width_mm) * MM * factor
        max_h = float(max_height_mm) * MM * factor

        suffix = target.suffix.lower()
        if suffix in SVG_SUFFIXES:
            logo = cls._load_svg(target, max_w, max_h)
        elif suffix in EPS_SUFFIXES:
            logo = cls._load_converted(target, max_w, max_h, convert_eps_to_png, "EPS")
        elif suffix in PDF_SUFFIXES:
            logo = cls._load_converted(target, max_w, max_h, convert_pdf_to_png, "PDF")
        else:
            logo = cls._load_raster(target, max_w, max_h)

        logo.scale = factor
        return logo

    @classmethod
    def _load_converted(
        cls,
        path: Path,
        max_w: float,
        max_h: float,
        converter: Callable[[Path], Path],
        kind: str,
    ) -> "PdfLogo":
        """
        Ladda EPS/PDF genom att först rastrera den till PNG (v2.11.0).

        Args:
            path:      Originalfilen (sparas som ``logo.path``).
            converter: Funktion som ger en PNG-sökväg.
            kind:      "EPS" eller "PDF" (för loggning).

        Raises:
            AssetError: om konverteringen misslyckas.
        """
        png = converter(path)
        logo = cls._load_raster(png, max_w, max_h)
        # Behåll originalfilens sökväg – det är den användaren valde
        logo.path = path
        logger.debug(f"Logotyp laddad från {kind}: {path.name}")
        return logo

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

    def auto_size(
        self,
        page_width: float,
        page_height: float,
        width_ratio: float = AUTO_WIDTH_RATIO,
        height_ratio: float = AUTO_HEIGHT_RATIO,
        max_width_mm: float = AUTO_MAX_WIDTH_MM,
        max_height_mm: float = AUTO_MAX_HEIGHT_MM,
        scale: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Beräkna logotypens storlek för en sida (v2.10.0).

        Logotypen får plats i en ruta som är en andel av sidans bredd och
        höjd (med ett tak i mm) och skalas **både upp och ned** så att den
        fyller rutan utan att förvrängas. Proportionerna behålls alltid.

        v2.11.0: ``scale`` (eller logotypens eget ``scale``) förstorar eller
        förminskar rutan, så att användaren kan anpassa storleken. Rutan
        begränsas fortfarande av sidan.

        Args:
            page_width / page_height: Sidans storlek i punkter.
            width_ratio / height_ratio: Andel av sidan som logotypen får ta.
            max_width_mm / max_height_mm: Tak i millimeter.
            scale: Egen skala (None = logotypens inställning).

        Returns:
            (bredd, höjd) i punkter.
        """
        if scale is None:
            factor = float(getattr(self, "scale", 1.0) or 1.0)
        else:
            factor = float(scale)
        factor = max(0.1, min(factor, 5.0))
        page_w = max(float(page_width), 1.0)
        page_h = max(float(page_height), 1.0)

        # Rutan som logotypen måste rymmas i (min-storleken gäller rutan,
        # så att logotypen aldrig hamnar utanför den eller förvrängs)
        box_w = max(
            min(page_w * float(width_ratio), float(max_width_mm) * MM),
            AUTO_MIN_WIDTH_PT,
        ) * factor
        box_h = max(
            min(page_h * float(height_ratio), float(max_height_mm) * MM),
            AUTO_MIN_HEIGHT_PT,
        ) * factor

        # Aldrig utanför sidan, oavsett reglage – och aldrig över tabellen
        box_w = min(
            box_w,
            max(page_w - 2 * DEFAULT_MARGIN_MM * MM, AUTO_MIN_WIDTH_PT),
            page_w * SCALE_MAX_WIDTH_RATIO,
        )
        box_h = min(
            box_h,
            max(page_h - 2 * DEFAULT_MARGIN_MM * MM, AUTO_MIN_HEIGHT_PT),
            page_h * SCALE_MAX_HEIGHT_RATIO,
        )

        natural_w = float(self.width) if self.width else 1.0
        natural_h = float(self.height) if self.height else 1.0
        if natural_w <= 0 or natural_h <= 0:
            natural_w = natural_h = 1.0

        # Skala proportionellt så att logotypen precis får plats i rutan
        scale = min(box_w / natural_w, box_h / natural_h)
        return natural_w * scale, natural_h * scale

    def draw_corner(
        self,
        canvas: Any,
        doc: Any,
        margin_mm: float = DEFAULT_MARGIN_MM,
        corner: str = "right",
        auto_size: bool = True,
    ) -> None:
        """
        Rita logotypen i övre högra (eller vänstra) hörnet på sidan.

        Args:
            canvas:    reportlab-canvas (eller None vid onPage).
            doc:       SimpleDocTemplate/BaseDocTemplate (för sidstorlek).
            margin_mm: Marginal till sidkanten.
            corner:    "right" eller "left".
            auto_size: True = storleken anpassas till sidan (v2.10.0).
        """
        page_size = getattr(doc, "pagesize", None) or getattr(canvas, "_pagesize", None)
        if not page_size:
            return

        page_w, page_h = float(page_size[0]), float(page_size[1])
        margin = float(margin_mm) * MM

        if auto_size:
            width, height = self.auto_size(page_w, page_h)
        else:
            width, height = self.width, self.height

        if corner == "left":
            x = margin
        else:
            x = page_w - margin - width
        y = page_h - margin - height

        canvas.saveState()
        try:
            self.draw_on(canvas, x, y, width=width, height=height)
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
        # Cachen ligger i appens egen temp-mapp och städas vid avslut (v2.11.0)
        from core.cache import logo_cache_dir

        cache_dir = logo_cache_dir()
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
    scale_key: str = "logo_scale",
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

    try:
        percent = int(float(settings.get(scale_key) or LOGO_SCALE_DEFAULT))
    except (TypeError, ValueError):
        percent = LOGO_SCALE_DEFAULT
    percent = max(LOGO_SCALE_MIN, min(percent, LOGO_SCALE_MAX))

    return PdfLogo.load(
        value,
        max_width_mm=max_width_mm,
        max_height_mm=max_height_mm,
        scale=percent / 100.0,
    )
