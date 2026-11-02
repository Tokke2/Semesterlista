#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatisk uppdatering mot GitHub Releases (v2.4.0)
===================================================

Denna modul sköter HELA uppdateringsflödet mot GitHub:

    1. Frågar GitHub API efter senaste release för repot
       (standard: Tokke2/Semesterlista, se config.json → "update").
    2. Jämför release-taggens version med appens APP_VERSION.
    3. Väljer rätt nedladdningsbar fil (installationsprogram eller arkiv)
       utifrån mönster i config.json → "update.asset_patterns".
    4. Laddar ner filen med progress-callback och verifierar SHA-256
       (GitHubs "digest"-fält eller en systerfil *.sha256).
    5. Packar upp arkivet till en tillfällig mapp och skriver ett
       hjälpskript som:
           - väntar tills Semesterlista har stängts,
           - kopierar de nya filerna över appmappen,
           - startar om programmet.
       Skriptet startas fristående och appen kan därför avslutas tryggt.

Modulen är MEDVETET fri från PySide6/Qt så att den kan:
    - köras från kommandoraden (se CLI nedan),
    - användas av CI/tester utan GUI,
    - återanvändas av plugins.

Användning:
    from core.updater import GitHubUpdater, load_update_config

    updater = GitHubUpdater.from_config(PROJECT_ROOT, APP_VERSION)
    info    = updater.check()          # None = redan senaste versionen
    if info:
        archive = updater.download(info, progress=print)
        updater.apply(info, archive)   # startar om appen när den stängts

CLI (användbart i CI eller för felsökning):
    python core/updater.py --check
    python core/updater.py --check --json
    python core/updater.py --download --install

Exit-koder:
    0   Ingen uppdatering tillgänglig
    10  Uppdatering tillgänglig
    20  Uppdatering nedladdad (--download)
    1   Fel (nätverk, API, nedladdning, uppackning)

Inställningar (config.json → "update"):
    owner, repo, channel ("stable" | "prerelease"), auto_check,
    check_interval_hours, asset_patterns, install_mode
    ("auto" | "installer" | "archive" | "browser"),
    restart_after_update, timeout_seconds, api_base, token.

Miljövariabler (överstyr config.json, används av tester/CI):
    SEMESTERLISTA_UPDATE_API    – annan API-rot, t.ex. http://localhost:8080
    SEMESTERLISTA_UPDATE_OWNER  – annat ägarnamn
    SEMESTERLISTA_UPDATE_REPO   – annat reponamn
    GITHUB_TOKEN                – höjer GitHub API:s ratelimit

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import webbrowser
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.4.0"

# ──────────────────────────────────────────────────────────
# Standardvärden för GitHub-uppdateringen
# ──────────────────────────────────────────────────────────
GITHUB_OWNER: str = "Tokke2"
GITHUB_REPO: str = "Semesterlista"
GITHUB_API: str = "https://api.github.com"
USER_AGENT: str = "Semesterlista-Updater"

#: Filer som ALDRIG ska väljas som nedladdning (kontrollsummor, signaturer …)
IGNORED_ASSET_SUFFIXES: Tuple[str, ...] = (
    ".sha256", ".sha256sum", ".sha512", ".md5", ".sig", ".asc",
    ".txt", ".json", ".blockmap", ".yml", ".yaml", ".md", ".sbom",
)

#: Mappar/filer som aldrig skrivs över av en uppdatering (användardata)
DEFAULT_PRESERVE_PATHS: Tuple[str, ...] = (
    "data", ".git", "Anställda.txt", "Fordon.txt", "Hyresgäster.txt",
)

DEFAULT_UPDATE_CONFIG: Dict[str, Any] = {
    "owner": GITHUB_OWNER,
    "repo": GITHUB_REPO,
    "channel": "stable",                 # "stable" eller "prerelease"
    "auto_check": True,                  # fråga GitHub vid start
    "check_interval_hours": 24,          # … men högst en gång per dygn
    "asset_patterns": [                  # prioritetsordning
        "*-setup.exe", "*setup*.exe", "*.msi", "*.dmg", "*.pkg",
        "*-win*.zip", "*.zip", "*.tar.gz", "*.tgz",
    ],
    "install_mode": "auto",              # auto | installer | archive | browser
    "restart_after_update": True,
    "preserve_paths": list(DEFAULT_PRESERVE_PATHS),
    "timeout_seconds": 15,
    "api_base": GITHUB_API,
    "token": "",
}


# ══════════════════════════════════════════════════════════
# FEL
# ══════════════════════════════════════════════════════════

class UpdateError(Exception):
    """Basfel för uppdateringsflödet."""


class UpdateCheckError(UpdateError):
    """Kunde inte hämta information om senaste release."""


class UpdateDownloadError(UpdateError):
    """Kunde inte ladda ner eller verifiera uppdateringen."""


class UpdateApplyError(UpdateError):
    """Kunde inte packa upp eller installera uppdateringen."""


# ══════════════════════════════════════════════════════════
# VERSIONSHANTERING
# ══════════════════════════════════════════════════════════

_VERSION_RE = re.compile(
    r"(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:[._\-]?(alpha|beta|preview|pre|rc|a|b)[._\-]?(\d+)?)?",
    re.IGNORECASE,
)

#: Rankning av förhandsversioner – högre = senare
_STAGE_RANK: Dict[str, int] = {
    "a": 0, "alpha": 0,
    "b": 1, "beta": 1,
    "pre": 2, "preview": 2, "rc": 2,
    "final": 3,
}


@dataclass(frozen=True, eq=False)
class Version:
    """
    Ett jämförbart versionsnummer.

    Stödjer "2.4.0", "v2.4.0", "2.4", "2.4.0-beta.1", "2.4.0rc2".
    Jämförelse: 2.3.0 < 2.4.0-beta.1 < 2.4.0-rc1 < 2.4.0.
    """

    major: int
    minor: int = 0
    patch: int = 0
    stage: str = "final"
    stage_number: int = 0
    raw: str = ""

    # ── Konstruktion ─────────────────────────────────────

    @classmethod
    def parse(cls, value: Any) -> "Version":
        """
        Tolka ett versionsnummer.

        Args:
            value: str, int eller Version (t.ex. "v2.4.0-beta.1").

        Raises:
            ValueError: om texten inte innehåller ett versionsnummer.
        """
        if isinstance(value, Version):
            return value

        text = str(value if value is not None else "").strip()
        if not text:
            raise ValueError("Tomt versionsnummer")

        # Tillåt taggar som "release-2.4.0" / "Semesterlista v2.4.0"
        match = _VERSION_RE.search(text)
        if match is None:
            raise ValueError(f"Ogiltigt versionsnummer: {value!r}")

        major, minor, patch, stage, number = match.groups()
        stage_norm = (stage or "final").lower()
        stage_norm = {"a": "alpha", "b": "beta"}.get(stage_norm, stage_norm)

        return cls(
            major=int(major),
            minor=int(minor or 0),
            patch=int(patch or 0),
            stage=stage_norm,
            stage_number=int(number or 0),
            raw=text,
        )

    # ── Egenskaper ───────────────────────────────────────

    @property
    def is_prerelease(self) -> bool:
        """True om versionen är alpha/beta/rc."""
        return self.stage != "final"

    def as_tuple(self) -> Tuple[int, int, int, int, int]:
        """Sorteringsnyckel – högre är senare."""
        return (
            self.major,
            self.minor,
            self.patch,
            _STAGE_RANK.get(self.stage, 3),
            self.stage_number,
        )

    # ── Jämförelse ───────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            try:
                other = Version.parse(other)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __lt__(self, other: "Version") -> bool:
        return self.as_tuple() < Version.parse(other).as_tuple()

    def __le__(self, other: "Version") -> bool:
        return self.as_tuple() <= Version.parse(other).as_tuple()

    def __gt__(self, other: "Version") -> bool:
        return self.as_tuple() > Version.parse(other).as_tuple()

    def __ge__(self, other: "Version") -> bool:
        return self.as_tuple() >= Version.parse(other).as_tuple()

    def __hash__(self) -> int:
        return hash(self.as_tuple())

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.is_prerelease:
            return f"{base}-{self.stage}.{self.stage_number}"
        return base

    def __repr__(self) -> str:  # pragma: no cover – endast felsökning
        return f"Version({str(self)!r})"


def normalize_version(value: Any) -> str:
    """Returnera "2.4.0" (eller "2.4.0-beta.1") för ett godtyckligt versionsvärde."""
    return str(Version.parse(value))


def compare_versions(candidate: Any, current: Any) -> int:
    """
    Jämför två versioner.

    Returns:
        1 om candidate är nyare, 0 om lika, -1 om äldre.
    """
    new, old = Version.parse(candidate), Version.parse(current)
    if new > old:
        return 1
    if new < old:
        return -1
    return 0


def is_newer(candidate: Any, current: Any) -> bool:
    """True om `candidate` är en nyare version än `current`."""
    try:
        return compare_versions(candidate, current) > 0
    except ValueError:
        return False


# ══════════════════════════════════════════════════════════
# RELEASE-INFORMATION
# ══════════════════════════════════════════════════════════

def _asset_is_usable(name: str) -> bool:
    """False för kontrollsummor, signaturer och annat vi inte ska ladda ner."""
    lower = (name or "").lower()
    return bool(lower) and not lower.endswith(IGNORED_ASSET_SUFFIXES)


def _select_asset(
    assets: Sequence[Dict[str, Any]],
    patterns: Sequence[str],
) -> Optional[Dict[str, Any]]:
    """
    Välj den fil som ska laddas ner.

    Första mönstret i `patterns` som matchar vinner; vid flera träffar
    väljs den största filen (installationsprogrammet före t.ex. en symbolfil).
    """
    usable = [
        a for a in assets
        if isinstance(a, dict) and _asset_is_usable(str(a.get("name", "")))
    ]
    if not usable:
        return None

    for pattern in patterns:
        matches = [
            a for a in usable
            if fnmatch.fnmatch(str(a.get("name", "")).lower(), str(pattern).lower())
        ]
        if matches:
            return max(matches, key=lambda a: int(a.get("size") or 0))

    return usable[0]


@dataclass
class UpdateInfo:
    """En tillgänglig release på GitHub."""

    version: str
    tag: str = ""
    name: str = ""
    notes: str = ""
    published_at: str = ""
    html_url: str = ""
    prerelease: bool = False
    asset_name: str = ""
    asset_url: str = ""
    asset_api_url: str = ""
    asset_size: int = 0
    asset_digest: str = ""
    checksum_url: str = ""

    # ── Egenskaper ───────────────────────────────────────

    @property
    def download_suffix(self) -> str:
        """Filändelse för den valda filen (gemener)."""
        name = self.asset_name.lower()
        for suffix in (".tar.gz", ".tar.bz2", ".tgz"):
            if name.endswith(suffix):
                return suffix
        return Path(name).suffix

    @property
    def is_installer(self) -> bool:
        """True om filen är ett installationsprogram."""
        return self.download_suffix in (
            ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage",
        )

    @property
    def is_archive(self) -> bool:
        """True om filen är ett arkiv som ska packas upp."""
        return self.download_suffix in (".zip", ".tar.gz", ".tgz", ".tar.bz2")

    @property
    def has_asset(self) -> bool:
        """True om releasen har en fil vi kan hämta."""
        return bool(self.asset_url)

    # ── Konstruktion ─────────────────────────────────────

    @classmethod
    def from_github_release(
        cls,
        data: Dict[str, Any],
        asset_patterns: Sequence[str] = (),
    ) -> "UpdateInfo":
        """
        Skapa UpdateInfo från GitHubs JSON för en release.

        Args:
            data:            JSON-objekt från /repos/{owner}/{repo}/releases.
            asset_patterns:  Önskad prioritetsordning på filer.
        """
        tag = str(data.get("tag_name") or data.get("name") or "")
        version = str(Version.parse(tag))

        assets = data.get("assets") or []
        if not isinstance(assets, list):
            assets = []

        asset = _select_asset(assets, asset_patterns or DEFAULT_UPDATE_CONFIG["asset_patterns"])
        asset_name = str(asset.get("name", "")) if asset else ""

        checksum_url = ""
        if asset_name:
            wanted = {
                f"{asset_name.lower()}.sha256",
                f"{asset_name.lower()}.sha256sum",
            }
            for candidate in assets:
                if str(candidate.get("name", "")).lower() in wanted:
                    checksum_url = str(
                        candidate.get("browser_download_url")
                        or candidate.get("url")
                        or ""
                    )
                    break

        return cls(
            version=version,
            tag=tag,
            name=str(data.get("name") or tag),
            notes=str(data.get("body") or ""),
            published_at=str(data.get("published_at") or ""),
            html_url=str(data.get("html_url") or ""),
            prerelease=bool(data.get("prerelease")),
            asset_name=asset_name,
            asset_url=str(
                (asset or {}).get("browser_download_url")
                or (asset or {}).get("url")
                or ""
            ),
            asset_api_url=str((asset or {}).get("url") or ""),
            asset_size=int((asset or {}).get("size") or 0),
            asset_digest=str((asset or {}).get("digest") or ""),
            checksum_url=checksum_url,
        )

    # ── Presentation ─────────────────────────────────────

    def published_date(self) -> str:
        """Publiceringsdatum som YYYY-MM-DD (tom sträng om det saknas)."""
        text = self.published_at.strip()
        if not text:
            return ""
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return text[:10]

    def to_dict(self) -> Dict[str, Any]:
        """JSON-vänlig representation (används av CLI:t)."""
        return {
            "version": self.version,
            "tag": self.tag,
            "name": self.name,
            "html_url": self.html_url,
            "published_at": self.published_at,
            "prerelease": self.prerelease,
            "notes": self.notes,
            "asset_name": self.asset_name,
            "asset_size": self.asset_size,
            "asset_url": self.asset_url,
            "has_asset": self.has_asset,
        }

    def __str__(self) -> str:  # pragma: no cover – endast logg
        return f"UpdateInfo(v{self.version}, asset={self.asset_name!r})"


@dataclass
class ApplyResult:
    """Resultat av GitHubUpdater.apply()."""

    mode: str                                  # installer | archive | browser
    script: Optional[Path] = None
    staged_dir: Optional[Path] = None
    command: Optional[List[str]] = None
    dry_run: bool = False

    @property
    def requires_restart(self) -> bool:
        """True om appen måste stängas för att uppdateringen ska slå igenom."""
        return self.mode in ("installer", "archive")


# ══════════════════════════════════════════════════════════
# KONFIGURATION
# ══════════════════════════════════════════════════════════

def load_update_config(
    project_root: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Läs uppdateringsinställningarna från config.json → "update".

    Saknade nycklar fylls på från DEFAULT_UPDATE_CONFIG. Miljövariabler
    (SEMESTERLISTA_UPDATE_API, SEMESTERLISTA_UPDATE_OWNER,
    SEMESTERLISTA_UPDATE_REPO, GITHUB_TOKEN) överstyr filen.

    Returns:
        Dict med kompletta inställningar.
    """
    config: Dict[str, Any] = dict(DEFAULT_UPDATE_CONFIG)

    path: Optional[Path] = None
    if config_path is not None:
        path = Path(config_path)
    elif project_root is not None:
        path = Path(project_root) / "config.json"

    if path is not None and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            section = data.get("update") or {}
            if isinstance(section, dict):
                for key, value in section.items():
                    if value is not None:
                        config[key] = value
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning(f"Kunde inte läsa {path}: {exc} – använder standardvärden")

    if os.environ.get("SEMESTERLISTA_UPDATE_API"):
        config["api_base"] = os.environ["SEMESTERLISTA_UPDATE_API"]
    if os.environ.get("SEMESTERLISTA_UPDATE_OWNER"):
        config["owner"] = os.environ["SEMESTERLISTA_UPDATE_OWNER"]
    if os.environ.get("SEMESTERLISTA_UPDATE_REPO"):
        config["repo"] = os.environ["SEMESTERLISTA_UPDATE_REPO"]
    if os.environ.get("GITHUB_TOKEN"):
        config["token"] = os.environ["GITHUB_TOKEN"]

    return config


def read_app_version(config_path: Path, default: str = "0.0.0") -> str:
    """Läs "version" ur config.json (används av CLI:t)."""
    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        return str(data.get("version") or default)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default


# ══════════════════════════════════════════════════════════
# UPPDATERAREN
# ══════════════════════════════════════════════════════════

ProgressCallback = Callable[[int, int], None]


class GitHubUpdater:
    """
    Hämtar, laddar ner och installerar releaser från GitHub.

    Alla nätverksanrop är synkrona – anropa check()/download() från en
    arbetstråd när modulen används i en GUI-app (se core/update_dialog.py).
    """

    def __init__(
        self,
        current_version: Any,
        app_root: Optional[Path] = None,
        owner: str = GITHUB_OWNER,
        repo: str = GITHUB_REPO,
        channel: str = "stable",
        asset_patterns: Optional[Sequence[str]] = None,
        install_mode: str = "auto",
        restart_after_update: bool = True,
        preserve_paths: Optional[Sequence[str]] = None,
        timeout: float = 15.0,
        api_base: str = GITHUB_API,
        token: str = "",
        user_agent: str = USER_AGENT,
        work_dir: Optional[Path] = None,
    ):
        """
        Args:
            current_version:      Appens nuvarande version (t.ex. "2.4.0").
            app_root:             Appens rotmapp (där main.pyw ligger).
            owner / repo:         GitHub-repo som uppdateringen hämtas från.
            channel:              "stable" (hoppar över förhandsversioner)
                                  eller "prerelease".
            asset_patterns:       Prioriterade filmönster.
            install_mode:         "auto", "installer", "archive" eller "browser".
            restart_after_update: Starta om appen efter uppdateringen.
            preserve_paths:       Filer/mappar som aldrig skrivs över.
            timeout:              Timeout i sekunder för nätverksanrop.
            api_base:             API-rot (överstyrbar för tester).
            token:                Valfri GitHub-token (höjer ratelimit).
            user_agent:           User-Agent för HTTP-anropen.
            work_dir:             Mapp för nedladdningar och hjälpskript
                                  (standard: temp/Semesterlista/updates).
        """
        self.current = Version.parse(current_version)
        self.app_root = Path(app_root).resolve() if app_root else Path.cwd().resolve()
        self.owner = owner.strip()
        self.repo = repo.strip()
        self.channel = "prerelease" if str(channel).lower().startswith("pre") else "stable"
        self.asset_patterns: List[str] = list(
            asset_patterns or DEFAULT_UPDATE_CONFIG["asset_patterns"]
        )
        self.install_mode = install_mode or "auto"
        self.restart_after_update = bool(restart_after_update)
        self.preserve_paths: List[str] = list(
            preserve_paths if preserve_paths is not None else DEFAULT_PRESERVE_PATHS
        )
        self.timeout = float(timeout or 15)
        self.api_base = (api_base or GITHUB_API).rstrip("/")
        self.token = (token or "").strip()
        self.user_agent = user_agent
        self.work_dir = Path(work_dir).resolve() if work_dir else None

    # ── Fabriker ─────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        project_root: Optional[Path] = None,
        current_version: Optional[Any] = None,
        config_path: Optional[Path] = None,
    ) -> "GitHubUpdater":
        """
        Skapa en uppdaterare från config.json.

        Args:
            project_root:    Appens rotmapp.
            current_version: Appens version. Om den utelämnas läses
                             "version" ur config.json.
            config_path:     Annan sökväg till config.json (valfritt).
        """
        root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parent.parent
        config = load_update_config(root, config_path)

        if current_version is None:
            current_version = read_app_version(config_path or (root / "config.json"))

        return cls(
            current_version=current_version,
            app_root=root,
            owner=str(config.get("owner", GITHUB_OWNER)),
            repo=str(config.get("repo", GITHUB_REPO)),
            channel=str(config.get("channel", "stable")),
            asset_patterns=config.get("asset_patterns"),
            install_mode=str(config.get("install_mode", "auto")),
            restart_after_update=bool(config.get("restart_after_update", True)),
            preserve_paths=config.get("preserve_paths"),
            timeout=float(config.get("timeout_seconds", 15) or 15),
            api_base=str(config.get("api_base", GITHUB_API)),
            token=str(config.get("token", "")),
        )

    # ── Beskrivning ──────────────────────────────────────

    @property
    def releases_url(self) -> str:
        """Webbadress till repots releasesida."""
        return f"https://github.com/{self.owner}/{self.repo}/releases"

    @property
    def api_releases_url(self) -> str:
        """API-adress som listar repots releaser."""
        return (
            f"{self.api_base}/repos/{self.owner}/{self.repo}"
            f"/releases?per_page=50"
        )

    def __repr__(self) -> str:  # pragma: no cover – endast felsökning
        return (
            f"GitHubUpdater({self.owner}/{self.repo}, "
            f"current={self.current}, channel={self.channel})"
        )

    # ── HTTP ─────────────────────────────────────────────

    def _headers(self, accept: str) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": accept,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if "api.github.com" in self.api_base:
            headers["X-GitHub-Api-Version"] = "2022-11-28"
        return headers

    def _open(self, url: str, accept: str):
        """Öppna en URL och returnera svaret (urllib-response)."""
        request = urllib.request.Request(url, headers=self._headers(accept))
        try:
            return urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            message = ""
            try:
                payload = exc.read().decode("utf-8", "replace")
                message = str(json.loads(payload).get("message") or "")
            except Exception:  # pragma: no cover – defensivt
                message = ""
            remaining = ""
            try:
                remaining = str(exc.headers.get("X-RateLimit-Remaining") or "")
            except Exception:  # pragma: no cover – defensivt
                remaining = ""
            if exc.code in (403, 429) and remaining == "0":
                raise UpdateCheckError(
                    "GitHub API:s gräns för antal anrop är nådd. "
                    "Försök igen senare eller ange en token i config.json."
                ) from exc
            raise UpdateError(
                f"HTTP {exc.code} från GitHub"
                + (f": {message}" if message else "")
            ) from exc
        except urllib.error.URLError as exc:
            raise UpdateError(f"Nätverksfel: {exc.reason}") from exc
        except TimeoutError as exc:  # pragma: no cover – defensivt
            raise UpdateError("Tidsgränsen för nätverksanropet överskreds") from exc

    def _get_json(self, url: str) -> Any:
        """Hämta och parsa JSON från GitHub API."""
        try:
            with self._open(url, "application/vnd.github+json") as response:
                payload = response.read()
        except UpdateError as exc:
            raise UpdateCheckError(str(exc)) from exc

        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateCheckError("GitHub svarade med ogiltig JSON") from exc

    def _get_text(self, url: str) -> str:
        """Hämta en liten textfil (t.ex. *.sha256)."""
        try:
            with self._open(url, "application/octet-stream") as response:
                return response.read().decode("utf-8", "replace")
        except UpdateError as exc:
            raise UpdateDownloadError(str(exc)) from exc

    # ── Kontroll ─────────────────────────────────────────

    def check(self) -> Optional[UpdateInfo]:
        """
        Sök efter en nyare release.

        Returns:
            UpdateInfo om en nyare version finns, annars None.

        Raises:
            UpdateCheckError: vid nätverks- eller API-fel.
        """
        releases = self._get_json(self.api_releases_url)

        if isinstance(releases, dict):
            message = str(releases.get("message") or "okänt API-svar")
            raise UpdateCheckError(f"GitHub API: {message}")

        if not isinstance(releases, list):
            raise UpdateCheckError("Oväntat svar från GitHub API")

        best: Optional[Tuple[Version, Dict[str, Any]]] = None

        for release in releases:
            if not isinstance(release, dict) or release.get("draft"):
                continue

            is_pre = bool(release.get("prerelease"))
            if is_pre and self.channel != "prerelease":
                continue

            try:
                version = Version.parse(
                    release.get("tag_name") or release.get("name") or ""
                )
            except ValueError:
                logger.debug(
                    f"Hoppar över release med ogiltig tagg: "
                    f"{release.get('tag_name')!r}"
                )
                continue

            if version.is_prerelease and self.channel != "prerelease":
                continue
            if version <= self.current:
                continue

            if best is None or version > best[0]:
                best = (version, release)

        if best is None:
            logger.info(
                f"Ingen nyare version än v{self.current} "
                f"({self.owner}/{self.repo}, kanal={self.channel})"
            )
            return None

        info = UpdateInfo.from_github_release(best[1], self.asset_patterns)
        logger.info(
            f"Ny version hittad: v{info.version} (har fil: {info.asset_name or 'nej'})"
        )
        return info

    # ── Nedladdning ──────────────────────────────────────

    def download_dir(self, version: Optional[str] = None) -> Path:
        """Mapp där nedladdade uppdateringar och hjälpskript sparas."""
        suffix = str(version or self.current)
        base = self.work_dir or (Path(tempfile.gettempdir()) / "Semesterlista" / "updates")
        path = base / suffix
        path.mkdir(parents=True, exist_ok=True)
        return path

    def download(
        self,
        update: UpdateInfo,
        dest_dir: Optional[Path] = None,
        progress: Optional[ProgressCallback] = None,
        verify: bool = True,
    ) -> Path:
        """
        Ladda ner release-filen.

        Args:
            update:   Informationen från check().
            dest_dir: Mapp att spara i (standard: temp/Semesterlista/updates/…).
            progress: Anropas som progress(nedladdade_bytes, totala_bytes).
            verify:   Verifiera SHA-256 när GitHub anger en checksumma.

        Returns:
            Sökvägen till den nedladdade filen.

        Raises:
            UpdateDownloadError: vid nätverksfel, avbrott eller fel checksumma.
        """
        if not update.asset_url:
            raise UpdateDownloadError(
                f"Releasen v{update.version} saknar en nedladdningsbar fil"
            )

        target_dir = Path(dest_dir) if dest_dir else self.download_dir(update.version)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / Path(update.asset_name or f"Semesterlista-v{update.version}.zip").name

        total_expected = int(update.asset_size or 0)
        downloaded = 0
        digest = hashlib.sha256()

        try:
            with self._open(update.asset_url, "application/octet-stream") as response:
                declared = response.headers.get("Content-Length") if response.headers else None
                if declared and str(declared).isdigit():
                    total_expected = int(declared)

                with open(target, "wb") as handle:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
                        downloaded += len(chunk)
                        if progress is not None:
                            try:
                                progress(downloaded, total_expected)
                            except Exception:  # pragma: no cover – callback-fel
                                logger.debug("Progress-callback kastade ett fel")
        except UpdateDownloadError:
            raise
        except UpdateError as exc:
            raise UpdateDownloadError(str(exc)) from exc
        except OSError as exc:
            raise UpdateDownloadError(f"Kunde inte skriva filen: {exc}") from exc

        if total_expected and downloaded != total_expected:
            raise UpdateDownloadError(
                f"Nedladdningen avbröts ({downloaded} av {total_expected} byte)"
            )

        if verify:
            expected = self._expected_sha256(update)
            if expected:
                actual = digest.hexdigest()
                if actual.lower() != expected.lower():
                    try:
                        target.unlink()
                    except OSError:  # pragma: no cover – defensivt
                        pass
                    raise UpdateDownloadError(
                        "Checksumman stämmer inte – filen är skadad eller utbytt"
                    )
                logger.info("SHA-256 verifierad")

        logger.info(f"Nedladdad: {target} ({downloaded} byte)")
        return target

    def _expected_sha256(self, update: UpdateInfo) -> str:
        """Hämta förväntad SHA-256 från release-metadatan."""
        digest = (update.asset_digest or "").strip()
        if digest.lower().startswith("sha256:"):
            return digest.split(":", 1)[1].strip()

        if update.checksum_url:
            try:
                text = self._get_text(update.checksum_url).strip()
            except UpdateDownloadError as exc:
                logger.warning(f"Kunde inte hämta checksumma: {exc}")
                return ""
            token = text.split()[0] if text.split() else ""
            if re.fullmatch(r"[0-9a-fA-F]{64}", token):
                return token

        return ""

    # ── Uppackning ───────────────────────────────────────

    def stage_archive(self, archive: Path) -> Path:
        """
        Packa upp ett arkiv till en tillfällig mapp.

        Ett ensamt toppkatalog (typiskt "Semesterlista/") används som källa.
        Användardata (preserve_paths) tas bort från den uppackade kopian
        så att data/ och indatafiler aldrig skrivs över.

        Raises:
            UpdateApplyError: vid osäker eller trasig arkivfil.
        """
        archive = Path(archive)
        if not archive.exists():
            raise UpdateApplyError(f"Filen finns inte: {archive}")

        staging_root = Path(
            tempfile.mkdtemp(prefix="semesterlista-update-")
        )
        extract_dir = staging_root / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            if zipfile.is_zipfile(archive):
                with zipfile.ZipFile(archive) as zf:
                    self._safe_extract_zip(zf, extract_dir)
            elif tarfile.is_tarfile(archive):
                with tarfile.open(archive) as tf:
                    self._safe_extract_tar(tf, extract_dir)
            else:
                raise UpdateApplyError(
                    f"Okänt arkivformat: {archive.name}"
                )
        except UpdateApplyError:
            shutil.rmtree(staging_root, ignore_errors=True)
            raise
        except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
            shutil.rmtree(staging_root, ignore_errors=True)
            raise UpdateApplyError(f"Kunde inte packa upp: {exc}") from exc

        source = extract_dir
        entries = list(extract_dir.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            source = entries[0]

        for name in self.preserve_paths:
            protected = source / name
            if protected.is_dir():
                shutil.rmtree(protected, ignore_errors=True)
            elif protected.exists():
                try:
                    protected.unlink()
                except OSError:  # pragma: no cover – defensivt
                    pass

        logger.info(f"Uppdateringen uppackad i {source}")
        return source

    @staticmethod
    def _safe_target(root: Path, name: str) -> Path:
        """Skydda mot path traversal i arkiv."""
        root_resolved = root.resolve()
        target = (root / name).resolve()
        if target != root_resolved and root_resolved not in target.parents:
            raise UpdateApplyError(f"Otillåten sökväg i arkivet: {name}")
        return target

    def _safe_extract_zip(self, zf: zipfile.ZipFile, dest: Path) -> None:
        for member in zf.infolist():
            self._safe_target(dest, member.filename)
        zf.extractall(dest)  # noqa: S202 – sökvägar redan verifierade

    def _safe_extract_tar(self, tf: tarfile.TarFile, dest: Path) -> None:
        for member in tf.getmembers():
            self._safe_target(dest, member.name)
            if member.issym() or member.islnk():
                raise UpdateApplyError(
                    f"Länkar i arkivet stöds inte: {member.name}"
                )
        tf.extractall(dest)  # noqa: S202 – sökvägar redan verifierade

    # ── Installation ─────────────────────────────────────

    def _restart_command(self) -> Optional[List[str]]:
        """Kommando som startar om appen efter uppdateringen."""
        if getattr(sys, "frozen", False):  # paketerad .exe
            return [sys.executable]

        entry = self.app_root / "main.pyw"
        if not entry.exists():
            entry = self.app_root / "main.py"

        python = sys.executable or "python"
        if os.name == "nt":
            candidate = Path(python).with_name("pythonw.exe")
            if candidate.exists():
                python = str(candidate)

        return [python, str(entry)]

    def apply(
        self,
        update: UpdateInfo,
        archive: Path,
        pid: Optional[int] = None,
        restart: Optional[bool] = None,
        dry_run: bool = False,
    ) -> ApplyResult:
        """
        Installera den nedladdade uppdateringen.

        Ett installationsprogram startas direkt. Ett arkiv packas upp och
        ett hjälpskript skrivs som väntar på att appen stängs, kopierar
        filerna och startar om programmet.

        Args:
            update:  Informationen från check().
            archive: Filen från download().
            pid:     Process-ID att vänta på (standard: denna process).
            restart: Starta om appen? (standard: enligt config).
            dry_run: Gör allt utom att starta installationsprogrammet.

        Returns:
            ApplyResult som beskriver vad som hände.
        """
        archive = Path(archive)
        if restart is None:
            restart = self.restart_after_update
        wait_pid = int(pid or os.getpid())

        if not archive.exists():
            raise UpdateApplyError(f"Filen finns inte: {archive}")

        mode = self.install_mode
        if mode == "auto":
            if archive.name.lower().endswith((".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage")):
                mode = "installer"
            elif archive.name.lower().endswith((".zip", ".tar.gz", ".tgz", ".tar.bz2")):
                mode = "archive"
            else:
                mode = "browser"

        if mode == "browser":
            if not dry_run:
                webbrowser.open(update.html_url or self.releases_url)
            return ApplyResult(mode="browser", command=None, dry_run=dry_run)

        if mode == "installer":
            command = self._installer_command(archive)
            if not dry_run:
                try:
                    subprocess.Popen(command, close_fds=True)  # noqa: S603
                except OSError as exc:
                    raise UpdateApplyError(
                        f"Kunde inte starta installationsprogrammet: {exc}"
                    ) from exc
                logger.info(f"Startade installationsprogram: {command}")
            return ApplyResult(mode="installer", command=command, dry_run=dry_run)

        # ── Arkiv ────────────────────────────────────────
        source = self.stage_archive(archive)
        script = self._write_apply_script(source, wait_pid=wait_pid, restart=bool(restart))

        if not dry_run:
            self._launch_script(script)
            logger.info(f"Uppdateringen installeras av {script}")

        return ApplyResult(
            mode="archive",
            script=script,
            staged_dir=source,
            dry_run=dry_run,
        )

    def _installer_command(self, archive: Path) -> List[str]:
        """Kommando för att starta ett installationsprogram."""
        suffix = archive.suffix.lower()
        if os.name == "nt":
            return ["cmd", "/c", "start", "", str(archive)]
        if platform.system() == "Darwin" and suffix in (".dmg", ".pkg"):
            return ["open", str(archive)]
        if suffix in (".deb", ".rpm"):
            # Kräver root – öppna filen i filhanteraren i stället.
            return ["xdg-open", str(archive)]
        try:
            archive.chmod(0o755)
        except OSError:  # pragma: no cover – defensivt
            pass
        return [str(archive)]

    # ── Hjälpskript ──────────────────────────────────────

    def _write_apply_script(
        self,
        source: Path,
        wait_pid: int,
        restart: bool,
    ) -> Path:
        """Skriv plattformsspecifikt skript som kopierar filerna efter avslut."""
        base = self.download_dir()
        restart_cmd = self._restart_command() if restart else None

        if os.name == "nt":
            script = base / "apply_update.bat"
            script.write_text(
                self._windows_script_text(source, wait_pid, restart_cmd),
                encoding="utf-8",
            )
        else:
            script = base / "apply_update.sh"
            script.write_text(
                self._posix_script_text(source, wait_pid, restart_cmd),
                encoding="utf-8",
            )
            script.chmod(0o755)

        return script

    def _windows_script_text(
        self,
        source: Path,
        wait_pid: int,
        restart_cmd: Optional[List[str]],
    ) -> str:
        log_path = self.download_dir() / "apply_update.log"
        lines = [
            "@echo off",
            "setlocal EnableExtensions DisableDelayedExpansion",
            "title Semesterlista - uppdatering",
            f'set "APP_DIR={self.app_root}"',
            f'set "SRC_DIR={source}"',
            f'set "APP_PID={wait_pid}"',
            f'set "LOG_FILE={log_path}"',
            'echo Uppdaterar Semesterlista %DATE% %TIME% >> "%LOG_FILE%"',
            "echo Vantar pa att Semesterlista ska stangas...",
            "set /a WAIT_COUNT=0",
            ":wait_for_exit",
            'tasklist /FI "PID eq %APP_PID%" /NH 2>NUL'
            ' | findstr /R /C:" %APP_PID% " >NUL',
            "if errorlevel 1 goto files_free",
            "set /a WAIT_COUNT+=1",
            "if %WAIT_COUNT% GEQ 600 goto wait_timeout",
            "timeout /t 1 /nobreak >NUL",
            "goto wait_for_exit",
            ":wait_timeout",
            'echo FEL: appen stangdes inte inom 10 minuter. >> "%LOG_FILE%"',
            "exit /b 1",
            ":files_free",
            "echo Kopierar nya filer...",
            'xcopy "%SRC_DIR%\\*" "%APP_DIR%" /E /Y /I /Q >> "%LOG_FILE%" 2>&1',
            "if errorlevel 1 goto copy_failed",
            "echo Klart. >> \"%LOG_FILE%\"",
        ]

        if restart_cmd:
            exe = str(restart_cmd[0])
            args = " ".join(f'"{part}"' for part in restart_cmd[1:])
            lines += [
                "echo Startar om Semesterlista...",
                f'start "" "{exe}" {args}'.rstrip(),
            ]

        lines += [
            "goto cleanup",
            ":copy_failed",
            'echo FEL: kunde inte kopiera filerna. >> "%LOG_FILE%"',
            "echo Uppdateringen misslyckades. Se %LOG_FILE%",
            ":cleanup",
            'del "%~f0" >NUL 2>&1',
            "endlocal",
            "",
        ]
        return "\r\n".join(lines)

    def _posix_script_text(
        self,
        source: Path,
        wait_pid: int,
        restart_cmd: Optional[List[str]],
    ) -> str:
        def quote(text: str) -> str:
            return "'" + str(text).replace("'", "'\\''") + "'"

        lines = [
            "#!/bin/sh",
            "# Semesterlista – uppdatering (genererad av core/updater.py)",
            f"APP_DIR={quote(str(self.app_root))}",
            f"SRC_DIR={quote(str(source))}",
            f"APP_PID={wait_pid}",
            'echo "Vantar pa att Semesterlista ska stangas..." >&2',
            "WAIT_COUNT=0",
            'while kill -0 "$APP_PID" 2>/dev/null; do',
            "    WAIT_COUNT=$((WAIT_COUNT + 1))",
            '    if [ "$WAIT_COUNT" -ge 600 ]; then',
            '        echo "FEL: appen stangdes inte inom 10 minuter." >&2',
            "        exit 1",
            "    fi",
            "    sleep 1",
            "done",
            'cp -a "$SRC_DIR/." "$APP_DIR/" || {',
            '    echo "Uppdateringen misslyckades – filerna finns i $SRC_DIR" >&2',
            "    exit 1",
            "}",
        ]

        if restart_cmd:
            command = " ".join(quote(part) for part in restart_cmd)
            lines += [
                f"cd {quote(str(self.app_root))} || exit 1",
                f"nohup {command} >/dev/null 2>&1 &",
            ]

        lines += ['rm -f "$0"', ""]
        return "\n".join(lines)

    def _launch_script(self, script: Path) -> None:
        """Starta hjälpskriptet fristående från appen."""
        try:
            if os.name == "nt":
                flags = 0
                flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
                flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                subprocess.Popen(  # noqa: S603
                    ["cmd", "/c", str(script)],
                    creationflags=flags,
                    close_fds=True,
                )
            else:
                subprocess.Popen(  # noqa: S603
                    ["/bin/sh", str(script)],
                    start_new_session=True,
                    close_fds=True,
                )
        except OSError as exc:
            raise UpdateApplyError(
                f"Kunde inte starta uppdateringsskriptet: {exc}"
            ) from exc

    # ── Hjälpmetoder ─────────────────────────────────────

    def open_release_page(self, update: Optional[UpdateInfo] = None) -> bool:
        """Öppna releasen (eller releasesidan) i webbläsaren."""
        url = (update.html_url if update else "") or self.releases_url
        try:
            return bool(webbrowser.open(url))
        except Exception:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte öppna {url}")
            return False


# ══════════════════════════════════════════════════════════
# AUTOMATISK KONTROLL – HJÄLPARE MOT SettingsManager
# ══════════════════════════════════════════════════════════
#
# Alla hjälpare arbetar mot ett objekt med get(key, default) och
# set(key, value) – dvs. core.settings_manager.SettingsManager, men
# även en enkel dict-wrapper i testerna.

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Tolka ISO-8601 till en tidszonsmedveten datetime."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def auto_check_enabled(settings: Any) -> bool:
    """True om automatisk kontroll är påslagen."""
    if settings is None:
        return False
    if settings.get("updates.auto_check", None) is not None:
        return bool(settings.get("updates.auto_check"))
    return bool(settings.get("advanced.check_updates", True))


def should_auto_check(settings: Any, now: Optional[datetime] = None) -> bool:
    """
    True om appen bör fråga GitHub nu.

    Tar hänsyn till:
        updates.auto_check            – på/av
        updates.check_interval_hours  – minsta tid mellan kontroller
        updates.snooze_until          – "påminn mig senare"
        updates.last_check            – senaste kontrollen
    """
    if not auto_check_enabled(settings):
        return False

    moment = now or _utcnow()

    snooze_until = _parse_datetime(settings.get("updates.snooze_until", ""))
    if snooze_until is not None and moment < snooze_until:
        return False

    interval_hours = settings.get("updates.check_interval_hours", 24)
    try:
        interval = float(interval_hours)
    except (TypeError, ValueError):
        interval = 24.0

    last_check = _parse_datetime(settings.get("updates.last_check", ""))
    if last_check is None:
        return True

    return (moment - last_check) >= timedelta(hours=max(interval, 0))


def record_check(
    settings: Any,
    found_version: str = "",
    now: Optional[datetime] = None,
) -> None:
    """Spara tidpunkten för senaste kontrollen."""
    if settings is None:
        return
    moment = now or _utcnow()
    settings.set("updates.last_check", moment.isoformat(timespec="seconds"))
    settings.set("updates.last_found", str(found_version or ""))


def skipped_version(settings: Any) -> str:
    """Version som användaren valt att hoppa över."""
    if settings is None:
        return ""
    return str(settings.get("updates.skipped_version", "") or "")


def is_skipped(settings: Any, version: Any) -> bool:
    """True om användaren hoppat över just den här versionen."""
    skipped = skipped_version(settings)
    if not skipped:
        return False
    try:
        return Version.parse(skipped) == Version.parse(version)
    except ValueError:
        return skipped == str(version)


def skip_version(settings: Any, version: Any) -> None:
    """Hoppa över en version (visas inte igen)."""
    if settings is None:
        return
    settings.set("updates.skipped_version", str(version))


def snooze(
    settings: Any,
    hours: float = 24,
    now: Optional[datetime] = None,
) -> None:
    """Påminn igen om `hours` timmar."""
    if settings is None:
        return
    moment = (now or _utcnow()) + timedelta(hours=float(hours))
    settings.set("updates.snooze_until", moment.isoformat(timespec="seconds"))


def clear_snooze(settings: Any) -> None:
    """Ta bort eventuell påminnelse-fördröjning."""
    if settings is None:
        return
    settings.set("updates.snooze_until", "")


def mark_update_found(settings: Any, version: Any) -> None:
    """Kom ihåg att en uppdatering hittades (används av statusraden)."""
    if settings is None:
        return
    settings.set("updates.last_found", str(version))


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

def _cli_progress(downloaded: int, total: int) -> None:
    if total > 0:
        percent = int(downloaded * 100 / total)
        print(f"\rLaddar ner … {percent:3d} %", end="", flush=True)
    else:
        print(f"\rLaddar ner … {downloaded} byte", end="", flush=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Kommandoradsgränssnitt för uppdateraren."""
    project_root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(
        description="Semesterlista – uppdatering mot GitHub Releases",
    )
    parser.add_argument("--project-root", type=Path, default=project_root)
    parser.add_argument("--config", type=Path, default=None, help="Sökväg till config.json")
    parser.add_argument("--version", default=None, help="Nuvarande version (annars från config.json)")
    parser.add_argument("--channel", choices=("stable", "prerelease"), default=None)
    parser.add_argument("--check", action="store_true", help="Sök efter uppdatering")
    parser.add_argument("--download", action="store_true", help="Ladda ner uppdateringen")
    parser.add_argument("--install", action="store_true", help="Installera uppdateringen")
    parser.add_argument("--json", action="store_true", help="Skriv resultat som JSON")
    parser.add_argument("--verbose", action="store_true", help="Visa debug-logg")
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not (args.check or args.download or args.install):
        args.check = True

    try:
        config = load_update_config(args.project_root, args.config)
        if args.channel:
            config["channel"] = args.channel

        current = args.version or read_app_version(
            args.config or (args.project_root / "config.json")
        )

        updater = GitHubUpdater.from_config(
            args.project_root, current, args.config
        )
        if args.channel:
            updater.channel = args.channel

        update = updater.check()
        if update is None:
            if args.json:
                print(json.dumps({"update_available": False, "current": current}, indent=2))
            else:
                print(f"Ingen uppdatering – du har senaste versionen (v{updater.current}).")
            return 0

        if args.json and not (args.download or args.install):
            print(json.dumps(
                {"update_available": True, "current": current, **update.to_dict()},
                indent=2,
            ))
            return 10

        if not args.json:
            print(f"Ny version tillgänglig: v{update.version} (du har v{updater.current})")
            if update.asset_name:
                size_mb = update.asset_size / (1024 * 1024) if update.asset_size else 0
                print(f"Fil: {update.asset_name} ({size_mb:.1f} MB)")

        if not (args.download or args.install):
            return 10

        archive = updater.download(update, progress=_cli_progress)
        print()
        if not args.json:
            print(f"Nedladdad: {archive}")

        if not args.install:
            if args.json:
                print(json.dumps({"downloaded": str(archive)}, indent=2))
            return 20

        result = updater.apply(update, archive)
        if args.json:
            print(json.dumps({
                "installed": True,
                "mode": result.mode,
                "script": str(result.script) if result.script else "",
            }, indent=2))
        else:
            print(f"Uppdateringen installeras ({result.mode}).")
        return 20

    except UpdateError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"Fel: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
