#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Versionshantering på ett ställe (v2.11.0)
=========================================

Appens version fanns tidigare på 13 olika ställen (``APP_VERSION`` i
``main.pyw``, ``VERSION`` i varje plugin, ``MODULE_VERSION`` i modulerna och
``config.json``). Glömdes ett ställe kvar kunde uppdateraren jämföra fel
version – t.ex. visa "ingen uppdatering" trots att en ny release fanns.

Modulen kan:

* **läsa** vilken version som gäller (``config.json`` är källan),
* **kontrollera** att alla ställen är synkade (``check_versions``),
* **skriva** en ny version överallt (``apply_version``).

Anropas från ``tools/bump_version.py``:

    python tools/bump_version.py 2.11.0     # ny version
    python tools/bump_version.py --check    # bara kontroll

Moduler vars version medvetet ligger kvar (t.ex. ``core/event_bus.py`` på
2.2.0) rörs aldrig – bara moduler som redan står på appens nuvarande version
följer med upp.

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

MODULE_VERSION: str = "2.21.1"

#: Filerna som alltid måste följa appens version
CONFIG_JSON = "config.json"
MAIN_PYW = "main.pyw"
SETTINGS_MANAGER = Path("core") / "settings_manager.py"
PLUGIN_GLOB = "plugin.py"

#: Moduler som *kan* följa med (endast om de redan står på appens version)
MODULE_GLOBS: Tuple[str, ...] = ("core/*.py", "plugins/*/*.py")

RE_APP_VERSION = re.compile(r'APP_VERSION:\s*str\s*=\s*"([^"]+)"')
RE_MODULE_VERSION = re.compile(r'MODULE_VERSION:\s*str\s*=\s*"([^"]+)"')
RE_PLUGIN_VERSION = re.compile(r'VERSION:\s+str\s*=\s*"([^"]+)"')
RE_JSON_VERSION = re.compile(r'"version"\s*:\s*"([^"]+)"')


@dataclass(frozen=True)
class VersionHit:
    """En plats där versionsnumret står."""

    path: Path
    line: int
    version: str
    pattern: "re.Pattern[str]"


def read_text(path: Path) -> str:
    """Läs en fil som text (CRLF normaliseras till LF)."""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """Skriv tillbaka en fil och behåll dess radbrytningar."""
    original = path.read_bytes()
    newline = "\r\n" if b"\r\n" in original else "\n"
    path.write_text(text, encoding="utf-8", newline=newline)


def current_version(root: Path) -> str:
    """
    Appens aktuella version enligt ``config.json``.

    Raises:
        FileNotFoundError: om ``config.json`` saknas.
        ValueError: om filen inte innehåller någon version.
    """
    data = json.loads(read_text(root / CONFIG_JSON))
    version = str(data.get("version", "")).strip()
    if not version:
        raise ValueError(f"Ingen version i {CONFIG_JSON}")
    return version


def _files_to_scan(root: Path) -> List[Path]:
    """Alla filer som kan innehålla ett versionsnummer."""
    files = [root / CONFIG_JSON, root / MAIN_PYW, root / SETTINGS_MANAGER]
    for pattern in MODULE_GLOBS:
        files.extend(sorted(root.glob(pattern)))

    unique = []
    seen = set()
    for file in files:
        if not file.is_file():
            continue
        key = file.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(file)
    return unique


def find_versions(root: Path) -> List[VersionHit]:
    """Hitta alla ställen där appens version står (per fil, första träffen)."""
    hits: List[VersionHit] = []
    for path in _files_to_scan(root):
        text = read_text(path).splitlines()
        patterns = [RE_APP_VERSION, RE_MODULE_VERSION, RE_PLUGIN_VERSION, RE_JSON_VERSION]
        if path.name == CONFIG_JSON:
            patterns = [RE_JSON_VERSION]
        elif path.name == MAIN_PYW:
            patterns = [RE_APP_VERSION]
        elif path.name == PLUGIN_GLOB:
            patterns = [RE_PLUGIN_VERSION, RE_JSON_VERSION]
        elif path == root / SETTINGS_MANAGER:
            patterns = [RE_MODULE_VERSION, RE_JSON_VERSION]

        for index, line in enumerate(text, start=1):
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    hits.append(VersionHit(path, index, match.group(1), pattern))
    return hits


def check_versions(root: Path) -> List[str]:
    """
    Kontrollera att appens version är densamma överallt.

    Returns:
        Lista med problembeskrivningar – tom lista betyder allt är synkat.
    """
    problems: List[str] = []
    try:
        version = current_version(root)
    except (FileNotFoundError, ValueError) as exc:
        return [f"{CONFIG_JSON}: {exc}"]

    required = {(root / MAIN_PYW).resolve()}
    plugins_dir = (root / "plugins").resolve()
    settings_manager = (root / SETTINGS_MANAGER).resolve()

    for hit in find_versions(root):
        path = hit.path.resolve()
        must_match = path in required or plugins_dir in path.parents
        # settings_manager.py har kvar sin egen MODULE_VERSION (2.2.0) –
        # bara pluginens standardversion ("version": ...) ska följa appen
        if path == settings_manager and hit.pattern is RE_MODULE_VERSION:
            must_match = False
        if must_match and hit.version != version:
            rel = hit.path.relative_to(root)
            problems.append(
                f"{rel}:{hit.line} har {hit.version!r}, förväntade {version!r}"
            )

    if not (root / MAIN_PYW).exists():
        problems.append(f"{MAIN_PYW} saknas")
    return problems


def apply_version(root: Path, new_version: str) -> List[str]:
    """
    Skriv ``new_version`` till alla ställen som följer appens version.

    Moduler som står på appens *nuvarande* version uppdateras också, medan
    moduler med egen lägre version (t.ex. ``event_bus`` 2.2.0) lämnas orörda.

    Returns:
        Lista med "fil:rad gammal → ny" för varje ändring.
    """
    new_version = str(new_version).strip()
    if not re.fullmatch(r"\d+\.\d+(\.\d+)?", new_version):
        raise ValueError(f"Ogiltig version: {new_version!r}")

    old_version = current_version(root)
    if old_version == new_version:
        return []

    changes: List[str] = []
    for path in _files_to_scan(root):
        text = read_text(path)
        original = text

        if path.name == CONFIG_JSON:
            patterns: Sequence["re.Pattern[str]"] = [RE_JSON_VERSION]
        elif path.name == MAIN_PYW:
            patterns = [RE_APP_VERSION]
        elif path.name == PLUGIN_GLOB:
            patterns = [RE_PLUGIN_VERSION, RE_JSON_VERSION]
        elif path.resolve() == (root / SETTINGS_MANAGER).resolve():
            patterns = [RE_MODULE_VERSION, RE_JSON_VERSION]
        else:
            patterns = [RE_MODULE_VERSION]

        lines = text.split("\n")
        for index, line in enumerate(lines):
            for pattern in patterns:
                match = pattern.search(line)
                if not match:
                    continue
                # Endast ställen som redan står på appens version bumpas
                if match.group(1) != old_version:
                    continue
                # Byt bara ut versionssträngen – radens formatering behålls
                lines[index] = line[: match.start(1)] + new_version + line[match.end(1):]
                changes.append(
                    f"{path.relative_to(root)}:{index + 1} {old_version} → {new_version}"
                )
                line = lines[index]
        text = "\n".join(lines)

        if text != original:
            write_text(path, text)
    return changes


def sync_status(root: Path) -> Tuple[str, List[VersionHit]]:
    """Kort sammanfattning: (version, alla träffar) för utskrift i CLI."""
    return current_version(root), find_versions(root)


__all__ = [
    "MODULE_VERSION",
    "VersionHit",
    "apply_version",
    "check_versions",
    "current_version",
    "find_versions",
    "sync_status",
]
