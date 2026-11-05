#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fordonsplugin (v2.8.0)
======================

Egen flik för limokörnings-/fordonsscheman. Fliken återanvänder vyn och
PDF-generatorn från lista-pluginet men låser läget till "Limokörning",
så att användaren slipper välja läge och slipper riskera att skriva ut
fel lista.

    Flikar i huvudfönstret:
        Hyra ............ plugins/hyra
        Semesterlista ... plugins/lista   (FIXED_MODE = "Semesterlista")
        Fordon .......... plugins/fordon  (FIXED_MODE = "Limokörning")

Standardfil: Fordon.txt i appens rotmapp. Listan redigeras enklast med
knappen "Redigera lista" (samma redigerare som semesterlistan).

Konfiguration (data/plugins.json → "Fordon"):

    {
      "Fordon": {
        "version": "2.15.2",
        "enabled": true,
        "settings": {
          "default_mode": "Limokörning",
          "last_file": "Fordon.txt",
          "months_per_page": 2,
          "start_month": 0,
          "auto_open_pdf": true,
          "logo_svg": "",
          "logo_scale": 100
        }
      }
    }

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from plugins.lista.plugin import Plugin as SemesterlistaPlugin

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Plugin-metadata
# ──────────────────────────────────────────────────────────

PLUGIN_INFO: Dict[str, str] = {
    "id": "fordon",
    "name": "Fordon",
    "version": "2.15.2",
    "author": "Din Organisation",
    "description": "Genererar limokörningsscheman per fordon i PDF-format",
}

#: Den gamla kombinerade fliken – används för att migrera inställningar
LEGACY_PLUGIN_NAME: str = "Semesterlista & Limokörning"


class Plugin(SemesterlistaPlugin):
    """
    Fordonsflik – semesterlistans vy med fast läge "Limokörning".

    Ärver allt från lista-pluginet:
        - vyn (SemesterlistaView)
        - PDFGenerator
        - listredigeraren / roster-hanteringen
        - logotypvalet (assets-mappen)

    Skillnader:
        - FIXED_MODE = "Limokörning"  → lägesväljaren döljs
        - DEFAULT_LIST_FILE = "Fordon.txt"
        - TAB_ORDER = 30 → fliken hamnar sist
    """

    NAME: str = PLUGIN_INFO["name"]
    VERSION: str = PLUGIN_INFO["version"]
    DESCRIPTION: str = PLUGIN_INFO["description"]
    AUTHOR: str = PLUGIN_INFO["author"]

    FIXED_MODE: str = "Limokörning"
    DEFAULT_LIST_FILE: str = "Fordon.txt"
    TAB_ORDER: int = 30

    # ──────────────────────────────────────────────────────
    # Inställningar
    # ──────────────────────────────────────────────────────

    def _load_settings(self) -> Dict[str, Any]:
        """
        Ladda fordonsinställningar och migrera från den gamla fliken.

        Om den gamla kombinerade fliken pekade på en fordonsfil
        (t.ex. "Fordon.txt") och den nya fliken fortfarande använder
        standardvärdet, ärvs fil, startmånad och månader/blad.
        """
        settings = super()._load_settings()

        try:
            legacy = self.settings_manager.get_plugin_settings(LEGACY_PLUGIN_NAME) or {}
        except Exception as exc:  # pragma: no cover – defensivt
            logger.warning(f"Kunde inte läsa gamla inställningar: {exc}")
            return settings

        legacy_file = str(legacy.get("last_file") or "")
        current_file = str(settings.get("last_file") or "")

        if legacy_file and "fordon" in legacy_file.casefold():
            if current_file in ("", self.DEFAULT_LIST_FILE):
                settings["last_file"] = legacy_file
                for key in ("months_per_page", "start_month", "auto_open_pdf"):
                    if key in legacy:
                        settings[key] = legacy[key]
                logger.info(
                    f"Migrerade fordonsinställningar från '{LEGACY_PLUGIN_NAME}'"
                )

        return settings


__all__ = ["Plugin", "PLUGIN_INFO"]
