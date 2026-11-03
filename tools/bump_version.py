#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Höj appens version på alla ställen (v2.11.0)
===========================================

``config.json`` är källan. Skriptet skriver samma version till ``main.pyw``,
pluginens ``VERSION``/``version``, ``core/settings_manager.py`` och till alla
moduler som redan står på appens nuvarande version.

Användning:

    python tools/bump_version.py 2.11.0     # höj till 2.11.0
    python tools/bump_version.py --check    # kontrollera utan att ändra
    python tools/bump_version.py --list     # visa var versionen står

Avslutningskod 1 vid problem (används av CI).

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import version  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Kör kommandoradsverktyget."""
    parser = argparse.ArgumentParser(
        description="Höj Semesterlistas version på alla ställen.",
    )
    parser.add_argument("version", nargs="?", help="ny version, t.ex. 2.11.0")
    parser.add_argument(
        "--check", action="store_true", help="kontrollera bara, ändra inget"
    )
    parser.add_argument(
        "--list", action="store_true", help="visa alla ställen versionen står på"
    )
    args = parser.parse_args(argv)

    root = PROJECT_ROOT

    try:
        current = version.current_version(root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"FEL: {exc}", file=sys.stderr)
        return 1

    print(f"Aktuell version (config.json): {current}")

    if args.list:
        for hit in version.find_versions(root):
            rel = hit.path.relative_to(root)
            print(f"  {rel}:{hit.line}  {hit.version}")
        return 0

    if args.check or not args.version:
        problems = version.check_versions(root)
        if problems:
            print("Versionerna är INTE synkade:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print("Alla ställen är synkade.")
        return 0

    try:
        changes = version.apply_version(root, args.version)
    except ValueError as exc:
        print(f"FEL: {exc}", file=sys.stderr)
        return 1

    if not changes:
        print(f"Inget att göra – versionen är redan {args.version}.")
        return 0

    for change in changes:
        print(f"  {change}")

    problems = version.check_versions(root)
    if problems:
        print("Varning: versionerna är fortfarande inte synkade:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"Klart – {len(changes)} ställen uppdaterade till {args.version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
