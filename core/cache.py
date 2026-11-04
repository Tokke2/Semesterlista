#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart cache – städar sig själv (v2.11.0)
========================================

Appen renderar SVG-logotyper till PNG i ``%TEMP%/Semesterlista/logotyper/``
så att samma logotyp bara behöver rastreras en gång. Filer i temp-mappen
försvinner inte av sig själva – utan städning ligger de kvar tills Windows
självt rensar, och på en del datorer blir det aldrig.

Den här modulen håller reda på appens egen cache och städar den **smart**:

* **Vid avslut** tas hela appens cache bort (``purge``) så att inget ligger
  kvar och skräpar. Filer som är låsta av en annan process hoppas över.
* **Vid start** rensas bara *gammalt* (``clean_stale``). Filer från den
  senaste timmen behålls, så att en snabb omstart inte tvingar fram en ny
  rendering av alla logotyper.
* **Bara appens egna mappar** rörs – ``%TEMP%/Semesterlista`` och
  ``semesterlista-*``-filer som blivit kvar efter en kraschad uppdatering.
  Inget annat i temp-mappen tas bort.
* **Torrkörning** (``dry_run``) finns för tester och loggning.

Användning:

    from core.cache import SmartCache

    cache = SmartCache()
    cache.clean_stale()          # vid start
    cache.register_exit_cleanup()  # rensar när Python avslutas
    ...
    cache.purge()                # vid avslut (anropas av main.pyw)

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import atexit
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence

logger = logging.getLogger(__name__)

MODULE_VERSION: str = "2.12.2"

#: Mappen under %TEMP% som appen äger
APP_DIR_NAME: str = "Semesterlista"

#: Undermappar som räknas som cache (loggar ligger kvar – de behövs vid felsökning)
CACHE_SUBDIRS: Sequence[str] = ("logotyper",)

#: Prefix för tillfälliga filer som en kraschad uppdatering kan lämna kvar
STALE_PREFIXES: Sequence[str] = ("semesterlista_uppdatering_", "semesterlista_update_")

#: Filer yngre än så här behålls vid rensning vid start (sekunder)
DEFAULT_STALE_HOURS: float = 1.0


@dataclass
class PurgeResult:
    """Resultat av en städning."""

    removed_files: int = 0
    removed_dirs: int = 0
    freed_bytes: int = 0
    skipped: List[str] = field(default_factory=list)

    @property
    def freed_mb(self) -> float:
        """Frigjord plats i MB (en decimal)."""
        return round(self.freed_bytes / (1024 * 1024), 2)

    def summary(self) -> str:
        """Kort text för loggen."""
        if not self.removed_files and not self.removed_dirs:
            return "Inget att rensa"
        return (
            f"{self.removed_files} filer, {self.removed_dirs} mappar, "
            f"{self.freed_mb} MB frigjort"
            + (f" ({len(self.skipped)} hoppades över)" if self.skipped else "")
        )


def app_cache_root(base: Path | None = None) -> Path:
    """
    Appens cacherot – ``%TEMP%/Semesterlista`` (eller ``base``).

    Args:
        base: Används av testerna för att peka ut en temporär mapp.
    """
    root = Path(base) if base is not None else Path(tempfile.gettempdir())
    return root / APP_DIR_NAME


def logo_cache_dir(base: Path | None = None) -> Path:
    """Mappen där rastrerade logotyper cachas (skapas vid behov)."""
    path = app_cache_root(base) / "logotyper"
    path.mkdir(parents=True, exist_ok=True)
    return path


class SmartCache:
    """
    Cache som städar sig själv vid avslut.

    Args:
        root:            appens cacherot (standard: ``%TEMP%/Semesterlista``).
        subdirs:         undermappar som får rensas.
        temp_dir:        var ``semesterlista-*``-rester letas (standard: %TEMP%).
        stale_hours:     hur gamla filer måste vara för att rensas vid start.
    """

    def __init__(
        self,
        root: Path | None = None,
        subdirs: Sequence[str] = CACHE_SUBDIRS,
        temp_dir: Path | None = None,
        stale_hours: float = DEFAULT_STALE_HOURS,
    ) -> None:
        self.root = app_cache_root(root)
        self.subdirs = tuple(subdirs)
        if temp_dir is not None:
            self.temp_dir = Path(temp_dir)
        elif root is not None:
            self.temp_dir = Path(root)
        else:
            self.temp_dir = Path(tempfile.gettempdir())
        self.stale_hours = float(stale_hours)
        self._exit_registered = False

    # ──────────────────────────────────────────────────────
    # Läsning
    # ──────────────────────────────────────────────────────

    def entries(self) -> List[Path]:
        """Alla filer som räknas som cache (inte mappar)."""
        files: List[Path] = []
        for name in self.subdirs:
            folder = self.root / name
            if folder.is_dir():
                files.extend(path for path in folder.rglob("*") if path.is_file())
        return files

    def stale_temp_entries(self) -> List[Path]:
        """Kvarblivna ``semesterlista_*``-filer/mappar i temp-mappen."""
        found: List[Path] = []
        if not self.temp_dir.is_dir():
            return found
        for pattern in STALE_PREFIXES:
            found.extend(self.temp_dir.glob(f"{pattern}*"))
        return found

    def size(self) -> int:
        """Cachestorlek i byte."""
        total = 0
        for path in self.entries():
            try:
                total += path.stat().st_size
            except OSError:  # pragma: no cover – filen kan försvinna
                continue
        return total

    # ──────────────────────────────────────────────────────
    # Städning
    # ──────────────────────────────────────────────────────

    def purge(
        self,
        keep: Iterable[Path] = (),
        dry_run: bool = False,
        include_stale_temp: bool = True,
    ) -> PurgeResult:
        """
        Ta bort appens cache (vid avslut).

        Args:
            keep:                filer som ska behållas (t.ex. logotyper i bruk).
            dry_run:             räkna bara, radera inget.
            include_stale_temp:  ta även bort kvarlämnade uppdateringsfiler.

        Returns:
            PurgeResult med antal filer, mappar och frigjord plats.
        """
        keep_paths = {Path(p).resolve() for p in keep}
        result = PurgeResult()

        targets = list(self.entries())
        if include_stale_temp:
            targets.extend(self.stale_temp_entries())

        for path in targets:
            try:
                if path.resolve() in keep_paths:
                    continue
                size = path.stat().st_size if path.is_file() else 0
                if path.is_dir():
                    if dry_run:
                        result.removed_dirs += 1
                    else:
                        shutil.rmtree(path)
                        result.removed_dirs += 1
                    continue
                if dry_run:
                    result.removed_files += 1
                    result.freed_bytes += size
                    continue
                path.unlink()
                result.removed_files += 1
                result.freed_bytes += size
            except (PermissionError, OSError) as exc:
                # Filen kan vara låst av en annan process (t.ex. PDF-läsaren)
                logger.debug(f"Kunde inte ta bort cachefilen {path}: {exc}")
                result.skipped.append(str(path))

        if not dry_run:
            self._remove_empty_dirs()

        return result

    def clean_stale(self, dry_run: bool = False) -> PurgeResult:
        """
        Rensa cache vid start – men behåll det som användes nyligen.

        Filer yngre än ``stale_hours`` lämnas kvar, så att en omstart direkt
        efter en krasch inte tvingar fram nya renderingar.
        """
        cutoff = time.time() - self.stale_hours * 3600
        keep: List[Path] = []
        for path in self.entries():
            try:
                if path.stat().st_mtime >= cutoff:
                    keep.append(path)
            except OSError:  # pragma: no cover
                continue

        result = self.purge(keep=keep, dry_run=dry_run)
        if result.removed_files or result.removed_dirs:
            logger.info(f"Cache städad vid start: {result.summary()}")
        return result

    def _remove_empty_dirs(self) -> None:
        """Ta bort tomma undermappar (men aldrig själva cacheroten)."""
        for name in self.subdirs:
            folder = self.root / name
            if not folder.is_dir():
                continue
            for path in sorted(folder.rglob("*"), reverse=True):
                if path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        continue
            try:
                folder.rmdir()
            except OSError:
                continue

    # ──────────────────────────────────────────────────────
    # Automatisk städning
    # ──────────────────────────────────────────────────────

    def register_exit_cleanup(self) -> None:
        """
        Registrera städning när Python avslutas (körs en gång).

        Skyddet gör att funktionen kan anropas från både main.pyw och
        testerna utan att städningen körs två gånger.
        """
        if self._exit_registered:
            return
        atexit.register(self._cleanup_at_exit)
        self._exit_registered = True

    def _cleanup_at_exit(self) -> None:
        """Städning som anropas av ``atexit`` – får aldrig kasta fel."""
        try:
            result = self.purge()
            if result.removed_files or result.removed_dirs:
                logger.info(f"Cache rensad vid avslut: {result.summary()}")
        except Exception as exc:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte rensa cachen vid avslut: {exc}")


#: Delad instans som main.pyw och pdf_assets.py använder
_default_cache: SmartCache | None = None


def get_cache() -> SmartCache:
    """Appens gemensamma cache-instans."""
    global _default_cache
    if _default_cache is None:
        _default_cache = SmartCache()
    return _default_cache


def purge_on_exit() -> PurgeResult:
    """Rensa appens cache – anropas när appen avslutas."""
    return get_cache().purge()


__all__ = [
    "APP_DIR_NAME",
    "CACHE_SUBDIRS",
    "MODULE_VERSION",
    "PurgeResult",
    "SmartCache",
    "app_cache_root",
    "get_cache",
    "logo_cache_dir",
    "purge_on_exit",
]
