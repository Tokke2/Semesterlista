#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uppdatering från GitHub Releases (v2.9.0)
=========================================

Hämtar senaste releasen från GitHub, jämför versioner och installerar den
nya versionen på plats. Bara standardbiblioteket används (``urllib``,
``zipfile``, ``json``) – inga extra beroenden.

Flöde:

1. ``check_for_update("2.8.1")``
   → ``GET /repos/Tokke2/Semesterlista/releases/latest``
   → ``GET /repos/…/contents/config.json?ref=<tagg>`` (ger appens version)
2. ``download_release(info, target)``
   → laddar ner ``zipball_url`` med progress-callback
3. ``install_from_zip(zip_path, app_dir)``
   → packar upp säkert i en temporär mapp, säkerhetskopierar ersatta filer
     till ``data/backup/`` och kopierar in de nya filerna
4. ``restart_command()``
   → kommandot som startar om appen

Användarens data rörs aldrig: ``data/``, ``*.txt``-listorna, ``.git/``,
``__pycache__`` och virtuella miljöer hoppas över.

Exempel:
    from core import updater

    info = updater.check_for_update("2.8.1")
    if info.available:
        zip_path = updater.download_release(info, temp_dir / "release.zip")
        result = updater.install_from_zip(zip_path, app_dir)
        print(result.version, len(result.files), result.backup)

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

MODULE_VERSION: str = "2.13.1"

#: GitHub-repot som uppdateringen hämtas från
GITHUB_OWNER: str = "Tokke2"
GITHUB_REPO: str = "Semesterlista"
API_BASE: str = "https://api.github.com"
RELEASES_URL: str = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

#: Timeout i sekunder för HTTP-anrop
TIMEOUT: int = 15

#: Maximal storlek på en nedladdad release (skydd mot skräp)
MAX_DOWNLOAD_BYTES: int = 80 * 1024 * 1024

#: Används av GitHub-API:t (krävs, annars 403)
USER_AGENT: str = f"Semesterlista-Updater/{MODULE_VERSION}"

#: Mappar som aldrig skrivs över vid uppdatering
SKIP_DIRS: Tuple[str, ...] = (
    ".git",
    ".github",
    "data",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
)

#: Filer som aldrig skrivs över (användarens egna listor + skräp)
SKIP_SUFFIXES: Tuple[str, ...] = (".pyc", ".pyo", ".bak", ".tmp", ".log")
SKIP_FILES: Tuple[str, ...] = (
    "Anställda.txt",
    "Fordon.txt",
    "Hyresgäster.txt",
    "app.log",
    "crash.log",
)

#: Filer som måste finnas i releasen för att den ska godkännas
REQUIRED_FILES: Tuple[str, ...] = ("main.pyw", "config.json")
REQUIRED_DIRS: Tuple[str, ...] = ("core", "plugins")


# ══════════════════════════════════════════════════════════
# Fel & resultat
# ══════════════════════════════════════════════════════════

class UpdateError(Exception):
    """Fel vid sökning, nedladdning eller installation."""


@dataclass
class UpdateInfo:
    """Information om senaste releasen på GitHub."""

    tag: str = ""
    version: str = ""
    name: str = ""
    published_at: str = ""
    notes: str = ""
    html_url: str = RELEASES_URL
    zip_url: str = ""
    local_version: str = ""
    from_api: bool = True
    error: str = ""

    @property
    def available(self) -> bool:
        """True om GitHub-versionen är nyare än den lokala."""
        if not self.version or not self.local_version:
            return False
        return is_newer(self.version, self.local_version)

    @property
    def published_date(self) -> str:
        """Publiceringsdatum som ``YYYY-MM-DD`` (eller råvärdet)."""
        if not self.published_at:
            return ""
        return self.published_at.split("T")[0]

    def as_dict(self) -> Dict[str, Any]:
        """Serialiserbar form (används av testerna och loggen)."""
        return {
            "tag": self.tag,
            "version": self.version,
            "name": self.name,
            "published_at": self.published_at,
            "html_url": self.html_url,
            "available": self.available,
            "local_version": self.local_version,
        }


@dataclass
class InstallResult:
    """Resultat av en installation."""

    version: str = ""
    files: List[str] = field(default_factory=list)
    backup: Optional[Path] = None
    skipped: List[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        """Antal uppdaterade filer."""
        return len(self.files)


# ══════════════════════════════════════════════════════════
# Versioner
# ══════════════════════════════════════════════════════════

_VERSION_RE = re.compile(r"(\d+(?:\.\d+)*)")


def parse_version(text: str) -> Tuple[int, ...]:
    """
    Gör om ``"v2.8.1"``, ``"2.8.1"`` eller ``"Release 2.9"`` till en tuple.

    Args:
        text: Versionssträng (tagg eller ``APP_VERSION``).

    Returns:
        Tuple med siffror, t.ex. ``(2, 8, 1)``. Tom tuple om inget hittas.
    """
    if not text:
        return ()

    match = _VERSION_RE.search(str(text))
    if match is None:
        return ()

    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(remote: str, local: str) -> bool:
    """
    True om ``remote`` är en nyare version än ``local``.

    Saknade delar räknas som 0, så ``2.9`` anses nyare än ``2.8.9``.
    """
    remote_version = parse_version(remote)
    local_version = parse_version(local)

    if not remote_version or not local_version:
        return False

    length = max(len(remote_version), len(local_version))
    padded_remote = remote_version + (0,) * (length - len(remote_version))
    padded_local = local_version + (0,) * (length - len(local_version))
    return padded_remote > padded_local


def version_from_config(path: Path) -> str:
    """Läs ``version`` ur en ``config.json`` ('' om det inte går)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return ""

    if isinstance(data, dict):
        return str(data.get("version", "") or "")
    return ""


# ══════════════════════════════════════════════════════════
# HTTP
# ══════════════════════════════════════════════════════════

def _request(
    url: str,
    timeout: int = TIMEOUT,
    accept: str = "application/vnd.github+json",
) -> bytes:
    """Hämta en URL (bytes) med rimliga huvuden."""
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateError(
                "Ingen release hittades på GitHub."
            ) from exc
        if exc.code == 403:
            raise UpdateError(
                "GitHub nekade åtkomst (403) – för många förfrågningar?"
            ) from exc
        raise UpdateError(f"GitHub svarade {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise UpdateError(f"Ingen kontakt med GitHub: {exc.reason}") from exc
    except TimeoutError as exc:
        raise UpdateError("Tidsgränsen gick ut – försök igen.") from exc
    except OSError as exc:
        raise UpdateError(f"Nätverksfel: {exc}") from exc


def _request_json(url: str, timeout: int = TIMEOUT) -> Any:
    """Hämta JSON från GitHub-API:t."""
    raw = _request(url, timeout=timeout)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise UpdateError("GitHub svarade med ogiltig JSON.") from exc


def fetch_latest_release(timeout: int = TIMEOUT) -> Dict[str, Any]:
    """
    Hämta senaste publika releasen från GitHub.

    Returns:
        Dict från ``/releases/latest``.

    Raises:
        UpdateError: Vid nätverksfel, 404 eller ogiltigt svar.
    """
    url = f"{API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    data = _request_json(url, timeout=timeout)
    if not isinstance(data, dict) or not data.get("tag_name"):
        raise UpdateError("GitHub svarade utan tagg – ingen release hittad.")
    return data


def fetch_version_at_tag(tag: str, timeout: int = TIMEOUT) -> str:
    """
    Läs appens version ur ``config.json`` vid en tagg.

    Args:
        tag: T.ex. ``"v0.0.1"``.

    Returns:
        Versionssträng ('' om den inte kan läsas).
    """
    if not tag:
        return ""

    url = (
        f"{API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/config.json"
        f"?ref={tag}"
    )
    try:
        data = _request_json(url, timeout=timeout)
    except UpdateError as exc:
        logger.warning("Kunde inte läsa config.json för %s: %s", tag, exc)
        return ""

    if not isinstance(data, dict):
        return ""

    content = data.get("content")
    if content:
        import base64

        try:
            decoded = base64.b64decode(content).decode("utf-8")
            return str(json.loads(decoded).get("version", "") or "")
        except (ValueError, UnicodeDecodeError) as exc:  # pragma: no cover
            logger.warning("Kunde inte avkoda config.json: %s", exc)
            return ""

    # Stora filer returneras utan content – hämta via download_url då
    download_url = data.get("download_url")
    if download_url:
        try:
            return str(json.loads(_request(download_url).decode("utf-8")).get("version", ""))
        except (UpdateError, ValueError):
            return ""
    return ""


def check_for_update(
    local_version: str,
    timeout: int = TIMEOUT,
) -> UpdateInfo:
    """
    Jämför appens version med senaste releasen på GitHub.

    Args:
        local_version: Appens version, t.ex. ``APP_VERSION``.
        timeout:       Timeout per HTTP-anrop.

    Returns:
        ``UpdateInfo`` – ``available`` är True om det finns en nyare version.

    Raises:
        UpdateError: Om GitHub inte kan nås eller saknar release.
    """
    release = fetch_latest_release(timeout=timeout)
    tag = str(release.get("tag_name", ""))

    info = UpdateInfo(
        tag=tag,
        name=str(release.get("name", "") or tag),
        published_at=str(release.get("published_at", "") or ""),
        notes=str(release.get("body", "") or ""),
        html_url=str(release.get("html_url", "") or RELEASES_URL),
        zip_url=str(release.get("zipball_url", "") or ""),
        local_version=local_version,
    )

    info.version = fetch_version_at_tag(tag, timeout=timeout)
    if not info.version:
        # Fallback: taggen kan innehålla versionen (t.ex. "v2.9.0")
        info.version = str(tag).lstrip("vV")
        logger.warning(
            "Kunde inte läsa versionen ur config.json – använder taggen %s", tag
        )

    logger.info(
        "Uppdateringskontroll: lokal %s, GitHub %s (%s) → %s",
        local_version,
        info.version,
        tag,
        "ny version finns" if info.available else "senaste versionen",
    )
    return info


# ══════════════════════════════════════════════════════════
# Nedladdning
# ══════════════════════════════════════════════════════════

def download_release(
    info: UpdateInfo,
    target: Path,
    progress: Optional[Callable[[int, int], None]] = None,
    timeout: int = 60,
) -> Path:
    """
    Ladda ner release-zipen.

    Args:
        info:     Resultat från ``check_for_update()``.
        target:   Sökväg för zip-filen.
        progress: Anropas med (nedladdat, totalt) i byte.
        timeout:  Timeout i sekunder.

    Returns:
        Sökvägen till zip-filen.

    Raises:
        UpdateError: Om URL saknas, filen blir för stor eller nedladdningen
                     misslyckas.
    """
    if not info.zip_url:
        raise UpdateError("Releasen saknar nedladdningsbar zip-fil.")

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    # GitHub svarar 415 om Accept är application/octet-stream på zipball-URL:er
    request = Request(
        info.zip_url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )

    try:
        with urlopen(request, timeout=timeout) as response, open(target, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            if total > MAX_DOWNLOAD_BYTES:
                raise UpdateError(
                    f"Releasen är för stor ({total} byte, max {MAX_DOWNLOAD_BYTES})."
                )

            downloaded = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    raise UpdateError("Nedladdningen blev för stor – avbruten.")
                if progress is not None:
                    progress(downloaded, total)
    except HTTPError as exc:
        raise UpdateError(f"Nedladdningen misslyckades ({exc.code}).") from exc
    except URLError as exc:
        raise UpdateError(f"Ingen kontakt med GitHub: {exc.reason}") from exc
    except OSError as exc:
        raise UpdateError(f"Kunde inte spara filen: {exc}") from exc

    if not target.exists() or target.stat().st_size == 0:
        raise UpdateError("Nedladdningen gav en tom fil.")

    logger.info(
        "Nedladdad %s (%.1f kB) → %s",
        info.version,
        target.stat().st_size / 1024,
        target,
    )
    return target


# ══════════════════════════════════════════════════════════
# Uppackning & installation
# ══════════════════════════════════════════════════════════

def safe_extract(zip_path: Path, destination: Path) -> Path:
    """
    Packa upp en zip utan att tillåta sökvägar utanför målmappen.

    Args:
        zip_path:    Zip-filen.
        destination: Mappen som filerna packas upp i.

    Returns:
        Rotmappen för innehållet (GitHub-zippar har en toppmapp).

    Raises:
        UpdateError: Vid osäker sökväg eller trasig zip.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()

    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                name = member.filename
                if not name or name.startswith("/") or ".." in Path(name).parts:
                    raise UpdateError(f"Osäker sökväg i zip-filen: {name}")

                target = (destination / name).resolve()
                if root not in target.parents and target != root:
                    raise UpdateError(f"Osäker sökväg i zip-filen: {name}")

            archive.extractall(destination)
    except zipfile.BadZipFile as exc:
        raise UpdateError("Den nedladdade filen är ingen giltig zip.") from exc

    entries = [item for item in destination.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return destination


def _skip_file(relative: Path) -> bool:
    """True om filen inte ska skrivas över."""
    if any(part in SKIP_DIRS for part in relative.parts[:-1]):
        return True
    if relative.name in SKIP_FILES:
        return True
    return relative.suffix.lower() in SKIP_SUFFIXES


def _iter_payload_files(root: Path) -> List[Path]:
    """Alla filer i releasen som ska installeras (relativa sökvägar)."""
    files: List[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _skip_file(relative):
            continue
        files.append(relative)
    return files


def verify_payload(root: Path) -> str:
    """
    Kontrollera att uppackat innehåll ser ut som Semesterlista.

    Returns:
        Versionen från ``config.json``.

    Raises:
        UpdateError: Om filer/mappar saknas eller versionen inte går att läsa.
    """
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            raise UpdateError(f"Releasen saknar {name} – avbruten.")

    for name in REQUIRED_DIRS:
        if not (root / name).is_dir():
            raise UpdateError(f"Releasen saknar mappen {name}/ – avbruten.")

    version = version_from_config(root / "config.json")
    if not version:
        raise UpdateError("Kunde inte läsa versionen ur releasens config.json.")

    return version


def _make_backup(
    app_dir: Path,
    files: List[Path],
    local_version: str,
    new_version: str,
    backup_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Zippa de filer som kommer att skrivas över."""
    existing = [rel for rel in files if (app_dir / rel).is_file()]
    if not existing:
        return None

    if backup_dir is None:
        backup_dir = app_dir / "data" / "backup"
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"uppdatering-{local_version or 'okand'}-till-{new_version}-{stamp}.zip"
    backup_path = backup_dir / name

    try:
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for relative in existing:
                archive.write(app_dir / relative, arcname=str(relative))
    except OSError as exc:  # pragma: no cover – full disk m.m.
        logger.warning("Kunde inte säkerhetskopiera: %s", exc)
        return None

    logger.info("Säkerhetskopia: %s (%d filer)", backup_path, len(existing))
    return backup_path


def install_from_zip(
    zip_path: Path,
    app_dir: Path,
    local_version: str = "",
    dry_run: bool = False,
    backup_dir: Optional[Path] = None,
) -> InstallResult:
    """
    Installera en nedladdad release ovanpå appens mapp.

    Bara filer som hör till programmet skrivs över – ``data/``, användarens
    ``*.txt``-listor och ``.git/`` lämnas orörda.

    Args:
        zip_path:      Nedladdad release-zip.
        app_dir:       Appens rotmapp (där main.pyw ligger).
        local_version: Nuvarande version (för säkerhetskopians namn).
        dry_run:       Om True skrivs inga filer (används av testerna).
        backup_dir:    Egen mapp för säkerhetskopian.

    Returns:
        ``InstallResult`` med version, filer och säkerhetskopia.

    Raises:
        UpdateError: Om innehållet inte ser ut som Semesterlista.
    """
    zip_path = Path(zip_path)
    app_dir = Path(app_dir)

    if not zip_path.is_file():
        raise UpdateError(f"Zip-filen finns inte: {zip_path}")
    if not app_dir.is_dir():
        raise UpdateError(f"Appmappen finns inte: {app_dir}")

    with tempfile.TemporaryDirectory(prefix="semesterlista_uppdatering_") as tmp:
        root = safe_extract(zip_path, Path(tmp))
        version = verify_payload(root)

        if local_version and not is_newer(version, local_version):
            raise UpdateError(
                f"Releasen ({version}) är inte nyare än {local_version}."
            )

        files = _iter_payload_files(root)
        if not files:  # pragma: no cover – verify_payload fångar detta
            raise UpdateError("Releasen innehöll inga filer att installera.")

        if dry_run:
            logger.info("Torrkörning: %d filer skulle uppdateras till %s", len(files), version)
            return InstallResult(
                version=version,
                files=[str(rel) for rel in files],
                skipped=sorted({str(p) for p in root.rglob("*") if p.is_file()}
                               - {str(root / rel) for rel in files}),
            )

        backup = _make_backup(app_dir, files, local_version, version, backup_dir)

        copied: List[str] = []
        for relative in files:
            source = root / relative
            destination = app_dir / relative
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Skriv via temp-fil så att en halv fil aldrig blir kvar
                temp_target = destination.with_name(destination.name + ".new")
                shutil.copy2(source, temp_target)
                os.replace(temp_target, destination)
                copied.append(str(relative))
            except OSError as exc:
                raise UpdateError(
                    f"Kunde inte skriva {relative}: {exc}. Stäng appen och "
                    "försök igen (filen kan vara låst)."
                ) from exc

    logger.info(
        "Uppdatering klar: %s → %s, %d filer, säkerhetskopia %s",
        local_version or "?",
        version,
        len(copied),
        backup or "saknas",
    )

    return InstallResult(version=version, files=copied, backup=backup)


# ══════════════════════════════════════════════════════════
# Omstart
# ══════════════════════════════════════════════════════════

def restart_command(app_dir: Optional[Path] = None) -> List[str]:
    """
    Kommandot som startar om appen.

    Args:
        app_dir: Appens rotmapp (standard: två nivåer upp från denna fil).

    Returns:
        Lista med program + argument, t.ex. ``["pythonw.exe", "main.pyw"]``.
    """
    root = Path(app_dir) if app_dir is not None else Path(__file__).resolve().parent.parent
    script = root / "main.pyw"
    if not script.is_file() and (root / "main.py").is_file():
        script = root / "main.py"

    executable = sys.executable or ("pythonw.exe" if platform.system() == "Windows" else "python3")
    return [executable, str(script)]


def github_release_url() -> str:
    """Webbadressen till senaste releasen (öppnas i webbläsaren)."""
    return f"{RELEASES_URL}/latest"


def app_version(app_dir: Optional[Path] = None) -> str:
    """Appens version enligt ``config.json``."""
    root = Path(app_dir) if app_dir is not None else Path(__file__).resolve().parent.parent
    return version_from_config(root / "config.json")


def wait_for_network(seconds: int = 3) -> bool:
    """
    Snabb koll om GitHub verkar nåbart (utan att kasta fel).

    Används för att undvika ett långt stopp vid uppstart utan nät.
    """
    url = f"{API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    try:
        _request(url, timeout=seconds)
        return True
    except UpdateError:
        return False


__all__ = [
    "API_BASE",
    "GITHUB_OWNER",
    "GITHUB_REPO",
    "RELEASES_URL",
    "MODULE_VERSION",
    "InstallResult",
    "UpdateError",
    "UpdateInfo",
    "app_version",
    "check_for_update",
    "download_release",
    "fetch_latest_release",
    "fetch_version_at_tag",
    "github_release_url",
    "install_from_zip",
    "is_newer",
    "parse_version",
    "restart_command",
    "safe_extract",
    "verify_payload",
    "version_from_config",
    "wait_for_network",
]
